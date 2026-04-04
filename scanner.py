"""
GAURAV'S TRADING SYSTEM — AUTOMATED MARKET SCANNER v3
Auto-fetches correct security IDs from Dhan instrument master
"""
import requests, json, time, datetime, os, sys, io, csv
from pathlib import Path

CLIENT_ID    = os.environ.get("DHAN_CLIENT_ID",    "1100847090")
ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN", "")
CAPITAL      = 5_000_000
RISK_PCT     = 0.01
BASE         = "https://api.dhan.co/v2"
HEADERS      = {"Content-Type":"application/json","access-token":ACCESS_TOKEN,"client-id":CLIENT_ID}

NIFTY500_SYMBOLS = [
    "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","HINDUNILVR","SBIN","BAJFINANCE",
    "BHARTIARTL","KOTAKBANK","WIPRO","AXISBANK","ASIANPAINT","MARUTI","TITAN","SUNPHARMA",
    "HCLTECH","ULTRACEMCO","BAJAJFINSV","NESTLEIND","POWERGRID","NTPC","ONGC","JSWSTEEL",
    "COALINDIA","M&M","TATASTEEL","ADANIENT","ADANIPORTS","LTIM","TECHM","CIPLA","DRREDDY",
    "EICHERMOT","BRITANNIA","DIVISLAB","APOLLOHOSP","HINDALCO","GRASIM","SBILIFE","HDFCLIFE",
    "ICICIPRULI","LT","TATACONSUM","ITC","BPCL","IOC","HINDPETRO","VEDL","TATAMOTORS",
    "TRENT","PIDILITIND","SIEMENS","GODREJCP","HAVELLS","DABUR","MARICO","COLPAL","ABB",
    "BOSCHLTD","CUMMINSIND","MUTHOOTFIN","CHOLAFIN","AUROPHARMA","TORNTPHARM","LUPIN",
    "ALKEM","GLENMARK","BIOCON","ZYDUSLIFE","IPCALAB","RECLTD","PFC","CANBK","UNIONBANK",
    "BANKBARODA","PNB","FEDERALBNK","IDFCFIRSTB","BANDHANBNK","MOTHERSON","BALKRISIND",
    "APOLLOTYRE","MRF","EXIDEIND","TATACHEM","UPL","PIIND","COROMANDEL","LICHSGFIN","IRFC",
    "TATAPOWER","ADANIGREEN","JSWENERGY","SUZLON","POLYCAB","KEI","CONCOR","HFCL",
    "TATAELXSI","PERSISTENT","MPHASIS","COFORGE","LTTS","KPIT","CYIENT","BIRLASOFT",
    "TANLA","ROUTE","INDIAMART","CAMS","CDSL","MCX","ANGELONE","DIXON","AMBER","VGUARD",
    "CROMPTON","VOLTAS","BLUESTAR","GODREJPROP","OBEROIRLTY","DLF","PRESTIGE","SOBHA",
    "PHOENIXLTD","SUNTV","ZOMATO","HAL","BEL","BHEL","ESCORTS","DEEPAKNTR","ATUL",
    "NAVINFLUOR","PAGEIND","MCDOWELL-N","RADICO","LUXIND","SHOPERSTOP","KAYNES","SYRMA",
    "TITAGARH","GNFC","CHAMBLFERT","NOCIL","VINATI","AARTI","FINEORG","ALKYLAMINE",
    "CLEAN","MATRIMONY","CAMPUS","NYKAA","DELHIVERY","PVRINOX","GRSE","IRCTC",
    "SHRIRAMFIN","BAJAJ-AUTO","HEROMOTOCO","TVSMOTOR","ASHOKLEY","AMARAJABAT",
    "SCHAEFFLER","SUNDRMFAST","ENDURANCE","TIINDIA","BLUEDART","APLAPOLLO","JINDALSAW",
    "RATNAMANI","WELSPUN","GMRAIRPORT","INTERGLOBE","VSTIND","GODFRYPHLP","CASTROLIND",
    "PETRONET","GAIL","MGL","IGL","TORNTPOWER","CESC","INOXWIND","GREENPANEL",
    "CENTURYTEX","ORIENTELEC","SYMPHONY","WHIRLPOOL","FINOLEX","ICRA","CRISIL",
    "CREDITACC","IIFL","GEOJIT","NETWORK18","TV18BRDCST","INOXLEISUR","WONDERLA",
    "BALRAMCHIN","DHAMPUR","TRIVENI","EIHOTEL","AVENUESUPRA","LATENTVIEW","INTELLECT",
    "ECLERX","JUSTDIAL","IDEAFORGE","PAYTM","POLICYBAZAAR","SAPPHIRE","DEVYANI",
    "NUVOCO","AVALON","MIDHANI","COCHINSHIP","RITES","RAILVIKAS","NHPC","SJVN",
    "HUDCO","MOTILALOFS","BSE","RBLBANK","KARURVYSYA","DCBBANK","KTKBANK","SOUTHBANK",
]
seen = set()
NIFTY500_SYMBOLS = [x for x in NIFTY500_SYMBOLS if not (x in seen or seen.add(x))]

def get_security_ids(symbols):
    print("  Downloading Dhan NSE_EQ instrument master...")
    try:
        r = requests.get(f"{BASE}/instrument/NSE_EQ", headers=HEADERS, timeout=60)
        print(f"  Master HTTP status: {r.status_code}")
        if r.status_code != 200:
            return {}
        content = r.text
        lines   = content.strip().split('\n')
        print(f"  Master rows: {len(lines)}")
        print(f"  Header: {lines[0][:200]}")
        reader  = csv.reader(io.StringIO(content))
        headers = [h.strip().lower() for h in next(reader)]

        sym_col = next((headers.index(c) for c in ["sem_trading_symbol","trading_symbol","symbol","tradingsymbol"] if c in headers), None)
        id_col  = next((headers.index(c) for c in ["sem_smst_security_id","security_id","securityid","sec_id"] if c in headers), None)

        if sym_col is None:
            for i,h in enumerate(headers):
                if "symbol" in h: sym_col=i; break
        if id_col is None:
            for i,h in enumerate(headers):
                if "security" in h and "id" in h: id_col=i; break

        print(f"  sym_col={sym_col} id_col={id_col}")
        if sym_col is None or id_col is None:
            print(f"  All headers: {headers}")
            return {}

        symbol_set = set(symbols)
        id_map = {}
        for row in reader:
            if len(row) <= max(sym_col, id_col): continue
            sym = row[sym_col].strip().upper()
            sid = row[id_col].strip()
            if sym in symbol_set and sid:
                id_map[sym] = sid

        print(f"  Found {len(id_map)} of {len(symbols)} symbols")
        return id_map
    except Exception as e:
        print(f"  ERROR: {e}")
        return {}

def get_index_ids():
    try:
        r = requests.get(f"{BASE}/instrument/IDX_I", headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return {}
        reader  = csv.reader(io.StringIO(r.text))
        headers = [h.strip().lower() for h in next(reader)]
        sym_col = next((headers.index(c) for c in ["sem_trading_symbol","trading_symbol","symbol"] if c in headers), None)
        id_col  = next((headers.index(c) for c in ["sem_smst_security_id","security_id","securityid"] if c in headers), None)
        if sym_col is None or id_col is None: return {}
        id_map = {}
        for row in reader:
            if len(row) <= max(sym_col, id_col): continue
            sym = row[sym_col].strip().upper()
            sid = row[id_col].strip()
            if sid: id_map[sym] = sid
        return id_map
    except: return {}

def dhan_hist(sec_id, seg="NSE_EQ", days=280, instrument="EQUITY"):
    to_dt = datetime.date.today()
    fr_dt = to_dt - datetime.timedelta(days=days+80)
    payload = {"securityId":str(sec_id),"exchangeSegment":seg,"instrument":instrument,
               "expiryCode":0,"oi":False,"fromDate":fr_dt.strftime("%Y-%m-%d"),"toDate":to_dt.strftime("%Y-%m-%d")}
    try:
        r = requests.post(f"{BASE}/charts/historical", headers=HEADERS, json=payload, timeout=20)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data,dict) and "close" in data and len(data["close"])>0:
                return data
    except: pass
    return None

def dhan_ltp(sid_list):
    if not sid_list: return {}
    try:
        r = requests.post(f"{BASE}/marketfeed/ltp", headers=HEADERS, json={"NSE_EQ":sid_list}, timeout=20)
        if r.status_code == 200:
            raw = r.json().get("data",{}).get("NSE_EQ",{})
            return {str(k):(v.get("last_price") if isinstance(v,dict) else v) for k,v in raw.items()}
    except: pass
    return {}

def sma(v,n):
    if len(v)<n: return None
    return sum(v[-n:])/n

def pct(v,n):
    if len(v)<n+1: return None
    b=v[-(n+1)]; return ((v[-1]-b)/b*100) if b else None

def analyse(sym, sid, hist, ltp=None):
    if not hist or "close" not in hist: return None
    c=hist["close"]; h=hist.get("high",[]); lo=hist.get("low",[]); v=hist.get("volume",[])
    if len(c)<200: return None
    cmp=float(ltp) if ltp else float(c[-1])
    s50=sma(c,50); s150=sma(c,150); s200=sma(c,200); s200p=sma(c[:-30],200) if len(c)>=230 else None
    hi52=max(h[-252:]) if len(h)>=252 else (max(h) if h else cmp)
    lo52=min(lo[-252:]) if len(lo)>=252 else (min(lo) if lo else cmp)
    hi30=max(h[-30:]) if len(h)>=30 else (max(h) if h else cmp)
    lo30=min(lo[-30:]) if len(lo)>=30 else (min(lo) if lo else cmp)
    hi60=max(h[-60:]) if len(h)>=60 else (max(h) if h else cmp)
    lo60=min(lo[-60:]) if len(lo)>=60 else (min(lo) if lo else cmp)
    v30=sum(v[-30:])/30 if len(v)>=30 else None
    v63=sum(v[-63:])/63 if len(v)>=63 else None
    r3m=pct(c,63)
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
    trisk=((cmp-lo30)/cmp*100) if lo30 else 7
    sc=0; sc+=(tts/8)*35; sc+=22 if rs_f>0 else 0
    sc+=min(vq or 0,100)/100*18
    if r30f: sc+=7
    if r60f: sc+=7
    sc=min(round(sc),100)
    rs_pos=rs_f>0
    if tts>=8 and rs_pos and sc>=78: grade="A+"
    elif tts>=7 and rs_pos and sc>=62: grade="A"
    elif tts>=6 and sc>=46: grade="B+"
    else: grade="B"
    ri=CAPITAL*RISK_PCT*0.75; rps=cmp*trisk/100
    shares=int(ri/rps) if rps>0 else 0
    entry=round(cmp*1.005,2); stop_p=round(lo30,2) if lo30 else round(cmp*0.93,2)
    t1=round(entry+2*(entry-stop_p),2); t2=round(entry+3*(entry-stop_p),2)
    return {"sym":sym,"sid":str(sid),"cmp":round(cmp,2),"tts":tts,"tt":tt,"grade":grade,"score":sc,
            "s50":round(s50 or 0,2),"s150":round(s150 or 0,2),"s200":round(s200 or 0,2),
            "hi52":round(hi52,2),"lo52":round(lo52,2),"rs":round(rs_f,2),"r3m":round(r3m or 0,2),
            "vq":round(vq or 0,1),"rng30":round(rng30 or 0,1),"rng60":round(rng60 or 0,1),
            "r30f":r30f,"r60f":r60f,"vcp":vcp,"d200":round(d200 or 0,1),"trisk":round(trisk,1),
            "entry":entry,"stop":stop_p,"t1":t1,"t2":t2,"shares":shares,"posval":round(shares*cmp)}

def market_direction(nh, vix=None):
    if not nh or "close" not in nh or len(nh["close"])<200:
        return {"regime":"UNKNOWN","exposure":75,"cmp":0,"s50":0,"s150":0,"s200":0,"r1m":0,"r3m":0,"vix":vix,"signals":["Nifty data unavailable"]}
    c=nh["close"]; cmp=c[-1]; s50=sma(c,50); s150=sma(c,150); s200=sma(c,200)
    r1m=pct(c,21); r3m=pct(c,63)
    if s200 and cmp>s200 and s50 and cmp>s50:
        regime="BULL-CAUTION" if (vix or 0)>22 else "BULL"; exposure=75 if (vix or 0)>22 else 100
    elif s200 and cmp>s200: regime="BULL-WEAK"; exposure=75
    elif s150 and cmp>s150: regime="TRANSITION"; exposure=50
    else: regime="BEAR"; exposure=25
    if (vix or 0)>30: exposure=min(exposure,25)
    elif (vix or 0)>22: exposure=min(exposure,50)
    sigs=[]
    sigs.append("Price > 50 SMA ✅" if (s50 and cmp>s50) else "Price < 50 SMA ⚠")
    sigs.append("Price > 200 SMA ✅" if (s200 and cmp>s200) else "Price < 200 SMA ❌")
    if r3m: sigs.append(f"Nifty 3M: {r3m:+.1f}%")
    if vix: sigs.append(f"VIX: {vix:.1f}")
    return {"regime":regime,"exposure":exposure,"cmp":round(cmp,2),"s50":round(s50 or 0,2),
            "s150":round(s150 or 0,2),"s200":round(s200 or 0,2),"r1m":round(r1m or 0,2),
            "r3m":round(r3m or 0,2),"vix":vix,"signals":sigs}

def sector_rotation(idx_data):
    sectors=[]
    for name,hist in idx_data.items():
        if "VIX" in name or not hist or "close" not in hist: continue
        c=hist["close"]; r1m=pct(c,21); r3m=pct(c,63); r6m=pct(c,126)
        s200=sma(c,200); cmp=c[-1]; ab200=cmp>s200 if s200 else False
        mom=(r1m or 0)*0.4+(r3m or 0)*0.4+(r6m or 0)*0.2
        tier="HOT" if mom>5 and ab200 else "WARM" if mom>0 else "COLD"
        sectors.append({"name":name.replace("NIFTY","").strip() or name,
                        "r1m":round(r1m or 0,2),"r3m":round(r3m or 0,2),"tier":tier,"momentum":round(mom,2)})
    return sorted(sectors,key=lambda x:x["momentum"],reverse=True)

def build_html(results,mkt,sectors,scan_time,total,found):
    results=sorted(results,key=lambda x:x["score"],reverse=True)
    tt7=sum(1 for r in results if r["tts"]>=7)
    vcp_c=sum(1 for r in results if r["vcp"])
    ap=sum(1 for r in results if r["grade"]=="A+")
    a_c=sum(1 for r in results if r["grade"]=="A")
    rc={"BULL":"#22c55e","BULL-WEAK":"#86efac","BULL-CAUTION":"#f59e0b","TRANSITION":"#fb923c","BEAR":"#ef4444","UNKNOWN":"#64748b"}
    regc=rc.get(mkt.get("regime","UNKNOWN"),"#64748b")
    sh=""
    for s in sectors[:9]:
        col="#22c55e" if s["tier"]=="HOT" else "#f59e0b" if s["tier"]=="WARM" else "#64748b"
        bg="rgba(34,197,94,.12)" if s["tier"]=="HOT" else "rgba(245,158,11,.1)" if s["tier"]=="WARM" else "rgba(100,116,139,.1)"
        sh+=f'<div style="background:{bg};border:1px solid {col}33;border-radius:8px;padding:10px 12px"><div style="font-size:10px;color:{col};font-weight:700">{s["tier"]}</div><div style="font-size:13px;font-weight:600;margin:3px 0">{s["name"]}</div><div style="font-family:monospace;font-size:10px;color:#94a3b8">1M:{s["r1m"]:+.1f}% 3M:{s["r3m"]:+.1f}%</div></div>'
    rows=""
    for i,s in enumerate(results):
        rk=i+1
        rnc="color:#f59e0b" if rk==1 else ("color:#94a3b8" if rk<=3 else "color:#a78bfa" if rk<=5 else "color:#64748b")
        dots="".join(f'<span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:{"#22c55e" if s["tt"][d] else "#1e293b"};margin-right:2px"></span>' for d in range(8))
        sc=s["score"]; scc="#22c55e" if sc>=75 else "#f59e0b" if sc>=50 else "#64748b"
        grc={"A+":"#4ade80","A":"#22c55e","B+":"#f59e0b","B":"#64748b"}.get(s["grade"],"#64748b")
        grb={"A+":"rgba(34,197,94,.2)","A":"rgba(34,197,94,.12)","B+":"rgba(245,158,11,.15)","B":"rgba(100,116,139,.1)"}.get(s["grade"],"rgba(100,116,139,.1)")
        r3c="#22c55e" if s["r3m"]>0 else "#ef4444"
        rsc="#22c55e" if s["rs"]>0 else "#ef4444"
        d2c="#22d3ee" if s["d200"]>0 else "#94a3b8"
        vcp='<span style="background:rgba(34,197,94,.15);color:#22c55e;padding:2px 6px;border-radius:3px;font-size:9px;font-weight:700;border:1px solid rgba(34,197,94,.3)">VCP</span>' if s["vcp"] else "—"
        rows+=f'<tr style="border-bottom:1px solid rgba(255,255,255,.05)"><td style="padding:7px 8px;font-family:monospace;font-size:10px;{rnc}">{rk}</td><td style="padding:7px 8px;font-weight:700;font-size:12px">{s["sym"]}</td><td style="padding:7px 8px;font-family:monospace;font-size:11px">₹{s["cmp"]:,.1f}</td><td style="padding:7px 8px">{dots}<div style="font-family:monospace;font-size:9px;color:#64748b">{s["tts"]}/8</div></td><td style="padding:7px 8px;font-family:monospace;font-weight:600;color:{scc}">{sc}</td><td style="padding:7px 8px"><span style="background:{grb};color:{grc};padding:2px 8px;border-radius:3px;font-size:10px;font-weight:700">{s["grade"]}</span></td><td style="padding:7px 8px;font-family:monospace;font-size:11px;color:{rsc}">{s["rs"]:+.2f}</td><td style="padding:7px 8px;font-family:monospace;font-size:11px;color:{r3c}">{s["r3m"]:+.1f}%</td><td style="padding:7px 8px;font-family:monospace;font-size:11px">{s["vq"]:.0f}%</td><td style="padding:7px 8px">{vcp}</td><td style="padding:7px 8px;font-family:monospace;font-size:11px;color:#94a3b8">{s["trisk"]:.1f}%</td><td style="padding:7px 8px;font-family:monospace;font-size:11px;color:{d2c}">{s["d200"]:+.1f}%</td><td style="padding:7px 8px;font-family:monospace;font-size:11px;color:#22c55e">₹{s["entry"]:,.2f}</td><td style="padding:7px 8px;font-family:monospace;font-size:11px;color:#ef4444">₹{s["stop"]:,.2f}</td><td style="padding:7px 8px;font-family:monospace;font-size:11px;color:#f59e0b">₹{s["t1"]:,.2f}</td><td style="padding:7px 8px;font-family:monospace;font-size:10px">₹{s["posval"]:,.0f}</td></tr>'
    sigs="".join(f'<div style="font-size:11px;color:#94a3b8;margin-bottom:3px">{sg}</div>' for sg in mkt.get("signals",[]))
    eff=round(CAPITAL*mkt.get("exposure",75)/100/100000,1)
    r1m=mkt.get("r1m",0) or 0; r3m=mkt.get("r3m",0) or 0; vx=mkt.get("vix") or 0
    r1c="#22c55e" if r1m>0 else "#ef4444"; r3c2="#22c55e" if r3m>0 else "#ef4444"
    vxc="#ef4444" if vx>20 else "#22c55e"; vxd=f"{vx:.1f}" if vx else "—"
    stats_items=[(total,"Scanned","#e2e8f0"),(found,"IDs found","#94a3b8"),(len(results),"Qualified","#e2e8f0"),(tt7,"TT 7-8","#22c55e"),(vcp_c,"VCP","#f59e0b"),(ap,"A+ Grade","#a78bfa"),(a_c,"A Grade","#3b82f6")]
    sthtml="".join(f'<div style="padding:12px 14px;border-right:1px solid rgba(255,255,255,.07)"><div style="font-family:monospace;font-size:19px;font-weight:600;color:{c}">{v}</div><div style="font-size:9px;color:#64748b;margin-top:2px;text-transform:uppercase;letter-spacing:.05em">{l}</div></div>' for v,l,c in stats_items)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Gaurav's Trading Dashboard — {scan_time}</title>
<style>@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0a0e1a;color:#e2e8f0;font-family:'IBM Plex Sans',sans-serif;font-size:13px}}.tw{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;font-size:11px}}th{{background:#0f1525;color:#64748b;font-size:9px;text-transform:uppercase;letter-spacing:.07em;padding:8px 8px;text-align:left;border-bottom:1px solid rgba(255,255,255,.1);white-space:nowrap;position:sticky;top:0;z-index:5}}tr:hover td{{background:rgba(255,255,255,.03)}}</style></head><body>
<div style="background:#0f1525;border-bottom:1px solid rgba(255,255,255,.07);padding:14px 20px;display:flex;justify-content:space-between;align-items:center"><div style="display:flex;align-items:center;gap:12px"><div style="width:36px;height:36px;border-radius:8px;background:rgba(34,197,94,.12);border:1px solid #22c55e;display:flex;align-items:center;justify-content:center;font-family:monospace;font-size:12px;color:#22c55e;font-weight:700">GT</div><div><div style="font-size:15px;font-weight:600">Gaurav's Trading System</div><div style="font-size:9px;color:#64748b;font-family:monospace;margin-top:2px">NIFTY 500 · MINERVINI SEPA · DHAN API · {scan_time}</div></div></div><div style="font-family:monospace;font-size:10px;color:#64748b">₹{CAPITAL//100000}L Capital · 1% Risk · Auto-updated 4:30 PM IST</div></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1px;background:rgba(255,255,255,.07);border-bottom:1px solid rgba(255,255,255,.07)"><div style="background:#0a0e1a;padding:18px 20px"><div style="font-size:9px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:8px">Market regime</div><div style="font-size:26px;font-weight:700;color:{regc};margin-bottom:4px">{mkt.get("regime","—")}</div><div style="display:flex;align-items:center;gap:8px;margin-bottom:12px"><span style="font-size:11px;color:#94a3b8">Deploy:</span><span style="font-size:16px;font-weight:700;color:{regc}">{mkt.get("exposure",75)}%</span><span style="font-size:11px;color:#64748b">= ₹{eff}L active</span></div>{sigs}</div><div style="background:#0a0e1a;padding:18px 20px"><div style="font-size:9px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">Nifty 50 levels</div><div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px"><div><div style="font-size:9px;color:#64748b">CMP</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px">{mkt.get("cmp","—")}</div></div><div><div style="font-size:9px;color:#64748b">50 SMA</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px">{mkt.get("s50","—")}</div></div><div><div style="font-size:9px;color:#64748b">200 SMA</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px">{mkt.get("s200","—")}</div></div><div><div style="font-size:9px;color:#64748b">1M Ret</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px;color:{r1c}">{r1m:+.1f}%</div></div><div><div style="font-size:9px;color:#64748b">3M Ret</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px;color:{r3c2}">{r3m:+.1f}%</div></div><div><div style="font-size:9px;color:#64748b">VIX</div><div style="font-family:monospace;font-size:14px;font-weight:600;margin-top:2px;color:{vxc}">{vxd}</div></div></div></div></div>
<div style="display:grid;grid-template-columns:repeat(7,1fr);border-bottom:1px solid rgba(255,255,255,.07)">{sthtml}</div>
<div style="padding:14px 20px;border-bottom:1px solid rgba(255,255,255,.07)"><div style="font-size:9px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">Sectoral rotation</div><div style="display:grid;grid-template-columns:repeat(9,1fr);gap:6px">{sh}</div></div>
<div class="tw"><table><thead><tr><th>#</th><th>Symbol</th><th>CMP</th><th>TT Score</th><th>Score</th><th>Grade</th><th>RS Filter</th><th>3M Ret</th><th>Vol Qual</th><th>VCP</th><th>Trade Risk</th><th>Dist 200</th><th>Entry</th><th>Stop</th><th>T1 (2R)</th><th>Pos Size</th></tr></thead><tbody>{rows}</tbody></table></div>
<div style="padding:8px 20px;border-top:1px solid rgba(255,255,255,.07);display:flex;justify-content:space-between;font-size:9px;color:#64748b;font-family:monospace;background:#0f1525"><span>Dhan API · NSE EOD · Minervini SEPA · VIX-adjusted · Auto-generated daily</span><span>Not financial advice · {scan_time}</span></div>
</body></html>"""

def main():
    print("="*60)
    print("  GAURAV'S TRADING SYSTEM v3")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M IST')}")
    print("="*60)
    if not ACCESS_TOKEN:
        print("ERROR: DHAN_ACCESS_TOKEN not set"); sys.exit(1)

    print("\n[0/3] Auto-fetching security IDs from Dhan master...")
    id_map = get_security_ids(NIFTY500_SYMBOLS)

    print("\n[1/3] Fetching index data...")
    idx_id_map = get_index_ids()
    print(f"  Index master keys: {list(idx_id_map.keys())[:8]}")

    nifty_sid = (idx_id_map.get("NIFTY 50") or idx_id_map.get("NIFTY50") or "13")
    print(f"  Nifty 50 SID: {nifty_sid}")
    nh = dhan_hist(nifty_sid, seg="IDX_I", days=300, instrument="INDEX")
    if not nh: nh = dhan_hist(nifty_sid, seg="NSE_EQ", days=300, instrument="EQUITY")
    print(f"  Nifty 50: {'OK ' + str(len(nh.get('close',[]))) + ' candles' if nh else 'FAILED'}")

    vix_sid = idx_id_map.get("INDIA VIX") or idx_id_map.get("INDIAVIX") or "50"
    vh = dhan_hist(vix_sid, seg="IDX_I", days=30, instrument="INDEX")
    vix_val = vh["close"][-1] if vh and "close" in vh else None
    print(f"  VIX: {vix_val}")

    idx_hist = {}
    for sname in ["BANKNIFTY","NIFTY BANK","NIFTYIT","NIFTY IT","NIFTYPHARMA","NIFTY PHARMA",
                  "NIFTYAUTO","NIFTY AUTO","NIFTYFMCG","NIFTY FMCG","NIFTYMETAL","NIFTY METAL",
                  "NIFTYREALTY","NIFTY REALTY"]:
        sid2 = idx_id_map.get(sname)
        if sid2:
            h2 = dhan_hist(sid2, seg="IDX_I", days=300, instrument="INDEX")
            if h2:
                clean_name = sname.replace("NIFTY ","NIFTY").replace(" ","")
                idx_hist[clean_name] = h2
                print(f"  {clean_name}: OK")
            time.sleep(0.3)

    mkt = market_direction(nh, vix_val)
    sectors = sector_rotation(idx_hist)
    print(f"  Regime: {mkt['regime']} | Exposure: {mkt['exposure']}%")

    print(f"\n[2/3] Fetching live prices for {len(id_map)} stocks...")
    ltp_raw = dhan_ltp(list(id_map.values()))
    ltp_by_sid = {str(k): v for k, v in ltp_raw.items()}
    print(f"  Got LTP for {len(ltp_by_sid)} stocks")

    print(f"\n[3/3] Analysing {len(id_map)} stocks...")
    results = []
    sym_list = list(id_map.items())
    for i, (sym, sid) in enumerate(sym_list):
        ltp = ltp_by_sid.get(str(sid))
        hist = dhan_hist(str(sid), seg="NSE_EQ", days=280, instrument="EQUITY")
        if hist:
            r = analyse(sym, sid, hist, ltp)
            if r: results.append(r)
        pct_done = (i+1)/len(sym_list)*100
        print(f"  [{i+1:>3}/{len(sym_list)}] {sym:<15} {pct_done:.0f}% | OK:{len(results)}", end="\r")
        time.sleep(0.12)
        if (i+1) % 30 == 0: time.sleep(1)

    scan_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M IST")
    print(f"\n\n  Done — {len(results)} qualified")
    if results:
        top = sorted(results, key=lambda x: x["score"], reverse=True)[:5]
        print("  TOP 5:")
        for i,s in enumerate(top):
            print(f"  {i+1}. {s['sym']:<15} Score:{s['score']} Grade:{s['grade']} TT:{s['tts']}/8 CMP:₹{s['cmp']}")

    html = build_html(results, mkt, sectors, scan_time, len(NIFTY500_SYMBOLS), len(id_map))
    out = Path("docs/index.html"); out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"  Dashboard → docs/index.html")
    print("="*60)

if __name__ == "__main__":
    main()
