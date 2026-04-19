"""
SwingAI v2 — Notification Engine
Full 4-section daily brief via Telegram + Gmail

Sections:
  1. Macro Market View     (Nifty trend, VIX, breadth)
  2. Sector Rotation       (leading vs lagging)
  3. Capital Allocation    (how much to deploy, position sizing)
  4. Stock Setups          (Minervini SEPA setups)

Setup:
  export GMAIL_USER=your@gmail.com
  export GMAIL_PASS=your_app_password
  export TELEGRAM_TOKEN=your_bot_token
  export TELEGRAM_CHAT_ID=your_chat_id
  export RECIPIENTS=a@gmail.com,b@gmail.com  (optional extra recipients)
"""

import json, os, smtplib, urllib.request, urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
SCAN_JSON = os.path.join(BASE_DIR, "scan_results.json")

# ── Auto-load .env ────────────────────────────────────────────────────────────
def _load_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
_load_env()

GMAIL_USER       = os.environ.get("GMAIL_USER", "")
GMAIL_PASS       = os.environ.get("GMAIL_PASS", "")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
RECIPIENTS       = [r.strip() for r in os.environ.get("RECIPIENTS", "").split(",") if r.strip()]

GRADE_EMOJI = {"A+": "🏆", "A": "🥇", "B+": "🥈", "B": "🥉", "C": "📌"}
GRADE_COLOR = {"A+": "#ffd700", "A": "#00ff9d", "B+": "#00d4ff", "B": "#a855f7", "C": "#64748b"}


# ── LOAD DATA ─────────────────────────────────────────────────────────────────
def load_scan():
    if not os.path.exists(SCAN_JSON):
        raise FileNotFoundError("scan_results.json not found. Run screener first.")
    with open(SCAN_JSON) as f:
        return json.load(f)


# ── TELEGRAM FORMATTER ────────────────────────────────────────────────────────
def format_telegram(data, macro=None, sectors=None, allocation=None):
    results = data.get("results", [])
    date    = data.get("scan_date", datetime.now().strftime("%Y-%m-%d"))
    aplus   = [r for r in results if r["grade"] == "A+"]
    a_grade = [r for r in results if r["grade"] == "A"]
    bplus   = [r for r in results if r["grade"] == "B+"]
    vcps    = [r for r in results if r["is_vcp"]]
    top     = aplus + a_grade

    lines = [
        f"SwingAI Daily Brief -- {date}",
        "Say What Data Says",
        "=" * 30,
        "",
    ]

    # Section 1: Macro
    if macro:
        n5      = macro.get("nifty500", {})
        n50     = macro.get("nifty50",  {})
        vix     = macro.get("vix",      {})
        breadth = macro.get("breadth",  {})
        chg_1d  = n5.get("chg_1d")
        chg_str = f" ({'+' if chg_1d and chg_1d > 0 else ''}{chg_1d}%)" if chg_1d else ""
        lines += [
            "SECTION 1 -- MACRO VIEW",
            f"Market: {macro.get('macro_label','—')} ({macro.get('macro_score','—')}/100)",
            "-" * 28,
            f"Nifty 500: Rs{n5.get('price','—')}{chg_str}",
            f"Trend: {n5.get('stage','—')}",
            f"MA50: Rs{n5.get('ma50','—')}  MA200: Rs{n5.get('ma200','—')}",
            f"1W: {n5.get('chg_1w','—')}%  1M: {n5.get('chg_1m','—')}%",
            f"Nifty 50: Rs{n50.get('price','—')} | Trend: {n50.get('stage','—')}",
            f"VIX: {vix.get('value','—')} -- {vix.get('signal','—')}",
            f"Breadth (above 200MA): {breadth.get('above_200_pct','—')}%",
            f"Breadth (above 50MA):  {breadth.get('above_50_pct','—')}%",
            f"Signal: {breadth.get('signal','—')}",
            "",
        ]
    else:
        lines += ["SECTION 1 -- MACRO VIEW", "Data unavailable", ""]

    # Section 2: Sectors
    if sectors:
        def _arrow(val):
            if val is None: return "—"
            return f"{'+' if val>0 else ''}{val:.1f}%"
        lines += [
            "SECTION 2 -- SECTOR ROTATION",
            f"Rotation: {sectors.get('rotation_type','—')}",
            "-" * 28,
            "Top Sectors:",
        ]
        for s in sectors.get("leaders", []):
            lines.append(f"  {s['sector']:<16} 1M:{_arrow(s.get('momentum_1m'))} 3M:{_arrow(s.get('momentum_3m'))}")
        lines += ["", "Bottom Sectors:"]
        for s in sectors.get("laggards", []):
            lines.append(f"  {s['sector']:<16} 1M:{_arrow(s.get('momentum_1m'))} 3M:{_arrow(s.get('momentum_3m'))}")
        lines += ["", f"Signal: {sectors.get('rotation_signal','—')}", ""]
    else:
        lines += ["SECTION 2 -- SECTOR ROTATION", "Data unavailable", ""]

    # Section 3: Allocation
    if allocation:
        gs = allocation.get("grade_sizing", {})
        lines += [
            "SECTION 3 -- CAPITAL ALLOCATION",
            f"Health: {allocation.get('health_score','—')}/100 -- {allocation.get('tier_label','—')}",
            "-" * 28,
            f"Portfolio:  Rs{allocation.get('portfolio_inr',0):>10,.0f}",
            f"Deploy Now: Rs{allocation.get('deploy_inr',0):>10,.0f} ({allocation.get('deploy_pct',0)}%)",
            f"Keep Cash:  Rs{allocation.get('cash_inr',0):>10,.0f} ({allocation.get('cash_pct',0)}%)",
            f"Max Positions: {allocation.get('max_positions','—')}",
            f"Risk/Trade: Rs{allocation.get('risk_per_trade_inr',0):,.0f}",
            f"Max Pos:    Rs{allocation.get('max_position_size_inr',0):,.0f}",
            f"Sizing: A+=Rs{gs.get('A+',{}).get('position_inr',0):,.0f} A=Rs{gs.get('A',{}).get('position_inr',0):,.0f} B+=Rs{gs.get('B+',{}).get('position_inr',0):,.0f}",
            "",
            "Rules:",
        ]
        for rule in allocation.get("key_rules", []):
            lines.append(f"  {rule}")
        lines.append("")
    else:
        lines += ["SECTION 3 -- CAPITAL ALLOCATION", "Data unavailable", ""]

    # Section 4: Setups
    lines += [
        "SECTION 4 -- STOCK SETUPS (MINERVINI SEPA)",
        f"Nifty 500 | {data.get('universe_size','—')} stocks",
        f"Setups: {len(results)} | A+:{len(aplus)} A:{len(a_grade)} B+:{len(bplus)} VCP:{len(vcps)}",
        "-" * 28,
    ]
    if not top:
        lines.append("No A/A+ setups today. Stay patient.")
    else:
        for r in top[:6]:
            vcp = " [VCP]" if r["is_vcp"] else ""
            lines += [
                f"[{r['grade']}] {r['ticker']}{vcp}",
                f"  Rs{r['price']:.2f} -> Entry:Rs{r['entry']:.2f} Stop:Rs{r['stop']:.2f} Target:Rs{r['target_2r']:.2f}",
                f"  Risk:{r['risk_pct']}% R:{r['r_multiple']} RS:{r['rs_rank']}",
                "",
            ]

    lines.append("Minervini SEPA -- Not financial advice")
    msg = "\n".join(lines)
    if len(msg) > 4000:
        msg = msg[:3950] + "\n\n[truncated -- see email for full details]"
    return msg


# ── EMAIL HTML FORMATTER ──────────────────────────────────────────────────────
def format_email_html(data, macro=None, sectors=None, allocation=None):
    results = data.get("results", [])
    date    = data.get("scan_date", datetime.now().strftime("%Y-%m-%d"))
    top     = [r for r in results if r["grade"] in ("A+", "A", "B+")]

    aplus = sum(1 for r in results if r["grade"] == "A+")
    a_cnt = sum(1 for r in results if r["grade"] == "A")
    vcps  = sum(1 for r in results if r["is_vcp"])

    macro_score = macro.get("macro_score", "—") if macro else "—"
    macro_label = macro.get("macro_label", "—") if macro else "—"
    deploy_pct  = allocation.get("deploy_pct", "—") if allocation else "—"
    cash_pct    = allocation.get("cash_pct", "—") if allocation else "—"
    rotation    = sectors.get("rotation_type", "—") if sectors else "—"

    rows = ""
    for r in top[:15]:
        color = GRADE_COLOR.get(r["grade"], "#64748b")
        vcp   = "VCP" if r["is_vcp"] else "—"
        rows += f"""<tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:8px;"><span style="background:{color}22;color:{color};border:1px solid {color}55;padding:2px 8px;border-radius:5px;font-weight:800;font-size:11px;">{r['grade']}</span></td>
          <td style="padding:8px;font-weight:700;">{r['ticker']}</td>
          <td style="padding:8px;">&#8377;{r['price']:.2f}</td>
          <td style="padding:8px;color:#00ff9d;font-weight:700;">&#8377;{r['entry']:.2f}</td>
          <td style="padding:8px;color:#ff4d6d;font-weight:700;">&#8377;{r['stop']:.2f}</td>
          <td style="padding:8px;">&#8377;{r['target_2r']:.2f}</td>
          <td style="padding:8px;font-weight:700;">{r['r_multiple']}R</td>
          <td style="padding:8px;">{r['risk_pct']}%</td>
          <td style="padding:8px;">{r['rs_rank']}</td>
          <td style="padding:8px;">{vcp}</td>
        </tr>"""

    if not rows:
        rows = '<tr><td colspan="10" style="padding:20px;text-align:center;color:#64748b;">No qualifying setups today.</td></tr>'

    sector_rows = ""
    if sectors:
        for s in sectors.get("sectors", [])[:12]:
            def _arrow_html(val):
                if val is None: return "—"
                c = "#00ff9d" if val > 0 else "#ff4d6d"
                sign = "+" if val > 0 else ""
                return f'<span style="color:{c}">{sign}{val:.1f}%</span>'
            rank_color = "#ffd700" if s["rank"] <= 3 else ("#ff4d6d" if s["rank"] >= len(sectors.get("sectors", [])) - 2 else "#94a3b8")
            sector_rows += f"""<tr style="border-bottom:1px solid #1e293b;">
              <td style="padding:8px;text-align:center;color:{rank_color};font-weight:700;">#{s['rank']}</td>
              <td style="padding:8px;font-weight:600;">{s['sector']}</td>
              <td style="padding:8px;">{_arrow_html(s.get('momentum_1m'))}</td>
              <td style="padding:8px;">{_arrow_html(s.get('momentum_3m'))}</td>
              <td style="padding:8px;font-size:11px;color:#64748b;">{round(s.get('score') or 0, 1)}</td>
            </tr>"""

    macro_html = ""
    if macro:
        n5 = macro.get("nifty500", {})
        n50 = macro.get("nifty50", {})
        vix = macro.get("vix", {})
        breadth = macro.get("breadth", {})
        def _chg_span(val):
            if val is None: return "—"
            c = "#00ff9d" if val > 0 else "#ff4d6d"
            s = "+" if val > 0 else ""
            return f'<span style="color:{c}">{s}{val}%</span>'
        macro_html = f"""<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px;">
          <div style="background:#111827;border-radius:10px;padding:18px;border:1px solid #1e293b;">
            <div style="font-weight:700;margin-bottom:8px;color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Nifty 500</div>
            <div style="font-size:22px;font-weight:900;">&#8377;{n5.get('price','—')}</div>
            <div style="margin-top:4px;">{_chg_span(n5.get('chg_1d'))} today &nbsp;|&nbsp; {_chg_span(n5.get('chg_1m'))} 1M</div>
            <div style="margin-top:6px;font-size:12px;color:#64748b;">{n5.get('stage','—')}</div>
            <div style="font-size:12px;color:#64748b;">MA50:&#8377;{n5.get('ma50','—')} | MA200:&#8377;{n5.get('ma200','—')}</div>
          </div>
          <div style="background:#111827;border-radius:10px;padding:18px;border:1px solid #1e293b;">
            <div style="font-weight:700;margin-bottom:8px;color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:1px;">VIX &amp; Breadth</div>
            <div style="font-size:22px;font-weight:900;">{vix.get('value','—')}</div>
            <div style="margin-top:4px;font-size:12px;">{vix.get('signal','—')}</div>
            <div style="margin-top:6px;font-size:12px;color:#64748b;">Above 200MA: {breadth.get('above_200_pct','—')}%</div>
            <div style="font-size:12px;color:#64748b;">Above 50MA:  {breadth.get('above_50_pct','—')}%</div>
            <div style="font-size:12px;margin-top:4px;">{breadth.get('signal','—')}</div>
          </div>
        </div>"""

    alloc_html = ""
    if allocation:
        deploy_inr = allocation.get("deploy_inr", 0)
        cash_inr   = allocation.get("cash_inr", 0)
        deploy_bar = int(allocation.get("deploy_pct", 0))
        gs         = allocation.get("grade_sizing", {})
        rules_html = "".join(f'<div style="padding:4px 0;font-size:13px;">{r}</div>' for r in allocation.get("key_rules", []))
        alloc_html = f"""<div style="background:#111827;border-radius:10px;padding:18px;border:1px solid #1e293b;margin-bottom:20px;">
          <div style="font-weight:700;margin-bottom:14px;font-size:15px;">Capital Allocation — {allocation.get('tier_label','')}</div>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px;">
            <div style="text-align:center;"><div style="font-size:26px;font-weight:900;color:#00ff9d;">{allocation.get('deploy_pct',0)}%</div><div style="font-size:11px;color:#64748b;text-transform:uppercase;">Deploy</div><div style="font-size:12px;">&#8377;{deploy_inr:,.0f}</div></div>
            <div style="text-align:center;"><div style="font-size:26px;font-weight:900;color:#ffd700;">{allocation.get('cash_pct',0)}%</div><div style="font-size:11px;color:#64748b;text-transform:uppercase;">Cash</div><div style="font-size:12px;">&#8377;{cash_inr:,.0f}</div></div>
            <div style="text-align:center;"><div style="font-size:26px;font-weight:900;color:#00d4ff;">{allocation.get('max_positions',0)}</div><div style="font-size:11px;color:#64748b;text-transform:uppercase;">Max Positions</div><div style="font-size:12px;">&#8377;{allocation.get('risk_per_trade_inr',0):,.0f}/trade</div></div>
          </div>
          <div style="margin-bottom:10px;"><div style="font-size:12px;color:#64748b;margin-bottom:4px;">Deployment ({deploy_bar}%)</div>
            <div style="background:#1e293b;border-radius:4px;height:8px;overflow:hidden;"><div style="background:linear-gradient(90deg,#00ff9d,#00d4ff);height:100%;width:{deploy_bar}%;border-radius:4px;"></div></div>
          </div>
          <div style="font-size:13px;color:#94a3b8;margin-bottom:10px;">
            A+ = &#8377;{gs.get('A+',{}).get('position_inr',0):,.0f} &nbsp;|&nbsp;
            A = &#8377;{gs.get('A',{}).get('position_inr',0):,.0f} &nbsp;|&nbsp;
            B+ = &#8377;{gs.get('B+',{}).get('position_inr',0):,.0f}
          </div>
          <div style="border-top:1px solid #1e293b;padding-top:10px;">{rules_html}</div>
        </div>"""

    kpis = "".join(f"""<div style="background:#111827;border-radius:8px;padding:14px;text-align:center;border:1px solid #1e293b;">
      <div style="font-size:26px;font-weight:900;color:{c};">{v}</div>
      <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-top:4px;">{l}</div>
    </div>""" for v, l, c in [
        (aplus, "A+ Setups", "#ffd700"),
        (a_cnt, "A Grade",   "#00ff9d"),
        (vcps,  "VCP",       "#00d4ff"),
        (len(results), "Total", "#a855f7"),
    ])

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="margin:0;padding:0;background:#0a0e1a;font-family:'Segoe UI',system-ui,sans-serif;color:#e2e8f0;">
<div style="max-width:860px;margin:0 auto;padding:20px;">
  <div style="background:linear-gradient(135deg,#0f172a,#1e1b4b);border-radius:12px;padding:28px 32px;margin-bottom:20px;">
    <div style="font-size:26px;font-weight:900;">SwingAI Daily Brief</div>
    <div style="color:#64748b;margin-top:6px;font-size:14px;">{date} &middot; Minervini SEPA &middot; Complete Advisory</div>
    <div style="margin-top:12px;font-size:13px;color:#94a3b8;">
      Market: <b>{macro_label}</b> ({macro_score}/100) &nbsp;&nbsp;
      Rotation: <b>{rotation}</b> &nbsp;&nbsp;
      Deploy: <b>{deploy_pct}%</b> | Cash: <b>{cash_pct}%</b>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;">{kpis}</div>
  <div style="font-weight:700;font-size:15px;margin-bottom:12px;">Section 1 — Macro Market View</div>
  {macro_html}
  <div style="background:#111827;border-radius:12px;border:1px solid #1e293b;overflow:hidden;margin-bottom:20px;">
    <div style="padding:16px 20px;font-weight:700;font-size:15px;border-bottom:1px solid #1e293b;">Section 2 — Sector Rotation <span style="float:right;font-size:12px;color:#64748b;font-weight:400;">{rotation}</span></div>
    <div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;">
      <thead><tr style="background:#0a0e1a;">{"".join(f'<th style="padding:8px;text-align:left;font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:1px;">{h}</th>' for h in ["#","Sector","1M","3M","Score"])}</tr></thead>
      <tbody>{sector_rows}</tbody>
    </table></div>
  </div>
  <div style="font-weight:700;font-size:15px;margin-bottom:12px;">Section 3 — Capital Allocation</div>
  {alloc_html}
  <div style="background:#111827;border-radius:12px;border:1px solid #1e293b;overflow:hidden;margin-bottom:20px;">
    <div style="padding:16px 20px;font-weight:700;font-size:15px;border-bottom:1px solid #1e293b;">Section 4 — Stock Setups (Minervini SEPA)</div>
    <div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;">
      <thead><tr style="background:#0a0e1a;">{"".join(f'<th style="padding:8px;text-align:left;font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:1px;white-space:nowrap;">{h}</th>' for h in ["Grade","Ticker","Price","Entry","Stop","Target","R","Risk%","RS","VCP"])}</tr></thead>
      <tbody>{rows}</tbody>
    </table></div>
  </div>
  <div style="text-align:center;color:#475569;font-size:11px;padding:12px;">SwingAI &middot; Minervini SEPA &middot; Not financial advice &middot; {date}</div>
</div></body></html>"""


# ── SEND TELEGRAM ──────────────────────────────────────────────────────────────
def send_telegram(data, macro=None, sectors=None, allocation=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("  ⚠ Telegram not configured. Set TELEGRAM_TOKEN + TELEGRAM_CHAT_ID.")
        return False

    msg = format_telegram(data, macro=macro, sectors=sectors, allocation=allocation)
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": msg}).encode()

    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        if result.get("ok"):
            print("  ✓ Telegram sent")
            return True
        print(f"  ✗ Telegram error: {result}")
        return False
    except Exception as e:
        print(f"  ✗ Telegram failed: {e}")
        return False


# ── SEND EMAIL ─────────────────────────────────────────────────────────────────
def send_email(data, macro=None, sectors=None, allocation=None):
    if not GMAIL_USER or not GMAIL_PASS:
        print("  ⚠ Gmail not configured. Set GMAIL_USER + GMAIL_PASS env vars.")
        return False

    to_list = RECIPIENTS if RECIPIENTS else [GMAIL_USER]
    date    = data.get("scan_date", "today")
    n       = len(data.get("results", []))
    macro_label = macro.get("macro_label", "") if macro else ""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"SwingAI Daily Brief -- {date} | {macro_label} | {n} Setups"
    msg["From"]    = f"SwingAI <{GMAIL_USER}>"
    msg["To"]      = ", ".join(to_list)
    msg.attach(MIMEText(format_email_html(data, macro=macro, sectors=sectors, allocation=allocation), "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_PASS)
            s.sendmail(GMAIL_USER, to_list, msg.as_string())
        print(f"  ✓ Email sent -> {', '.join(to_list)}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("  ✗ Gmail auth failed. Use App Password: myaccount.google.com -> Security -> App Passwords")
        return False
    except Exception as e:
        print(f"  ✗ Email error: {e}")
        return False


# ── MAIN ──────────────────────────────────────────────────────────────────────
def save_daily_brief_html(data, macro=None, sectors=None, allocation=None):
    """Save today's visual HTML brief to daily_brief_visual.html (auto-updated each morning)."""
    try:
        date_str = data.get("scan_date", datetime.now().strftime("%Y-%m-%d"))
        out_path = os.path.join(BASE_DIR, "daily_brief_visual.html")
        html = format_email_html(data, macro=macro, sectors=sectors, allocation=allocation)
        with open(out_path, "w") as f:
            f.write(html)
        print(f"  ✓ Visual brief saved → daily_brief_visual.html ({date_str})")
    except Exception as e:
        print(f"  ⚠ Visual brief save failed: {e}")


def run_notifications(data=None, macro=None, sectors=None, allocation=None):
    print(f"\n{'='*50}")
    print(f"  SwingAI v2 -- Notification Engine")
    print(f"{'='*50}")
    if data is None:
        print("  Loading scan_results.json...")
        data = load_scan()
    n = len(data.get("results", []))
    print(f"  Scan: {data.get('scan_date','—')} | Setups: {n}")
    print()
    print("  Telegram (4-section brief)...")
    send_telegram(data, macro=macro, sectors=sectors, allocation=allocation)
    print("  Email (full HTML brief)...")
    send_email(data, macro=macro, sectors=sectors, allocation=allocation)
    print("  Saving visual brief HTML...")
    save_daily_brief_html(data, macro=macro, sectors=sectors, allocation=allocation)
    print()


if __name__ == "__main__":
    run_notifications()
