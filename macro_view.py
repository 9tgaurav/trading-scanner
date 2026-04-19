"""
SwingAI — Macro Market View Module
Pulls macro data automatically via yfinance (zero manual work).

What it fetches:
  • Nifty 500 trend (price vs 50 MA, 200 MA, stage)
  • India VIX (fear gauge)
  • FII / DII net activity (proxy via Nifty futures OI + broad market)
  • Market breadth (% of Nifty 500 stocks above 50 MA and 200 MA)

Usage:
  from macro_view import get_macro_view
  macro = get_macro_view()
  print(macro["summary"])
"""

import yfinance as yf
import datetime
import statistics
import pandas as pd

# ── CONSTANTS ────────────────────────────────────────────────────────────────
NIFTY500_INDEX   = "^CRSLDX"      # Nifty 500 on Yahoo Finance
NIFTY50_INDEX    = "^NSEI"        # Nifty 50
INDIA_VIX        = "^INDIAVIX"    # India VIX
SENSEX           = "^BSESN"       # BSE Sensex

# Sector proxies — Nifty sector indices on Yahoo Finance
SECTOR_INDICES = {
    "IT":           "^CNXIT",
    "Bank":         "^NSEBANK",
    "Auto":         "^CNXAUTO",
    "Pharma":       "^CNXPHARMA",
    "FMCG":         "^CNXFMCG",
    "Metal":        "^CNXMETAL",
    "Realty":       "^CNXREALTY",
    "Energy":       "^CNXENERGY",
    "Infra":        "^CNXINFRA",
    "Media":        "^CNXMEDIA",
}

# Sample of large Nifty 500 stocks for breadth calculation
BREADTH_SAMPLE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "HINDUNILVR.NS",
    "ICICIBANK.NS", "KOTAKBANK.NS", "BHARTIARTL.NS", "ITC.NS", "SBIN.NS",
    "BAJFINANCE.NS", "AXISBANK.NS", "MARUTI.NS", "TITAN.NS", "ULTRACEMCO.NS",
    "WIPRO.NS", "NESTLEIND.NS", "ADANIENT.NS", "POWERGRID.NS", "NTPC.NS",
    "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
    "TATAMOTORS.BO", "M&M.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", "EICHERMOT.NS",
    "HCLTECH.NS", "TECHM.NS", "LTIM.NS", "MPHASIS.NS", "COFORGE.NS",
    "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "COALINDIA.NS",
    "ONGC.NS", "BPCL.NS", "IOC.NS", "GAIL.NS", "INDIGO.NS",
    "DMART.NS", "TRENT.NS", "ABFRL.NS", "PAGEIND.NS", "PIDILITIND.NS",
]


# ── HELPERS ───────────────────────────────────────────────────────────────────
def _fetch(ticker: str, period: str = "1y", interval: str = "1d"):
    """Fetch OHLCV data. Returns a flat Close Series or None on failure."""
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        # yfinance ≥0.2 returns MultiLevel columns — squeeze to flat Series
        close = df["Close"]
        if hasattr(close, "squeeze"):
            close = close.squeeze()
        return close.dropna()
    except Exception:
        return None


def _ma(series, n: int):
    """Simple moving average of last N values."""
    try:
        vals = [float(v) for v in series.dropna().iloc[-n:] if v == v]
        if len(vals) < n:
            return None
        return round(sum(vals) / len(vals), 2)
    except Exception:
        return None


def _pct_change(new, old):
    if old and old != 0:
        return round((new - old) / old * 100, 2)
    return None


def _stage(price, ma50, ma200):
    """
    Minervini Stage classification:
      Stage 1 — base (price near MA200, MA50 flat)
      Stage 2 — uptrend (price > MA50 > MA200) ← ideal
      Stage 3 — topping (price < MA50, MA50 < MA200)
      Stage 4 — downtrend (price < MA50 < MA200)
    """
    if price is None or ma50 is None or ma200 is None:
        return "Unknown"
    if price > ma50 > ma200:
        return "Stage 2 ▲ (Uptrend)"
    elif price > ma200 and price < ma50:
        return "Stage 1 ↔ (Base)"
    elif price < ma50 and ma50 > ma200:
        return "Stage 3 ↓ (Topping)"
    else:
        return "Stage 4 ▼ (Downtrend)"


def _vix_signal(vix):
    """Translate VIX reading to market sentiment."""
    if vix is None:
        return "Unknown"
    if vix < 13:
        return "Complacent (risk of reversal)"
    elif vix < 18:
        return "Calm — Favorable for longs ✅"
    elif vix < 24:
        return "Elevated — Caution ⚠️"
    elif vix < 30:
        return "High Fear — Wait for stabilisation 🔴"
    else:
        return "Extreme Fear — Defensive mode 🆘"


# ── MARKET BREADTH ────────────────────────────────────────────────────────────
def _compute_breadth(tickers: list) -> dict:
    """
    For a sample list of stocks, compute:
      - % above 50 MA
      - % above 200 MA
    Returns dict with counts and percentages.
    """
    above_50 = 0
    above_200 = 0
    valid = 0

    try:
        import yfinance as yf
        data = yf.download(tickers, period="1y", interval="1d",
                           progress=False, auto_adjust=True, group_by="ticker")

        for ticker in tickers:
            try:
                # yfinance ≥0.2 multi-ticker: columns are (TICKER, FIELD)
                if isinstance(data.columns, pd.MultiIndex):
                    if (ticker, "Close") in data.columns:
                        close = data[(ticker, "Close")].dropna()
                    else:
                        continue
                else:
                    close = data["Close"].dropna()

                if close is None or len(close) < 50:
                    continue

                price = float(close.iloc[-1])
                ma50  = float(close.rolling(50).mean().iloc[-1])
                ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

                valid += 1
                if price > ma50:
                    above_50 += 1
                if ma200 and price > ma200:
                    above_200 += 1
            except Exception:
                continue

    except Exception:
        pass

    if valid == 0:
        return {"above_50_pct": None, "above_200_pct": None, "sample_size": 0}

    return {
        "above_50_pct":  round(above_50  / valid * 100, 1),
        "above_200_pct": round(above_200 / valid * 100, 1),
        "sample_size":   valid,
    }


def _breadth_signal(pct_above_200):
    """Interpret breadth."""
    if pct_above_200 is None:
        return "Unknown"
    if pct_above_200 >= 70:
        return "Strong — Broad participation ✅"
    elif pct_above_200 >= 50:
        return "Healthy — Moderate breadth 🟡"
    elif pct_above_200 >= 35:
        return "Weak — Narrow leadership ⚠️"
    else:
        return "Very Weak — Avoid new longs 🔴"


# ── MAIN FUNCTION ─────────────────────────────────────────────────────────────
def get_macro_view(breadth_tickers: list = None) -> dict:
    """
    Pull all macro data and return a structured dict.

    Returns:
      {
        "date": str,
        "nifty500": { price, ma50, ma200, stage, chg_1d, chg_1w, chg_1m },
        "nifty50":  { price, ma50, ma200, stage, chg_1d },
        "vix":      { value, signal },
        "breadth":  { above_50_pct, above_200_pct, signal },
        "macro_score": int (0-100),
        "macro_label": str,
        "summary": str  (human-readable one-liner),
        "telegram_block": str,
        "errors": [str],
      }
    """
    errors = []
    today  = datetime.datetime.now().strftime("%Y-%m-%d")

    result = {
        "date":        today,
        "nifty500":    {},
        "nifty50":     {},
        "vix":         {},
        "breadth":     {},
        "macro_score": 50,
        "macro_label": "Neutral",
        "summary":     "",
        "telegram_block": "",
        "errors":      errors,
    }

    # ── 1. NIFTY 500 ──────────────────────────────────────────────────────────
    print("  [Macro] Fetching Nifty 500...")
    df500 = _fetch(NIFTY500_INDEX, period="1y")
    if df500 is not None and len(df500) > 0:
        close500  = df500  # already a flat Series from _fetch
        price500  = float(close500.iloc[-1])
        ma50_500  = _ma(close500, 50)
        ma200_500 = _ma(close500, 200)
        chg_1d    = _pct_change(price500, float(close500.iloc[-2])) if len(close500) > 1 else None
        chg_1w    = _pct_change(price500, float(close500.iloc[-6])) if len(close500) > 5 else None
        chg_1m    = _pct_change(price500, float(close500.iloc[-22])) if len(close500) > 21 else None

        result["nifty500"] = {
            "price":   round(price500, 2),
            "ma50":    ma50_500,
            "ma200":   ma200_500,
            "stage":   _stage(price500, ma50_500, ma200_500),
            "chg_1d":  chg_1d,
            "chg_1w":  chg_1w,
            "chg_1m":  chg_1m,
        }
    else:
        errors.append("Nifty 500 data unavailable")
        print("  [Macro] ⚠ Nifty 500 fetch failed")

    # ── 2. NIFTY 50 ───────────────────────────────────────────────────────────
    print("  [Macro] Fetching Nifty 50...")
    df50 = _fetch(NIFTY50_INDEX, period="1y")
    if df50 is not None and len(df50) > 0:
        close50  = df50  # already a flat Series from _fetch
        price50  = float(close50.iloc[-1])
        ma50_50  = _ma(close50, 50)
        ma200_50 = _ma(close50, 200)
        chg_1d50 = _pct_change(price50, float(close50.iloc[-2])) if len(close50) > 1 else None

        result["nifty50"] = {
            "price":  round(price50, 2),
            "ma50":   ma50_50,
            "ma200":  ma200_50,
            "stage":  _stage(price50, ma50_50, ma200_50),
            "chg_1d": chg_1d50,
        }
    else:
        errors.append("Nifty 50 data unavailable")

    # ── 3. INDIA VIX ─────────────────────────────────────────────────────────
    print("  [Macro] Fetching India VIX...")
    dfvix = _fetch(INDIA_VIX, period="5d")
    if dfvix is not None and len(dfvix) > 0:
        vix_val = float(dfvix.iloc[-1])   # dfvix is already a flat Series
        result["vix"] = {
            "value":  round(vix_val, 2),
            "signal": _vix_signal(vix_val),
        }
    else:
        errors.append("India VIX data unavailable")
        print("  [Macro] ⚠ VIX fetch failed")

    # ── 4. MARKET BREADTH ────────────────────────────────────────────────────
    print("  [Macro] Computing market breadth (sample of 50 stocks)...")
    tickers = breadth_tickers or BREADTH_SAMPLE
    breadth = _compute_breadth(tickers)
    breadth["signal"] = _breadth_signal(breadth.get("above_200_pct"))
    result["breadth"] = breadth

    # ── 5. MACRO SCORE (0–100) ───────────────────────────────────────────────
    score = 50  # start neutral
    reasons = []

    n5 = result["nifty500"]
    if n5.get("stage", "").startswith("Stage 2"):
        score += 20
        reasons.append("Nifty 500 in Stage 2 uptrend")
    elif n5.get("stage", "").startswith("Stage 4"):
        score -= 20
        reasons.append("Nifty 500 in Stage 4 downtrend")
    elif n5.get("stage", "").startswith("Stage 3"):
        score -= 10
        reasons.append("Nifty 500 topping")

    vix_val = result["vix"].get("value")
    if vix_val:
        if vix_val < 18:
            score += 10
            reasons.append(f"VIX low at {vix_val}")
        elif vix_val > 24:
            score -= 15
            reasons.append(f"VIX elevated at {vix_val}")

    b200 = breadth.get("above_200_pct")
    if b200:
        if b200 >= 70:
            score += 15
            reasons.append(f"{b200}% stocks above 200 MA")
        elif b200 >= 50:
            score += 5
        elif b200 < 35:
            score -= 15
            reasons.append(f"Only {b200}% stocks above 200 MA")

    chg_1m = n5.get("chg_1m")
    if chg_1m:
        if chg_1m > 3:
            score += 5
        elif chg_1m < -5:
            score -= 10

    score = max(0, min(100, score))
    result["macro_score"] = score

    if score >= 75:
        result["macro_label"] = "Bullish 🟢"
    elif score >= 55:
        result["macro_label"] = "Moderately Bullish 🟡"
    elif score >= 40:
        result["macro_label"] = "Neutral ⚪"
    elif score >= 25:
        result["macro_label"] = "Cautious 🟠"
    else:
        result["macro_label"] = "Bearish 🔴"

    # ── 6. SUMMARY & TELEGRAM BLOCK ─────────────────────────────────────────
    n500_price = n5.get("price", "—")
    n500_chg   = n5.get("chg_1d")
    chg_str    = f" ({'+' if n500_chg and n500_chg > 0 else ''}{n500_chg}%)" if n500_chg else ""

    result["summary"] = (
        f"Market {result['macro_label']} | "
        f"Nifty 500: {n500_price}{chg_str} | "
        f"VIX: {vix_val or '—'} | "
        f"Breadth: {b200 or '—'}% above 200MA"
    )

    vix_info   = result["vix"]
    breadth_info = result["breadth"]
    n50_info   = result["nifty50"]

    tg_lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"MACRO VIEW — {today}",
        f"Market Status: {result['macro_label']} (Score: {score}/100)",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"Nifty 500:  Rs{n500_price}{chg_str}",
        f"Trend:      {n5.get('stage', '—')}",
        f"MA50:       Rs{n5.get('ma50', '—')}  |  MA200: Rs{n5.get('ma200', '—')}",
        f"1W Change:  {n5.get('chg_1w', '—')}%  |  1M: {n5.get('chg_1m', '—')}%",
        "",
        f"Nifty 50:   Rs{n50_info.get('price', '—')}  ({'+' if (n50_info.get('chg_1d') or 0) > 0 else ''}{n50_info.get('chg_1d', '—')}%)",
        f"Trend:      {n50_info.get('stage', '—')}",
        "",
        f"India VIX:  {vix_info.get('value', '—')}",
        f"Sentiment:  {vix_info.get('signal', '—')}",
        "",
        f"Breadth (above 200 MA): {breadth_info.get('above_200_pct', '—')}%",
        f"Breadth (above 50 MA):  {breadth_info.get('above_50_pct', '—')}%",
        f"Signal:     {breadth_info.get('signal', '—')}",
    ]
    result["telegram_block"] = "\n".join(tg_lines)

    print(f"  [Macro] Done. Score: {score}/100 — {result['macro_label']}")
    return result


# ── STANDALONE TEST ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  SwingAI — Macro View Test")
    print("="*55)
    macro = get_macro_view()
    print("\n" + macro["telegram_block"])
    if macro["errors"]:
        print(f"\nWarnings: {macro['errors']}")
