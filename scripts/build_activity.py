#!/usr/bin/env python3
"""Draw the activity log (assets/activity-log.svg and -dark.svg) from real GitHub data.

    GITHUB_TOKEN=... GH_LOGIN=Afhaam11 python scripts/build_activity.py     # live: what the workflow runs
    python scripts/build_activity.py --static                               # no network, no numbers
    python scripts/build_activity.py --from-json user.json --today 2026-11-16   # offline test

Standard library only. Real data only: contributions per month and the latest commit of each recently pushed public
repository. If the API call fails, the existing files are left untouched and the script exits non-zero, so the last
good log stays on the page. Output depends only on the data and the current month (never on a run timestamp), so an
unchanged log gives byte-identical files and no commit.
"""
import argparse, datetime as dt, json, os, sys, time, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fj import LIGHT, DARK, svg_doc, text, line, plate_frame, smooth_d, n

OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets"))
API = "https://api.github.com/graphql"
QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
    repositories(first: 8, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        name
        primaryLanguage { name }
        defaultBranchRef { target { ... on Commit { history(first: 1) { nodes { messageHeadline committedDate } } } } }
      }
    }
  }
}
"""
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
STATIC_ROWS = (("001", "Explainable RL, batch reactor", "research"), ("002", "Rice leaf disease + RAG", "vision, RAG"),
               ("003", "Northstar CRM AI", "LLM app"), ("004", "Kidney disease prediction", "ML"),
               ("005", "E-commerce segmentation", "analytics"))


def first_month(today):
    y, m = today.year, today.month - 11
    while m < 1: m += 12; y -= 1
    return y, m


def fetch(login, token, today, tries=3):
    y, m = first_month(today)
    body = json.dumps({"query": QUERY, "variables": {"login": login, "from": "%04d-%02d-01T00:00:00Z" % (y, m),
                                                      "to": today.strftime("%Y-%m-%dT23:59:59Z")}}).encode()
    req = urllib.request.Request(API, body, {"Authorization": "bearer " + token, "Content-Type": "application/json",
                                             "User-Agent": login + "-field-log"})
    for i in range(tries):                       # rate limits and 5xx: wait and retry, then give up without touching the page
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                out = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 502, 503) and i < tries - 1: time.sleep(5 * 3 ** i); continue
            raise SystemExit("GitHub API error %s: %s" % (e.code, e.read()[:200]))
        except urllib.error.URLError as e:
            if i < tries - 1: time.sleep(5 * 3 ** i); continue
            raise SystemExit("network error: %s" % e)
    if out.get("errors") or not (out.get("data") or {}).get("user"):
        raise SystemExit("GraphQL error: " + json.dumps(out.get("errors", "no such user"))[:300])
    return out["data"]["user"]


def summarise(user, today):
    keys = []; y, m = first_month(today)
    for _ in range(12):
        keys.append((y, m)); m += 1
        if m == 13: m, y = 1, y + 1
    per = {k: 0 for k in keys}
    for wk in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
        for d in wk["contributionDays"]:
            k = (int(d["date"][:4]), int(d["date"][5:7]))
            if k in per: per[k] += d["contributionCount"]
    repos = []
    for r in user["repositories"]["nodes"]:
        h = ((((r.get("defaultBranchRef") or {}).get("target") or {}).get("history") or {}).get("nodes")) or []
        if h: repos.append(dict(name=r["name"], lang=(r.get("primaryLanguage") or {}).get("name") or "",
                                date=h[0]["committedDate"][:10], msg=h[0]["messageHeadline"]))
    repos.sort(key=lambda r: (r["date"], r["name"]), reverse=True)
    return dict(keys=keys, counts=[per[k] for k in keys], repos=repos[:6])


def pchip(h, dx):
    """Fritsch-Carlson slopes for equally spaced heights: a smooth curve with no overshoot."""
    d = [(h[i + 1] - h[i]) / dx for i in range(len(h) - 1)]
    return [d[0]] + [0.0 if d[i - 1] * d[i] <= 0 else 2 * d[i - 1] * d[i] / (d[i - 1] + d[i]) for i in range(1, len(h) - 1)] + [d[-1]]


def hermite(h, m, dx, i, t):
    t2, t3 = t * t, t * t * t
    return (2 * t3 - 3 * t2 + 1) * h[i] + (t3 - 2 * t2 + t) * dx * m[i] + (-2 * t3 + 3 * t2) * h[i + 1] + (t3 - t2) * dx * m[i + 1]


LANG = {"Jupyter Notebook": "Jupyter"}


def clip(s, k):
    s = " ".join(s.split())
    return s if len(s) <= k else s[:k - 1] + "\u2026"


def render(pal, data):
    W, H = 1000, 540
    ink, ink2, mute, rule, strong = pal["ink"], pal["ink2"], pal["mute"], pal["rule"], pal["strong"]
    live = data is not None
    b = [plate_frame(W, H, pal), text(56, 66, "FIELD LOG", 13, ink2, ls=3.2),
         text(W - 56, 66, "SOURCE \u00b7 GITHUB API" if live else "STATIC VIEW", 11, mute, anchor="end", ls=1.8),
         text(56, 108, "Recent activity", 31, ink, cls="s"), text(56, 140, "PUBLIC REPOSITORIES \u00b7 PAST 12 MONTHS", 12, ink2, ls=2.2),
         line(56, 160, W - 56, 160, strong, 0.8), text(56, 196, "THE YEAR, BY MONTH", 11, ink2, ls=2.4),
         text(520, 196, "RECENT PUSHES", 11, ink2, ls=2.4)]
    x0, x1, base, ch = 64, 462, 372, 120
    if live:
        c = data["counts"]; total = sum(c); peak = max(c); slot = (x1 - x0) / 12.0
        b.append(text(470, 196, "%d CONTRIBUTION%s" % (total, "" if total == 1 else "S"), 11, ink, anchor="end", ls=1.6))
        b.append(line(x0, base, x1, base, strong, 1))
        sc = ch / float(max(peak, 4))
        xs = [x0 + slot * (i + 0.5) for i in range(12)]; hs = [v * sc for v in c]; ys = [base - h for h in hs]
        m = pchip(hs, slot)
        hatch = []                                      # section hatching under the ridge, from the same curve
        x = int(xs[0]) + 1
        while x <= xs[-1]:
            i = min(10, int((x - xs[0]) // slot)); h = hermite(hs, m, slot, i, (x - xs[i]) / slot)
            if h > 0.8: hatch.append("M%d %dv-%s" % (x, base, n(h)))
            x += 5
        if hatch: b.append('<path d="%s" fill="none" stroke="%s" stroke-width=".7"/>' % ("".join(hatch), rule))
        if peak:
            d = "M%s %s" % (n(xs[0]), n(ys[0]))
            for i in range(11):
                d += "C%s %s %s %s %s %s" % (n(xs[i] + slot / 3), n(base - (hs[i] + m[i] * slot / 3)), n(xs[i + 1] - slot / 3),
                                             n(base - (hs[i + 1] - m[i + 1] * slot / 3)), n(xs[i + 1]), n(ys[i + 1]))
            b.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.4"/>' % (d, ink2))
        for i, v in enumerate(c):
            if v: b.append(line(xs[i], base, xs[i], ys[i], ink, 1.2, cap="round") + '<circle cx="%s" cy="%s" r="2.6" fill="%s"/>' % (n(xs[i]), n(ys[i]), ink))
            else: b.append(line(xs[i], base, xs[i], base - 3, strong, 1))
        if peak:
            i = c.index(peak); b.append(text(xs[i], ys[i] - 10, str(peak), 12, ink, anchor="middle"))
        else:
            b.append(text((x0 + x1) / 2, 322, "NO CONTRIBUTIONS IN THE PAST 12 MONTHS", 10, mute, anchor="middle", ls=1.4))
        for i, (y_, m_) in enumerate(data["keys"]):
            b.append(text(xs[i], 392, MONTHS[m_ - 1][0], 10, mute, anchor="middle"))
        (y0_, m0_), (y1_, m1_) = data["keys"][0], data["keys"][-1]
        b.append(text(x0, 412, "%s %d" % (MONTHS[m0_ - 1], y0_), 10, ink2, ls=1)); b.append(text(x1, 412, "%s %d" % (MONTHS[m1_ - 1], y1_), 10, ink2, anchor="end", ls=1))
        busiest = MONTHS[data["keys"][c.index(peak)][1] - 1].title() if peak else "\u2013"
        for x, lab, val in ((64, "THIS MONTH", str(c[-1])), (200, "ACTIVE MONTHS", "%d / 12" % sum(1 for v in c if v)), (336, "BUSIEST MONTH", busiest)):
            b.append(text(x, 446, lab, 10, mute, ls=1.6)); b.append(text(x, 474, val, 26, ink, cls="s"))
    else:
        b.append('<rect x="%d" y="236" width="%d" height="136" rx="3" fill="none" stroke="%s" stroke-width="1" stroke-dasharray="4 4"/>' % (x0, x1 - x0, strong))
        b.append(text((x0 + x1) / 2, 300, "AWAITING FIRST SYNC", 12, ink2, anchor="middle", ls=2.4))
        b.append(text((x0 + x1) / 2, 322, "contribution history appears here", 10, mute, anchor="middle", ls=0.6))
        b.append(line(x0, base, x1, base, strong, 1))
    # recent pushes
    rows = data["repos"] if live else None
    for i in range(6):
        y = 212 + i * 44
        b.append(line(520, y, 944, y, rule, 0.8))
        if live and i < len(rows):
            r = rows[i]
            b.append(text(520, y + 26, r["date"], 12, ink2)); b.append(text(606, y + 22, clip(r["name"], 28), 13, ink))
            b.append(text(606, y + 38, clip(r["msg"], 58), 11.5, mute, cls="a"))
            if r["lang"]: b.append(text(944, y + 22, clip(LANG.get(r["lang"], r["lang"]), 16), 10, mute, anchor="end", ls=0.6))
        elif not live and i < len(STATIC_ROWS):
            sid, name, kind = STATIC_ROWS[i]
            b.append(text(520, y + 26, sid, 12, ink2)); b.append(text(606, y + 22, name, 13, ink)); b.append(text(944, y + 22, kind, 10, mute, anchor="end", ls=0.6))
    b.append(line(520, 212 + 6 * 44, 944, 212 + 6 * 44, rule, 0.8))
    if live and not rows: b.append(text(520, 242, "NO PUBLIC PUSHES YET", 11, mute, ls=1.6))
    if live:
        last = ("LAST ACTIVITY %s \u00b7 %s" % (rows[0]["date"], clip(rows[0]["name"], 36))) if rows else "NO PUBLIC ACTIVITY YET"
        b.append(text(56, 506, last, 10, ink2, ls=1.2)); right = "DRAWN FROM THE GITHUB API BY A SCHEDULED ACTION"
    else:
        b.append(text(56, 506, "STATIC VIEW", 10, ink2, ls=1.2)); right = "A SCHEDULED ACTION REPLACES THIS WITH LIVE DATA"
    b.append(text(W - 56, 506, right, 10, mute, anchor="end", ls=1.2))
    return svg_doc(W, H, "Activity log",
                   ("Activity log window. Left: public contributions per month over the past twelve months, drawn as a ridge of survey stakes with the monthly "
                    "total and the busiest month. Right: the most recently pushed public repositories with the date and headline of the latest commit. "
                    "Drawn from the GitHub API." if live else
                    "Activity log window in its static state: an empty chart area marked 'awaiting first sync' beside an index of five public projects. "
                    "A scheduled action replaces it with real contribution and push data."), "".join(b), "activity")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--static", action="store_true", help="draw the no-data state (no network)")
    ap.add_argument("--from-json", help="read the GraphQL 'user' object from a file instead of calling the API")
    ap.add_argument("--today", help="YYYY-MM-DD, for reproducible offline tests")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.today) if a.today else dt.datetime.now(dt.timezone.utc).date()
    if a.static: data = None
    else:
        if a.from_json: user = json.load(open(a.from_json, encoding="utf-8"))
        else:
            tok, login = os.environ.get("GITHUB_TOKEN"), os.environ.get("GH_LOGIN", "Afhaam11")
            if not tok: raise SystemExit("set GITHUB_TOKEN (the workflow does), or use --static / --from-json")
            user = fetch(login, tok, today)
        data = summarise(user, today)
    files = {"activity-log.svg": render(LIGHT, data), "activity-log-dark.svg": render(DARK, data)}   # build both before touching disk
    os.makedirs(a.out, exist_ok=True)
    for name, svg in files.items():
        path = os.path.join(a.out, name)
        if os.path.exists(path) and open(path, encoding="utf-8").read() == svg: print("unchanged", name); continue
        open(path, "w", encoding="utf-8", newline="\n").write(svg); print("wrote    %-24s %5.1f KB" % (name, len(svg.encode()) / 1024))


if __name__ == "__main__":
    main()
