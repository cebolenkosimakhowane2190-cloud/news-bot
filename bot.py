import re, os, json, time, urllib.request
import xml.etree.ElementTree as ET

FEEDS = [
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "https://www.investing.com/rss/news_1.rss",
]

ASSETS = {
    "GOLD":   ["gold", "bullion", "xau", "safe haven", "safe-haven"],
    "NASDAQ": ["nasdaq", "tech stocks", "big tech", "nvidia", "apple", "microsoft", "tesla", "chips?"],
    "USDJPY": ["yen", "usd/jpy", "usdjpy", "bank of japan", "boj", "japan", "dollar", "fed"],
}

def topics(headline):
    text = headline.lower()
    return [a for a, keys in ASSETS.items()
            if any(re.search(r"\b" + k + r"\b", text) for k in keys)]

BULL = {
    "NASDAQ": {"rally", "rallies", "record", "beats", "surge", "surges", "ai boom"},
    "GOLD":   {"war", "geopolitical"},
}
BEAR = {
    "NASDAQ": {"selloff", "plunge", "plunges", "slump", "tariff", "tariffs", "miss", "misses", "bubble"},
}

def direction(headline, asset):
    text = headline.lower()
    bull = sum(p in text for p in BULL.get(asset, ()))
    bear = sum(p in text for p in BEAR.get(asset, ()))
    if bull > bear: return "⬆️ BULLISH"
    if bear > bull: return "⬇️ BEARISH"
    return None

def fetch_headlines(url, limit=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        root = ET.fromstring(r.read())
    titles = [(i.findtext("title") or "").strip() for i in root.iter("item")]
    return [t for t in titles if t][:limit]

# ================= MACRO ENGINE =================
def has(p, t): return re.search(p, t) is not None

G, J, N = "GOLD", "USDJPY", "NASDAQ"
HAWK = {G: -1, J: +1, N: -1}
DOVE = {G: +1, J: -1, N: +1}

FLIP   = r"\b(fade|fades|fading|dim|dims|wane|wanes|pare|pares|fewer|unlikely|delay|delays|rules? out|ruled out|pushes? back|doubts?)\b"
NOT_US = (r"\b(boj|bank of japan|japan\w*|ueda|ecb|euro ?zone|boe|bank of england|britain|british|rba|snb|pboc|"
          r"bok|bank of korea|korea\w*|rbi|india\w*|rbnz|new zealand|boc|bank of canada|canad\w*|australia\w*|"
          r"banxico|mexic\w*|riksbank|norges|sarb|south africa\w*|turk\w*|brazil\w*|china|chinese|taiwan\w*|"
          r"indonesia\w*|philippine\w*|thai\w*|swiss|swedish|norw\w*|asia fx|emerging markets?|"
          r"uk|u\.k\.|england|sterling|germany|german|france|french|italy|italian|spain|spanish)\b")
US_CB  = r"\b(fed|fomc|federal reserve|powell|u\.s\.|us)\b"   # a Fed/US mention keeps the signal
OTHER_USD = r"(canadian|australian|aussie|kiwi|new zealand|hong kong|singapore|taiwan) dollar|\bloonie\b"
UNSURE = r"\b(split|divided|debate|debating|undecided|mixed)\b"
FLIP   = FLIP[:-3] + r"|no rush|no hurry|in no hurry|not (yet )?ready|patient|cautious)\b"
WATCH  = r"\b(fed|fomc|powell|federal reserve|jackson hole|dot plot|fomc minutes|rate decision|interest rates?|cpi|pce|ppi|nfp|payrolls|inflation)\b"

INFL = r"\b(inflation|cpi|pce|ppi|consumer prices)\b"
UP   = r"\b(rise|rises|rising|rose|climb|climbs|jump|jumps|surge|surges|higher|highest|spike|spikes|soar|soars|lift|lifts)\b"
DOWN = r"\b(fall|falls|fell|drop|drops|dropped|slide|slides|slid|lower|retreat|retreats|tumble|tumbles|decline|declines|eases?|slump|slumps|sink|sinks|dip|dips)\b"

# (theme, topic, mood, effects, can_flip, exclude)
MACRO_RULES = [
 # --- inflation ---
 ("Hot inflation", INFL,
  r"\b(hot|hotter|accelerates?|accelerating|reaccelerates?|stubborn|sticky|rises|rose|jumps|jumped|surges|surged|tops|topped)\b|higher than expected|above (expectations|forecasts?|estimates)",
  HAWK, False, None),
 ("Cooling inflation", INFL,
  r"\b(cooler|cools|cooled|cooling|eases|eased|slows|slowed|softer|disinflation|falls|fell|drops|dropped|declines)\b|lower than expected|below (expectations|forecasts?|estimates)|less than expected",
  DOVE, False, None),
 # --- Fed expectations ---
 ("Rate-cut bets", r"rate cuts?|rate-cut|cut bets|cut hopes|cut odds|cut expectations|cuts? (interest )?rates?|\bfed cuts?\b|\bcutting rates\b",
  None, DOVE, True, NOT_US),
 ("Dovish Fed", r"\b(dovish|fed pivot|policy pivot|rate pivot|easing cycle|monetary easing|policy easing)\b", None, DOVE, False, NOT_US),
 ("Rate-hike bets", r"rate hikes?|rate-hike|hike bets|(raises?|raising) (interest )?rates?|hikes? (interest )?rates?",
  None, HAWK, True, NOT_US),
 ("Hawkish Fed", r"\b(hawkish|higher for longer|tightening)\b", None, HAWK, False, NOT_US),
 # --- yields ---
 ("Yields rising", r"\byields?\b", UP, HAWK, False, None),
 ("Yields falling", r"\byields?\b", DOWN, DOVE, False, None),
 # --- dollar ---
 ("Dollar strengthening", r"\b(dollar|greenback|dxy)\b",
  r"\b(strengthens?|strengthened|firm|firms|firmer|rises|rose|gains|gained|jumps|climbs|rallies|rally|higher|strong|stronger|surges|winning|win|highest|rebounds?)\b|best week",
  {G: -1, J: +1}, False, OTHER_USD),
 ("Dollar weakening", r"\b(dollar|greenback|dxy)\b",
  r"\b(weakens?|weakened|weaker|falls|fell|slides|slips|drops|slumps|lower|sinks|losing|loss|lowest|weak|retreats)\b",
  {G: +1, J: -1}, False, OTHER_USD),
 # --- jobs / growth ---
 ("Strong jobs data", r"\b(jobs|payrolls|nonfarm|nfp|labou?r market|jobless claims|employment|hiring)\b",
  r"\b(strong|stronger|beats?|tops?|robust|resilient|surges?)\b|above (expectations|forecasts?)|better than expected|more than expected",
  HAWK, False, None),
 ("Weak jobs data", r"\b(jobs|payrolls|nonfarm|nfp|labou?r market|jobless claims|employment|hiring)\b",
  r"\b(weak|weaker|misses|missed|slows|slowed|slump|contracts?|layoffs?)\b|below (expectations|forecasts?)|worse than expected|less than expected",
  {G: +1, J: -1}, False, None),
 ("Recession fears", r"recession|slowdown|stagflation|hard landing|growth fears", None,
  {G: +1, J: -1, N: -1}, False, None),
 ("Safe-haven demand", r"safe[- ]haven|flight to safety|geopolitic|escalat|tensions", None,
  {G: +1, J: -1, N: -1}, False, None),
 # --- Japan ---
 ("BOJ hawkish", r"\b(boj|bank of japan|ueda)\b",
  r"\b(hike|hikes|raise|raises|hawkish|tighten|tightening|normali[sz]e|normali[sz]ation)\b|rate increase",
  {J: -1}, False, None),
 ("BOJ dovish", r"\b(boj|bank of japan|ueda)\b",
  r"\b(hold|holds|dovish|delay|delays|cautious|stimulus)\b|ultra-loose|no rush",
  {J: +1}, False, None),
 ("Yen strengthening", r"\byen\b",
  r"\b(strengthens?|gains|gained|rallies|rally|jumps|surges|firms|highest|rebounds?)\b", {J: -1}, False, None),
 ("Yen weakening", r"\byen\b",
  r"\b(weakens?|weaker|slides|slumps|falls|drops|lowest|slips|sinks)\b", {J: +1}, False, None),
 ("Yen intervention risk", r"\byen\b",
  r"intervention|intervene|finance ministry|\bmof\b|excessive|speculative", {J: -1}, False, None),
 # --- gold's own move (confirmation) ---
 ("Gold already rising", r"\b(gold|bullion|xau)\b",
  r"\b(rises|rallies|jumps|climbs|surges|gains|record)\b", {G: +1}, False, None),
 ("Gold already falling", r"\b(gold|bullion|xau)\b",
  r"\b(falls|drops|slides|slumps|tumbles|retreats|slips|dips|sinks)\b", {G: -1}, False, None),
 ("Strong dollar", r"\b(strong|stronger|firmer|stronger-than-expected|rising)\s+(dollar|greenback|dxy)\b", None, {G: -1, J: +1}, False, OTHER_USD),
 ("Weak dollar",   r"\b(weak|weaker|softer|falling|sliding)\s+(dollar|greenback|dxy)\b", None, {G: +1, J: -1}, False, OTHER_USD),
 ("Strong yen",    r"\b(strong|stronger|firmer|rising)\s+yen\b", None, {J: -1}, False, None),
 ("Weak yen",      r"\b(weak|weaker|softer|sliding|falling)\s+yen\b", None, {J: +1}, False, None),
]

FOREIGN_SENSITIVE = {"Hot inflation", "Cooling inflation", "Strong jobs data", "Weak jobs data"}

def analyze(headline):
    text = headline.lower()
    flipped = has(FLIP, text)
    totals = {G: 0, J: 0, N: 0}
    why = {G: [], J: [], N: []}
    for theme, topic, mood, effects, can_flip, exclude in MACRO_RULES:
        if exclude is None and theme in FOREIGN_SENSITIVE:
            exclude = NOT_US          # other countries' inflation/jobs data don't move US-driven signals
        m = re.search(topic, text)
        if not m:
            continue
        # only look at words near the topic, so "Gold slides as yields rise"
        # doesn't make yields "fall"
        if 'yield' in topic:
            before, after = 14, 30
        elif any(k in topic for k in ('dollar', 'yen', 'gold')):
            before, after = 0, 30
        else:
            before, after = 28, 45
        near = text[max(0, m.start() - before): m.end() + after]
        if before == 0:
            near = text[m.end(): m.end() + after].split(",")[0]
        if mood and not has(mood, near):
            continue
        if exclude and has(exclude, text):
            if not (exclude == NOT_US and has(US_CB, text)):
                continue
        sign = -1 if (flipped and can_flip) else 1
        if can_flip and has(UNSURE, text):
            sign = 0
        for asset, v in effects.items():
            totals[asset] += v * sign
            why[asset].append(theme + (" (fading)" if sign < 0 else " (unclear)" if sign == 0 else ""))
    return totals, why

def label(net):
    if net >= 2:  return "⬆️⬆️ STRONG BULLISH"
    if net == 1:  return "⬆️ BULLISH"
    if net <= -2: return "⬇️⬇️ STRONG BEARISH"
    return "⬇️ BEARISH"

def build_alerts(h):
    totals, why = analyze(h)
    lines = []
    for a in (G, J, N):
        reasons = ", ".join(dict.fromkeys(why[a]))
        if totals[a] != 0:
            lines.append(f"{a} {label(totals[a])}: {reasons}")
        elif why[a]:
            lines.append(f"{a} ⚖️ MIXED: {reasons}")
        elif a in topics(h):
            d = direction(h, a)
            if d:
                lines.append(f"{a} {d}: keywords")
    if not lines and has(WATCH, h.lower()):
        lines.append("GOLD 👀 WATCH: Fed/inflation headline, no clear direction")
    return lines

# ================= SETTINGS =================
TOPIC = os.environ.get("NTFY_TOPIC", "")      # kept secret in GitHub, never in this file
MIN_SCORE = {"GOLD": 1, "USDJPY": 2, "NASDAQ": 2}   # strength needed to ping you
QUIET = (22, 7)             # no pings 22:00-07:00 South African time
SUMMARY_HOURS = (7, 18)     # summaries at 07:00 and 18:00
COOLDOWN_MIN = 30           # same asset + direction pings once per 30 min
STATE_FILE = "state.json"
# ============================================

from datetime import datetime, timezone, timedelta
TZ = timezone(timedelta(hours=2))
def now(): return datetime.now(TZ)

def send_alert(text, title="Market alert", priority="default"):
    if not TOPIC:
        print("(no NTFY_TOPIC set, not sending)")
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{TOPIC}",
        data=text.encode("utf-8"),
        headers={"Title": title, "Priority": priority, "User-Agent": "Mozilla/5.0"},
    )
    urllib.request.urlopen(req, timeout=10)

def is_quiet(t):
    start, end = QUIET
    return t.hour >= start or t.hour < end

def signals(h):
    """List of (asset, net, reasons). net=0 means mixed or watch-only."""
    totals, why = analyze(h)
    out = []
    for a in (G, J, N):
        reasons = ", ".join(dict.fromkeys(why[a]))
        if totals[a] != 0:
            out.append((a, totals[a], reasons))
        elif why[a]:
            out.append((a, 0, "MIXED: " + reasons))
        elif a in topics(h):
            d = direction(h, a)
            if d:
                out.append((a, 1 if "BULL" in d else -1, "keywords"))
    if not out and has(WATCH, h.lower()):
        out.append((G, 0, "WATCH: Fed/inflation event, no clear direction"))
    return out

def arrow(net):
    if net >= 2: return "⬆️⬆️"
    if net == 1: return "⬆️"
    if net <= -2: return "⬇️⬇️"
    if net == -1: return "⬇️"
    return "⚖️"

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return None

def save_state(S):
    with open(STATE_FILE, "w") as f:
        json.dump(S, f, ensure_ascii=False, indent=0)

def handle(h, S):
    t = now()
    strong = []
    for a, net, reasons in signals(h):
        pushed = False
        if net != 0 and abs(net) >= MIN_SCORE[a]:
            key = f"{a}|{int(net > 0)}"
            last = S["last_push"].get(key)
            recent = last and (t - datetime.fromisoformat(last)) < timedelta(minutes=COOLDOWN_MIN)
            if not is_quiet(t) and not recent:
                strong.append((a, net, reasons))
                S["last_push"][key] = t.isoformat()
                pushed = True
        S["digest"].append({"t": t.isoformat(), "a": a, "net": net, "h": h, "pushed": pushed})
    if strong:
        lines = [f"{a} {arrow(n)} {r}" for a, n, r in strong]
        msg = h + "\n\n" + "\n".join(lines)
        print("ALERT: " + msg.replace("\n", " | "))
        prio = "high" if any(abs(n) >= 2 for _, n, _ in strong) else "default"
        try:
            send_alert(msg, title="Market alert", priority=prio)
        except Exception as e:
            print(f"Phone send failed ({type(e).__name__})")

def send_summary(S):
    digest = S["digest"]
    if not digest:
        return
    directional = [d for d in digest if d["net"] != 0]
    mixed = len(digest) - len(directional)
    pushed = sum(d["pushed"] for d in digest)
    lines = [f"{len(digest)} signals, {pushed} pinged, {mixed} mixed/watch", ""]
    for d in directional[-12:]:
        mark = "" if d["pushed"] else " (not pinged)"
        tt = datetime.fromisoformat(d["t"])
        lines.append(f"{tt:%H:%M} {d['a']} {arrow(d['net'])}{mark}\n  {d['h'][:90]}")
    text = "\n".join(lines)[:3500]
    print("SUMMARY sent")
    try:
        send_alert(text, title="Market summary")
    except Exception as e:
        print(f"Summary send failed ({type(e).__name__})")
    S["digest"] = []

def main():
    S = load_state()
    first = S is None
    t = now()
    if first:
        S = {"seen": [], "last_push": {}, "sent_summaries": [], "digest": []}
        S["sent_summaries"] = [f"{t.date()}-{h}" for h in SUMMARY_HOURS if h <= t.hour]
    seen = dict.fromkeys(S["seen"])
    scanned = failed = 0
    for url in FEEDS:
        try:
            items = fetch_headlines(url)
        except Exception as e:
            failed += 1
            print(f"Feed failed: {url[:45]} ({type(e).__name__})")
            continue
        for h in items:
            scanned += 1
            if h in seen:
                continue
            seen[h] = 1
            if not first:          # first run only learns today's headlines
                try:
                    handle(h, S)
                except Exception as e:
                    print(f"Skipped one headline ({type(e).__name__}): {str(h)[:60]}")
    for h in SUMMARY_HOURS:
        key = f"{t.date()}-{h}"
        if t.hour >= h and key not in S["sent_summaries"]:
            S["sent_summaries"].append(key)
            send_summary(S)
    S["sent_summaries"] = S["sent_summaries"][-20:]
    S["seen"] = list(seen)[-3000:]
    S["digest"] = S["digest"][-300:]
    save_state(S)
    if first:
        try:
            send_alert("Bot is now running on GitHub. Alerts will arrive here.", title="Bot started")
        except Exception as e:
            print(f"Phone send failed ({type(e).__name__})")
    print(f"[{t:%H:%M}] Scanned {scanned} headlines, {failed} feeds failed, {len(S['digest'])} signals pending summary.")

RUN_MINUTES = float(os.environ.get("RUN_MINUTES", "0") or 0)
CHECK_EVERY = int(os.environ.get("CHECK_EVERY", "300") or 300)

def run():
    """Check now, then keep checking every CHECK_EVERY seconds for RUN_MINUTES."""
    end = time.time() + RUN_MINUTES * 60
    while True:
        try:
            main()
        except Exception as e:
            print(f"Check failed ({type(e).__name__}): {str(e)[:80]}")
        if time.time() + CHECK_EVERY >= end:
            break
        time.sleep(CHECK_EVERY)

if __name__ == "__main__":
    run()
