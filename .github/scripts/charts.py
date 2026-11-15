"""
Generates the SVG charts used in the profile README:
  assets/stats.svg      - headline numbers
  assets/languages.svg  - language breakdown across public repos
  assets/activity.svg   - contributions per month (last 12 months)

Runs in GitHub Actions with the built-in GITHUB_TOKEN. Standard library only.
"""

import json
import os
import urllib.request
from datetime import datetime, timezone

USER = os.environ.get("GH_USER", "Daanyaal5")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "assets")
SKIP_REPOS = {USER.lower()}  # the profile repo itself

# Theme (matches daanyaalsportfolio.vercel.app)
BG = "#0f0d16"
PANEL = "#17141f"
LINE = "#2a2536"
TEXT = "#f3eee6"
MUTED = "#a8a1b4"
SUN, HOT, VIOLET, CASH = "#ffb21e", "#ff3d81", "#7b3cff", "#79d96b"
PALETTE = ["#ffb21e", "#ff3d81", "#7b3cff", "#2fc5e8", "#79d96b", "#ff7a3d", "#c86bff", "#8a8f9c"]
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"


def api(url, data=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-charts"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fetch():
    repos = api(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner")
    repos = [r for r in repos if not r["fork"] and r["name"].lower() not in SKIP_REPOS]

    languages = {}
    for r in repos:
        for lang, n in api(r["languages_url"]).items():
            languages[lang] = languages.get(lang, 0) + n

    stars = sum(r["stargazers_count"] for r in repos)

    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }"""
    cal = api("https://api.github.com/graphql", {"query": query, "variables": {"login": USER}})
    cal = cal["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]

    return {
        "repos": len(repos),
        "stars": stars,
        "languages": languages,
        "total": cal["totalContributions"],
        "days": days,
    }


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def frame(w, h, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{title}">
  <defs>
    <linearGradient id="sunset" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0" stop-color="{SUN}"/><stop offset="0.55" stop-color="{HOT}"/><stop offset="1" stop-color="{VIOLET}"/>
    </linearGradient>
    <linearGradient id="rise" x1="0" x2="0" y1="1" y2="0">
      <stop offset="0" stop-color="{SUN}"/><stop offset="0.6" stop-color="{HOT}"/><stop offset="1" stop-color="{VIOLET}"/>
    </linearGradient>
    <style>
      text {{ font-family: {FONT}; }}
      .title {{ font-size: 15px; font-weight: 700; letter-spacing: 2px; fill: {TEXT}; }}
      .muted {{ font-size: 12px; fill: {MUTED}; }}
      .rise {{ animation: rise .9s cubic-bezier(.2,.8,.2,1) both; transform-box: fill-box; transform-origin: bottom; }}
      @keyframes rise {{ from {{ transform: scaleY(0); }} to {{ transform: scaleY(1); }} }}
      .fade {{ animation: fade .8s ease both; }}
      @keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    </style>
  </defs>
  <clipPath id="card"><rect x="0" y="0" width="{w}" height="{h}" rx="12"/></clipPath>
  <rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="{BG}" stroke="{LINE}"/>
  <rect x="0" y="0" width="{w}" height="4" fill="url(#sunset)" clip-path="url(#card)"/>
  <text x="24" y="36" class="title">{title.upper()}</text>
{body}
</svg>
"""


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def stats_svg(d):
    best = max((sum(x["contributionCount"] for x in d["days"][i:i + 7]) for i in range(0, len(d["days"]), 7)), default=0)
    streak = cur = 0
    for day in d["days"]:
        cur = cur + 1 if day["contributionCount"] else 0
        streak = max(streak, cur)
    items = [
        ("Contributions (last year)", d["total"], SUN),
        ("Public repositories", d["repos"], HOT),
        ("Longest streak", f"{streak} days", VIOLET),
        ("Best week", best, CASH),
    ]
    body = []
    for i, (label, value, color) in enumerate(items):
        x = 24 + (i % 2) * 196
        y = 64 + (i // 2) * 70
        body.append(
            f'  <g class="fade" style="animation-delay:{i * 0.12:.2f}s">'
            f'<rect x="{x}" y="{y}" width="184" height="58" rx="8" fill="{PANEL}"/>'
            f'<rect x="{x}" y="{y}" width="4" height="58" rx="2" fill="{color}"/>'
            f'<text x="{x + 16}" y="{y + 32}" style="font-size:24px;font-weight:800;fill:{TEXT}">{esc(value)}</text>'
            f'<text x="{x + 16}" y="{y + 49}" class="muted">{esc(label)}</text></g>'
        )
    body.append(f'  <text x="24" y="226" class="muted">Updated daily · {datetime.now(timezone.utc):%b %d, %Y}</text>')
    return frame(428, 242, "GitHub stats", "\n".join(body))


def languages_svg(d):
    total = sum(d["languages"].values()) or 1
    ranked = sorted(d["languages"].items(), key=lambda kv: -kv[1])
    top = ranked[:7]
    other = sum(n for _, n in ranked[7:])
    if other:
        top.append(("Other", other))

    # Stacked bar
    body, x = [], 24.0
    width = 380.0
    for i, (lang, n) in enumerate(top):
        w = width * n / total
        body.append(
            f'  <rect class="fade" style="animation-delay:{i * 0.08:.2f}s" x="{x:.2f}" y="56" width="{max(w, 1.5):.2f}" height="12" '
            f'fill="{PALETTE[i % len(PALETTE)]}"/>'
        )
        x += w
    body.insert(0, f'  <clipPath id="bar"><rect x="24" y="56" width="{width:.0f}" height="12" rx="6"/></clipPath><g clip-path="url(#bar)">')
    body.append("  </g>")

    # Legend
    for i, (lang, n) in enumerate(top):
        col, row = i % 2, i // 2
        lx, ly = 24 + col * 196, 98 + row * 30
        pct = 100 * n / total
        body.append(
            f'  <g class="fade" style="animation-delay:{0.3 + i * 0.06:.2f}s">'
            f'<circle cx="{lx + 6}" cy="{ly - 4}" r="6" fill="{PALETTE[i % len(PALETTE)]}"/>'
            f'<text x="{lx + 20}" y="{ly}" style="font-size:13px;fill:{TEXT};font-weight:600">{esc(lang)}</text>'
            f'<text x="{lx + 176}" y="{ly}" text-anchor="end" class="muted">{pct:.1f}%</text></g>'
        )
    h = 98 + ((len(top) + 1) // 2) * 30 + 6
    return frame(428, max(h, 242), "Top languages", "\n".join(body))


def activity_svg(d):
    # Sum contributions per calendar month, last 12 months
    months = {}
    for day in d["days"]:
        key = day["date"][:7]
        months[key] = months.get(key, 0) + day["contributionCount"]
    keys = sorted(months)[-12:]
    values = [months[k] for k in keys]
    peak = max(values) or 1

    w, h = 880, 250
    left, right, top, bottom = 48, 24, 60, 200
    plot_w = w - left - right
    bar_w = plot_w / max(len(keys), 1)
    body = []

    # Gridlines
    for frac in (0.25, 0.5, 0.75, 1.0):
        y = bottom - (bottom - top) * frac
        body.append(f'  <line x1="{left}" x2="{w - right}" y1="{y:.1f}" y2="{y:.1f}" stroke="{LINE}" stroke-dasharray="3 5"/>')
        body.append(f'  <text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" class="muted">{round(peak * frac)}</text>')

    for i, (k, v) in enumerate(zip(keys, values)):
        bh = (bottom - top) * v / peak
        x = left + i * bar_w + bar_w * 0.18
        bw = bar_w * 0.64
        label = datetime.strptime(k, "%Y-%m").strftime("%b")
        body.append(
            f'  <rect class="rise" style="animation-delay:{i * 0.05:.2f}s" x="{x:.1f}" y="{bottom - bh:.1f}" width="{bw:.1f}" '
            f'height="{max(bh, 2):.1f}" rx="4" fill="url(#rise)"><title>{label}: {v} contributions</title></rect>'
        )
        if v:
            body.append(
                f'  <text class="fade" style="animation-delay:{0.6 + i * 0.05:.2f}s;font-size:11px;fill:{TEXT};font-weight:600" '
                f'x="{x + bw / 2:.1f}" y="{bottom - bh - 8:.1f}" text-anchor="middle">{v}</text>'
            )
        body.append(f'  <text x="{x + bw / 2:.1f}" y="{bottom + 20}" text-anchor="middle" class="muted">{label}</text>')

    body.append(f'  <text x="{w - 24}" y="36" text-anchor="end" class="muted">{d["total"]} contributions in the last year</text>')
    return frame(w, h, "Contribution activity", "\n".join(body))


def main():
    d = fetch()
    os.makedirs(OUT, exist_ok=True)
    for name, svg in (("stats.svg", stats_svg(d)), ("languages.svg", languages_svg(d)), ("activity.svg", activity_svg(d))):
        with open(os.path.join(OUT, name), "w") as f:
            f.write(svg)
    print(f"Wrote charts: {d['repos']} repos, {d['total']} contributions, {len(d['languages'])} languages")


if __name__ == "__main__":
    main()
