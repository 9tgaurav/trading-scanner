"""
SwingAI — Capital Allocation Engine
Tells you exactly how much to deploy vs keep in cash, every day.

Inputs  : macro_score (0-100), breadth, VIX, setup count, portfolio size
Output  : deploy%, cash%, max position size, risk per trade

Based on Minervini's market exposure model:
  - Full exposure (80-100%) only in confirmed Stage 2 bull market
  - Reduce to 50% when breadth weakens
  - Go defensive (<25%) when VIX spikes or market breaks down

Usage:
  from capital_allocation import get_capital_allocation
  alloc = get_capital_allocation(macro, sectors, scan_data, portfolio_inr=1_000_000)
  print(alloc["telegram_block"])
"""

import datetime


# ── ALLOCATION RULES ──────────────────────────────────────────────────────────
# Minervini exposure tiers (based on market health score)
EXPOSURE_TIERS = [
    # (min_score, max_score, deploy_pct, label, description)
    (80, 100, 90, "Aggressive",  "Market confirmed bull — deploy fully"),
    (65,  79, 75, "Offensive",   "Good conditions — take quality setups"),
    (50,  64, 55, "Moderate",    "Mixed signals — only A/A+ setups"),
    (35,  49, 35, "Defensive",   "Weak breadth — reduce size, wait"),
    (20,  34, 15, "Capital Pres","Danger zone — minimal exposure"),
    ( 0,  19,  0, "Cash",        "Bear market — 100% cash, protect capital"),
]

# Max risk per trade as % of portfolio (Minervini: never more than 1-2%)
RISK_PER_TRADE_PCT = 1.0  # 1% of portfolio per trade

# Position sizing adjustment based on setup grade
GRADE_SIZE_MULT = {
    "A+": 1.0,
    "A":  0.8,
    "B+": 0.6,
    "B":  0.4,
    "C":  0.0,  # skip C grade
}


# ── HELPERS ───────────────────────────────────────────────────────────────────
def _get_tier(score: int) -> dict:
    for mn, mx, deploy, label, desc in EXPOSURE_TIERS:
        if mn <= score <= mx:
            return {"deploy_pct": deploy, "label": label, "description": desc}
    return {"deploy_pct": 0, "label": "Cash", "description": "Unknown conditions"}


def _vix_adjustment(vix_val) -> int:
    """Return score penalty based on VIX."""
    if vix_val is None:
        return 0
    if vix_val > 30:
        return -20
    elif vix_val > 24:
        return -10
    elif vix_val < 13:
        return -5   # complacency also slightly negative
    return 0


def _setup_count_signal(n_setups: int) -> str:
    """Interpret number of quality setups."""
    if n_setups >= 15:
        return f"Strong ({n_setups} setups) — market generating opportunity ✅"
    elif n_setups >= 8:
        return f"Moderate ({n_setups} setups) — selective entries only 🟡"
    elif n_setups >= 3:
        return f"Thin ({n_setups} setups) — very selective ⚠️"
    else:
        return f"Scarce ({n_setups} setups) — stay patient, no chasing 🔴"


def _compute_max_positions(deploy_pct: int, risk_pct: float, avg_risk_per_setup: float) -> int:
    """
    Max concurrent positions given exposure and per-trade risk.
    deploy_pct: % of portfolio deployed
    risk_pct: max risk per trade (% of total portfolio)
    avg_risk_per_setup: typical stop distance (% of stock price)
    """
    if avg_risk_per_setup <= 0 or risk_pct <= 0:
        return 0
    # Each position = risk_pct / avg_risk_per_setup of portfolio
    pos_size_pct = risk_pct / avg_risk_per_setup * 100
    if pos_size_pct <= 0:
        return 0
    return max(1, int(deploy_pct / pos_size_pct))


# ── MAIN FUNCTION ─────────────────────────────────────────────────────────────
def get_capital_allocation(
    macro: dict,
    sectors: dict,
    scan_data: dict,
    portfolio_inr: int = 1_000_000,
) -> dict:
    """
    Compute capital allocation based on current market conditions.

    Args:
      macro        : output from macro_view.get_macro_view()
      sectors      : output from sector_rotation.get_sector_rotation()
      scan_data    : output from screener (scan_results.json)
      portfolio_inr: total portfolio in INR (default ₹10L)

    Returns:
      {
        "date": str,
        "portfolio_inr": int,
        "health_score": int,
        "deploy_pct": int,
        "cash_pct": int,
        "deploy_inr": int,
        "cash_inr": int,
        "tier_label": str,
        "tier_description": str,
        "max_positions": int,
        "risk_per_trade_inr": int,
        "max_position_size_inr": int,
        "setup_signal": str,
        "grade_sizing": dict,
        "key_rules": [str],
        "telegram_block": str,
      }
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # ── HEALTH SCORE ──────────────────────────────────────────────────────────
    base_score = macro.get("macro_score", 50)
    vix_val    = macro.get("vix", {}).get("value")
    vix_adj    = _vix_adjustment(vix_val)
    health_score = max(0, min(100, base_score + vix_adj))

    # ── TIER ──────────────────────────────────────────────────────────────────
    tier = _get_tier(health_score)
    deploy_pct = tier["deploy_pct"]
    cash_pct   = 100 - deploy_pct

    deploy_inr = int(portfolio_inr * deploy_pct / 100)
    cash_inr   = portfolio_inr - deploy_inr

    # ── SETUP ANALYSIS ───────────────────────────────────────────────────────
    results    = scan_data.get("results", [])
    aplus      = [r for r in results if r["grade"] == "A+"]
    a_grade    = [r for r in results if r["grade"] == "A"]
    quality_setups = len(aplus) + len(a_grade)

    setup_signal = _setup_count_signal(quality_setups)

    # Average risk % from top setups
    top_setups = (aplus + a_grade)[:10]
    if top_setups:
        avg_risk = sum(float(r.get("risk_pct", 8)) for r in top_setups) / len(top_setups)
    else:
        avg_risk = 8.0  # default 8% stop distance

    # ── POSITION SIZING ───────────────────────────────────────────────────────
    risk_per_trade_inr = int(portfolio_inr * RISK_PER_TRADE_PCT / 100)

    # Max position size = risk amount / stop distance %
    # e.g. risk ₹10k on 8% stop → position = ₹10k / 8% = ₹1.25L
    if avg_risk > 0:
        max_position_inr = int(risk_per_trade_inr / (avg_risk / 100))
    else:
        max_position_inr = int(deploy_inr * 0.2)

    # Cap: never more than 20% of portfolio in one position
    max_position_inr = min(max_position_inr, int(portfolio_inr * 0.20))

    # Max concurrent positions
    if max_position_inr > 0 and deploy_inr > 0:
        max_positions = min(int(deploy_inr / max_position_inr), 10)
    else:
        max_positions = 0

    # ── GRADE-BASED SIZING ───────────────────────────────────────────────────
    grade_sizing = {}
    for grade, mult in GRADE_SIZE_MULT.items():
        pos_inr = int(max_position_inr * mult)
        shares_example = "—"
        # Find an example stock from scan results for this grade
        ex = next((r for r in results if r["grade"] == grade), None)
        if ex and ex.get("entry", 0) > 0 and pos_inr > 0:
            shares_example = int(pos_inr / ex["entry"])
        grade_sizing[grade] = {
            "position_inr": pos_inr,
            "multiplier":   mult,
        }

    # ── KEY RULES ─────────────────────────────────────────────────────────────
    key_rules = []

    if deploy_pct == 0:
        key_rules.append("🔴 STAY IN CASH — Do not enter any new positions")
    elif deploy_pct <= 25:
        key_rules.append("⚠️ Minimal exposure — Only the highest conviction A+ setups")
        key_rules.append("⚠️ Half normal position size on all trades")
    elif deploy_pct <= 55:
        key_rules.append("🟡 Selective mode — A and A+ setups only, no B grades")
        key_rules.append("🟡 Cut losers fast at -7% or 1st stop")
    else:
        key_rules.append("✅ Normal exposure — Work all quality setups (A, A+, B+)")
        key_rules.append("✅ Let winners run — trail stop after +10%")

    # Sector-specific rule
    rotation_type = sectors.get("rotation_type", "Mixed")
    leaders       = sectors.get("leaders", [])
    if leaders and rotation_type == "Risk-On":
        top_sector = leaders[0]["sector"]
        key_rules.append(f"✅ Sector tailwind: Focus on {top_sector} stocks first")
    elif rotation_type == "Defensive":
        key_rules.append("⚠️ Market in defensive mode — avoid cyclical/small caps")

    # VIX rule
    if vix_val and vix_val > 24:
        key_rules.append(f"⚠️ VIX at {vix_val} — reduce position size by 30%")

    key_rules.append(f"📌 Max risk per trade: ₹{risk_per_trade_inr:,.0f} ({RISK_PER_TRADE_PCT}% of portfolio)")

    # ── TELEGRAM BLOCK ────────────────────────────────────────────────────────
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"CAPITAL ALLOCATION — {today}",
        f"Market Health: {health_score}/100 — {tier['label']}",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"Portfolio:      Rs{portfolio_inr:>12,.0f}",
        f"Deploy Now:     Rs{deploy_inr:>12,.0f}  ({deploy_pct}%)",
        f"Keep in Cash:   Rs{cash_inr:>12,.0f}  ({cash_pct}%)",
        "",
        f"Max Positions:  {max_positions}",
        f"Risk/Trade:     Rs{risk_per_trade_inr:,.0f}  (1% rule)",
        f"Max Pos Size:   Rs{max_position_inr:,.0f}",
        "",
        "POSITION SIZING BY GRADE:",
        f"  A+ Setup:  Rs{grade_sizing.get('A+', {}).get('position_inr', 0):>10,.0f}  (full size)",
        f"  A  Setup:  Rs{grade_sizing.get('A',  {}).get('position_inr', 0):>10,.0f}  (80% size)",
        f"  B+ Setup:  Rs{grade_sizing.get('B+', {}).get('position_inr', 0):>10,.0f}  (60% size)",
        "",
        f"Setup Quality: {setup_signal}",
        "",
        "TODAY'S RULES:",
    ]
    for rule in key_rules:
        lines.append(f"  {rule}")

    result = {
        "date":                  today,
        "portfolio_inr":         portfolio_inr,
        "health_score":          health_score,
        "deploy_pct":            deploy_pct,
        "cash_pct":              cash_pct,
        "deploy_inr":            deploy_inr,
        "cash_inr":              cash_inr,
        "tier_label":            tier["label"],
        "tier_description":      tier["description"],
        "max_positions":         max_positions,
        "risk_per_trade_inr":    risk_per_trade_inr,
        "max_position_size_inr": max_position_inr,
        "avg_stop_pct":          round(avg_risk, 1),
        "setup_signal":          setup_signal,
        "quality_setups":        quality_setups,
        "grade_sizing":          grade_sizing,
        "key_rules":             key_rules,
        "telegram_block":        "\n".join(lines),
    }

    print(f"  [Allocation] Score: {health_score}/100 → Deploy {deploy_pct}% (₹{deploy_inr:,.0f}), Cash {cash_pct}%")
    return result


# ── STANDALONE TEST ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  SwingAI — Capital Allocation Test (mock data)")
    print("="*55)

    # Mock inputs for testing without running full pipeline
    mock_macro = {
        "macro_score": 68,
        "macro_label": "Moderately Bullish",
        "vix": {"value": 16.5, "signal": "Calm"},
        "breadth": {"above_200_pct": 62},
        "nifty500": {"stage": "Stage 2 ▲ (Uptrend)"},
    }
    mock_sectors = {
        "rotation_type": "Risk-On",
        "leaders": [{"sector": "Bank"}, {"sector": "Auto"}, {"sector": "Metal"}],
    }
    mock_scan = {
        "results": [
            {"grade": "A+", "ticker": "RELIANCE", "entry": 1250, "risk_pct": 7.5},
            {"grade": "A",  "ticker": "TCS",      "entry": 3400, "risk_pct": 8.2},
            {"grade": "B+", "ticker": "INFY",     "entry": 1560, "risk_pct": 9.0},
        ]
    }

    alloc = get_capital_allocation(mock_macro, mock_sectors, mock_scan, portfolio_inr=1_000_000)
    print("\n" + alloc["telegram_block"])
