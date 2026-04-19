"""
SwingAI NSE Screener — Full Nifty 500 Universe
Minervini SEPA: Trend Template + VCP Detection + Position Sizing

Compatible with yfinance >= 1.0 (handles MultiIndex columns)

Usage:
  python screener.py                     # full Nifty 500 scan
  python screener.py --portfolio 5000000 # ₹50L portfolio
  python screener.py --workers 25        # more parallel threads
  python screener.py --tickers RELIANCE.NS,TCS.NS  # custom list
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import json, os, sys, time, argparse, csv, io
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import warnings
warnings.filterwarnings("ignore")

# ── CONFIG ────────────────────────────────────────────────────────────────────
OUTPUT_DIR      = os.path.dirname(os.path.abspath(__file__))
TODAY           = datetime.now().strftime("%Y-%m-%d")
NSE_CSV_URL     = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
DEFAULT_WORKERS = 20

# ── NIFTY 500 FALLBACK (April 2026) ──────────────────────────────────────────
NIFTY500_FALLBACK = [
    "360ONE","3MINDIA","ABB","ACC","ACMESOLAR","AIAENG","APLAPOLLO","AUBANK",
    "AWL","AADHARHFC","AARTIIND","AAVAS","ABBOTINDIA","ABCAPITAL","ABFRL",
    "ADANIENSOL","ADANIENT","ADANIGREEN","ADANIPORTS","ADANIPOWER","ATGL",
    "ADANITRANS","AFFLE","AJANTPHARM","AKUMS","ALKEM","ALKYLAMINE","ALOKINDS",
    "AMBUJACEM","ANANDRATHI","ANGELONE","APARINDS","APOLLOHOSP","APOLLOTYRE",
    "APTUS","ARMANFIN","ASAHIINDIA","ASHOKLEY","ASIANPAINT","ASTERDM","ASTRAL",
    "ATUL","AUROPHARMA","AVANTIFEED","AXISBANK","BAJAJ-AUTO","BAJAJFINSV",
    "BAJAJHLDNG","BAJFINANCE","BALKRISIND","BALRAMCHIN","BANDHANBNK","BANKBARODA",
    "BANKINDIA","BATAINDIA","BAYERCROP","BEL","BEML","BERGEPAINT","BHARATFORG",
    "BHARTIARTL","BHEL","BIKAJI","BIOCON","BIRLACORPN","BSOFT","BLUESTARCO",
    "BOSCHLTD","BPCL","BRIGADE","BSE","CAMS","CANFINHOME","CANBK","CAPLIPOINT",
    "CARBORUNIV","CASTROLIND","CDSL","CEATLTD","CENTURYPLY","CENTURYTEX","CERA",
    "CHALET","CHAMBLFERT","CHOLAFIN","CHOLAHLDNG","CIPLA","CUB","COALINDIA",
    "COFORGE","COLPAL","CONCOR","COROMANDEL","CRAFTSMAN","CREDITACC","CROMPTON",
    "CYIENT","DALBHARAT","DATAPATTNS","DEEPAKNTR","DELHIVERY","DEVYANI","DIXON",
    "DLF","DMART","DRREDDY","DOMS","ECLERX","EICHERMOT","ELECON","EMAMILTD",
    "ENDURANCE","ENGINERSIN","EPIGRAL","EQUITASBNK","ERIS","ESCORTS","EXIDEIND",
    "FDC","FEDERALBNK","FINCABLES","FINEORG","FINPIPE","FORTIS","GMRINFRA",
    "GAIL","GILLETTE","GLAXO","GLENMARK","GNFC","GODREJCP","GODREJIND",
    "GODREJPROP","GRANULES","GRAPHITE","GRASIM","GRINDWELL","GSFC","GSPL",
    "GUJGASLTD","GULFOILLUB","HBLPOWER","HDFCAMC","HDFCBANK","HDFCLIFE","HEG",
    "HFCL","HGINFRA","HIKAL","HINDCOPPER","HINDPETRO","HINDUNILVR","HINDALCO",
    "HAL","HONASA","HUDCO","ICICIBANK","ICICIGI","ICICIPRULI","IDFCFIRSTB",
    "IEX","IIFL","INDHOTEL","INDIAMART","INDIANB","INDIGO","INDUSINDBK",
    "INDUSTOWER","INFY","INTELLECT","IOB","IOC","IPCALAB","IRCTC","IREDA",
    "IRFC","ITC","JBCHEPHARM","JKCEMENT","JKLAKSHMI","JKPAPER","JKTYRE",
    "JMFINANCIL","JSWENERGY","JSWINFRA","JSWSTEEL","JUBLFOOD","JUSTDIAL",
    "KAJARIACER","KANSAINER","KALYANKJIL","KAYNES","KEC","KEI","KFINTECH",
    "KNRCON","KPIL","KOTAKBANK","KRBL","LTF","LTTS","LICHSGFIN","LICI",
    "LINDEINDIA","LT","LTIM","LUPIN","LUXIND","M&M","M&MFIN","MANAPPURAM",
    "MARICO","MARUTI","MASTEK","MAXHEALTH","MCX","METROPOLIS","MFSL","MGL",
    "MOIL","MPHASIS","MRF","MRPL","MUTHOOTFIN","NAUKRI","NAVINFLUOR","NCC",
    "NESTLEIND","NHPC","NILKAMAL","NMDC","NOCIL","NTPC","OBEROIRLTY","OFSS",
    "OIL","ONGC","PAGEIND","PATANJALI","PCBL","PERSISTENT","PETRONET","PFC",
    "PFIZER","PGHH","PHOENIXLTD","PIDILITIND","PIIND","PNB","PNBHOUSING",
    "POLICYBZR","POLYCAB","POLYMED","POONAWALLA","POWERGRID","PRAJIND",
    "PRESTIGE","PRINCEPIPE","PVRINOX","RAILTEL","RAINBOW","RAJESHEXPO",
    "RECLTD","REDINGTON","RELIANCE","RENUKA","ROSSARI","ROUTE","SBIN","SBFC",
    "SBICARD","SBILIFE","SCHAEFFLER","SHREECEM","SHRIRAMFIN","SIEMENS","SJVN",
    "SKFINDIA","SOBHA","SONACOMS","SOLARINDS","SRF","STARHEALTH","STLTECH",
    "SUDARSCHEM","SUMICHEM","SUNPHARMA","SUNTV","SUPREMEIND","SURYAROSNI",
    "SUZLON","SWIGGY","SYNGENE","TANLA","TATACOMM","TATACONSUM","TATAELXSI",
    "TATAMOTORS","TATAPOWER","TATASTEEL","TATATECH","TCS","TECHM","TIINDIA",
    "TIMKEN","TITAGARH","TITAN","TORNTPHARM","TORNTPOWER","TRENT","TRIDENT",
    "TRIVENI","TVSMOTORS","UCOBANK","UJJIVANSFB","ULTRACEMCO","UNIONBANK",
    "UPL","UTIAMC","VBL","VAIBHAVGBL","VEDL","VINATIORGA","VOLTAS","VMART",
    "WHIRLPOOL","WIPRO","WOCKPHARMA","YESBANK","ZEEL","ZENSARTECH","ZYDUSLIFE",
    "ZYDUSWELL","CDSL","DALBHARAT","DEEPAKNTR","EDELWEISS","GMRAIRPORT",
    "IDBI","INNOVACAP","JBMA","MMTC","MSUMI","OLECTRA","POLYMED","PVRINOX",
]


# ── FETCH LIVE NIFTY 500 FROM NSE ─────────────────────────────────────────────
def fetch_nifty500_live():
    """Fetches live Nifty 500 from NSE. Falls back to built-in list on error."""
    try:
        req = urllib.request.Request(
            NSE_CSV_URL,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SwingAI/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(raw))
        tickers = [
            row["Symbol"].strip() + ".NS"
            for row in reader
            if row.get("Series", "").strip() == "EQ" and row.get("Symbol", "").strip()
        ]
        if len(tickers) >= 450:
            return tickers
        print(f"  ⚠ NSE returned {len(tickers)} tickers — using fallback")
        return [t + ".NS" for t in NIFTY500_FALLBACK]
    except Exception as e:
        print(f"  ⚠ NSE fetch failed ({e}) — using built-in list")
        return [t + ".NS" for t in NIFTY500_FALLBACK]


# ── FLATTEN YFINANCE DATAFRAME ────────────────────────────────────────────────
def flatten_df(df):
    """
    yfinance >= 1.0 returns MultiIndex columns: ('Close', 'TICKER').
    This flattens to simple columns: 'Close', 'High', etc.
    Also handles single-level columns (older yfinance) gracefully.
    """
    if df is None or df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.droplevel(1)
    return df


# ── MINERVINI TREND TEMPLATE (8 criteria) ────────────────────────────────────
def check_trend_template(df):
    """
    Returns (passes: bool, score: int, details: dict)
    All 8 Minervini criteria checked.
    """
    if df is None or len(df) < 200:
        return False, 0, {}

    close = df["Close"].squeeze()  # ensure Series
    if not isinstance(close, pd.Series):
        return False, 0, {}

    current = float(close.iloc[-1])
    if current <= 0 or np.isnan(current):
        return False, 0, {}

    ma50  = float(close.rolling(50).mean().iloc[-1])
    ma150 = float(close.rolling(150).mean().iloc[-1])
    ma200 = float(close.rolling(200).mean().iloc[-1])

    ma200_series = close.rolling(200).mean().dropna()
    if len(ma200_series) < 22:
        return False, 0, {}
    ma200_1m_ago = float(ma200_series.iloc[-22])

    n        = min(252, len(close))
    high_52w = float(close.iloc[-n:].max())
    low_52w  = float(close.iloc[-n:].min())

    if any(np.isnan(v) for v in [ma50, ma150, ma200, ma200_1m_ago, high_52w, low_52w]):
        return False, 0, {}

    criteria = {
        "above_ma150_ma200":     current > ma150 and current > ma200,
        "ma150_above_ma200":     ma150 > ma200,
        "ma200_trending_up":     ma200 > ma200_1m_ago,
        "ma50_above_ma150_200":  ma50 > ma150 and ma50 > ma200,
        "price_above_ma50":      current > ma50,
        "above_30pct_52w_low":   current >= low_52w * 1.30,
        "within_25pct_52w_high": current >= high_52w * 0.75,
        "rs_proxy":              current >= (high_52w * 0.60),  # in top 40% of 52w range
    }

    score = sum(criteria.values())
    details = {
        "price":    round(current, 2),
        "ma50":     round(ma50, 2),
        "ma150":    round(ma150, 2),
        "ma200":    round(ma200, 2),
        "52w_high": round(high_52w, 2),
        "52w_low":  round(low_52w, 2),
        "tt_score": f"{score}/8",
    }
    return score >= 7, score, details


# ── VCP DETECTION ─────────────────────────────────────────────────────────────
def detect_vcp(df, lookback=60):
    """
    Volatility Contraction Pattern:
    3 successive range contractions + volume drying up.
    Returns (is_vcp: bool, tightness_pct: float)
    """
    if df is None or len(df) < lookback:
        return False, 0.0

    recent = df.tail(lookback).copy()
    high   = recent["High"].squeeze()
    low    = recent["Low"].squeeze()
    vol    = recent["Volume"].squeeze()
    close  = recent["Close"].squeeze()

    seg = lookback // 3
    ranges, vol_avgs = [], []
    for i in range(3):
        h = high.iloc[i * seg:(i + 1) * seg]
        l = low.iloc[i * seg:(i + 1) * seg]
        v = vol.iloc[i * seg:(i + 1) * seg]
        lmin = float(l.min())
        rng  = ((float(h.max()) - lmin) / lmin * 100) if lmin > 0 else 0.0
        ranges.append(rng)
        vol_avgs.append(float(v.mean()))

    contracting = ranges[0] > ranges[1] > ranges[2]
    vol_drying   = vol_avgs[2] < vol_avgs[0]

    last10    = recent.tail(10)
    cp        = float(last10["Close"].squeeze().iloc[-1])
    h10       = float(last10["High"].squeeze().max())
    l10       = float(last10["Low"].squeeze().min())
    tightness = ((h10 - l10) / cp * 100) if cp > 0 else 99.0

    is_vcp = contracting and vol_drying and tightness < 15
    return is_vcp, round(tightness, 2)


# ── SETUP GRADING ─────────────────────────────────────────────────────────────
def grade_setup(tt_score, is_vcp, tightness, volume_ratio, rs_rank):
    if tt_score < 6:
        return "REJECT"
    pts = {8: 4, 7: 3, 6: 1}.get(tt_score, 0)
    if is_vcp:              pts += 3
    if tightness < 8:       pts += 2
    elif tightness < 12:    pts += 1
    if volume_ratio > 2.0:  pts += 2
    elif volume_ratio > 1.5: pts += 1
    if rs_rank > 90:        pts += 2
    elif rs_rank > 80:      pts += 1
    if pts >= 11: return "A+"
    if pts >= 9:  return "A"
    if pts >= 7:  return "B+"
    if pts >= 5:  return "B"
    return "C"


# ── ENTRY / STOP / TARGET ─────────────────────────────────────────────────────
def calculate_levels(df, current_price):
    """Pivot breakout entry, 8% initial stop, 2R and 3R targets."""
    recent = df.tail(20)
    pivot  = float(recent["High"].squeeze().max())
    entry  = round(pivot * 1.005, 2)          # 0.5% above pivot
    stop   = round(current_price * 0.92, 2)   # 8% stop
    risk   = max(entry - stop, 0.01)
    t2     = round(entry + 2 * risk, 2)
    t3     = round(entry + 3 * risk, 2)
    return {
        "entry":      entry,
        "stop":       stop,
        "target_2r":  t2,
        "target_3r":  t3,
        "risk_pct":   round((entry - stop) / entry * 100, 1),
        "r_multiple": round((t2 - entry) / risk, 1),
    }


# ── POSITION SIZING ───────────────────────────────────────────────────────────
def position_size_inr(entry, stop, portfolio_inr=1_000_000, risk_pct=1.0):
    """Risk 1% of portfolio per trade."""
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return 0, 0
    risk_amount = portfolio_inr * (risk_pct / 100)
    shares      = int(risk_amount / risk_per_share)
    return shares, int(round(shares * entry, 0))


# ── SINGLE STOCK SCAN (runs in thread) ───────────────────────────────────────
def scan_one(ticker, portfolio_inr):
    """
    Downloads 2 years of daily data, runs SEPA analysis.
    Returns result dict or None (rejected / insufficient data / error).
    """
    try:
        raw = yf.download(
            ticker, period="2y", interval="1d",
            progress=False, auto_adjust=True
        )
        if raw is None or raw.empty:
            return None

        # ← KEY FIX: flatten MultiIndex columns from yfinance >= 1.0
        df = flatten_df(raw).dropna()

        if len(df) < 200:
            return None

        # Verify required columns exist after flatten
        for col in ["Close", "High", "Low", "Volume"]:
            if col not in df.columns:
                return None

        current = float(df["Close"].squeeze().iloc[-1])
        if current <= 0 or np.isnan(current):
            return None

        # Trend Template
        passes_tt, tt_score, tt_details = check_trend_template(df)
        if tt_score < 6:
            return None

        # VCP
        is_vcp, tightness = detect_vcp(df)

        # Volume ratio vs 20-day average
        vol_series = df["Volume"].squeeze()
        vol_today  = float(vol_series.iloc[-1])
        vol_avg20  = float(vol_series.tail(20).mean())
        vol_ratio  = round(vol_today / vol_avg20, 2) if vol_avg20 > 0 else 1.0

        # RS rank proxy (position in 52-week range)
        close_series = df["Close"].squeeze()
        n        = min(252, len(close_series))
        high_52w = float(close_series.iloc[-n:].max())
        low_52w  = float(close_series.iloc[-n:].min())
        rs_rank  = int((current - low_52w) / (high_52w - low_52w) * 100) \
                   if high_52w > low_52w else 50

        grade = grade_setup(tt_score, is_vcp, tightness, vol_ratio, rs_rank)
        if grade == "REJECT":
            return None

        levels       = calculate_levels(df, current)
        shares, pval = position_size_inr(levels["entry"], levels["stop"], portfolio_inr)

        return {
            "ticker":        ticker.replace(".NS", "").replace(".BO", ""),
            "grade":         grade,
            "price":         round(current, 2),
            "tt_score":      tt_details["tt_score"],
            "is_vcp":        is_vcp,
            "tightness_pct": tightness,
            "volume_ratio":  vol_ratio,
            "rs_rank":       rs_rank,
            "entry":         levels["entry"],
            "stop":          levels["stop"],
            "target_2r":     levels["target_2r"],
            "target_3r":     levels["target_3r"],
            "risk_pct":      levels["risk_pct"],
            "r_multiple":    levels["r_multiple"],
            "shares":        shares,
            "position_inr":  pval,
            "ma50":          tt_details["ma50"],
            "ma150":         tt_details["ma150"],
            "ma200":         tt_details["ma200"],
            "52w_high":      tt_details["52w_high"],
            "52w_low":       tt_details["52w_low"],
            "scan_date":     TODAY,
        }

    except Exception:
        return None


# ── MAIN SCREENER ─────────────────────────────────────────────────────────────
def run_screener(tickers=None, portfolio_inr=1_000_000, workers=DEFAULT_WORKERS):
    t0 = time.time()

    if tickers is None:
        print("  Fetching live Nifty 500 list from NSE India...")
        tickers = fetch_nifty500_live()

    total = len(tickers)
    print(f"\n{'='*65}")
    print(f"  SWINGAI SCREENER — {TODAY}")
    print(f"  Universe : {total} stocks (Nifty 500)")
    print(f"  Method   : Minervini SEPA (Trend Template + VCP)")
    print(f"  Threads  : {workers} parallel")
    print(f"  Portfolio: ₹{portfolio_inr:,.0f}")
    print(f"{'='*65}\n")

    results, errors, done = [], [], 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(scan_one, t, portfolio_inr): t for t in tickers}
        for future in as_completed(future_map):
            ticker = future_map[future]
            done  += 1
            filled = int(30 * done / total)
            bar    = "█" * filled + "░" * (30 - filled)
            print(f"\r  [{bar}] {done/total*100:5.1f}%  {done}/{total}  ", end="", flush=True)
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as e:
                errors.append({"ticker": ticker, "error": str(e)})

    elapsed = round(time.time() - t0, 1)
    print(f"\n\n  Scan complete in {elapsed}s\n")

    # Sort: grade → RS rank desc
    grade_order = {"A+": 0, "A": 1, "B+": 2, "B": 3, "C": 4}
    results.sort(key=lambda x: (grade_order.get(x["grade"], 5), -x["rs_rank"]))

    # Console output
    print(f"{'='*65}")
    print(f"  RESULTS: {len(results)} setups found across {total} stocks")
    print(f"{'='*65}")
    for r in results:
        vcp = "✓VCP" if r["is_vcp"] else "    "
        print(
            f"  [{r['grade']:>2}] {r['ticker']:<14}  ₹{r['price']:>9.2f}  "
            f"E:₹{r['entry']:>9.2f}  S:₹{r['stop']:>9.2f}  "
            f"TT:{r['tt_score']}  {vcp}  RS:{r['rs_rank']}"
        )
    if not results:
        print("  No setups pass criteria today — market breadth weak.")
    if errors:
        print(f"\n  Skipped {len(errors)} tickers (data unavailable)")

    # Save JSON
    output = {
        "scan_date":     TODAY,
        "universe_size": total,
        "setups_found":  len(results),
        "portfolio_inr": portfolio_inr,
        "scan_time_sec": elapsed,
        "results":       results,
        "errors":        errors,
    }
    json_path = os.path.join(OUTPUT_DIR, "scan_results.json")
    with open(json_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  ✓ scan_results.json saved")
    print(f"  ✓ Open dashboard.html in Chrome")
    print(f"  ✓ Run notify.py to send email + Telegram\n")
    return output


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SwingAI NSE Screener — Nifty 500")
    parser.add_argument("--portfolio", type=int, default=1_000_000)
    parser.add_argument("--workers",   type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--tickers",   type=str, default=None,
                        help="Comma-separated e.g. RELIANCE.NS,TCS.NS")
    args = parser.parse_args()

    custom = [t.strip() for t in args.tickers.split(",") if t.strip()] \
             if args.tickers else None

    run_screener(tickers=custom, portfolio_inr=args.portfolio, workers=args.workers)
