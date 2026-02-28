"""
InsightX AI — FastAPI Backend v2
==================================
NEW in v2:
  GET  /api/dashboard   ← returns computed KPIs + chart data from uploaded CSV

All original endpoints unchanged:
  POST /api/chat
  POST /api/upload-csv
  GET  /api/overview
  GET  /api/health
  GET  /api/session/{id}
  DELETE /api/session/{id}

INSTALL & RUN:
  pip install fastapi uvicorn openai pandas python-dotenv numpy
  uvicorn main:app --reload --port 8000
"""

import os, json, uuid, io
from pathlib import Path
from datetime import datetime
from typing import Optional, Any

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import pandas as pd
    import numpy as np
except ImportError:
    raise RuntimeError("pip install pandas numpy")

try:
    from openai import OpenAI
except ImportError:
    raise RuntimeError("pip install openai")


# ── Config ────────────────────────────────────────────────────────────────────
NVIDIA_BASE_URL    = "https://integrate.api.nvidia.com/v1"
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"

PROVIDER  = os.getenv("AI_PROVIDER", "nvidia")
AI_MODEL  = os.getenv("AI_MODEL", "meta/llama-3.3-70b-instruct")
API_KEY   = os.getenv("NVIDIA_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")

MAX_PROFILE_CHARS = 24_000
MAX_DYNAMIC_CHARS = 4_000
MAX_HISTORY_TURNS = 6

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="InsightX AI API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://localhost:5173", "http://localhost:5174",
        "http://127.0.0.1:3000", "http://127.0.0.1:5173",
    ],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# ── Global state ──────────────────────────────────────────────────────────────
sessions:         dict[str, list[dict]] = {}
_df:              Optional[pd.DataFrame] = None
_df_filename:     str = ""
_system_prompt:   str = ""
_dashboard_cache: Optional[dict] = None   # computed once on upload


# ══════════════════════════════════════════════════════════════════════════════
# STATIC SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════
STATIC_SYSTEM_PROMPT = """You are InsightX AI — a conversational business intelligence assistant for a 250,000-row UPI digital payments dataset (India, 2024).

DATASET FACTS:
- Total transactions: 250,000 | Total volume: ₹32.79 Crore | Success rate: 95.05%
- Avg: ₹1,311.76 | Median: ₹629 | Fraud rate: 0.192% (480 cases)
- Peak hour: 7 PM | Top state by volume: Maharashtra

FRAUD RATES by category: Transport 0.214% | Education 0.211% | Shopping 0.208% | Utilities 0.148% (lowest)
By state: Karnataka 0.232% | Rajasthan 0.23% | Tamil Nadu 0.158% (lowest)
By network: WiFi 0.235% (highest) | 5G 0.184% (lowest)
By bank: Kotak 0.25% | ICICI 0.222% | Yes Bank 0.161% (lowest)
By age: 18-25 0.229% | 46-55 0.125% (lowest)
By type: Recharge 0.239% | P2P 0.183% (lowest)

RESPONSE FORMAT:
1. **Direct Answer** — precise number
2. **Key Numbers** — supporting stats
3. **Pattern** — why it matters
4. **Business Recommendation** — 1 actionable insight

Use ₹ for amounts, % for rates. Be confident and concise."""


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD COMPUTATION  — runs once after CSV upload
# ══════════════════════════════════════════════════════════════════════════════

def _safe(val):
    """Convert numpy types → plain Python for JSON."""
    if isinstance(val, (np.integer,)):   return int(val)
    if isinstance(val, (np.floating,)):  return round(float(val), 4)
    if isinstance(val, np.ndarray):      return val.tolist()
    if isinstance(val, dict):            return {k: _safe(v) for k, v in val.items()}
    if isinstance(val, list):            return [_safe(v) for v in val]
    try:
        if pd.isna(val): return None
    except Exception:
        pass
    return val


def compute_dashboard(df: pd.DataFrame, filename: str) -> dict:
    """
    Compute KPIs, chart datasets and anomaly cards for any uploaded CSV.
    The frontend renders these directly — no extra API call needed.
    """
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    rows, cols = df.shape

    # ── KPI cards (up to 12) ──────────────────────────────────────────────────
    kpis = [
        {"val": f"{rows:,}",      "label": "Total Rows",     "icon": "📋", "color": "#2563eb"},
        {"val": str(cols),        "label": "Total Columns",  "icon": "🗂️",  "color": "#6366f1"},
        {"val": str(len(num_cols)), "label": "Numeric Cols", "icon": "🔢", "color": "#0ea5e9"},
        {"val": str(len(cat_cols)), "label": "Category Cols","icon": "🏷️",  "color": "#10b981"},
    ]

    # numeric summary KPIs — first 4 numeric cols
    for nc in num_cols[:4]:
        mean_val = float(df[nc].mean())
        kpis.append({
            "val": f"{mean_val:,.2f}" if abs(mean_val) < 1e6 else f"{mean_val/1e6:.2f}M",
            "label": f"Avg {nc}",
            "icon": "📊",
            "color": "#f59e0b",
        })

    # fraud/flag column
    fraud_col = next(
        (c for c in df.columns if any(k in c.lower() for k in ("fraud", "flag", "risk", "anomaly"))),
        None
    )
    if fraud_col:
        try:
            rate = float(df[fraud_col].mean()) * 100
            cnt  = int(df[fraud_col].sum())
            kpis.append({"val": f"{rate:.3f}%", "label": f"{fraud_col} Rate", "icon": "🚨", "color": "#ef4444"})
            kpis.append({"val": f"{cnt:,}",      "label": f"Total {fraud_col}", "icon": "⚠️", "color": "#f97316"})
        except Exception:
            pass

    # status/success column
    status_col = next(
        (c for c in df.columns if any(k in c.lower() for k in ("status", "success", "result"))),
        None
    )
    if status_col and df[status_col].dtype == object:
        try:
            vc = df[status_col].value_counts(normalize=True) * 100
            kpis.append({"val": f"{vc.iloc[0]:.1f}%", "label": f"{vc.index[0]} Rate", "icon": "✅", "color": "#10b981"})
        except Exception:
            pass

    # ── Numeric distribution histogram (first numeric col) ────────────────────
    num_dist = []
    primary_num = num_cols[0] if num_cols else None
    if primary_num:
        try:
            counts, edges = np.histogram(df[primary_num].dropna(), bins=10)
            for cnt, lo, hi in zip(counts, edges[:-1], edges[1:]):
                lbl = f"{lo:.0f}–{hi:.0f}" if hi < 1e6 else f"{lo/1e3:.0f}K–{hi/1e3:.0f}K"
                num_dist.append({"range": lbl, "count": int(cnt)})
        except Exception:
            pass

    # ── Category bar charts (top 3 cat cols × primary numeric) ───────────────
    cat_charts = []
    for cc in cat_cols[:3]:
        try:
            if primary_num:
                grp = (
                    df.groupby(cc)[primary_num]
                    .agg(["mean", "sum", "count"])
                    .round(2)
                    .reset_index()
                    .rename(columns={cc: "name", "mean": "avg", "sum": "total", "count": "count"})
                    .sort_values("count", ascending=False)
                    .head(10)
                )
                cat_charts.append({"col": cc, "num_col": primary_num,
                                    "data": _safe(grp.to_dict(orient="records"))})
            else:
                vc = df[cc].value_counts().head(10).reset_index()
                vc.columns = ["name", "count"]
                cat_charts.append({"col": cc, "num_col": None,
                                    "data": _safe(vc.to_dict(orient="records"))})
        except Exception:
            pass

    # ── Fraud rate by category ────────────────────────────────────────────────
    fraud_by_cat = []
    if fraud_col:
        for cc in cat_cols[:2]:
            try:
                grp = (df.groupby(cc)[fraud_col].mean() * 100).sort_values(ascending=False).round(4)
                fraud_by_cat.append({
                    "col": cc,
                    "data": _safe([{"name": k, "rate": float(v)} for k, v in grp.items()])
                })
            except Exception:
                pass

    # ── Time series (monthly) ─────────────────────────────────────────────────
    time_series = []
    date_col = next(
        (c for c in df.columns if any(k in c.lower() for k in ("date", "time", "timestamp", "month", "period"))),
        None
    )
    if date_col and primary_num:
        try:
            df2 = df.copy()
            df2["__dt"] = pd.to_datetime(df2[date_col], errors="coerce")
            df2 = df2.dropna(subset=["__dt"])
            df2["__p"] = df2["__dt"].dt.to_period("M").astype(str)
            ts = df2.groupby("__p")[primary_num].sum().reset_index()
            ts.columns = ["period", "value"]
            time_series = _safe(ts.to_dict(orient="records"))
        except Exception:
            pass

    # ── Correlation top pairs ─────────────────────────────────────────────────
    correlations = []
    if len(num_cols) >= 2:
        try:
            corr = df[num_cols].corr().round(3)
            pairs, seen = [], set()
            for c1 in corr.columns:
                for c2 in corr.columns:
                    if c1 != c2 and (c2, c1) not in seen:
                        pairs.append({"col_a": c1, "col_b": c2, "r": float(corr.loc[c1, c2])})
                        seen.add((c1, c2))
            pairs.sort(key=lambda x: abs(x["r"]), reverse=True)
            correlations = pairs[:9]
        except Exception:
            pass

    # ── Auto-detected anomaly cards ───────────────────────────────────────────
    anomalies = []

    if fraud_col:
        overall_fraud = float(df[fraud_col].mean()) * 100
        for cc in cat_cols[:3]:
            try:
                grp = df.groupby(cc)[fraud_col].mean() * 100
                worst = grp.idxmax();  worst_rate = float(grp.max())
                best  = grp.idxmin();  best_rate  = float(grp.min())
                if worst_rate > overall_fraud * 1.15:
                    pct = (worst_rate - overall_fraud) / overall_fraud * 100
                    anomalies.append({
                        "title": f"High Risk: {worst} ({cc})",
                        "desc":  f"{worst} has {worst_rate:.3f}% fraud rate — {pct:.0f}% above dataset avg of {overall_fraud:.3f}%. Immediate review recommended.",
                        "icon": "🚨", "color": "#ef4444"
                    })
                if len(anomalies) < 8 and best_rate < overall_fraud * 0.85:
                    pct = (overall_fraud - best_rate) / overall_fraud * 100
                    anomalies.append({
                        "title": f"Safest Segment: {best} ({cc})",
                        "desc":  f"{best} has only {best_rate:.3f}% fraud rate — {pct:.0f}% below average. Study this segment for best practices.",
                        "icon": "✅", "color": "#10b981"
                    })
            except Exception:
                pass

    # Missing-value alerts
    missing = df.isnull().sum()
    for col, cnt in missing[missing > rows * 0.05].items():
        if len(anomalies) >= 9: break
        anomalies.append({
            "title": f"Data Gap: {col}",
            "desc":  f"Column '{col}' is missing {cnt:,} values ({cnt/rows*100:.1f}% of rows). Imputation or exclusion recommended.",
            "icon": "⚠️", "color": "#f59e0b"
        })

    # Skewed distribution alerts
    for nc in num_cols[:3]:
        if len(anomalies) >= 9: break
        try:
            skew = float(df[nc].skew())
            if abs(skew) > 2:
                anomalies.append({
                    "title": f"Skewed: {nc}",
                    "desc":  f"'{nc}' has skewness {skew:.2f}. Highly skewed distributions may indicate outliers or require log transformation.",
                    "icon": "📈", "color": "#6366f1"
                })
        except Exception:
            pass

    return {
        "filename":        filename,
        "rows":            rows,
        "columns":         cols,
        "column_names":    df.columns.tolist(),
        "num_cols":        num_cols,
        "cat_cols":        cat_cols,
        "primary_num_col": primary_num,
        "fraud_col":       fraud_col,
        "date_col":        date_col,
        "kpis":            kpis[:12],
        "num_dist":        num_dist,
        "cat_charts":      cat_charts,
        "fraud_by_cat":    fraud_by_cat,
        "time_series":     time_series,
        "correlations":    correlations,
        "anomalies":       anomalies[:9],
    }


# ══════════════════════════════════════════════════════════════════════════════
# AI UTILITIES  (unchanged from v1)
# ══════════════════════════════════════════════════════════════════════════════

def profile_dataframe(df: pd.DataFrame, filename: str) -> str:
    lines = [f"File: {filename}", f"Shape: {df.shape[0]:,} rows × {df.shape[1]} columns\n"]
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if num_cols:
        lines.append("NUMERIC COLUMNS:")
        desc = df[num_cols].describe().round(2)
        for col in num_cols:
            d = desc[col]
            lines.append(f"  {col}: mean={d['mean']}, min={d['min']}, max={d['max']}, "
                         f"std={d['std']:.2f}, median={d['50%']}, nulls={int(df[col].isna().sum())}")
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    if cat_cols:
        lines.append("\nCATEGORICAL COLUMNS:")
        for col in cat_cols:
            vc = df[col].value_counts()
            lines.append(f"  {col}: {df[col].nunique()} unique, "
                         f"nulls={int(df[col].isna().sum())}, top5={dict(vc.head(5))}")
    if len(num_cols) >= 2:
        corr = df[num_cols].corr().round(3)
        pairs, seen = [], set()
        for c1 in corr.columns:
            for c2 in corr.columns:
                if c1 != c2 and (c2, c1) not in seen:
                    pairs.append((c1, c2, float(corr.loc[c1, c2]))); seen.add((c1, c2))
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        lines.append("\nTOP CORRELATIONS:")
        for a, b, r in pairs[:8]: lines.append(f"  {a} ↔ {b}  r={r}")
    lines.append("\nSAMPLE ROWS (first 5):")
    lines.append(df.head(5).to_string(index=False, max_cols=20))
    full = "\n".join(lines)
    return full[:MAX_PROFILE_CHARS] + "\n...[truncated]" if len(full) > MAX_PROFILE_CHARS else full


def compute_dynamic_stats(df: pd.DataFrame, question: str) -> str:
    q, extras = question.lower(), []
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    for col in cat_cols:
        if col.lower() in q or col.replace("_", " ").lower() in q:
            for nc in num_cols[:2]:
                try:
                    grp = df.groupby(col)[nc].agg(["mean", "sum", "count"]).round(2)
                    extras.append(f"GroupBy {col}×{nc}:\n{grp.to_string()}")
                except Exception: pass
            extras.append(f"Value counts '{col}':\n{df[col].value_counts().head(8).to_string()}")
            break
    for col in df.columns:
        if any(k in col.lower() for k in ("fraud", "risk", "anomaly", "flag")):
            if col.lower() in q or "fraud" in q or "risk" in q:
                try:
                    extras.append(f"'{col}':\n{df[col].value_counts().to_string()}")
                    for cc in cat_cols[:2]:
                        grp = df.groupby(cc)[col].mean().sort_values(ascending=False).round(4)
                        extras.append(f"Fraud by '{cc}':\n{grp.to_string()}")
                except Exception: pass
            break
    if any(k in q for k in ("top", "highest", "most", "largest")):
        for nc in num_cols[:1]:
            extras.append(f"Top 5 '{nc}':\n{df[nc].nlargest(5).to_string()}")
    result = "\n\n".join(extras) if extras else ""
    return result[:MAX_DYNAMIC_CHARS] + "\n...[truncated]" if len(result) > MAX_DYNAMIC_CHARS else result


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

Use ₹ for Indian currency, % for rates. Be confident and concise."""


def get_system_prompt() -> str:
    return _system_prompt if _system_prompt else STATIC_SYSTEM_PROMPT


def get_ai_client() -> OpenAI:
    if not API_KEY:
        raise HTTPException(status_code=500, detail="No API key configured. Set NVIDIA_API_KEY or ANTHROPIC_API_KEY in .env")
    base_url = NVIDIA_BASE_URL if PROVIDER == "nvidia" else ANTHROPIC_BASE_URL
    return OpenAI(api_key=API_KEY, base_url=base_url)


def call_ai(messages: list[dict]) -> str:
    client = get_ai_client()
    try:
        resp = client.chat.completions.create(
            model=AI_MODEL, messages=messages, max_tokens=1024, temperature=0.3
        )
        return resp.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI API error: {str(e)}")


def detect_chart_type(query: str) -> Optional[str]:
    q = query.lower()
    if any(k in q for k in ("highest","largest","maximum","biggest","top 10","distribution","bucket","range")): return "amountdist"
    if any(k in q for k in ("hour","peak","time of day")): return "hourly"
    if any(k in q for k in ("state","region","maharashtra","karnataka")): return "state"
    if any(k in q for k in ("categor","merchant","grocery","food","shopping")): return "category"
    if any(k in q for k in ("device","ios","android","web browser","compare device")): return "device_compare"
    if any(k in q for k in ("network","4g","5g","wifi","3g")): return "network"
    if any(k in q for k in ("bank","sbi","hdfc","icici","kotak")): return "bank"
    if any(k in q for k in ("day","week","monday","weekend")): return "daily"
    if any(k in q for k in ("age","young","senior","26-35")): return "age"
    if any(k in q for k in ("type","p2p","p2m","recharge","bill")): return "txtype"
    if "fraud" in q: return "fraud_overview"
    if any(k in q for k in ("volume","summary","overview")): return "category"
    return None


# ══════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    chart_type: Optional[str] = None

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
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok", provider=PROVIDER, model=AI_MODEL,
        csv_loaded=_df is not None,
        csv_filename=_df_filename if _df is not None else None,
    )


@app.get("/api/dashboard")
def get_dashboard():
    """
    Returns pre-computed dashboard stats for the currently loaded CSV.
    Called by the frontend when the Dashboard tab is opened.
    Returns {"csv_loaded": false} when no CSV has been uploaded yet.
    """
    if _df is None or _dashboard_cache is None:
        return {"csv_loaded": False}
    return {"csv_loaded": True, **_dashboard_cache}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    sid = req.session_id or str(uuid.uuid4())
    if sid not in sessions:
        sessions[sid] = []
    history = sessions[sid]

    user_content = req.message
    if _df is not None:
        dynamic = compute_dynamic_stats(_df, req.message)
        if dynamic:
            user_content = f"{req.message}\n\n[LIVE DATA STATS]\n{dynamic}"

    history.append({"role": "user", "content": user_content})
    trimmed  = history[-(MAX_HISTORY_TURNS * 2):]
    messages = [{"role": "system", "content": get_system_prompt()}] + trimmed
    reply    = call_ai(messages)
    history.append({"role": "assistant", "content": reply})
    sessions[sid] = history

    return ChatResponse(reply=reply, session_id=sid, chart_type=detect_chart_type(req.message))


@app.get("/api/overview", response_model=OverviewResponse)
def get_overview():
    sid = str(uuid.uuid4())
    sessions[sid] = []
    question = ("Give me a concise executive overview of this dataset. "
                "What are the 3-5 most important headlines a CEO should know immediately? "
                "Highlight key risks, top performers, and strategic opportunities. Be brief.")
    req    = ChatRequest(message=question, session_id=sid)
    result = chat(req)
    return OverviewResponse(overview=result.reply, session_id=sid)


@app.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    global _df, _df_filename, _system_prompt, _dashboard_cache

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")

    contents = await file.read()
    df = None
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(io.BytesIO(contents), encoding=enc, low_memory=False)
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    if df is None:
        raise HTTPException(status_code=400, detail="Could not decode CSV.")

    _df              = df
    _df_filename     = file.filename
    _system_prompt   = build_system_prompt_for_csv(df, file.filename)
    _dashboard_cache = compute_dashboard(df, file.filename)   # ← computes everything

    return {
        "message":      "CSV loaded successfully",
        "filename":     file.filename,
        "rows":         df.shape[0],
        "columns":      df.shape[1],
        "column_names": df.columns.tolist(),
    }


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    clean = [
        {"role": m["role"], "content": m["content"].split("[LIVE DATA STATS]")[0].strip()}
        for m in sessions[session_id]
    ]
    return {"session_id": session_id, "messages": clean}


@app.delete("/api/session/{session_id}")
def clear_session(session_id: str):
    if session_id in sessions:
        sessions.pop(session_id)
    return {"message": "Session cleared", "session_id": session_id}


@app.get("/")
def root():
    return {"name": "InsightX AI API", "version": "2.0.0", "docs": "/docs", "health": "/api/health"}