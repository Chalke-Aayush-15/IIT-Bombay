"""
InsightX AI — Conversational Leadership Analytics Engine
=========================================================
Supports TWO AI providers:
  1. NVIDIA NIM → Llama, Nemotron … (integrate.api.nvidia.com)  FREE key
  2. Anthropic  → Claude             (api.anthropic.com)

REQUIREMENTS:  pip install openai pandas rich python-dotenv

QUICK START:
  python insightx_ai.py my_data.csv --provider nvidia
  python insightx_ai.py my_data.csv --provider anthropic

.env file:
  NVIDIA_API_KEY=nvapi-...
  ANTHROPIC_API_KEY=sk-ant-...
"""

import os, sys, json, argparse
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env optional

try:
    import pandas as pd
except ImportError:
    sys.exit("❌  pip install pandas")

try:
    from openai import OpenAI
except ImportError:
    sys.exit("❌  pip install openai")

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table
    HAS_RICH = True
    console  = Console()
except ImportError:
    HAS_RICH = False
    console  = None

# ── Constants ─────────────────────────────────────────────────────────────────
NVIDIA_BASE_URL    = "https://integrate.api.nvidia.com/v1"
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"

# MAX chars sent to the model in the system prompt (≈ 6 000 tokens, well under 131k)
MAX_PROFILE_CHARS = 24_000
# MAX chars for dynamic stats per question
MAX_DYNAMIC_CHARS = 4_000
# MAX conversation history messages kept (prevents context creep over many turns)
MAX_HISTORY_TURNS = 6

NVIDIA_MODELS = [
    ("meta/llama-3.3-70b-instruct",            "Llama 3.3 70B      ← recommended"),
    ("nvidia/llama-3.3-nemotron-super-49b-v1", "Nemotron Super 49B (NVIDIA reasoning)"),
    ("nvidia/llama-3.1-nemotron-nano-8b-v1",   "Nemotron Nano 8B   (fast)"),
    ("meta/llama-3.1-70b-instruct",            "Llama 3.1 70B      (stable)"),
]
DEFAULT_NVIDIA_MODEL    = NVIDIA_MODELS[0][0]
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-6"

# ── Display helpers ───────────────────────────────────────────────────────────
def print_md(text):
    if HAS_RICH:
        console.print(Markdown(text))
    else:
        print(text)

def print_panel(text, title="", style="blue"):
    if HAS_RICH:
        console.print(Panel(text, title=title, border_style=style))
    else:
        print(f"\n{'='*60}\n  {title}\n{'='*60}\n{text}\n")

# ── CSV loader ────────────────────────────────────────────────────────────────
def load_csv(path):
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(path, encoding=enc, low_memory=False)
            print(f"\n✅  Loaded '{Path(path).name}'  →  {df.shape[0]:,} rows × {df.shape[1]} columns")
            return df
        except UnicodeDecodeError:
            continue
        except Exception as e:
            sys.exit(f"❌  {e}")
    sys.exit("❌  Cannot decode CSV.")

# ── Smart dataset profiler (token-safe) ───────────────────────────────────────
def profile_dataframe(df: pd.DataFrame) -> str:
    """
    Build a COMPACT plain-text profile of the dataframe.
    Hard-capped at MAX_PROFILE_CHARS to never blow the context window.
    """
    lines = []
    lines.append(f"Shape: {df.shape[0]:,} rows × {df.shape[1]} columns\n")

    # ── Numeric columns ───────────────────────────────────────────────────────
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

    # ── Categorical columns ───────────────────────────────────────────────────
    cat_cols = df.select_dtypes(include=["object","category"]).columns.tolist()
    if cat_cols:
        lines.append("\nCATEGORICAL COLUMNS:")
        for col in cat_cols:
            vc    = df[col].value_counts()
            top5  = dict(vc.head(5))
            lines.append(
                f"  {col}: {df[col].nunique()} unique, "
                f"nulls={int(df[col].isna().sum())}, "
                f"top5={top5}"
            )

    # ── Correlations (top 8 pairs only) ───────────────────────────────────────
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

    # ── Sample rows (5 rows, stringified compactly) ───────────────────────────
    lines.append("\nSAMPLE ROWS (first 5):")
    sample_str = df.head(5).to_string(index=False, max_cols=20)
    lines.append(sample_str)

    # ── Missing values ─────────────────────────────────────────────────────────
    missing = df.isnull().sum()
    missing = missing[missing > 0]
    if not missing.empty:
        lines.append("\nMISSING VALUES:")
        for col, cnt in missing.items():
            lines.append(f"  {col}: {cnt}")
    else:
        lines.append("\nMISSING VALUES: None")

    full = "\n".join(lines)

    # Hard cap — never send more than MAX_PROFILE_CHARS to the model
    if len(full) > MAX_PROFILE_CHARS:
        full = full[:MAX_PROFILE_CHARS] + "\n... [profile truncated to stay within token limit]"

    return full


# ── Dynamic stats per question (also token-safe) ──────────────────────────────
def compute_dynamic_stats(df: pd.DataFrame, question: str) -> str:
    q        = question.lower()
    extras   = []
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include=["object","category"]).columns.tolist()

    # Categorical groupby if column name mentioned in question
    for col in cat_cols:
        if col.lower() in q or col.replace("_"," ").lower() in q:
            for nc in num_cols[:2]:          # max 2 numeric cols
                try:
                    grp = df.groupby(col)[nc].agg(["mean","sum","count"]).round(2)
                    extras.append(f"GroupBy {col}×{nc}:\n{grp.to_string()}")
                except Exception:
                    pass
            vc = df[col].value_counts().head(8)
            extras.append(f"Value counts '{col}':\n{vc.to_string()}")
            break   # only one cat col per query

    # Time trend
    for col in df.columns:
        if any(kw in col.lower() for kw in ("date","time","month","year","period")):
            if any(kw in q for kw in ("trend","over time","monthly","yearly","growth")):
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

    # Fraud/risk breakdown
    for col in df.columns:
        if any(kw in col.lower() for kw in ("fraud","risk","anomaly","flag")):
            if col.lower() in q or "fraud" in q or "risk" in q:
                try:
                    extras.append(f"'{col}' counts:\n{df[col].value_counts().to_string()}")
                    for cc in cat_cols[:2]:
                        grp = df.groupby(cc)[col].mean().sort_values(ascending=False).round(4)
                        extras.append(f"Fraud rate by '{cc}':\n{grp.to_string()}")
                except Exception:
                    pass
            break

    # Top / bottom
    if any(kw in q for kw in ("top","highest","most","largest")):
        for nc in num_cols[:1]:
            extras.append(f"Top 5 '{nc}':\n{df[nc].nlargest(5).to_string()}")
    if any(kw in q for kw in ("bottom","lowest","least","smallest")):
        for nc in num_cols[:1]:
            extras.append(f"Bottom 5 '{nc}':\n{df[nc].nsmallest(5).to_string()}")

    result = "\n\n".join(extras) if extras else "(No additional stats for this question.)"

    # Cap dynamic stats too
    if len(result) > MAX_DYNAMIC_CHARS:
        result = result[:MAX_DYNAMIC_CHARS] + "\n... [truncated]"
    return result


# ── System prompt (compact) ───────────────────────────────────────────────────
SYSTEM_TMPL = """You are InsightX AI — an elite AI Chief Data Officer for C-suite leadership.

Your mission:
1. Answer data questions with precision, citing exact numbers from the dataset.
2. Surface hidden risks, opportunities, and anomalies proactively.
3. Provide strategic, executive-level recommendations — not just observations.

DATASET: {filename}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{profile}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RESPONSE FORMAT:
• Use Markdown (headers, bold, bullets, tables where useful).
• Lead with the direct answer / key number.
• "📊 Analysis" — 2-4 sentences of interpretation.
• "💡 Leadership Recommendation" — 1-3 actionable bullets.
• Never fabricate numbers. Only use data from the profile or live stats provided."""


# ── AI engine ─────────────────────────────────────────────────────────────────
class InsightXAI:
    def __init__(self, df, filename, provider, api_key, model):
        self.df       = df
        self.filename = filename
        self.model    = model
        self.history  = []

        print("⏳  Profiling dataset...")
        profile_text  = profile_dataframe(df)
        print(f"✅  Profile size: {len(profile_text):,} chars  (~{len(profile_text)//4:,} tokens)")

        self.system = SYSTEM_TMPL.format(filename=filename, profile=profile_text)

        base_url = NVIDIA_BASE_URL if provider == "nvidia" else ANTHROPIC_BASE_URL
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _trimmed_history(self):
        """Keep only the last MAX_HISTORY_TURNS * 2 messages to prevent context bloat."""
        return self.history[-(MAX_HISTORY_TURNS * 2):]

    def ask(self, question: str) -> str:
        dynamic  = compute_dynamic_stats(self.df, question)
        enriched = f"{question}\n\n[LIVE STATS FOR THIS QUESTION]\n{dynamic}"

        self.history.append({"role": "user", "content": enriched})

        messages = [{"role": "system", "content": self.system}] + self._trimmed_history()

        try:
            resp   = self.client.chat.completions.create(
                model=self.model, messages=messages,
                max_tokens=1024, temperature=0.3
            )
            answer = resp.choices[0].message.content
        except Exception as e:
            answer = f"⚠️  API error: {e}"

        self.history.append({"role": "assistant", "content": answer})
        return answer

    def quick_overview(self) -> str:
        return self.ask(
            "Give me a concise executive overview of this dataset. "
            "What are the 3-5 most important headlines a CEO should know immediately? "
            "Highlight key risks, top performers, and strategic opportunities. Be brief."
        )

    def reset(self):
        self.history = []
        print("🔄  Conversation cleared.")


# ── CLI helpers ───────────────────────────────────────────────────────────────
HELP = """
┌──────────────────────────────────────────────────┐
│           InsightX AI  —  Commands               │
├──────────────────────────────────────────────────┤
│  overview   Re-generate executive overview       │
│  reset      Clear conversation history           │
│  columns    List dataset columns                 │
│  stats      Numeric summary table                │
│  model      Show current provider & model        │
│  export     Save Q&A session to .txt             │
│  help       Show this menu                       │
│  exit/quit  End session                          │
└──────────────────────────────────────────────────┘
"""

SUGGESTED = [
    "What are the top 3 risks I should address immediately?",
    "Which segment drives the most revenue / volume?",
    "Show fraud patterns by category and region.",
    "What time of day sees the most activity?",
    "Which age group has the highest transaction value?",
    "Compare performance across banks / devices / networks.",
    "What does the trend look like over time?",
    "Give me a SWOT analysis based on this data.",
]

def show_columns(df):
    if HAS_RICH:
        tbl = Table(title="Columns", header_style="bold blue")
        tbl.add_column("#", style="dim", width=4)
        tbl.add_column("Column", style="bold")
        tbl.add_column("Type")
        tbl.add_column("Non-null")
        for i, col in enumerate(df.columns, 1):
            tbl.add_row(str(i), col, str(df[col].dtype), str(df[col].count()))
        console.print(tbl)
    else:
        for i, col in enumerate(df.columns, 1):
            print(f"  {i:3}. {col}  ({df[col].dtype})")

def show_stats(df):
    num = df.select_dtypes(include="number")
    if num.empty:
        print("No numeric columns.")
        return
    desc = num.describe().round(2)
    if HAS_RICH:
        tbl = Table(title="Numeric Summary", header_style="bold green")
        tbl.add_column("Stat", style="bold")
        for col in desc.columns:
            tbl.add_column(col)
        for idx in desc.index:
            tbl.add_row(idx, *[str(desc.loc[idx,c]) for c in desc.columns])
        console.print(tbl)
    else:
        print(desc.to_string())

def export_session(history, filename):
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(f"insightx_session_{ts}.txt")
    lines = [f"InsightX AI — {filename}  ({ts})\n{'='*60}"]
    for m in history:
        role    = "YOU" if m["role"] == "user" else "INSIGHTX AI"
        content = m["content"].split("[LIVE STATS FOR THIS QUESTION]")[0].strip()
        lines.append(f"\n[{role}]\n{content}\n{'─'*60}")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅  Saved: {out.resolve()}")

def get_api_key(cli_key, provider):
    env = "NVIDIA_API_KEY" if provider == "nvidia" else "ANTHROPIC_API_KEY"
    key = cli_key or os.environ.get(env, "").strip()
    if not key:
        print(f"\n🔑  No API key found (env: {env})")
        import getpass
        key = getpass.getpass(f"   Enter {'NVIDIA NIM' if provider=='nvidia' else 'Anthropic'} key: ").strip()
    if not key:
        sys.exit("❌  API key required.")
    return key

def get_csv_path(cli_path):
    if cli_path and Path(cli_path).exists():
        return cli_path
    if cli_path:
        print(f"⚠️   Not found: {cli_path}")
    while True:
        p = input("\n📂  CSV path: ").strip().strip("'\"")
        if Path(p).exists():
            return p
        print(f"   Not found: {p}")

def pick_provider():
    print("\nChoose AI provider:")
    print("  1. NVIDIA NIM  — free key at build.nvidia.com")
    print("  2. Anthropic   — paid key at console.anthropic.com  (Claude)")
    return "anthropic" if input("Enter 1 or 2 [default 1]: ").strip() == "2" else "nvidia"

def pick_model(provider):
    if provider == "nvidia":
        print("\nAvailable NVIDIA NIM models:")
        for i, (mid, desc) in enumerate(NVIDIA_MODELS, 1):
            print(f"  {i}. {desc}")
        try:
            idx = int(input(f"Pick [1-{len(NVIDIA_MODELS)}, default 1]: ").strip()) - 1
            return NVIDIA_MODELS[idx][0]
        except (ValueError, IndexError):
            return DEFAULT_NVIDIA_MODEL
    return DEFAULT_ANTHROPIC_MODEL


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="InsightX AI")
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--provider", choices=["nvidia","anthropic"])
    ap.add_argument("--api-key")
    ap.add_argument("--model")
    ap.add_argument("--no-overview", action="store_true")
    args = ap.parse_args()

    print("""
╔═══════════════════════════════════════════════════════════════╗
║           InsightX AI — Leadership Analytics Engine           ║
║   Providers:  NVIDIA NIM (free)   •   Anthropic Claude        ║
╚═══════════════════════════════════════════════════════════════╝""")

    provider = args.provider or pick_provider()
    model    = args.model    or pick_model(provider)
    api_key  = get_api_key(args.api_key, provider)
    csv_path = get_csv_path(args.csv)
    filename = Path(csv_path).name

    df = load_csv(csv_path)
    ai = InsightXAI(df, filename, provider, api_key, model)

    prov_label = "NVIDIA NIM" if provider == "nvidia" else "Anthropic"
    if HAS_RICH:
        print_panel(
            f"Provider : [bold]{prov_label}[/bold]\n"
            f"Model    : [bold]{model}[/bold]\n"
            f"Dataset  : [bold]{filename}[/bold]  |  {df.shape[0]:,} rows × {df.shape[1]} cols",
            title="✅  Ready", style="green"
        )
    else:
        print(f"\nReady! {prov_label} / {model} | {filename} {df.shape[0]:,}r × {df.shape[1]}c")

    print("\n💡  Suggested questions:")
    for i, q in enumerate(SUGGESTED, 1):
        print(f"   {i}. {q}")

    if not args.no_overview:
        print("\n⏳  Generating executive overview...\n")
        try:
            print_md(ai.quick_overview())
        except Exception as e:
            print(f"⚠️  {e}")

    print("\n" + "─"*64)
    print("💬  Ask questions below   (type 'help' or 'exit')")
    print("─"*64 + "\n")

    while True:
        try:
            user_input = input("You ▶  ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋  Goodbye!")
            break

        if not user_input:
            continue
        cmd = user_input.lower()

        if   cmd in ("exit","quit","q"):  print("👋  Goodbye!"); break
        elif cmd == "help":               print(HELP)
        elif cmd == "reset":              ai.reset()
        elif cmd == "columns":            show_columns(df)
        elif cmd == "stats":              show_stats(df)
        elif cmd == "model":              print(f"\n  {prov_label}  /  {model}\n")
        elif cmd == "export":             export_session(ai.history, filename)
        elif cmd == "overview":
            print("\n⏳  Generating...\n")
            try:    print_md(ai.quick_overview())
            except Exception as e: print(f"❌  {e}")
        else:
            print("\n⏳  Thinking...\n")
            try:    print_md(ai.ask(user_input))
            except Exception as e: print(f"❌  {e}")
            print("\n" + "─"*64)

if __name__ == "__main__":
    main()