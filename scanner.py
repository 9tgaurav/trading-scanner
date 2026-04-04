"""
GAURAV'S TRADING SYSTEM — AUTOMATED MARKET SCANNER
Dhan API + Minervini SEPA + Market Direction + Sector Rotation
Runs daily via GitHub Actions at 4:30 PM IST
"""

import requests, json, time, datetime, os, sys
from pathlib import Path

# ── CREDENTIALS (loaded from GitHub Secrets) ──────────────
CLIENT_ID    = os.environ.get("DHAN_CLIENT_ID",    "1100847090")
ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN", "")

CAPITAL      = 5_000_000   # ₹50 Lakhs
RISK_PCT     = 0.01        # 1% per trade

BASE    = "https://api.dhan.co/v2"
HEADERS = {
    "Content-Type": "application/json",
    "access-token": ACCESS_TOKEN,
    "client-id":    CLIENT_ID,
}

# ── NIFTY 500 — Top 150 liquid stocks ─────────────────────
STOCKS = {
    "RELIANCE":"2885","TCS":"11536","HDFCBANK":"1333","INFY":"1594",
    "ICICIBANK":"4963","HINDUNILVR":"1394","SBIN":"3045","BAJFINANCE":"317",
    "BHARTIARTL":"10604","KOTAKBANK":"1922","WIPRO":"3787","AXISBANK":"5900",
    "ASIANPAINT":"236","MARUTI":"10999","TITAN":"3506","SUNPHARMA":"3351",
    "HCLTECH":"1348","ULTRACEMCO":"11532","BAJAJFINSV":"16675","NESTLEIND":"17963",
    "POWERGRID":"14977","NTPC":"11630","ONGC":"2475","JSWSTEEL":"11723",
    "COALINDIA":"20374","M&M":"2031","TATASTEEL":"3499","ADANIENT":"25",
    "ADANIPORTS":"15083","LTIM":"17818","TECHM":"13538","CIPLA":"694",
    "DRREDDY":"881","EICHERMOT":"910","BRITANNIA":"547","DIVISLAB":"10243",
    "APOLLOHOSP":"157","HINDALCO":"1363","GRASIM":"1108","SBILIFE":"21808",
    "HDFCLIFE":"119","LT":"11483","TATACONSUM":"3460","ITC":"1660",
    "BPCL":"526","IOC":"1624","HINDPETRO":"1406","VEDL":"3063",
    "TATAMOTORS":"3456","TRENT":"3519","PIDILITIND":"2252","SIEMENS":"3150",
    "GODREJCP":"10099","HAVELLS":"430","DABUR":"772","MARICO":"4067",
    "COLPAL":"732","ABB":"13","BOSCHLTD":"500","CUMMINSIND":"771",
    "MUTHOOTFIN":"3900","CHOLAFIN":"685","AUROPHARMA":"275","TORNTPHARM":"3518",
    "LUPIN":"10440","ALKEM":"13751","GLENMARK":"1068","BIOCON":"3436",
    "ZYDUSLIFE":"10940","IPCALAB":"1635","RECLTD":"2883","PFC":"14299",
    "CANBK":"10794","UNIONBANK":"10957","BANKBARODA":"1452","PNB":"2730",
    "FEDERALBNK":"1023","IDFCFIRSTB":"12086","BANDHANBNK":"541",
    "MOTHERSON":"4204","BALKRISIND":"335","APOLLOTYRE":"157","MRF":"2277",
    "EXIDEIND":"951","TATACHEM":"3443","UPL":"11287","PIIND":"2255",
    "COROMANDEL":"752","GSPL":"21263","AAVAS":"19061","LICHSGFIN":"1975",
    "IRFC":"20286","TATAPOWER":"3426","ADANIGREEN":"11931","JSWENERGY":"20650",
    "SUZLON":"3347","POLYCAB":"20793","KEI":"1750","FINOLEX":"1030",
    "CONCOR":"740","HFCL":"1372","TATAELXSI":"3453","PERSISTENT":"2171",
    "MPHASIS":"2225","COFORGE":"20785","LTTS":"18365","KPIT":"20812",
    "CYIENT":"771","BIRLASOFT":"20814","TANLA":"3449","ROUTE":"21145",
    "INDIAMART":"21023","CAMS":"20820","CDSL":"20771","MCX":"14307",
    "ANGELONE":"20871","DIXON":"20750","AMBER":"20704","VGUARD":"17015",
    "CROMPTON":"17094","VOLTAS":"3681","BLUESTAR":"499","WHIRLPOOL":"3787",
    "GODREJPROP":"10100","OBEROIRLTY":"14364","DLF":"1346","PRESTIGE":"2286",
    "SOBHA":"3229","PHOENIXLTD":"2274","SUNTV":"3344","TV18BRDCST":"3561",
    "PVRINOX":"20286","ZOMATO":"21296","NYKAA":"543384","DELHIVERY":"543529",
    "IRCTC":"20286","HAL":"20266","BEL":"383","BHEL":"438",
    "ESCORTS":"930","TITAGARH":"3507","RITES":"20286","GRSE":"20286",
    "TATACHEM":"3443","GNFC":"1073","CHAMBLFERT":"670","DEEPAKNTR":"11038",
    "ATUL":"210","NAVINFLUOR":"2189","ALKYLAMINE":"13726","CLEAN":"21371",
    "FINEORG":"21013","NOCIL":"2165","VINATI":"3741","AARTI":"21014",
    "PAGEIND":"14413","MCDOWELL-N":"16990","RADICO":"2872","GLOBUSSPR":"1090",
    "LUXIND":"1992","TRENT":"3519","SHOPERSTOP":"3203","CAMPUS":"543294",
    "MATRIMONY":"20752","KAYNES":"543278","SYRMA":"543573","AVALON":"543526",
}

# ── INDICES (NSE_INDICES segment) ─────────────────────────
# Security IDs for major indices via Dhan
INDICES = {
    "NIFTY50":   {"id": "13",    "seg": "IDX_I"},
    "BANKNIFTY": {"id": "25",    "seg": "IDX_I"},
    "NIFTYIT":   {"id": "11",    "seg": "IDX_I"},
    "NIFTYPHARMA":{"id":"10",   "seg": "IDX_I"},
    "NIFTYAUTO": {"id": "14",   "seg": "IDX_I"},
    "NIFTYFMCG": {"id": "16",   "seg": "IDX_I"},
    "NIFTYMETAL": {"id":"17",   "seg": "IDX_I"},
    "NIFTYREALTY":{"id":"12",   "seg": "IDX_I"},
    "NIFTYENERGY":{"id":"15",   "seg": "IDX_I"},
    "INDIAVIX":  {"id": "50",   "seg": "IDX_I"},
}

# ── DHAN API HELPERS ──────────────────────────────────────
def dhan_historical(sec_id, seg="NSE_EQ", days=260):
    to_dt   = datetime.date.today()
    fr_dt   = to_dt - datetime.timedelta(days=days + 60)
    payload = {
        "securityId": sec_id, "exchangeSegment": seg,
        "instrument": "INDEX" if seg == "IDX_I" else "EQUITY",
        "expiryCode": 0, "oi": False,
        "fromDate": fr_dt.strftime("%Y-%m-%d"),
        "toDate":   to_dt.strftime("%Y-%m-%d"),
    }
    try:
        r = requests.post(f"{BASE}/charts/historical",
                          headers=HEADERS, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        pass
    return None

def dhan_ltp_batch(sec_ids):
    """Batch LTP for up to 1000 NSE_EQ instruments."""
    payload = {"NSE_EQ": sec_ids}
    try:
        r = requests.post(f"{BASE}/marketfeed/ltp",
                          headers=HEADERS, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json().get("data", {}).get("NSE_EQ", {})
    except Exception:
        pass
    return {}

# ── CALCULATIONS ──────────────────────────────────────────
def sma(vals, n):
    if len(vals) < n: return None
    return sum(vals[-n:]) / n

def pct_chg(vals, n):
    if len(vals) < n: return None
    return (vals[-1] - vals[-n]) / vals[-n] * 100

def analyse(sym, sid, hist, ltp=None):
    if not hist or "close" not in hist: return None
    c = hist["close"]; h = hist.get("high",[]); lo = hist.get("low",[]); v = hist.get("volume",[])
    if len(c) < 200: return None

    cmp    = ltp if ltp else c[-1]
    s50    = sma(c, 50);  s150 = sma(c, 150); s200 = sma(c, 200)
    s200p  = sma(c[:-30], 200) if len(c) >= 230 else None
    hi52   = max(h[-252:]) if len(h) >= 252 else max(h)
    lo52   = min(lo[-252:]) if len(lo) >= 252 else min(lo)
    hi30   = max(h[-30:])  if len(h) >= 30  else max(h)
    lo30   = min(lo[-30:]) if len(lo) >= 30  else min(lo)
    hi60   = max(h[-60:])  if len(h) >= 60  else max(h)
    lo60   = min(lo[-60:]) if len(lo) >= 60  else min(lo)
    v30    = sum(v[-30:]) / 30 if len(v) >= 30 else None
    v63    = sum(v[-63:]) / 63 if len(v) >= 63 else None
    r3m    = pct_chg(c, 63)

    tt = [False]*8
    if s200:
        tt[0] = cmp > s200
        tt[1] = (s200 > s200p) if s200p else False
        if s150: tt[2] = s150 > s200
        if s50 and s150: tt[3] = s50 > s150 and s50 > s200
        if s50:  tt[4] = cmp > s50
        tt[5] = cmp >= lo52 * 1.25
        tt[6] = cmp >= hi52 * 0.75
        tt[7] = (r3m or 0) > 5

    if not tt[0]: return None  # Hard reject

    tts    = sum(tt)
    rng30  = (hi30 - lo30) / lo30 * 100 if lo30 else None
    rng60  = (hi60 - lo60) / lo60 * 100 if lo60 else None
    r30f   = rng30 is not None and rng30 < 10
    r60f   = rng60 is not None and rng60 < 20
    vcp    = r30f and r60f
    rs_f   = ((r3m or 0) - 5)
    vq     = (v30 / v63 * 100) if (v30 and v63) else None
    d200   = ((cmp - s200) / s200 * 100) if s200 else None
    trisk  = ((cmp - lo30) / cmp * 100) if lo30 else None

    sc = 0
    sc += (tts / 8) * 35
    sc += 22 if rs_f > 0 else 0
    sc += min(vq or 0, 100) / 100 * 18
    if r30f: sc += 7
    if r60f: sc += 7
    sc = min(round(sc), 100)

    rs_pos = rs_f > 0
    if tts >= 8 and rs_pos and sc >= 78:  grade = "A+"
    elif tts >= 7 and rs_pos and sc >= 62: grade = "A"
    elif tts >= 6 and sc >= 46:            grade = "B+"
    else:                                   grade = "B"

    risk_inr = CAPITAL * RISK_PCT * 0.75
    rps      = cmp * (trisk or 7) / 100
    shares   = int(risk_inr / rps) if rps > 0 else 0
    entry    = round(cmp * 1.005, 2)
    stop_p   = round(lo30, 2) if lo30 else round(cmp * 0.93, 2)
    t1       = round(entry + 2 * (entry - stop_p), 2)
    t2       = round(entry + 3 * (entry - stop_p), 2)

    return {
        "sym": sym, "cmp": round(cmp, 2), "tts": tts, "tt": tt,
        "grade": grade, "score": sc, "s50": s50, "s150": s150, "s200": s200,
        "hi52": hi52, "lo52": lo52, "rs": round(rs_f, 2), "r3m": round(r3m or 0, 2),
        "vq": round(vq or 0, 1), "rng30": round(rng30 or 0, 1), "rng60": round(rng60 or 0, 1),
        "r30f": r30f, "r60f": r60f, "vcp": vcp, "d200": round(d200 or 0, 1),
        "trisk": round(trisk or 0, 1), "entry": entry, "stop": stop_p,
        "t1": t1, "t2": t2, "shares": shares, "posval": round(shares * cmp),
    }

# ── MARKET DIRECTION ─────────────────────────────────────
def market_direction(nifty_hist, vix_val=None):
    if not nifty_hist or "close" not in nifty_hist:
        return {"regime": "UNKNOWN", "exposure": 75, "signal": "No index data"}
    c    = nifty_hist["close"]
    if len(c) < 200:
        return {"regime": "INSUFFICIENT DATA", "exposure": 75, "signal": "Need more data"}

    cmp  = c[-1]
    s50  = sma(c, 50)
    s150 = sma(c, 150)
    s200 = sma(c, 200)
    r1m  = pct_chg(c, 21)
    r3m  = pct_chg(c, 63)

    # Count stocks above 200 SMA (breadth) — approximated from index position
    breadth_ok = cmp > s200 if s200 else False

    if s200 and cmp > s200 and s50 and cmp > s50:
        if (vix_val or 0) > 25:
            regime = "BULL-CAUTION"; exposure = 75
        else:
            regime = "BULL"; exposure = 100
    elif s200 and cmp > s200:
        regime = "BULL-WEAK"; exposure = 75
    elif s150 and cmp > s150:
        regime = "TRANSITION"; exposure = 50
    else:
        regime = "BEAR"; exposure = 25

    # VIX overlay
    if vix_val:
        if vix_val > 30:   exposure = min(exposure, 25)
        elif vix_val > 22: exposure = min(exposure, 50)
        elif vix_val > 17: exposure = min(exposure, 75)

    signals = []
    if s50  and cmp > s50:  signals.append("Price > 50 SMA ✅")
    else:                    signals.append("Price < 50 SMA ⚠")
    if s200 and cmp > s200: signals.append("Price > 200 SMA ✅")
    else:                    signals.append("Price < 200 SMA ❌")
    if r3m is not None:      signals.append(f"3M return: {r3m:+.1f}%")
    if vix_val:              signals.append(f"VIX: {vix_val:.1f}")

    return {
        "regime": regime, "exposure": exposure,
        "cmp": round(cmp, 2), "s50": round(s50 or 0, 2),
        "s150": round(s150 or 0, 2), "s200": round(s200 or 0, 2),
        "r1m": round(r1m or 0, 2), "r3m": round(r3m or 0, 2),
        "vix": vix_val, "signals": signals,
    }

# ── SECTOR ROTATION ───────────────────────────────────────
def sector_rotation(idx_data):
    sectors = []
    for name, hist in idx_data.items():
        if name == "INDIAVIX" or not hist or "close" not in hist: continue
        c    = hist["close"]
        r1m  = pct_chg(c, 21)
        r3m  = pct_chg(c, 63)
        r6m  = pct_chg(c, 126)
        s200 = sma(c, 200)
        cmp  = c[-1]
        above200 = cmp > s200 if s200 else False
        momentum = (r1m or 0) * 0.4 + (r3m or 0) * 0.4 + (r6m or 0) * 0.2
        tier = "HOT" if momentum > 5 and above200 else "WARM" if momentum > 0 else "COLD"
        sectors.append({
            "name": name.replace("NIFTY","").replace("50","").strip(),
            "cmp": round(cmp, 2), "r1m": round(r1m or 0, 2),
            "r3m": round(r3m or 0, 2), "r6m": round(r6m or 0, 2),
            "above200": above200, "momentum": round(momentum, 2), "tier": tier,
        })
    return sorted(sectors, key=lambda x: x["momentum"], reverse=True)

# ── HTML GENERATOR ────────────────────────────────────────
def build_html(results, mkt, sectors, scan_time, total):
    results = sorted(results, key=lambda x: x["score"], reverse=True)
    tt7  = sum(1 for r in results if r["tts"] >= 7)
    vcp  = sum(1 for r in results if r["vcp"])
    ap   = sum(1 for r in results if r["grade"] == "A+")

    regime_color = {
        "BULL": "#22c55e", "BULL-WEAK": "#86efac",
        "BULL-CAUTION": "#f59e0b", "TRANSITION": "#fb923c",
        "BEAR": "#ef4444", "UNKNOWN": "#64748b"
    }.get(mkt.get("regime", "UNKNOWN"), "#64748b")

    sector_html = ""
    for s in sectors[:9]:
        col = "#22c55e" if s["tier"]=="HOT" else "#f59e0b" if s["tier"]=="WARM" else "#64748b"
        bg  = "rgba(34,197,94,.12)" if s["tier"]=="HOT" else "rgba(245,158,11,.1)" if s["tier"]=="WARM" else "rgba(100,116,139,.1)"
        sector_html += f"""<div style="background:{bg};border:1px solid {col}33;border-radius:8px;padding:12px 14px">
          <div style="font-size:11px;color:{col};font-weight:600;letter-spacing:.05em">{s['tier']}</div>
          <div style="font-size:14px;font-weight:600;margin:4px 0">{s['name']}</div>
          <div style="font-family:monospace;font-size:11px;color:#94a3b8">1M: {s['r1m']:+.1f}% · 3M: {s['r3m']:+.1f}%</div>
        </div>"""

    rows = ""
    for i, s in enumerate(results):
        rk   = i + 1
        dots = "".join(f'<span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:{"#22c55e" if s["tt"][d] else "#1e293b"};margin-right:2px"></span>' for d in range(8))
        sc   = s["score"]
        sc_c = "#22c55e" if sc>=75 else "#f59e0b" if sc>=50 else "#64748b"
        gr_c = {"A+":"#4ade80","A":"#22c55e","B+":"#f59e0b","B":"#64748b"}.get(s["grade"],"#64748b")
        gr_bg= {"A+":"rgba(34,197,94,.2)","A":"rgba(34,197,94,.12)","B+":"rgba(245,158,11,.15)","B":"rgba(100,116,139,.1)"}.get(s["grade"],"rgba(100,116,139,.1)")
        r3c  = "#22c55e" if s["r3m"]>0 else "#ef4444"
        rsc  = "#22c55e" if s["rs"]>0 else "#ef4444"
        d2c  = "#22d3ee" if s["d200"]>0 else "#94a3b8"
        vcp_h= '<span style="background:rgba(34,197,94,.15);color:#22c55e;padding:2px 6px;border-radius:3px;font-size:9px;font-weight:700;border:1px solid rgba(34,197,94,.3)">VCP</span>' if s["vcp"] else "—"
        rows += f"""<tr style="border-bottom:1px solid rgba(255,255,255,.06)">
          <td style="padding:8px 10px;font-family:monospace;color:#64748b;font-size:11px">{rk}</td>
          <td style="padding:8px 10px;font-weight:700;font-size:13px">{s['sym']}</td>
          <td style="padding:8px 10px;font-family:monospace">₹{s['cmp']:,.1f}</td>
          <td style="padding:8px 10px">{dots}<div style="font-family:monospace;font-size:9px;color:#64748b;margin-top:2px">{s['tts']}/8</div></td>
          <td style="padding:8px 10px"><span style="background:rgba(255,255,255,.06);color:{sc_c};padding:2px 8px;border-radius:3px;font-family:monospace;font-weight:600">{sc}</span></td>
          <td style="padding:8px 10px"><span style="background:{gr_bg};color:{gr_c};padding:3px 9px;border-radius:4px;font-size:11px;font-weight:700">{s['grade']}</span></td>
          <td style="padding:8px 10px;font-family:monospace;color:{rsc}">{s['rs']:+.2f}</td>
          <td style="padding:8px 10px;font-family:monospace;color:{r3c}">{s['r3m']:+.1f}%</td>
          <td style="padding:8px 10px;font-family:monospace">{s['vq']:.0f}%</td>
          <td style="padding:8px 10px">{vcp_h}</td>
          <td style="padding:8px 10px;font-family:monospace;color:#94a3b8">{s['trisk']:.1f}%</td>
          <td style="padding:8px 10px;font-family:monospace;color:{d2c}">{s['d200']:+.1f}%</td>
          <td style="padding:8px 10px;font-family:monospace;color:#22c55e">₹{s['entry']:,.2f}</td>
          <td style="padding:8px 10px;font-family:monospace;color:#ef4444">₹{s['stop']:,.2f}</td>
          <td style="padding:8px 10px;font-family:monospace;color:#f59e0b">₹{s['t1']:,.2f}</td>
          <td style="padding:8px 10px;font-family:monospace;font-size:11px">₹{s['posval']:,.0f}</td>
        </tr>"""

    signals_html = "".join(f'<div style="font-size:11px;color:#94a3b8;margin-bottom:3px">{sg}</div>' for sg in mkt.get("signals", []))
    eff_capital  = round(CAPITAL * mkt.get("exposure", 75) / 100 / 100000, 1)

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gaurav's Trading Dashboard — {scan_time}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0e1a;color:#e2e8f0;font-family:'IBM Plex Sans',sans-serif;font-size:13px}}
.tw{{overflow-x:auto}} table{{width:100%;border-collapse:collapse}}
th{{background:#0f1525;color:#64748b;font-size:9px;text-transform:uppercase;letter-spacing:.07em;padding:8px 10px;text-align:left;border-bottom:1px solid rgba(255,255,255,.1);white-space:nowrap;position:sticky;top:0;z-index:5}}
tr:hover td{{background:rgba(255,255,255,.03)}}
</style></head><body>

<div style="background:#0f1525;border-bottom:1px solid rgba(255,255,255,.07);padding:16px 24px;display:flex;justify-content:space-between;align-items:center">
  <div style="display:flex;align-items:center;gap:14px">
    <div style="width:38px;height:38px;border-radius:9px;background:rgba(34,197,94,.12);border:1px solid #22c55e;display:flex;align-items:center;justify-content:center;font-family:monospace;font-size:13px;color:#22c55e;font-weight:600">GT</div>
    <div>
      <div style="font-size:16px;font-weight:600">Gaurav's Trading System</div>
      <div style="font-size:10px;color:#64748b;font-family:monospace;margin-top:2px;letter-spacing:.04em">NIFTY 500 · MINERVINI SEPA · DHAN API · {scan_time}</div>
    </div>
  </div>
  <div style="font-family:monospace;font-size:11px;color:#64748b">Capital ₹{CAPITAL//100000}L · Risk 1%</div>
</div>

<!-- MARKET DIRECTION -->
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1px;background:rgba(255,255,255,.07);border-bottom:1px solid rgba(255,255,255,.07)">
  <div style="background:#0a0e1a;padding:20px 24px">
    <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">Market regime</div>
    <div style="font-size:28px;font-weight:700;color:{regime_color};margin-bottom:6px">{mkt.get('regime','—')}</div>
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
      <span style="font-size:12px;color:#94a3b8">Deploy capital:</span>
      <span style="font-size:18px;font-weight:700;color:{regime_color}">{mkt.get('exposure',75)}%</span>
      <span style="font-size:12px;color:#64748b">= ₹{eff_capital}L active</span>
    </div>
    {signals_html}
  </div>
  <div style="background:#0a0e1a;padding:20px 24px">
    <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">Nifty 50 levels</div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
      <div><div style="font-size:10px;color:#64748b">CMP</div><div style="font-family:monospace;font-size:15px;font-weight:600;margin-top:3px">{mkt.get('cmp','—')}</div></div>
      <div><div style="font-size:10px;color:#64748b">50 SMA</div><div style="font-family:monospace;font-size:15px;font-weight:600;margin-top:3px">{mkt.get('s50','—')}</div></div>
      <div><div style="font-size:10px;color:#64748b">200 SMA</div><div style="font-family:monospace;font-size:15px;font-weight:600;margin-top:3px">{mkt.get('s200','—')}</div></div>
      <div><div style="font-size:10px;color:#64748b">1M Return</div><div style="font-family:monospace;font-size:15px;font-weight:600;margin-top:3px;color:{'#22c55e' if (mkt.get('r1m',0) or 0)>0 else '#ef4444'}">{mkt.get('r1m',0):+.1f}%</div></div>
      <div><div style="font-size:10px;color:#64748b">3M Return</div><div style="font-family:monospace;font-size:15px;font-weight:600;margin-top:3px;color:{'#22c55e' if (mkt.get('r3m',0) or 0)>0 else '#ef4444'}">{mkt.get('r3m',0):+.1f}%</div></div>
      <div><div style="font-size:10px;color:#64748b">VIX</div><div style="font-family:monospace;font-size:15px;font-weight:600;margin-top:3px;color:{'#ef4444' if (mkt.get('vix') or 0)>20 else '#22c55e'}">{mkt.get('vix') or '—'}</div></div>
    </div>
  </div>
</div>

<!-- STATS -->
<div style="display:grid;grid-template-columns:repeat(6,1fr);border-bottom:1px solid rgba(255,255,255,.07)">
  {''.join(f"""<div style="padding:12px 16px;border-right:1px solid rgba(255,255,255,.07)"><div style="font-family:monospace;font-size:20px;font-weight:600;color:{c}">{v}</div><div style="font-size:9px;color:#64748b;margin-top:2px;text-transform:uppercase;letter-spacing:.05em">{l}</div></div>"""
  for v,l,c in [(total,"Scanned","#e2e8f0"),(len(results),"Qualified","#e2e8f0"),(tt7,"TT 7-8","#22c55e"),(vcp,"VCP","#f59e0b"),(ap,"A+ Grade","#a78bfa"),( sum(1 for r in results if r['grade']=='A'),"A Grade","#3b82f6")])}
</div>

<!-- SECTOR ROTATION -->
<div style="padding:16px 24px;border-bottom:1px solid rgba(255,255,255,.07)">
  <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:12px">Sectoral rotation</div>
  <div style="display:grid;grid-template-columns:repeat(9,1fr);gap:8px">{sector_html}</div>
</div>

<!-- TABLE -->
<div class="tw">
<table>
  <thead><tr>
    <th>#</th><th>Symbol</th><th>CMP</th><th>TT Score</th><th>Scan Score</th>
    <th>Grade</th><th>RS Filter</th><th>3M Ret</th><th>Vol Qual</th><th>VCP</th>
    <th>Trade Risk</th><th>Dist 200</th><th>Entry</th><th>Stop</th><th>T1 (2R)</th><th>Pos Size</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>
</div>

<div style="padding:10px 24px;border-top:1px solid rgba(255,255,255,.07);display:flex;justify-content:space-between;font-size:10px;color:#64748b;font-family:monospace;background:#0f1525">
  <span>Source: Dhan API · NSE_EQ · Daily EOD · Minervini SEPA · VIX-adjusted exposure</span>
  <span>Not financial advice · Auto-generated {scan_time}</span>
</div>
</body></html>"""

# ── MAIN ─────────────────────────────────────────────────
def main():
    print("="*60)
    print("  GAURAV'S TRADING SYSTEM — AUTO SCAN")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M IST')}")
    print("="*60)

    if not ACCESS_TOKEN:
        print("❌ DHAN_ACCESS_TOKEN not set in GitHub Secrets")
        sys.exit(1)

    # 1. Fetch index data
    print("\n[1/3] Fetching index & VIX data...")
    idx_hist = {}
    for name, info in INDICES.items():
        hist = dhan_historical(info["id"], seg=info["seg"], days=300)
        idx_hist[name] = hist
        print(f"  {name}: {'OK' if hist else 'FAILED'}")
        time.sleep(0.3)

    nifty_hist = idx_hist.get("NIFTY50")
    vix_hist   = idx_hist.get("INDIAVIX")
    vix_val    = vix_hist["close"][-1] if vix_hist and "close" in vix_hist else None
    mkt        = market_direction(nifty_hist, vix_val)
    sectors    = sector_rotation(idx_hist)

    print(f"\n  Market: {mkt['regime']} | Exposure: {mkt['exposure']}% | VIX: {vix_val}")

    # 2. Fetch batch LTP
    print(f"\n[2/3] Fetching live prices for {len(STOCKS)} stocks...")
    ltp_raw = dhan_ltp_batch(list(STOCKS.values()))
    ltp_map = {}
    for sid, val in ltp_raw.items():
        ltp_map[sid] = val.get("last_price") if isinstance(val, dict) else val
    print(f"  Got LTP for {len(ltp_map)} stocks")

    # 3. Historical + analysis
    print(f"\n[3/3] Analysing stocks (this takes ~4 mins)...")
    results = []
    for i, (sym, sid) in enumerate(STOCKS.items()):
        ltp  = ltp_map.get(sid)
        hist = dhan_historical(sid, days=280)
        if hist:
            r = analyse(sym, sid, hist, ltp)
            if r: results.append(r)
        pct = (i+1) / len(STOCKS) * 100
        print(f"  [{i+1:>3}/{len(STOCKS)}] {sym:<16} {pct:.0f}% | Qualified: {len(results)}", end="\r")
        time.sleep(0.12)
        if (i+1) % 25 == 0: time.sleep(1)

    scan_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M IST")
    print(f"\n\n  ✅ Done — {len(results)} stocks qualified")
    print(f"  TT 7-8: {sum(1 for r in results if r['tts']>=7)}")
    print(f"  A+ Grade: {sum(1 for r in results if r['grade']=='A+')}")
    print(f"  VCP: {sum(1 for r in results if r['vcp'])}")

    # 4. Generate HTML
    html = build_html(results, mkt, sectors, scan_time, len(STOCKS))
    out  = Path("docs/index.html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"\n  Dashboard saved → docs/index.html")
    print("="*60)

if __name__ == "__main__":
    main()
