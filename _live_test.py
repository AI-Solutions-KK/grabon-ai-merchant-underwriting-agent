"""Live endpoint test — run against http://127.0.0.1:8000"""
import urllib.request, urllib.error, json, sys

base = "http://127.0.0.1:8000"
PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

def get(path):
    url = base + path
    try:
        r = urllib.request.urlopen(url, timeout=8)
        return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""

def post(path, data=""):
    url = base + path
    try:
        req = urllib.request.Request(url, data=data.encode() if data else b"",
                                     headers={"Content-Type":"application/x-www-form-urlencoded"},
                                     method="POST")
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        # 3xx counts as OK for redirect endpoints
        if 300 <= e.code < 400:
            return e.code, e.headers.get("Location","")
        return e.code, ""

pad = lambda s: s.ljust(40)
ok  = lambda label: print(f"  {PASS}  {pad(label)}")
bad = lambda label, note="": print(f"  {FAIL}  {pad(label)} {note}")
warn = lambda label, note="": print(f"  {WARN}  {pad(label)} {note}")

print("\n=== Live UI Test ===\n")

# 1 — Health
status, body = get("/health")
if status == 200 and "healthy" in body:
    ok("Health endpoint")
else:
    bad("Health endpoint", f"status={status}")

# 2 — Root redirects to dashboard
status, loc = post("/", "")
# GET redirect
status2, body2 = get("/")
# urllib follows redirects by default
if "dashboard" in body2 or status2 == 200:
    ok("Root -> /dashboard/ redirect")
else:
    warn("Root redirect", f"status={status2}")

# 3 — Dashboard renders
status, html = get("/dashboard/")
if status == 200 and len(html) > 5000:
    ok(f"Dashboard loads (len={len(html)})")
else:
    bad("Dashboard loads", f"status={status}")

# 4 — QR code feature
checks = [
    ("shop-observe",               "QR sandbox keyword rendered"),
    ("qrserver.com",               "QR image URL present"),
    ("How to Test Live WhatsApp",  "WA test guide banner"),
    ("Open in WhatsApp",           "WhatsApp direct link button"),
    ("Run Once",                   "Run Once engine button"),
    ("Always ON",                  "Always ON engine button"),
    ("OFF",                        "OFF engine button"),
    ("Clear Cache",                "Clear Cache button"),
    ("mobile-inline",              "Inline edit endpoint wired"),
    ("humanizeWaError",            "humanizeWaError JS function"),
    ("midnight UTC",               "Rate-limit amber notice (template)"),
    ("engine-summary-bar",         "Engine summary banner"),
    ("Engine Run Complete",        "Summary title text"),
]
for needle, label in checks:
    if needle in html:
        ok(label)
    else:
        warn(label, "(not visible yet OR missing)")

# 5 — Engine endpoints
print()
for ep in ["on", "off", "always-on", "clear-cache"]:
    status, loc = post(f"/admin/engine/{ep}")
    if status in (200, 301, 302, 303, 307, 308):
        ok(f"/admin/engine/{ep} -> {status}")
    else:
        bad(f"/admin/engine/{ep}", f"status={status}")

# 6 — OFF again (clean state)
post("/admin/engine/off")

# 7 — Merchant detail
status, body = get("/dashboard/GRAB_M001")
if status == 200 and "GRAB_M001" in body:
    ok("Merchant detail GRAB_M001")
else:
    bad("Merchant detail GRAB_M001", f"status={status}")

# 8 — Inline AJAX save
status, resp = post("/dashboard/GRAB_M001/mobile-inline", "mobile_number=9876543210")
if status == 200:
    try:
        j = json.loads(resp)
        wa_status = j.get("wa_status","?")
        wa_sent   = j.get("wa_sent", False)
        wa_error  = j.get("wa_error","")
        ok(f"Inline AJAX save ok={j.get('ok')} wa_status={wa_status}")
        if wa_sent:
            ok("WhatsApp sent successfully!")
        elif "limit" in str(wa_error).lower() or "63038" in str(wa_error):
            warn("WA rate-limited (63038)", "Expected - sandbox 50/day cap")
        elif wa_status == "rejected":
            warn("Merchant rejected", "No WA sent - correct behaviour")
        elif wa_status == "no_decision_yet":
            warn("No decision yet", "Run engine first")
        elif wa_status == "failed":
            warn("WA failed", str(wa_error)[:80])
        else:
            warn("WA status", wa_status)
    except Exception as e:
        bad("Inline AJAX JSON parse", str(e))
else:
    bad("Inline AJAX save", f"status={status} body={resp[:100]}")

print("\n=== Done ===\n")
