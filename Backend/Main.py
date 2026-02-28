"""
InsightX AI — FastAPI Backend
==============================
Connects your React/JSX frontend to the AI model.

ENDPOINTS:
  POST /api/chat          ← main chat endpoint (frontend calls this)
  POST /api/upload-csv    ← upload a new CSV to replace live data
  GET  /api/overview      ← auto executive overview on page load
  GET  /api/health        ← health check
  GET  /api/session/{id}  ← get session history
  DELETE /api/session/{id}← clear session history

INSTALL & RUN:
  pip install fastapi uvicorn openai pandas python-dotenv

  uvicorn main:app --reload --port 8000

CORS is pre-configured for localhost:3000 / localhost:5173 (Vite/CRA).
"""

import os, json, uuid
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import pandas as pd
except ImportError:
    raise RuntimeError("pip install pandas")

try:
    from openai import OpenAI
except ImportError:
    raise RuntimeError("pip install openai")


# ── Config ────────────────────────────────────────────────────────────────────

NVIDIA_BASE_URL    = "https://integrate.api.nvidia.com/v1"
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"

PROVIDER  = os.getenv("AI_PROVIDER", "nvidia")          # "nvidia" or "anthropic"
AI_MODEL  = os.getenv("AI_MODEL", "meta/llama-3.3-70b-instruct")
API_KEY   = os.getenv("NVIDIA_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")

MAX_PROFILE_CHARS  = 24_000
MAX_DYNAMIC_CHARS  = 4_000
MAX_HISTORY_TURNS  = 6

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="InsightX AI API",
    description="Conversational analytics backend for UPI transaction intelligence",
    version="1.0.0",
)

# Allow all localhost origins so your React dev server can talk to this
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Create React App
        "http://localhost:5173",   # Vite
        "http://localhost:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory session store  { session_id: [{"role":..,"content":..}, ...] } ──
sessions: dict[str, list[dict]] = {}

# ── Global DataFrame (loaded once, can be hot-swapped via /api/upload-csv) ───
_df: Optional[pd.DataFrame] = None
_df_filename: str = "upi_transactions_2024.csv"
_system_prompt: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# DATASET  UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

# The full system prompt from the JSX (verbatim) is used when no CSV is loaded.
# When a CSV IS loaded, we generate a live profile instead.

STATIC_SYSTEM_PROMPT = """You are InsightX AI — a conversational business intelligence assistant for a 250,000-row UPI digital payments dataset (India, 2024). You help non-technical business leaders understand their payment data through natural language.

DATASET FACTS:
- Total transactions: 250,000 | Total volume: ₹32.79 Crore | Success rate: 95.05%
- Avg: ₹1,311.76 | Median: ₹629 | Min: ₹10 | Max: ₹42,099 | Std Dev: ₹1,848
- 90th pct: ₹3,236 | 95th pct: ₹4,687 | 99th pct: ₹9,003
- Fraud rate: 0.192% (480 cases) | Date range: 2024 full year

AMOUNT DISTRIBUTION:
Under ₹100: 13,099 (5.2%) | ₹100–500: 93,363 (37.3%) | ₹500–1K: 51,135 (20.5%) | ₹1K–5K: 81,444 (32.6%) | ₹5K–10K: 9,154 (3.7%) | Above ₹10K: 1,805 (0.72%)

TRANSACTION TYPES: P2P (112,445), P2M (87,660), Bill Payment (37,368), Recharge (12,527)
MERCHANT CATEGORIES (by count): Grocery 49,966 | Food 37,464 | Shopping 29,872 | Fuel 25,063 | Other 24,828 | Utilities 22,338 | Transport 20,105 | Entertainment 20,103 | Healthcare 12,663 | Education 7,598
TOP STATES BY VOLUME: Maharashtra ₹4.9Cr | Uttar Pradesh ₹4.0Cr | Karnataka ₹3.8Cr | Tamil Nadu ₹3.3Cr | Delhi ₹3.3Cr
DEVICES: Android 187,777 (75.1%) | iOS 49,613 (19.8%) | Web 12,610 (5.0%)
NETWORKS: 4G 59.9% | 5G 25.0% | WiFi 10.1% | 3G 5.0%
TOP BANKS: SBI 62,693 | HDFC 37,485 | ICICI 29,769
AGE GROUPS: 26-35 (34.97%) | 36-45 (25.15%) | 18-25 (24.94%) | 46-55 (9.94%) | 56+ (5.00%)

FRAUD RATES:
By category: Transport 0.214% | Education 0.211% | Shopping 0.208% | Food 0.195% | Utilities 0.148% (lowest)
By state: Karnataka 0.232% | Rajasthan 0.23% | Gujarat 0.214% | Tamil Nadu 0.158% (lowest)
By network: WiFi 0.235% (highest!) | 5G 0.184% (lowest)
By bank: Kotak 0.25% | ICICI 0.222% | Yes Bank 0.161% (lowest)
By age: 18-25 0.229% | 46-55 0.125% (lowest)
By type: Recharge 0.239% | P2P 0.183% (lowest)

DEVICE STATS:
- Android: avg ₹1,313.98 | fraud 0.194% | success 95.06%
- iOS:     avg ₹1,306.10 | fraud 0.181% | success 95.07%  (safest)
- Web:     avg ₹1,300.81 | fraud 0.206% | success 94.85%  (most risky)

FAILURE RATES: Education 5.25% | Shopping 5.09% | Transport 4.76% (lowest)
PEAK ACTIVITY: 7 PM busiest (21,232 txns) | 4 AM quietest (1,247 txns)
HIGH-VALUE (>₹10K): 1,805 transactions | fraud rate 0.332% (73% higher than average)

RESPONSE FORMAT:
1. **Direct Answer** — precise, with the exact number asked for
2. **Key Numbers** — supporting stats
3. **Pattern** — why it matters
4. **Business Recommendation** — 1 actionable insight

Use ₹ for amounts, % for rates. Be confident and concise."""


def profile_dataframe(df: pd.DataFrame, filename: str) -> str:
    """Compact, token-safe profile of any uploaded CSV."""
    lines = [f"File: {filename}", f"Shape: {df.shape[0]:,} rows × {df.shape[1]} columns\n"]

    num_cols = df.select_dtypes(include="number").columns.tolist()
    if num_cols:
        lines.append("NUMERIC COLUMNS:")
        desc = df[num_cols].describe().round(2)
        for col in num_cols:
            d = desc[col]
            lines.append(
                f"  {col}: mean={d['mean']}, min={d['min']}, max={d['max']}, "
                f"std={d['std']:.2f}, p25={d['25%']}, median={d['50%']}, p75={d['75%']}, "
                f"nulls={int(df[col].isna().sum())}"
            )

    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    if cat_cols:
        lines.append("\nCATEGORICAL COLUMNS:")
        for col in cat_cols:
            vc = df[col].value_counts()
            lines.append(
                f"  {col}: {df[col].nunique()} unique, "
                f"nulls={int(df[col].isna().sum())}, "
                f"top5={dict(vc.head(5))}"
            )

    if len(num_cols) >= 2:
        corr  = df[num_cols].corr().round(3)
        pairs, seen = [], set()
        for c1 in corr.columns:
            for c2 in corr.columns:
                if c1 != c2 and (c2, c1) not in seen:
                    pairs.append((c1, c2, float(corr.loc[c1, c2])))
                    seen.add((c1, c2))
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        lines.append("\nTOP CORRELATIONS:")
        for a, b, r in pairs[:8]:
            lines.append(f"  {a} ↔ {b}  r={r}")

    lines.append("\nSAMPLE ROWS (first 5):")
    lines.append(df.head(5).to_string(index=False, max_cols=20))

    missing = df.isnull().sum()
    missing = missing[missing > 0]
    lines.append("\nMISSING VALUES:")
    lines.append("\n".join(f"  {k}: {v}" for k, v in missing.items()) if not missing.empty else "  None")

    full = "\n".join(lines)
    if len(full) > MAX_PROFILE_CHARS:
        full = full[:MAX_PROFILE_CHARS] + "\n...[truncated]"
    return full


def compute_dynamic_stats(df: pd.DataFrame, question: str) -> str:
    q        = question.lower()
    extras   = []
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

    for col in cat_cols:
        if col.lower() in q or col.replace("_", " ").lower() in q:
            for nc in num_cols[:2]:
                try:
                    grp = df.groupby(col)[nc].agg(["mean", "sum", "count"]).round(2)
                    extras.append(f"GroupBy {col}×{nc}:\n{grp.to_string()}")
                except Exception:
                    pass
            extras.append(f"Value counts '{col}':\n{df[col].value_counts().head(8).to_string()}")
            break

    for col in df.columns:
        if any(kw in col.lower() for kw in ("date", "time", "month", "year", "period")):
            if any(kw in q for kw in ("trend", "over time", "monthly", "yearly", "growth")):
                try:
                    df2 = df.copy()
                    df2["__dt"] = pd.to_datetime(df2[col], errors="coerce")
                    df2 = df2.dropna(subset=["__dt"])
                    df2["__p"] = df2["__dt"].dt.to_period("M")
                    for nc in num_cols[:1]:
                        ts = df2.groupby("__p")[nc].sum().tail(12)
                        extras.append(f"Monthly '{nc}':\n{ts.to_string()}")
                except Exception:
                    pass
            break

    for col in df.columns:
        if any(kw in col.lower() for kw in ("fraud", "risk", "anomaly", "flag")):
            if col.lower() in q or "fraud" in q or "risk" in q:
                try:
                    extras.append(f"'{col}':\n{df[col].value_counts().to_string()}")
                    for cc in cat_cols[:2]:
                        grp = df.groupby(cc)[col].mean().sort_values(ascending=False).round(4)
                        extras.append(f"Fraud by '{cc}':\n{grp.to_string()}")
                except Exception:
                    pass
            break

    if any(kw in q for kw in ("top", "highest", "most", "largest")):
        for nc in num_cols[:1]:
            extras.append(f"Top 5 '{nc}':\n{df[nc].nlargest(5).to_string()}")
    if any(kw in q for kw in ("bottom", "lowest", "least", "smallest")):
        for nc in num_cols[:1]:
            extras.append(f"Bottom 5 '{nc}':\n{df[nc].nsmallest(5).to_string()}")

    result = "\n\n".join(extras) if extras else ""
    if len(result) > MAX_DYNAMIC_CHARS:
        result = result[:MAX_DYNAMIC_CHARS] + "\n...[truncated]"
    return result


def build_system_prompt_for_csv(df: pd.DataFrame, filename: str) -> str:
    profile = profile_dataframe(df, filename)
    return f"""You are InsightX AI — an elite AI Chief Data Officer for C-suite leadership.

Your mission:
1. Answer data questions with precision, citing exact numbers.
2. Surface hidden risks, opportunities, and anomalies proactively.
3. Provide strategic, executive-level recommendations.

DATASET PROFILE:
{profile}

RESPONSE FORMAT:
1. **Direct Answer** — precise number or finding
2. **Key Numbers** — supporting stats
3. **Pattern** — interpretation
4. **Business Recommendation** — 1 actionable insight

Use ₹ for Indian currency amounts, % for rates. Be confident and concise."""


def get_ai_client() -> OpenAI:
    if not API_KEY:
        raise HTTPException(status_code=500, detail="No API key configured. Set NVIDIA_API_KEY or ANTHROPIC_API_KEY in .env")
    base_url = NVIDIA_BASE_URL if PROVIDER == "nvidia" else ANTHROPIC_BASE_URL
    return OpenAI(api_key=API_KEY, base_url=base_url)


def get_system_prompt() -> str:
    """Return live CSV-based prompt if CSV was uploaded, else static prompt."""
    global _system_prompt
    return _system_prompt if _system_prompt else STATIC_SYSTEM_PROMPT


def call_ai(messages: list[dict]) -> str:
    client = get_ai_client()
    try:
        resp = client.chat.completions.create(
            model=AI_MODEL,
            messages=messages,
            max_tokens=1024,
            temperature=0.3,
        )
        return resp.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI API error: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE MODELS
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None   # pass None to start a new session

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    chart_type: Optional[str] = None   # hint for the frontend to render a chart

class OverviewResponse(BaseModel):
    overview: str
    session_id: str

class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    csv_loaded: bool
    csv_filename: Optional[str]


# ══════════════════════════════════════════════════════════════════════════════
# CHART TYPE DETECTION  (mirrors the frontend's detectChartType)
# ══════════════════════════════════════════════════════════════════════════════

def detect_chart_type(query: str) -> Optional[str]:
    q = query.lower()
    if any(k in q for k in ("highest", "largest", "maximum", "biggest", "top 10", "distribution", "bucket", "range")):
        return "amountdist"
    if any(k in q for k in ("hour", "peak", "time of day")):
        return "hourly"
    if any(k in q for k in ("state", "region", "maharashtra", "karnataka")):
        return "state"
    if any(k in q for k in ("categor", "merchant", "grocery", "food", "shopping")):
        return "category"
    if any(k in q for k in ("device", "ios", "android", "web browser", "compare device")):
        return "device_compare"
    if any(k in q for k in ("network", "4g", "5g", "wifi", "3g")):
        return "network"
    if any(k in q for k in ("bank", "sbi", "hdfc", "icici", "kotak")):
        return "bank"
    if any(k in q for k in ("day", "week", "monday", "weekend")):
        return "daily"
    if any(k in q for k in ("age", "young", "senior", "26-35")):
        return "age"
    if any(k in q for k in ("type", "p2p", "p2m", "recharge", "bill")):
        return "txtype"
    if "fraud" in q:
        return "fraud_overview"
    if any(k in q for k in ("volume", "summary", "overview")):
        return "category"
    return None


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        provider=PROVIDER,
        model=AI_MODEL,
        csv_loaded=_df is not None,
        csv_filename=_df_filename if _df is not None else None,
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Main chat endpoint. The frontend sends every user message here.

    Flow:
      1. Resolve or create session
      2. Optionally compute dynamic stats from uploaded CSV
      3. Build message list (system + trimmed history + new message)
      4. Call AI
      5. Store reply in session
      6. Return reply + chart type hint
    """
    # ── Session management ─────────────────────────────────────────────────
    sid = req.session_id or str(uuid.uuid4())
    if sid not in sessions:
        sessions[sid] = []

    history = sessions[sid]

    # ── Dynamic stats injection (only if CSV was uploaded) ─────────────────
    user_content = req.message
    if _df is not None:
        dynamic = compute_dynamic_stats(_df, req.message)
        if dynamic:
            user_content = f"{req.message}\n\n[LIVE DATA STATS]\n{dynamic}"

    history.append({"role": "user", "content": user_content})

    # ── Trim history to prevent context overflow ───────────────────────────
    trimmed = history[-(MAX_HISTORY_TURNS * 2):]

    messages = [{"role": "system", "content": get_system_prompt()}] + trimmed

    # ── Call AI ────────────────────────────────────────────────────────────
    reply = call_ai(messages)

    history.append({"role": "assistant", "content": reply})
    sessions[sid] = history  # save back

    return ChatResponse(
        reply=reply,
        session_id=sid,
        chart_type=detect_chart_type(req.message),
    )


@app.get("/api/overview", response_model=OverviewResponse)
def get_overview():
    """
    Called once when the frontend loads to get the executive overview.
    Creates a fresh session and returns its ID so subsequent /api/chat
    calls can continue the same conversation.
    """
    sid = str(uuid.uuid4())
    sessions[sid] = []

    question = (
        "Give me a concise executive overview of this dataset. "
        "What are the 3-5 most important headlines a CEO should know immediately? "
        "Highlight key risks, top performers, and strategic opportunities. Be brief."
    )

    req = ChatRequest(message=question, session_id=sid)
    result = chat(req)
    return OverviewResponse(overview=result.reply, session_id=sid)


@app.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """
    Hot-swap the dataset. Accepts a CSV file, profiles it,
    and rebuilds the system prompt in memory.
    The existing chat sessions continue working — they'll pick up the new prompt
    on the next message.
    """
    global _df, _df_filename, _system_prompt

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")

    contents = await file.read()

    # Try multiple encodings
    df = None
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            import io
            df = pd.read_csv(io.BytesIO(contents), encoding=enc, low_memory=False)
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    if df is None:
        raise HTTPException(status_code=400, detail="Could not decode CSV. Try UTF-8 encoding.")

    _df           = df
    _df_filename  = file.filename
    _system_prompt = build_system_prompt_for_csv(df, file.filename)

    return {
        "message": "CSV loaded successfully",
        "filename": file.filename,
        "rows": df.shape[0],
        "columns": df.shape[1],
        "column_names": df.columns.tolist(),
    }


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    """Return the full conversation history for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    history = sessions[session_id]
    # Strip injected dynamic stats from display
    clean = []
    for msg in history:
        content = msg["content"].split("[LIVE DATA STATS]")[0].strip()
        clean.append({"role": msg["role"], "content": content})
    return {"session_id": session_id, "messages": clean}


@app.delete("/api/session/{session_id}")
def clear_session(session_id: str):
    """Clear conversation history for a session (= 'New Chat' button)."""
    if session_id in sessions:
        sessions.pop(session_id)
    return {"message": "Session cleared", "session_id": session_id}


@app.get("/")
def root():
    return {
        "name": "InsightX AI API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }