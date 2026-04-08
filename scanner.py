"""
GAURAV'S TRADING SYSTEM — MARKET SCANNER v8
- 100% yfinance: LTP + Historical data
- Zero tokens, zero expiry, works forever
- NSE universe: Nifty 500 constituents
- Minervini SEPA criteria + VCP detection
"""

import yfinance as yf
import time, datetime, os, sys
from pathlib import Path

CAPITAL  = 5_000_000
RISK_PCT = 0.01
MIN_PRICE = 50.0
MAX_STOCKS = 500

# ── NSE UNIVERSE ─────────────────────────────────────────
# Nifty 500 symbols - comprehensive liquid NSE universe
NSE_SYMBOLS = [
    "RELIANCE","TCS","HDFCBANK","BHARTIARTL","ICICIBANK","INFOSYS","SBIN","HINDUNILVR",
    "ITC","LT","KOTAKBANK","AXISBANK","BAJFINANCE","MARUTI","ASIANPAINT","TITAN","SUNPHARMA",
    "ULTRACEMCO","ONGC","NESTLEIND","WIPRO","ADANIENT","POWERGRID","NTPC","TECHM","HCLTECH",
    "BAJAJFINSV","TATAMOTORS","COALINDIA","DIVISLAB","DRREDDY","CIPLA","EICHERMOT","INDUSINDBK",
    "APOLLOHOSP","BPCL","TATACONSUM","GRASIM","HINDALCO","JSWSTEEL","TATASTEEL","VEDL",
    "ADANIPORTS","ADANIGREEN","ADANIPOWER","SIEMENS","ABB","HAVELLS","VOLTAS","WHIRLPOOL",
    "PIDILITIND","BERGEPAINT","KANSAINER","AKZOINDIA","ASTRAL","POLYCAB","CUMMINSIND",
    "THERMAX","BHEL","BEL","HAL","COCHINSHIP","GRSE","MAZDOCK","MIDHANI",
    "BAJAJ-AUTO","HEROMOTOCO","TVSMOTORS","M&M","TVSMOTOR","ESCORTS","ASHOKLEY",
    "MOTHERSON","BOSCHLTD","EXIDEIND","AMARAJABAT","MINDA","SUNDRFC","GABRIEL",
    "HDFCLIFE","SBILIFE","ICICIGI","BAJAJHLDNG","MUTHOOTFIN","CHOLAFIN","SHRIRAMFIN",
    "MANAPPURAM","CREDITACC","UJJIVANSFB","AUBANK","FEDERALBNK","IDFCFIRSTB","BANDHANBNK",
    "RBLBANK","YESBANK","PNB","BANKBARODA","CANBK","UNIONBANK","INDIANB","UCOBANK",
    "MAHABANK","CENTRALBK","IOB","JKBANK","KTKBANK","DCBBANK","KARURVYSYA",
    "HDFCAMC","NIPPONLIFE","ABCAPITAL","IIFL","360ONE","ANGELONE","MCLEODRUSSEL",
    "ZOMATO","NYKAA","PAYTM","POLICYBZR","DELHIVERY","CARTRADE","EASEMYTRIP",
    "INFY","WIPRO","HCLTECH","TECHM","MPHASIS","LTIMINDTREE","COFORGE","PERSISTENT",
    "HEXAWARE","NIITTECH","KPITTECH","TATAELXSI","CYIENT","ZENSAR","RAMSARUP",
    "SUNPHARMA","DRREDDY","CIPLA","DIVISLAB","AUROPHARMA","TORNTPHARM","ALKEM",
    "LUPIN","BIOCON","GLENMARK","IPCA","NATCOPHARM","GRANULES","LAURUSLABS",
    "IPCALAB","AJANTPHARM","SYNGENE","ABBINDIA","PFIZER","GLAXO","SANOFI",
    "ASIANPAINT","BERGER","KANSAINER","NEROLAC","AKZOINDIA","INDIGO","SPICEJET",
    "IRCTC","GMRINFRA","AIAENG","THERMAX","CUMMINSIND","GRINDWELL","SCHAEFFLER",
    "SKF","TIMKEN","FAG","NRB","SUPRAJIT","MINDA","ENDURANCE","BALKRISIND",
    "MRF","APOLLOTYRE","CEAT","GOODYEAR","JKTYRE","TVSSRICHAK",
    "ACC","AMBUJACEM","ULTRACEMCO","DALMIABHA","RAMCOCEM","JKCEMENT","HEIDELBERG",
    "SHREECEM","ORIENTCEM","MANGCITY","PRISM","BIRLATYRES",
    "SAIL","TATASTEEL","JSWSTEEL","HINDALCO","NATIONALUM","VEDL","NMDC",
    "MOIL","GMDC","SANDUMA","WELSPUNIND","TRIDENT","RAYMOND","VARDHMAN",
    "PAGEIND","KALYANKJIL","TITAN","PCJEWELLER","SENCO","RAJESHEXPO",
    "TRENT","ABFRL","SHOPERSTOP","VMART","DMART","BATA","RELAXO","METRO",
    "JUBLFOOD","WESTLIFE","DEVYANI","SAPPHIRE","BARBEQUE","BURGERKING",
    "MARICO","DABUR","COLPAL","GODREJCP","EMAMILTD","JYOTHYLAB","VBL",
    "BRITANNIA","NESTLEIND","TATACONSUM","VENKEYS","KRBL","LTFOODS",
    "GODREJAGRO","PIIND","DHANUKA","BAYER","RALLIS","SUMICHEM","INSECTICID",
    "POWERGRID","NTPC","TATAPOWER","ADANIGREEN","CESC","TORNTPOWER","JSWENERGY",
    "GREENKO","RPOWER","JPPOWER","INDIGRID","POWERMECH",
    "DLF","GODREJPROP","OBEROIRLTY","PRESTIGE","BRIGADE","SOBHA","MAHLIFE",
    "PHOENIXLTD","KOLTEPATIL","SUNTECK","PURAVANK","LODHA","MACROTECH",
    "IRFC","RECLTD","PFC","HUDCO","NHAI","INDIGRID","PGHH","GILLETTE",
    "HONAUT","3MINDIA","ASTRAZEN","NOVARTIS","MERCK",
    "ZYDUSLIFE","WOCKPHARMA","STRIDES","SOLARA","LALPATHLAB","METROPOLIS",
    "HINDPETRO","BPCL","IOC","CASTROLIND","AEGISLOG","GAIL","PETRONET",
    "GSPL","MGL","IGL","ATGL","GUJGASLTD",
    "NAUKRI","JUSTDIAL","MATRIMONY","AFFLE","INDIAMART","MOENGAGE",
    "ZEEL","SUNTVTV","NETWORK18","TVTODAY","JAGRAN","DBCORP",
    "CHOLAFIN","BAJFINANCE","BAJAJFINSV","HDFCAMC","ICICIGI","SBICARD",
    "LTFH","POONAWALLA","APTUS","HOMEFIRST","AAVAS","CANFINHOME",
    "LICI","GICRE","NIACL","STARHEALTH","MAXHEALTH",
    "CONCOR","BLUEDART","GATI","MAHINDLOG","TCI","VRL","ALLCARGO",
    "ADANIPORTS","GPPL","ESABINDIA","COCHINSHIP","SCI",
    "WIPRO","MPHASIS","HEXAWARE","MASTEK","OFSS","INFOEDGE",
    "TATACOMM","RAILTEL","BSNL","HFCL","STLTECH","TEJAS",
    "DRREDDY","SUNPHARMA","BIOCON","SEQUENT","GLAND","PIRAMAL",
    "EQUITASBNK","SURYODAY","ESAFSFB","NORTHEASTSB",
    "FACT","CHAMBAL","GSFC","COROMANDEL","NFL","RCF","GNFC",
    "DEEPAKNTR","AARTI","VINATI","CLEAN","TATACHEM","GHCL",
    "NAVINFLUOR","FLUOROCHEM","SRF","ATUL","NOCIL","PCBL",
    "BALRAMCHIN","TRIVENI","DWARIKESH","RENUKA","EID",
    "MCDOWELL-N","RADICO","GLOBUSMED","UNITDSPR",
    "VGUARD","ORIENTELEC","CROMPTON","BLUESTARCO","SYMPHONY","AMBER",
    "BATAINDIA","VIPIND","SAFARI","SKFINDIA","NCC","HCC","KNR",
    "PNCINFRA","AHLUWALIA","JKIL","ITD","WELCORP","RATNAMANI",
    "MAHSEAMLES","HLEGLAS","FINOLEX","KPIL","GPPL","JYOTI",
    "TRIL","INOX","PVR","SAREGAMA","TIPS","SHEMAROO",
    "ASTERDM","NHPC","SJVN","NBCC","ENGINERSIN","RITES","IRCON",
    "CAPACITE","PSPPROJECT","DILIPBUILDCON","GAYAPROJ",
    "TANLA","ONMOBILE","LATENTVIEW","HAPPYMINDS","INTELLECT",
    "ROUTE","GOCOLORS","CAMS","CDSL","BSE","MCX",
]

# Remove duplicates
NSE_SYMBOLS = list(dict.fromkeys(NSE_SYMBOLS))

def sma(v, n):
    if len(v) < n: return None
    return sum(v[-n:]) / n

def pchg(v, n):
    if len(v) < n + 1: return None
    b = v[-(n+1)]
    return ((v[-1] - b) / b * 100) if b else None

def analyse(sym, h, ltp=None):
    if h is None or h.empty: return None
    try:
        c  = list(h["Close"].dropna())
        hh = list(h["High"].dropna())
        lo = list(h["Low"].dropna())
        v  = list(h["Volume"].dropna())
    except: return None
    if len(c) < 200: return None

    cmp    = float(ltp) if ltp else float(c[-1])
    if cmp < MIN_PRICE: return None

    s50    = sma(c, 50); s150 = sma(c, 150); s200 = sma(c, 200)
    s200p  = sma(c[:-30], 200) if len(c) >= 230 else None
    hi52   = max(hh[-252:]) if len(hh) >= 252 else max(hh)
    lo52   = min(lo[-252:]) if len(lo) >= 252 else min(lo)
    hi30   = max(hh[-30:])  if len(hh) >= 30  else max(hh)
    lo30   = min(lo[-30:])  if len(lo) >= 30  else min(lo)
    hi60   = max(hh[-60:])  if len(hh) >= 60  else max(hh)
    lo60   = min(lo[-60:])  if len(lo) >= 60  else min(lo)
    v30    = sum(v[-30:]) / 30 if len(v) >= 30 else None
    v63    = sum(v[-63:]) / 63 if len(v) >= 63 else None
    r3m    = pchg(c, 63)

    tt = [False] * 8
    if s200:
        tt[0] = cmp > s200
        tt[1] = (s200 > s200p) if s200p else False
        if s150:           tt[2] = s150 > s200
        if s50 and s150:   tt[3] = s50 > s150 and s50 > s200
        if s50:            tt[4] = cmp > s50
        if lo52:           tt[5] = cmp >= lo52 * 1.25
        if hi52:           tt[6] = cmp >= hi52 * 0.75
        tt[7] = (r3m or 0) > 5

    if not tt[0]: return None
    tts = sum(tt)

    rng30  = ((hi30 - lo30) / lo30 * 100) if lo30 else None
    rng60  = ((hi60 - lo60) / lo60 * 100) if lo60 else None
    r30f   = rng30 is not None and rng30 < 10
    r60f   = rng60 is not None and rng60 < 20
    vcp    = r30f and r60f
    rs_f   = (r3m or 0) - 5
    vq     = (v30 / v63 * 100) if (v30 and v63) else None
    d200   = ((cmp - s200) / s200 * 100) if s200 else None
    trisk  = ((cmp - lo30) / cmp * 100) if lo30 else 7.0

    sc = 0
    sc += (tts / 8) * 35
    sc += 22 if rs_f > 0 else 0
    sc += min(vq or 0, 100) / 100 * 18
    if r30f: sc += 7
    if r60f: sc += 7
    sc = min(round(sc), 100)

    if   tts >= 8 and rs_f > 0 and sc >= 78: grade = "A+"
    elif tts >= 7 and rs_f > 0 and sc >= 62: grade = "A"
    elif tts >= 6 and sc >= 46:               grade = "B+"
    else:                                      grade = "B"

    ri     = CAPITAL * RISK_PCT * 0.75
    rps    = cmp * trisk / 100
    shares = int(ri / rps) if rps > 0 else 0
    entry  = round(cmp * 1.005, 2)
    stop_p = round(lo30, 2) if lo30 else round(cmp * 0.93, 2)
    t1     = round(entry + 2 * (entry - stop_p), 2)

    return {"sym": sym, "cmp": round(cmp, 2), "tts": tts, "tt": tt,
            "grade": grade, "score": sc,
            "s50": round(s50 or 0, 2), "s150": round(s150 or 0, 2), "s200": round(s200 or 0, 2),
            "rs": round(rs_f, 2), "r3m": round(r3m or 0, 2),
            "vq": round(vq or 0, 1), "r30f": r30f, "r60f": r60f, "vcp": vcp,
            "d200": round(d200 or 0, 1), "trisk": round(trisk, 1),
            "entry": entry, "stop": stop_p, "t1": t1,
            "shares": shares, "posval": round(shares * cmp)}

def mkt_dir(nh):
    if nh is None or nh.empty or len(nh) < 200:
        return {"regime": "UNKNOWN", "exposure": 75, "cmp": 0,
                "s50": 0, "s150": 0, "s200": 0, "r1m": 0, "r3m": 0,
                "vix": None, "signals": ["Nifty data unavailable"]}
    c   = list(nh["Close"].dropna())
    cmp = c[-1]; s50 = sma(c,50); s150 = sma(c,150); s200 = sma(c,200)
    r1m = pchg(c,21); r3m = pchg(c,63)

    # VIX from yfinance
    try:
        vix_data = yf.download("^INDIAVIX", period="5d", interval="1d",
                                progress=False, auto_adjust=True)
        vix_val  = float(vix_data["Close"].dropna().iloc[-1])
    except:
        vix_val = None

    if s200 and cmp > s200 and s50 and cmp > s50:
        regime   = "BULL-CAUTION" if (vix_val or 0) > 22 else "BULL"
        exposure = 75 if (vix_val or 0) > 22 else 100
    elif s200 and cmp > s200:
        regime = "BULL-WEAK"; exposure = 75
    elif s150 and cmp > s150:
        regime = "TRANSITION"; exposure = 50
    else:
        regime = "BEAR"; exposure = 25

    if (vix_val or 0) > 30: exposure = min(exposure, 25)
    elif (vix_val or 0) > 22: exposure = min(exposure, 50)

    sigs = []
    sigs.append("Price > 50 SMA ✅" if (s50 and cmp > s50) else "Price < 50 SMA ⚠")
    sigs.append("Price > 200 SMA ✅" if (s200 and cmp > s200) else "Price < 200 SMA ❌")
    if r3m: sigs.append(f"Nifty 3M: {r3m:+.1f}%")
    if vix_val: sigs.append(f"India VIX: {vix_val:.1f}")

    return {"regime": regime, "exposure": exposure, "cmp": round(cmp, 2),
            "s50": round(s50 or 0, 2), "s150": round(s150 or 0, 2), "s200": round(s200 or 0, 2),
            "r1m": round(r1m or 0, 2), "r3m": round(r3m or 0, 2),
            "vix": vix_val, "signals": sigs}

def sect_rot():
    sectors = {
        "BANKNIFTY": "^NSEBANK", "NIFTYIT": "^CNXIT", "NIFTYPHARMA": "^CNXPHARMA",
        "NIFTYAUTO": "^CNXAUTO", "NIFTYFMCG": "^CNXFMCG", "NIFTYMETAL": "^CNXMETAL",
        "NIFTYREALTY": "^CNXREALTY", "NIFTYENERGY": "^CNXENERGY",
    }
    result = []
    for label, ticker in sectors.items():
        try:
            h = yf.download(ticker, period="9mo", interval="1d",
                            progress=False, auto_adjust=True)
            if h.empty or len(h) < 30: continue
            c    = list(h["Close"].dropna())
            r1m  = pchg(c, 21); r3m = pchg(c, 63); r6m = pchg(c, 126)
            s200 = sma(c, 200); cmp = c[-1]
            ab200= cmp > s200 if s200 else False
            mom  = (r1m or 0)*0.4 + (r3m or 0)*0.4 + (r6m or 0)*0.2
            tier = "HOT" if mom > 5 and ab200 else "WARM" if mom > 0 else "COLD"
            result.append({"name": label, "r1m": round(r1m or 0, 2),
                           "r3m": round(r3m or 0, 2), "tier": tier, "momentum": round(mom, 2)})
        except: pass
    return sorted(result, key=lambda x: x["momentum"], reverse=True)

def build_html(results, mkt, sectors, scan_time, total):
    results = sorted(results, key=lambda x:x["score"], reverse=True)
    tt7  = sum(1 for r in results if r["tts"]>=7)
    vcp_c= sum(1 for r in results if r["vcp"])
    ap   = sum(1 for r in results if r["grade"]=="A+")
    a_c  = sum(1 for r in results if r["grade"]=="A")
    rc   = {"BULL":"#22c55e","BULL-WEAK":"#86efac","BULL-CAUTION":"#f59e0b",
            "TRANSITION":"#fb923c","BEAR":"#ef4444","UNKNOWN":"#64748b"}
    regc = rc.get(mkt.get("regime","UNKNOWN"),"#64748b")
    sh=""
    for s in sectors[:8]:
        col="#22c55e" if s["tier"]=="HOT" else "#f59e0b" if s["tier"]=="WARM" else "#64748b"
        bg="rgba(34,197,94,.12)" if s["tier"]=="HOT" else "rgba(245,158,11,.1)" if s["tier"]=="WARM" else "rgba(100,116,139,.1)"
        sh+=f'<div style="background:{bg};border:1px solid {col}33;border-radius:8px;padding:10px 12px"><div style="font-size:10px;color:{col};font-weight:700">{s["tier"]}</div><div style="font-size:13px;font-weight:600;margin:3px 0">{s["name"]}</div><div style="font-family:monospace;font-size:10px;color:#94a3b8">1M:{s["r1m"]:+.1f}% 3M:{s["r3m"]:+.1f}%</div></div>'
    rows=""
    for i,s in enumerate(results):
        rk=i+1
        rnc="color:#f59e0b" if rk==1 else "color:#94a3b8" if rk<=3 else "color:#64748b"
        dots="".join(f'<span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:{"#22c55e" if s["tt"][d] else "#1e293b"};margin-right:2px"></span>' for d in range(8))
        sc=s["score"]; scc="#22c55e" if sc>=75 else "#f59e0b" if sc>=50 else "#64748b"
        grc={"A+":"#4ade80","A":"#22c55e","B+":"#f59e0b","B":"#64748b"}.get(s["grade"],"#64748b")
        grb={"A+":"rgba(34,197,94,.2)","A":"rgba(34,197,94,.12)","B+":"rgba(245,158,11,.15)","B":"rgba(100,116,139,.1)"}.get(s["grade"],"rgba(100,116,139,.1)")
        r3c="#22c55e" if s["r3m"]>0 else "#ef4444"
        rsc="#22c55e" if s["rs"]>0  else "#ef4444"
        d2c="#22d3ee" if s["d200"]>0 else "#94a3b8"
        vcp='<span style="background:rgba(34,197,94,.15);color:#22c55e;padding:2px 6px;border-radius:3px;font-size:9px;font-weight:700">VCP</span>' if s["vcp"] else "—"
        rows+=f'<tr style="border-bottom:1px solid rgba(255,255,255,.05)"><td style="padding:7px 8px;font-family:monospace;font-size:10px;{rnc}">{rk}</td><td style="padding:7px 8px;font-weight:700;font-size:12px">{s["sym"]}</td><td style="padding:7px 8px;font-family:monospace;font-size:11px">Rs.{s["cmp"]:,.1f}</td><td style="padding:7px 8px">{dots}<div style="font-family:monospace;font-size:9px;color:#64748b">{s["tts"]}/8</div></td><td style="padding:7px 8px;font-family:monospace;font-weight:600;color:{scc}">{sc}</td><td style="padding:7px 8px"><span style="background:{grb};color:{grc};padding:2px 8px;border-radius:3px;font-size:10px;font-weight:700">{s["grade"]}</span></td><td style="padding:7px 8px;font-family:monospace;font-size:11px;color:{rsc}">{s["rs"]:+.2f}</td><td style="padding:7px 8px;font-family:monospace;font-size:11px;color:{r3c}">{s["r3m"]:+.1f}%</td><td style="padding:7px 8px;font-family:monospace;font-size:11px">{s["vq"]:.0f}%</td><td style="padding:7px 8px">{vcp}</td><td style="padding:7px 8px;font-family:monospace;font-size:11px;color:#94a3b8">{s["trisk"]:.1f}%</td><td style="padding:7px 8px;font-family:monospace;font-size:11px;color:{d2c}">{s["d200"]:+.1f}%</td><td style="padding:7px 8px;font-family:monospace;font-size:11px;color:#22c55e">Rs.{s["entry"]:,.2f}</td><td style="padding:7px 8px;font-family:monospace;font-size:11px;color:#ef4444">Rs.{s["stop"]:,.2f}</td><td style="padding:7px 8px;font-family:monospace;font-size:11px;color:#f59e0b">Rs.{s["t1"]:,.2f}</td><td style="padding:7px 8px;font-family:monospace;font-size:10px">Rs.{s["posval"]:,.0f}</td></tr>'
    sigs="".join(f'<div style="font-size:11px;color:#94a3b8;margin-bottom:3px">{sg}</div>' for sg in mkt.get("signals",[]))
    eff=round(CAPITAL*mkt.get("exposure",75)/100/100000,1)
    r1m=mkt.get("r1m",0) or 0; r3m=mkt.get("r3m",0) or 0
    r1c="#22c55e" if r1m>0 else "#ef4444"; r3c2="#22c55e" if r3m>0 else "#ef4444"
    stats=[(total,"Universe","#e2e8f0"),(len(results),"Qualified","#e2e8f0"),
           (tt7,"TT 7-8","#22c55e"),(ap,"A+ Grade","#a78bfa"),(a_c,"A Grade","#3b82f6"),(vcp_c,"VCP","#f59e0b")]
    sthtml="".join(f'<div style="padding:12px 14px;border-right:1px solid rgba(255,255,255,.07)"><div style="font-family:monospace;font-size:18px;font-weight:600;color:{c}">{v}</div><div style="font-size:9px;color:#64748b;margin-top:2px;text-transform:uppercase;letter-spacing:.05em">{l}</div></div>' for v,l,c in stats)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Gaurav's Trading Dashboard - {scan_time}</title>
<style>@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0a0e1a;color:#e2e8f0;font-family:'IBM Plex Sans',sans-serif;font-size:13px}}
.tw{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{background:#0f1525;color:#64748b;font-size:9px;text-transform:uppercase;letter-spacing:.07em;padding:8px;text-align:left;border-bottom:1px solid rgba(255,255,255,.1);white-space:nowrap;position:sticky;top:0;z-index:5}}
tr:hover td{{background:rgba(255,255,255,.03)}}</style></head><body>
<div style="background:#0f1525;border-bottom:1px solid rgba(255,255,255,.07);padding:14px 20px;display:flex;justify-content:space-between;align-items:center">
  <div style="display:flex;align-items:center;gap:12px">
    <div style="width:36px;height:36px;border-radius:8px;background:rgba(34,197,94,.12);border:1px solid #22c55e;display:flex;align-items:center;justify-content:center;font-family:monospace;font-size:12px;color:#22c55e;font-weight:700">GT</div>
    <div><div style="font-size:15px;font-weight:600">Gaurav's Trading System</div>
    <div style="font-size:9px;color:#64748b;font-family:monospace;margin-top:2px">NSE UNIVERSE · MINERVINI SEPA · YFINANCE · {scan_time}</div></div>
  </div>
  <div style="font-family:monospace;font-size:10px;color:#64748b">Rs.{CAPITAL//100000}L Capital · 1% Risk · Auto 4:30 PM IST</div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1px;background:rgba(255,255,255,.07);border-bottom:1px solid rgba(255,255,255,.07)">
  <div style="background:#0a0e1a;padding:18px 20px">
    <div style="font-size:9px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:8px">Market Regime</div>
    <div style="font-size:26px;font-weight:700;color:{regc};margin-bottom:4px">{mkt.get("regime","—")}</div>
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
      <span style="font-size:11px;color:#94a3b8">Deploy:</span>
      <span style="font-size:16px;font-weight:700;color:{regc}">{mkt.get("exposure",75)}%</span>
      <span style="font-size:11px;color:#64748b">= Rs.{eff}L active</span>
    </div>{sigs}
  </div>
  <div style="background:#0a0e1a;padding:18px 20px">
    <div style="font-size:9px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">Nifty 50 Levels</div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
      <div><div style="font-size:9px;color:#64748b">CMP</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px">{mkt.get("cmp","—")}</div></div>
      <div><div style="font-size:9px;color:#64748b">50 SMA</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px">{mkt.get("s50","—")}</div></div>
      <div><div style="font-size:9px;color:#64748b">200 SMA</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px">{mkt.get("s200","—")}</div></div>
      <div><div style="font-size:9px;color:#64748b">1M Ret</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px;color:{r1c}">{r1m:+.1f}%</div></div>
      <div><div style="font-size:9px;color:#64748b">3M Ret</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px;color:{r3c2}">{r3m:+.1f}%</div></div>
      <div><div style="font-size:9px;color:#64748b">VIX</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px">Live</div></div>
    </div>
  </div>
</div>
<div style="display:grid;grid-template-columns:repeat(6,1fr);border-bottom:1px solid rgba(255,255,255,.07)">{sthtml}</div>
<div style="padding:14px 20px;border-bottom:1px solid rgba(255,255,255,.07)">
  <div style="font-size:9px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">Sectoral Rotation</div>
  <div style="display:grid;grid-template-columns:repeat(8,1fr);gap:6px">{sh}</div>
</div>
<div class="tw"><table><thead><tr>
  <th>#</th><th>Symbol</th><th>CMP</th><th>TT Score</th><th>Score</th><th>Grade</th>
  <th>RS Filter</th><th>3M Ret</th><th>Vol Qual</th><th>VCP</th>
  <th>Trade Risk</th><th>Dist 200</th><th>Entry</th><th>Stop</th><th>T1 (2R)</th><th>Pos Size</th>
</tr></thead><tbody>{rows}</tbody></table></div>
<div style="padding:8px 20px;border-top:1px solid rgba(255,255,255,.07);display:flex;justify-content:space-between;font-size:9px;color:#64748b;font-family:monospace;background:#0f1525">
  <span>yfinance · NSE Universe · EOD · Minervini SEPA · No token required · Auto-runs daily</span>
  <span>Not financial advice · {scan_time}</span>
</div></body></html>"""


def main():
    print("="*60)
    print("  GAURAV'S TRADING SYSTEM v8 — 100% yfinance")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M IST')}")
    print("="*60)

    # ── Market direction (Nifty 50) ──
    print("\n[1/3] Fetching Nifty 50 & sector data...")
    nh = yf.download("^NSEI", period="14mo", interval="1d",
                     progress=False, auto_adjust=True)
    mkt     = mkt_dir(nh)
    sectors = sect_rot()
    print(f"  Regime: {mkt['regime']} | Exposure: {mkt['exposure']}%")

    # ── Batch download: LTP + history in ONE call per batch ──
    print(f"\n[2/3] Downloading price history for {len(NSE_SYMBOLS)} stocks...")
    yf_syms  = [s + ".NS" for s in NSE_SYMBOLS]
    results  = []
    BATCH    = 100

    for i in range(0, len(yf_syms), BATCH):
        batch_yf  = yf_syms[i:i+BATCH]
        batch_sym = NSE_SYMBOLS[i:i+BATCH]
        try:
            raw = yf.download(
                batch_yf,
                period="15mo",
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=True
            )
            for yf_sym, sym in zip(batch_yf, batch_sym):
                try:
                    if len(batch_yf) == 1:
                        h = raw
                    else:
                        h = raw[yf_sym]
                    h = h.dropna(how="all")
                    if len(h) < 200: continue
                    ltp = float(h["Close"].iloc[-1])
                    r   = analyse(sym, h, ltp)
                    if r: results.append(r)
                except: pass
        except Exception as e:
            print(f"  Batch {i//BATCH+1} error: {e}")
        pct = min((i + BATCH), len(yf_syms)) / len(yf_syms) * 100
        print(f"  Batch {i//BATCH+1}/{(len(yf_syms)+BATCH-1)//BATCH} done | Qualified so far: {len(results)} | {pct:.0f}%")
        time.sleep(1)

    scan_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M IST")
    print(f"\n{'='*60}")
    print(f"  COMPLETE · Qualified: {len(results)}")
    print(f"  TT 7-8: {sum(1 for r in results if r['tts']>=7)}")
    print(f"  A+: {sum(1 for r in results if r['grade']=='A+')}")
    print(f"  VCP: {sum(1 for r in results if r['vcp'])}")
    if results:
        top5 = sorted(results, key=lambda x: x["score"], reverse=True)[:5]
        print("\n  TOP 5:")
        for i, s in enumerate(top5):
            print(f"  {i+1}. {s['sym']:<14} Score:{s['score']} {s['grade']} TT:{s['tts']}/8 ₹{s['cmp']:,.0f}")

    html = build_html(results, mkt, sectors, scan_time,
                      len(NSE_SYMBOLS), len(results), len(NSE_SYMBOLS))
    out  = Path("docs/index.html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"\n  Dashboard → docs/index.html")
    print("="*60)

if __name__ == "__main__":
    main()
