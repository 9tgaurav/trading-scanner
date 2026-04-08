"""
GAURAV'S TRADING SYSTEM — MARKET SCANNER v6
- Auto-fetches ALL NSE EQ stocks from Dhan master
- Pre-filters by price (>=50) and LTP availability before fetching history
- Only fetches historical data for liquid stocks
- Targets <8 min runtime — well within GitHub Actions 30 min limit
"""

import requests, time, datetime, os, sys, io, csv
from pathlib import Path

CLIENT_ID    = os.environ.get("DHAN_CLIENT_ID",    "").strip()
ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN", "").strip().strip("\n").strip("\r")

CAPITAL  = 5_000_000
RISK_PCT = 0.01
BASE     = "https://api.dhan.co/v2"
MIN_PRICE = 50.0       # Skip stocks below ₹50
MAX_STOCKS = 600       # Cap at 600 after LTP filter to stay within time limit

def hdrs():
    return {"Content-Type":"application/json","access-token":ACCESS_TOKEN,"client-id":CLIENT_ID}

# ── FETCH ALL NSE EQ STOCKS ───────────────────────────────
def fetch_nse_master():
    print("  Downloading Dhan NSE_EQ master...")
    try:
        r = requests.get(f"{BASE}/instrument/NSE_EQ", headers=hdrs(), timeout=60)
        print(f"  HTTP: {r.status_code} | Size: {len(r.text)} chars")
        if r.status_code != 200:
            return []
        lines = r.text.strip().split('\n')
        print(f"  Rows: {len(lines)}")
        print(f"  Header: {lines[0][:400]}")

        reader  = csv.reader(io.StringIO(r.text))
        raw_hdr = next(reader)
        headers = [h.strip().lower().replace(' ','_') for h in raw_hdr]
        print(f"  Cleaned headers: {headers[:15]}")

        def fc(*cands):
            for c in cands:
                if c in headers: return headers.index(c)
            for c in cands:
                for i,h in enumerate(headers):
                    if c in h: return i
            return -1

        i_sym    = fc('sem_trading_symbol','trading_symbol','symbol','tradingsymbol')
        i_sid    = fc('sem_smst_security_id','security_id','securityid','isin')
        i_series = fc('sem_series','series','instrument_type','seg')
        print(f"  sym_col={i_sym} sid_col={i_sid} series_col={i_series}")

        if i_sym < 0 or i_sid < 0:
            print("  ERROR: key columns not found")
            return []

        stocks = []
        for row in reader:
            if not row or len(row) <= max(i_sym, i_sid): continue
            sym = row[i_sym].strip().upper()
            sid = row[i_sid].strip()
            ser = row[i_series].strip().upper() if i_series >= 0 else 'EQ'
            if not sym or not sid: continue
            if ser and ser not in ('EQ','EQUITY',''): continue
            stocks.append({'sym': sym, 'sid': sid})

        print(f"  EQ stocks: {len(stocks)}")
        return stocks
    except Exception as e:
        print(f"  ERROR: {e}")
        return []

# ── BATCH LTP (up to 1000 per call) ──────────────────────
def batch_ltp(sid_list):
    result = {}
    for i in range(0, len(sid_list), 900):
        batch = sid_list[i:i+900]
        # Dhan requires integer security IDs
        try:
            int_batch = [int(s) for s in batch if str(s).strip().isdigit()]
        except:
            int_batch = batch
        if not int_batch:
            continue
        try:
            r = requests.post(f"{BASE}/marketfeed/ltp", headers=hdrs(),
                              json={"NSE_EQ": int_batch}, timeout=30)
            print(f"  LTP batch {i//900+1}: HTTP {r.status_code} | {len(int_batch)} sids")
            if r.status_code == 200:
                resp = r.json()
                # Handle both response formats
                raw = resp.get("data",{})
                if isinstance(raw, dict):
                    nse_data = raw.get("NSE_EQ", raw)
                    for k,v in nse_data.items():
                        price = v.get("last_price") if isinstance(v,dict) else v
                        if price and float(price) > 0:
                            result[str(k)] = float(price)
                elif isinstance(raw, list):
                    for item in raw:
                        if isinstance(item, dict):
                            sid = str(item.get("security_id",""))
                            price = item.get("last_price", 0)
                            if sid and price: result[sid] = float(price)
            else:
                print(f"  LTP error body: {r.text[:300]}")
        except Exception as e:
            print(f"  LTP batch error: {e}")
        time.sleep(0.3)
    return result

# ── HISTORICAL ────────────────────────────────────────────
def hist(sid, seg="NSE_EQ", days=280, instrument="EQUITY"):
    to_dt = datetime.date.today()
    fr_dt = to_dt - datetime.timedelta(days=days+80)
    try:
        r = requests.post(f"{BASE}/charts/historical", headers=hdrs(), timeout=15,
            json={"securityId":str(sid),"exchangeSegment":seg,"instrument":instrument,
                  "expiryCode":0,"oi":False,
                  "fromDate":fr_dt.strftime("%Y-%m-%d"),"toDate":to_dt.strftime("%Y-%m-%d")})
        if r.status_code == 200:
            d = r.json()
            if isinstance(d,dict) and "close" in d and len(d["close"])>0:
                return d
    except: pass
    return None

# ── INDEX IDs ─────────────────────────────────────────────
def fetch_index_ids():
    try:
        r = requests.get(f"{BASE}/instrument/IDX_I", headers=hdrs(), timeout=30)
        if r.status_code != 200: return {}
        reader  = csv.reader(io.StringIO(r.text))
        headers = [h.strip().lower().replace(' ','_') for h in next(reader)]
        def fc(*c):
            for x in c:
                if x in headers: return headers.index(x)
            return -1
        i_sym = fc('sem_trading_symbol','trading_symbol','symbol')
        i_sid = fc('sem_smst_security_id','security_id','securityid')
        if i_sym<0 or i_sid<0: return {}
        idx={}
        for row in reader:
            if len(row)<=max(i_sym,i_sid): continue
            sym=row[i_sym].strip().upper(); sid=row[i_sid].strip()
            if sym and sid: idx[sym]=sid
        print(f"  Index IDs: {len(idx)} — {dict(list(idx.items())[:6])}")
        return idx
    except Exception as e:
        print(f"  Index error: {e}"); return {}

# ── MATHS ─────────────────────────────────────────────────
def sma(v,n):
    if len(v)<n: return None
    return sum(v[-n:])/n

def pchg(v,n):
    if len(v)<n+1: return None
    b=v[-(n+1)]; return ((v[-1]-b)/b*100) if b else None

# ── ANALYSE ───────────────────────────────────────────────
def analyse(sym, sid, h, ltp=None):
    if not h or "close" not in h: return None
    c=h["close"]; hh=h.get("high",[]); lo=h.get("low",[]); v=h.get("volume",[])
    if len(c)<200: return None
    cmp=float(ltp) if ltp else float(c[-1])
    s50=sma(c,50); s150=sma(c,150); s200=sma(c,200)
    s200p=sma(c[:-30],200) if len(c)>=230 else None
    hi52=max(hh[-252:]) if len(hh)>=252 else (max(hh) if hh else cmp)
    lo52=min(lo[-252:]) if len(lo)>=252 else (min(lo) if lo else cmp)
    hi30=max(hh[-30:]) if len(hh)>=30 else (max(hh) if hh else cmp)
    lo30=min(lo[-30:]) if len(lo)>=30 else (min(lo) if lo else cmp)
    hi60=max(hh[-60:]) if len(hh)>=60 else (max(hh) if hh else cmp)
    lo60=min(lo[-60:]) if len(lo)>=60 else (min(lo) if lo else cmp)
    v30=sum(v[-30:])/30 if len(v)>=30 else None
    v63=sum(v[-63:])/63 if len(v)>=63 else None
    r3m=pchg(c,63)
    tt=[False]*8
    if s200:
        tt[0]=cmp>s200; tt[1]=(s200>s200p) if s200p else False
        if s150: tt[2]=s150>s200
        if s50 and s150: tt[3]=s50>s150 and s50>s200
        if s50: tt[4]=cmp>s50
        if lo52: tt[5]=cmp>=lo52*1.25
        if hi52: tt[6]=cmp>=hi52*0.75
        tt[7]=(r3m or 0)>5
    if not tt[0]: return None
    tts=sum(tt)
    rng30=((hi30-lo30)/lo30*100) if lo30 else None
    rng60=((hi60-lo60)/lo60*100) if lo60 else None
    r30f=rng30 is not None and rng30<10
    r60f=rng60 is not None and rng60<20
    vcp=r30f and r60f
    rs_f=(r3m or 0)-5
    vq=(v30/v63*100) if (v30 and v63) else None
    d200=((cmp-s200)/s200*100) if s200 else None
    trisk=((cmp-lo30)/cmp*100) if lo30 else 7.0
    sc=0; sc+=(tts/8)*35; sc+=22 if rs_f>0 else 0
    sc+=min(vq or 0,100)/100*18
    if r30f: sc+=7
    if r60f: sc+=7
    sc=min(round(sc),100)
    if tts>=8 and rs_f>0 and sc>=78: grade="A+"
    elif tts>=7 and rs_f>0 and sc>=62: grade="A"
    elif tts>=6 and sc>=46: grade="B+"
    else: grade="B"
    ri=CAPITAL*RISK_PCT*0.75; rps=cmp*trisk/100
    shares=int(ri/rps) if rps>0 else 0
    entry=round(cmp*1.005,2)
    stop_p=round(lo30,2) if lo30 else round(cmp*0.93,2)
    t1=round(entry+2*(entry-stop_p),2)
    return {"sym":sym,"sid":str(sid),"cmp":round(cmp,2),"tts":tts,"tt":tt,
            "grade":grade,"score":sc,"s50":round(s50 or 0,2),"s150":round(s150 or 0,2),
            "s200":round(s200 or 0,2),"rs":round(rs_f,2),"r3m":round(r3m or 0,2),
            "vq":round(vq or 0,1),"r30f":r30f,"r60f":r60f,"vcp":vcp,
            "d200":round(d200 or 0,1),"trisk":round(trisk,1),
            "entry":entry,"stop":stop_p,"t1":t1,"shares":shares,"posval":round(shares*cmp)}

# ── MARKET DIRECTION ─────────────────────────────────────
def mkt_dir(nh, vix=None):
    if not nh or "close" not in nh or len(nh["close"])<200:
        return {"regime":"UNKNOWN","exposure":75,"cmp":0,"s50":0,"s150":0,"s200":0,
                "r1m":0,"r3m":0,"vix":vix,"signals":["Nifty index data unavailable"]}
    c=nh["close"]; cmp=c[-1]; s50=sma(c,50); s150=sma(c,150); s200=sma(c,200)
    r1m=pchg(c,21); r3m=pchg(c,63)
    if s200 and cmp>s200 and s50 and cmp>s50:
        regime="BULL-CAUTION" if (vix or 0)>22 else "BULL"
        exposure=75 if (vix or 0)>22 else 100
    elif s200 and cmp>s200: regime="BULL-WEAK"; exposure=75
    elif s150 and cmp>s150: regime="TRANSITION"; exposure=50
    else: regime="BEAR"; exposure=25
    if (vix or 0)>30: exposure=min(exposure,25)
    elif (vix or 0)>22: exposure=min(exposure,50)
    sigs=[]
    sigs.append("Price > 50 SMA ✅" if (s50 and cmp>s50) else "Price < 50 SMA ⚠")
    sigs.append("Price > 200 SMA ✅" if (s200 and cmp>s200) else "Price < 200 SMA ❌")
    if r3m: sigs.append(f"Nifty 3M: {r3m:+.1f}%")
    if vix: sigs.append(f"India VIX: {vix:.1f}")
    return {"regime":regime,"exposure":exposure,"cmp":round(cmp,2),
            "s50":round(s50 or 0,2),"s150":round(s150 or 0,2),"s200":round(s200 or 0,2),
            "r1m":round(r1m or 0,2),"r3m":round(r3m or 0,2),"vix":vix,"signals":sigs}

def sect_rot(idx_data):
    sectors=[]
    for name,h in idx_data.items():
        if "VIX" in name or not h or "close" not in h: continue
        c=h["close"]; r1m=pchg(c,21); r3m=pchg(c,63); r6m=pchg(c,126)
        s200=sma(c,200); cmp=c[-1]; ab200=cmp>s200 if s200 else False
        mom=(r1m or 0)*0.4+(r3m or 0)*0.4+(r6m or 0)*0.2
        tier="HOT" if mom>5 and ab200 else "WARM" if mom>0 else "COLD"
        label=name.replace("NIFTY","").replace("50","").strip() or name
        sectors.append({"name":label,"r1m":round(r1m or 0,2),"r3m":round(r3m or 0,2),
                        "tier":tier,"momentum":round(mom,2)})
    return sorted(sectors,key=lambda x:x["momentum"],reverse=True)

# ── HTML ──────────────────────────────────────────────────
def build_html(results,mkt,sectors,scan_time,total_master,ltp_found,hist_scanned):
    results=sorted(results,key=lambda x:x["score"],reverse=True)
    tt7=sum(1 for r in results if r["tts"]>=7)
    vcp_c=sum(1 for r in results if r["vcp"])
    ap=sum(1 for r in results if r["grade"]=="A+")
    a_c=sum(1 for r in results if r["grade"]=="A")
    rc={"BULL":"#22c55e","BULL-WEAK":"#86efac","BULL-CAUTION":"#f59e0b",
        "TRANSITION":"#fb923c","BEAR":"#ef4444","UNKNOWN":"#64748b"}
    regc=rc.get(mkt.get("regime","UNKNOWN"),"#64748b")
    sh=""
    for s in sectors[:9]:
        col="#22c55e" if s["tier"]=="HOT" else "#f59e0b" if s["tier"]=="WARM" else "#64748b"
        bg="rgba(34,197,94,.12)" if s["tier"]=="HOT" else "rgba(245,158,11,.1)" if s["tier"]=="WARM" else "rgba(100,116,139,.1)"
        sh+=(f'<div style="background:{bg};border:1px solid {col}33;border-radius:8px;padding:10px 12px">'
             f'<div style="font-size:10px;color:{col};font-weight:700">{s["tier"]}</div>'
             f'<div style="font-size:13px;font-weight:600;margin:3px 0">{s["name"]}</div>'
             f'<div style="font-family:monospace;font-size:10px;color:#94a3b8">1M:{s["r1m"]:+.1f}% 3M:{s["r3m"]:+.1f}%</div>'
             f'</div>')
    rows=""
    for i,s in enumerate(results):
        rk=i+1
        rnc="color:#f59e0b" if rk==1 else "color:#94a3b8" if rk<=3 else "color:#a78bfa" if rk<=5 else "color:#64748b"
        dots="".join(f'<span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:{"#22c55e" if s["tt"][d] else "#1e293b"};margin-right:2px"></span>' for d in range(8))
        sc=s["score"]; scc="#22c55e" if sc>=75 else "#f59e0b" if sc>=50 else "#64748b"
        grc={"A+":"#4ade80","A":"#22c55e","B+":"#f59e0b","B":"#64748b"}.get(s["grade"],"#64748b")
        grb={"A+":"rgba(34,197,94,.2)","A":"rgba(34,197,94,.12)","B+":"rgba(245,158,11,.15)","B":"rgba(100,116,139,.1)"}.get(s["grade"],"rgba(100,116,139,.1)")
        r3c="#22c55e" if s["r3m"]>0 else "#ef4444"
        rsc="#22c55e" if s["rs"]>0 else "#ef4444"
        d2c="#22d3ee" if s["d200"]>0 else "#94a3b8"
        vcp='<span style="background:rgba(34,197,94,.15);color:#22c55e;padding:2px 6px;border-radius:3px;font-size:9px;font-weight:700;border:1px solid rgba(34,197,94,.3)">VCP</span>' if s["vcp"] else "—"
        rows+=(f'<tr style="border-bottom:1px solid rgba(255,255,255,.05)">'
               f'<td style="padding:7px 8px;font-family:monospace;font-size:10px;{rnc}">{rk}</td>'
               f'<td style="padding:7px 8px;font-weight:700;font-size:12px">{s["sym"]}</td>'
               f'<td style="padding:7px 8px;font-family:monospace;font-size:11px">₹{s["cmp"]:,.1f}</td>'
               f'<td style="padding:7px 8px">{dots}<div style="font-family:monospace;font-size:9px;color:#64748b">{s["tts"]}/8</div></td>'
               f'<td style="padding:7px 8px;font-family:monospace;font-weight:600;color:{scc}">{sc}</td>'
               f'<td style="padding:7px 8px"><span style="background:{grb};color:{grc};padding:2px 8px;border-radius:3px;font-size:10px;font-weight:700">{s["grade"]}</span></td>'
               f'<td style="padding:7px 8px;font-family:monospace;font-size:11px;color:{rsc}">{s["rs"]:+.2f}</td>'
               f'<td style="padding:7px 8px;font-family:monospace;font-size:11px;color:{r3c}">{s["r3m"]:+.1f}%</td>'
               f'<td style="padding:7px 8px;font-family:monospace;font-size:11px">{s["vq"]:.0f}%</td>'
               f'<td style="padding:7px 8px">{vcp}</td>'
               f'<td style="padding:7px 8px;font-family:monospace;font-size:11px;color:#94a3b8">{s["trisk"]:.1f}%</td>'
               f'<td style="padding:7px 8px;font-family:monospace;font-size:11px;color:{d2c}">{s["d200"]:+.1f}%</td>'
               f'<td style="padding:7px 8px;font-family:monospace;font-size:11px;color:#22c55e">₹{s["entry"]:,.2f}</td>'
               f'<td style="padding:7px 8px;font-family:monospace;font-size:11px;color:#ef4444">₹{s["stop"]:,.2f}</td>'
               f'<td style="padding:7px 8px;font-family:monospace;font-size:11px;color:#f59e0b">₹{s["t1"]:,.2f}</td>'
               f'<td style="padding:7px 8px;font-family:monospace;font-size:10px">₹{s["posval"]:,.0f}</td>'
               f'</tr>')
    sigs="".join(f'<div style="font-size:11px;color:#94a3b8;margin-bottom:3px">{sg}</div>' for sg in mkt.get("signals",[]))
    eff=round(CAPITAL*mkt.get("exposure",75)/100/100000,1)
    r1m=mkt.get("r1m",0) or 0; r3m=mkt.get("r3m",0) or 0; vx=mkt.get("vix") or 0
    r1c="#22c55e" if r1m>0 else "#ef4444"; r3c2="#22c55e" if r3m>0 else "#ef4444"
    vxc="#ef4444" if vx>20 else "#22c55e"; vxd=f"{vx:.1f}" if vx else "—"
    stats=[(total_master,"NSE master","#e2e8f0"),(ltp_found,"LTP found","#94a3b8"),
           (hist_scanned,"Hist scanned","#94a3b8"),(len(results),"Qualified","#e2e8f0"),
           (tt7,"TT 7-8","#22c55e"),(ap,"A+ Grade","#a78bfa"),(a_c,"A Grade","#3b82f6")]
    sthtml="".join(
        f'<div style="padding:12px 14px;border-right:1px solid rgba(255,255,255,.07)">'
        f'<div style="font-family:monospace;font-size:18px;font-weight:600;color:{c}">{v}</div>'
        f'<div style="font-size:9px;color:#64748b;margin-top:2px;text-transform:uppercase;letter-spacing:.05em">{l}</div></div>'
        for v,l,c in stats)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gaurav's Trading Dashboard — {scan_time}</title>
<style>@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0a0e1a;color:#e2e8f0;font-family:'IBM Plex Sans',sans-serif;font-size:13px}}
.tw{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{background:#0f1525;color:#64748b;font-size:9px;text-transform:uppercase;letter-spacing:.07em;padding:8px;text-align:left;border-bottom:1px solid rgba(255,255,255,.1);white-space:nowrap;position:sticky;top:0;z-index:5}}
tr:hover td{{background:rgba(255,255,255,.03)}}</style></head><body>
<div style="background:#0f1525;border-bottom:1px solid rgba(255,255,255,.07);padding:14px 20px;display:flex;justify-content:space-between;align-items:center">
  <div style="display:flex;align-items:center;gap:12px">
    <div style="width:36px;height:36px;border-radius:8px;background:rgba(34,197,94,.12);border:1px solid #22c55e;display:flex;align-items:center;justify-content:center;font-family:monospace;font-size:12px;color:#22c55e;font-weight:700">GT</div>
    <div><div style="font-size:15px;font-weight:600">Gaurav's Trading System</div>
    <div style="font-size:9px;color:#64748b;font-family:monospace;margin-top:2px">NSE LIQUID UNIVERSE · MINERVINI SEPA · DHAN API · {scan_time}</div></div>
  </div>
  <div style="font-family:monospace;font-size:10px;color:#64748b">₹{CAPITAL//100000}L Capital · 1% Risk · Auto 4:30 PM IST</div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1px;background:rgba(255,255,255,.07);border-bottom:1px solid rgba(255,255,255,.07)">
  <div style="background:#0a0e1a;padding:18px 20px">
    <div style="font-size:9px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:8px">Market regime</div>
    <div style="font-size:26px;font-weight:700;color:{regc};margin-bottom:4px">{mkt.get("regime","—")}</div>
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
      <span style="font-size:11px;color:#94a3b8">Deploy:</span>
      <span style="font-size:16px;font-weight:700;color:{regc}">{mkt.get("exposure",75)}%</span>
      <span style="font-size:11px;color:#64748b">= ₹{eff}L active</span>
    </div>{sigs}
  </div>
  <div style="background:#0a0e1a;padding:18px 20px">
    <div style="font-size:9px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">Nifty 50 levels</div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
      <div><div style="font-size:9px;color:#64748b">CMP</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px">{mkt.get("cmp","—")}</div></div>
      <div><div style="font-size:9px;color:#64748b">50 SMA</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px">{mkt.get("s50","—")}</div></div>
      <div><div style="font-size:9px;color:#64748b">200 SMA</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px">{mkt.get("s200","—")}</div></div>
      <div><div style="font-size:9px;color:#64748b">1M Ret</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px;color:{r1c}">{r1m:+.1f}%</div></div>
      <div><div style="font-size:9px;color:#64748b">3M Ret</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px;color:{r3c2}">{r3m:+.1f}%</div></div>
      <div><div style="font-size:9px;color:#64748b">VIX</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px;color:{vxc}">{vxd}</div></div>
    </div>
  </div>
</div>
<div style="display:grid;grid-template-columns:repeat(7,1fr);border-bottom:1px solid rgba(255,255,255,.07)">{sthtml}</div>
<div style="padding:14px 20px;border-bottom:1px solid rgba(255,255,255,.07)">
  <div style="font-size:9px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">Sectoral rotation</div>
  <div style="display:grid;grid-template-columns:repeat(9,1fr);gap:6px">{sh}</div>
</div>
<div class="tw"><table><thead><tr>
  <th>#</th><th>Symbol</th><th>CMP</th><th>TT Score</th><th>Score</th><th>Grade</th>
  <th>RS Filter</th><th>3M Ret</th><th>Vol Qual</th><th>VCP</th>
  <th>Trade Risk</th><th>Dist 200</th><th>Entry</th><th>Stop</th><th>T1 (2R)</th><th>Pos Size</th>
</tr></thead><tbody>{rows}</tbody></table></div>
<div style="padding:8px 20px;border-top:1px solid rgba(255,255,255,.07);display:flex;justify-content:space-between;font-size:9px;color:#64748b;font-family:monospace;background:#0f1525">
  <span>Dhan API · NSE Liquid Universe · EOD · Minervini SEPA · VIX-adjusted · Auto-generated daily</span>
  <span>Not financial advice · {scan_time}</span>
</div>
</body></html>"""

# ── MAIN ─────────────────────────────────────────────────
def main():
    print("="*60)
    print("  GAURAV'S TRADING SYSTEM v6 — LIQUID UNIVERSE")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M IST')}")
    print("="*60)
    if not ACCESS_TOKEN:
        print("ERROR: DHAN_ACCESS_TOKEN not set"); sys.exit(1)
    print(f"\n  Token length: {len(ACCESS_TOKEN)} | Client: {CLIENT_ID}")

    # ── Step 0: Get full NSE master ──
    print("\n[0/3] Fetching NSE instrument master...")
    master = fetch_nse_master()
    if not master:
        print("CRITICAL: Cannot fetch instrument master"); sys.exit(1)
    print(f"  Master size: {len(master)} EQ stocks")

    # ── Step 1: Index data ──
    print("\n[1/3] Fetching index & VIX data...")
    idx_ids = fetch_index_ids()
    nifty_keys=["NIFTY 50","NIFTY50","NIFTY_50"]
    nifty_sid=next((idx_ids.get(k) for k in nifty_keys if idx_ids.get(k)),None)
    nh=None
    if nifty_sid:
        nh=hist(nifty_sid,seg="IDX_I",days=300,instrument="INDEX")
        if not nh: nh=hist(nifty_sid,seg="NSE_EQ",days=300,instrument="EQUITY")
    print(f"  Nifty 50: {'OK '+str(len(nh.get('close',[])))+'c' if nh else 'FAILED'}")
    vix_keys=["INDIA VIX","INDIAVIX","INDIA_VIX"]
    vix_sid=next((idx_ids.get(k) for k in vix_keys if idx_ids.get(k)),None)
    vh=hist(vix_sid,seg="IDX_I",days=30,instrument="INDEX") if vix_sid else None
    vix_val=vh["close"][-1] if vh and "close" in vh else None
    print(f"  VIX: {vix_val}")
    idx_hist={}
    smap={"NIFTY BANK":"BANKNIFTY","NIFTYBANK":"BANKNIFTY","NIFTY IT":"NIFTYIT",
          "NIFTYIT":"NIFTYIT","NIFTY PHARMA":"NIFTYPHARMA","NIFTYPHARMA":"NIFTYPHARMA",
          "NIFTY AUTO":"NIFTYAUTO","NIFTYAUTO":"NIFTYAUTO","NIFTY FMCG":"NIFTYFMCG",
          "NIFTYFMCG":"NIFTYFMCG","NIFTY METAL":"NIFTYMETAL","NIFTYMETAL":"NIFTYMETAL",
          "NIFTY REALTY":"NIFTYREALTY","NIFTYREALTY":"NIFTYREALTY"}
    for k,label in smap.items():
        sid2=idx_ids.get(k)
        if sid2 and label not in idx_hist:
            h2=hist(sid2,seg="IDX_I",days=300,instrument="INDEX")
            if h2: idx_hist[label]=h2; print(f"  {label}: OK")
            time.sleep(0.2)
    mkt=mkt_dir(nh,vix_val); sectors=sect_rot(idx_hist)
    print(f"  Regime: {mkt['regime']} | Exposure: {mkt['exposure']}%")

    # ── Step 2: BATCH LTP for all stocks (liquidity pre-filter) ──
    print(f"\n[2/3] Batch LTP for {len(master)} stocks (pre-filter)...")
    all_sids=[s['sid'] for s in master]
    ltp_map=batch_ltp(all_sids)
    print(f"  LTP received: {len(ltp_map)}")

    # Build sid→symbol map
    sid_to_sym={s['sid']:s['sym'] for s in master}

    # Filter: must have LTP and price >= MIN_PRICE
    liquid=[]
    for sid,price in ltp_map.items():
        if price and float(price)>=MIN_PRICE:
            sym=sid_to_sym.get(str(sid),"")
            if sym: liquid.append({'sym':sym,'sid':str(sid),'ltp':float(price)})

    # FALLBACK: if LTP returned nothing, use all master stocks with ltp=None
    if len(liquid) == 0:
        print("  WARNING: LTP returned 0 results — falling back to master list (will use hist close)")
        liquid = [{'sym':s['sym'],'sid':s['sid'],'ltp':None} for s in master]
        liquid = liquid[:MAX_STOCKS]
    else:
        # Sort by price descending (higher price = more liquid generally), cap at MAX_STOCKS
        liquid.sort(key=lambda x:x['ltp'],reverse=True)
        liquid=liquid[:MAX_STOCKS]
    print(f"  After price filter (>={MIN_PRICE}): {len(liquid)} stocks")
    print(f"  Capped at: {MAX_STOCKS} stocks for time budget")

    # ── Step 3: Historical + Minervini analysis ──
    print(f"\n[3/3] Analysing {len(liquid)} liquid stocks...")
    results=[]
    for i,stock in enumerate(liquid):
        h=hist(stock['sid'],seg="NSE_EQ",days=280,instrument="EQUITY")
        if h:
            r=analyse(stock['sym'],stock['sid'],h,stock['ltp'])
            if r: results.append(r)
        pct=(i+1)/len(liquid)*100
        print(f"  [{i+1:>3}/{len(liquid)}] {stock['sym']:<14} {pct:.0f}% | Qualified:{len(results)}",end="\r")
        time.sleep(0.08)
        if (i+1)%50==0: time.sleep(0.5)

    scan_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M IST")
    print(f"\n\n{'='*60}")
    print(f"  COMPLETE · Qualified: {len(results)}")
    print(f"  TT 7-8: {sum(1 for r in results if r['tts']>=7)}")
    print(f"  A+: {sum(1 for r in results if r['grade']=='A+')}")
    print(f"  VCP: {sum(1 for r in results if r['vcp'])}")
    if results:
        top5=sorted(results,key=lambda x:x["score"],reverse=True)[:5]
        print("\n  TOP 5:")
        for i,s in enumerate(top5):
            print(f"  {i+1}. {s['sym']:<14} Score:{s['score']} {s['grade']} TT:{s['tts']}/8 ₹{s['cmp']:,.0f}")

    html=build_html(results,mkt,sectors,scan_time,len(master),len(ltp_map),len(liquid))
    out=Path("docs/index.html"); out.parent.mkdir(exist_ok=True)
    out.write_text(html,encoding="utf-8")
    print(f"\n  Dashboard → docs/index.html")
    print("="*60)

if __name__=="__main__":
    main()
