"""
SwingAI — Sector Rotation Module
Ranks NSE sectors by momentum. Zero manual work — all via yfinance.

What it does:
  • Fetches Nifty sector indices (IT, Bank, Auto, Pharma, FMCG, Metal, etc.)
  • Ranks by 1-month and 3-month price momentum
  • Outputs: Top 3 Leading, Bottom 3 Lagging, Rotation Signal

Usage:
  from sector_rotation import get_sector_rotation
  sectors = get_sector_rotation()
  print(sectors["telegram_block"])
"""

import yfinance as yf
import datetime

# ── SECTOR INDEX MAP ──────────────────────────────────────────────────────────
# Yahoo Finance tickers for NSE sector indices
SECTORS = {
    "IT":           "^CNXIT",
    "Bank":         "^NSEBANK",
    "Auto":         "^CNXAUTO",
    "Pharma":       "^CNXPHARMA",
    "FMCG":         "^CNXFMCG",
    "Metal":        "^CNXMETAL",
    "Realty":       "^CNXREALTY",
    "Energy":       "^CNXENERGY",
    "Infrastructure":"^CNXINFRA",
    "Financial Svcs":"^CNXFIN",
    "Consumption":  "^CNXCONSUM",
    "MidSmall":     "^NSMIDCP",
}

ROTATION_SIGNALS = {
    "Risk-On":   "Market favoring cyclicals (Bank, Auto, Metal, Realty) — increase exposure ✅",
    "Defensive": "Market rotating to defensives (FMCG, Pharma, IT) — reduce cyclical risk ⚠️",
    "Mixed":     "No clear rotation — stock picking matters more than sector ⚪",
    "Weak":      "Most sectors falling — preserve capital 🔴",
}


# ── HELPERS ───────────────────────────────────────────────────────────────────
def _pct_change(series, n_days: int):
    """Return % change over last n_days from a price series."""
    vals = [float(v) for v in series.dropna() if v == v]
    if len(vals) < n_days + 1:
        return None
    old = vals[-(n_days + 1)]
    new = vals[-1]
    if old == 0:
        return None
    return round((new - old) / old * 100, 2)


def _momentum_score(m1, m3):
    """Combined momentum score (60% weight on 1M, 40% on 3M)."""
    if m1 is None and m3 is None:
        return None
    m1 = m1 or 0
    m3 = m3 or 0
    return round(0.6 * m1 + 0.4 * m3, 2)


def _rotation_type(ranked: list) -> str:
    """
    Determine rotation type from top 3 leading sectors.
    Cyclicals: Bank, Auto, Metal, Realty, Energy, Infrastructure
    Defensives: FMCG, Pharma, IT
    """
    if not ranked:
        return "Weak"

    cyclicals  = {"Bank", "Auto", "Metal", "Realty", "Energy", "Infrastructure", "Financial Svcs"}
    defensives = {"FMCG", "Pharma", "IT"}

    top3 = [r["sector"] for r in ranked[:3]]
    top3_cyc = sum(1 for s in top3 if s in cyclicals)
    top3_def = sum(1 for s in top3 if s in defensives)

    # If majority of sectors are falling overall
    positive = sum(1 for r in ranked if (r.get("momentum_1m") or 0) > 0)
    if positive < len(ranked) * 0.35:
        return "Weak"

    if top3_cyc >= 2:
        return "Risk-On"
    elif top3_def >= 2:
        return "Defensive"
    else:
        return "Mixed"


# ── MAIN FUNCTION ─────────────────────────────────────────────────────────────
def get_sector_rotation() -> dict:
    """
    Fetch and rank NSE sectors by momentum.

    Returns:
      {
        "date": str,
        "sectors": [ {sector, price, momentum_1m, momentum_3m, score, rank} ],
        "leaders": [ top 3 sectors ],
        "laggards": [ bottom 3 sectors ],
        "rotation_type": str,
        "rotation_signal": str,
        "telegram_block": str,
        "errors": [str],
      }
    """
    errors = []
    today  = datetime.datetime.now().strftime("%Y-%m-%d")

    print("  [Sectors] Fetching sector data...")

    sector_data = []

    for name, ticker in SECTORS.items():
        try:
            df = yf.download(ticker, period="6mo", interval="1d",
                             progress=False, auto_adjust=True)
            if df is None or df.empty:
                errors.append(f"{name} data unavailable")
                continue

            # yfinance ≥0.2 returns MultiLevel DataFrame — squeeze to flat Series
            close = df["Close"]
            if hasattr(close, "squeeze"):
                close = close.squeeze()
            close  = close.dropna()
            price  = float(close.iloc[-1])
            m1     = _pct_change(close, 22)   # ~1 month
            m3     = _pct_change(close, 63)   # ~3 months
            score  = _momentum_score(m1, m3)

            sector_data.append({
                "sector":      name,
                "ticker":      ticker,
                "price":       round(price, 2),
                "momentum_1m": m1,
                "momentum_3m": m3,
                "score":       score,
            })

        except Exception as e:
            errors.append(f"{name}: {str(e)[:50]}")
            continue

    # ── RANK ─────────────────────────────────────────────────────────────────
    valid   = [s for s in sector_data if s["score"] is not None]
    ranked  = sorted(valid, key=lambda x: x["score"], reverse=True)

    for i, s in enumerate(ranked):
        s["rank"] = i + 1

    leaders  = ranked[:3]
    laggards = ranked[-3:] if len(ranked) >= 3 else []
    laggards = list(reversed(laggards))  # worst first

    rotation_type   = _rotation_type(ranked)
    rotation_signal = ROTATION_SIGNALS.get(rotation_type, "Mixed")

    # ── TELEGRAM BLOCK ────────────────────────────────────────────────────────
    def _arrow(val):
        if val is None:
            return "—"
        return f"{'▲' if val > 0 else '▼'} {abs(val):.1f}%"

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"SECTOR ROTATION — {today}",
        f"Rotation: {rotation_type}",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "TOP 3 LEADING SECTORS:",
    ]
    for s in leaders:
        lines.append(
            f"  #{s['rank']} {s['sector']:<16} "
            f"1M: {_arrow(s['momentum_1m'])}  3M: {_arrow(s['momentum_3m'])}"
        )

    lines += ["", "BOTTOM 3 LAGGING SECTORS:"]
    for s in laggards:
        lines.append(
            f"  #{s['rank']} {s['sector']:<16} "
            f"1M: {_arrow(s['momentum_1m'])}  3M: {_arrow(s['momentum_3m'])}"
        )

    lines += [
        "",
        f"Signal: {rotation_signal}",
    ]

    result = {
        "date":            today,
        "sectors":         ranked,
        "leaders":         leaders,
        "laggards":        laggards,
        "rotation_type":   rotation_type,
        "rotation_signal": rotation_signal,
        "telegram_block":  "\n".join(lines),
        "errors":          errors,
    }

    print(f"  [Sectors] Done. {len(ranked)} sectors ranked. Rotation: {rotation_type}")
    return result


# ── STANDALONE TEST ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  SwingAI — Sector Rotation Test")
    print("="*55)
    result = get_sector_rotation()
    print("\n" + result["telegram_block"])
    if result["errors"]:
        print(f"\nWarnings: {result['errors']}")
