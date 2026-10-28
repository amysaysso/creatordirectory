#!/usr/bin/env python3
"""
Creator Directory generator.

Reads the PUBLISH Google Sheet (published as CSV, one row per show) and writes
a static, crawler-readable page into ./public:
  index.html, sitemap.xml, robots.txt, CNAME (if CUSTOM_DOMAIN is set)

Columns (headers must match; extra columns are ignored):
  Date of Submission/Renewal  hidden. If a show appears twice, the newest row wins.
  Name                        shown ("Hosted by ...")
  Show Name                   shown (card title). Rows without Name or Show Name are skipped.
  Show Description            shown
  Show Style                  shown as tags + filter. Several allowed, separated by commas.
                              (An older "Format" column is used if Show Style is missing.
                              "Hybrid" is shown as "Mixed format".)
  Primary Topic               shown as a tag, searchable. Topics shared by 2+ shows
                              also appear in the topic filter.
  Faith                       "Yes" shows a "Faith-based" tag; visitors can show or hide these.
  Politics                    "Yes" shows a "Political show" tag; visitors can show or hide these.
  Showcase Video              shown as a "Watch the Showcase" button
  Website, Listen, YouTube, Newsletter, Instagram, LinkedIn, Facebook, Threads,
  TikTok, Pinterest, X / Twitter, Twitch
                              shown as links. Full links work everywhere; @handles also
                              work for the social platforms.
  Other Links                 any number of full links in one cell (separated by spaces,
                              commas or new lines). Each is labeled automatically by its
                              address, so new platforms need no new column.
  RSS                         never shown (a raw feed isn't useful to visitors).
                              Only used to mark the show as Audio.

Medium (Audio, Video, Newsletter, Livestream) is worked out from the links;
there is no column for it.

Settings (environment variables):
  SHEET_CSV_URL      required  published CSV link (or a local .csv path for testing)
  SITE_URL           optional  e.g. https://creators.imperfectadulting.com
  CUSTOM_DOMAIN      optional  e.g. creators.imperfectadulting.com
  SITE_TITLE         optional  page heading and title
  SITE_DESCRIPTION   optional  one or two sentences under the heading
  GA_MEASUREMENT_ID  optional  Google Analytics 4 ID (G-...)

Uses only the Python standard library.
"""

import csv
import html
import io
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone

SHEET_CSV_URL = os.environ.get("SHEET_CSV_URL", "").strip()
SITE_URL = os.environ.get("SITE_URL", "").strip().rstrip("/")
CUSTOM_DOMAIN = os.environ.get("CUSTOM_DOMAIN", "").strip()
SITE_TITLE = os.environ.get("SITE_TITLE", "").strip() or "Creator Directory"
SITE_DESCRIPTION = os.environ.get("SITE_DESCRIPTION", "").strip() or (
    "A free directory of independent women creators: podcasts, YouTube "
    "channels, newsletters and more. Search by topic, style and format."
)
GA_MEASUREMENT_ID = os.environ.get("GA_MEASUREMENT_ID", "").strip().upper()
if GA_MEASUREMENT_ID and not re.match(r"^G-[A-Z0-9]{4,15}$", GA_MEASUREMENT_ID):
    print(f"Ignoring GA_MEASUREMENT_ID '{GA_MEASUREMENT_ID}': it should look like G-ABC123XYZ.")
    GA_MEASUREMENT_ID = ""
OUT_DIR = "public"

# Column -> (label on the card, how to build a link from a bare @handle)
LINK_COLUMNS = [
    ("Website", "Website", None),
    ("Listen", "Listen", None),
    ("YouTube", "YouTube", "https://www.youtube.com/@{}"),
    ("Newsletter", "Newsletter", None),
    ("Instagram", "Instagram", "https://www.instagram.com/{}"),
    ("LinkedIn", "LinkedIn", "https://www.linkedin.com/in/{}"),
    ("Facebook", "Facebook", "https://www.facebook.com/{}"),
    ("Threads", "Threads", "https://www.threads.net/@{}"),
    ("TikTok", "TikTok", "https://www.tiktok.com/@{}"),
    ("Pinterest", "Pinterest", "https://www.pinterest.com/{}"),
    ("X / Twitter", "X", "https://x.com/{}"),
    ("Twitch", "Twitch", "https://www.twitch.tv/{}"),
]

# Web address -> label, for links in "Other Links". Unknown sites use their own name.
KNOWN_SITES = [
    ("youtube.com", "YouTube"), ("youtu.be", "YouTube"), ("instagram.com", "Instagram"),
    ("tiktok.com", "TikTok"), ("facebook.com", "Facebook"), ("fb.com", "Facebook"),
    ("linkedin.com", "LinkedIn"), ("threads.net", "Threads"), ("threads.com", "Threads"),
    ("x.com", "X"), ("twitter.com", "X"), ("pinterest.com", "Pinterest"),
    ("twitch.tv", "Twitch"), ("bsky.app", "Bluesky"), ("substack.com", "Substack"),
    ("beehiiv.com", "Newsletter"), ("patreon.com", "Patreon"), ("medium.com", "Medium"),
    ("spotify.com", "Spotify"), ("podcasts.apple.com", "Apple Podcasts"),
    ("music.amazon.com", "Amazon Music"), ("linktr.ee", "Linktree"), ("snapchat.com", "Snapchat"),
    ("discord.gg", "Discord"), ("discord.com", "Discord"), ("tumblr.com", "Tumblr"),
    ("rumble.com", "Rumble"), ("kick.com", "Kick"), ("lemon8-app.com", "Lemon8"),
]

STYLE_LABELS = {"hybrid": "Mixed format"}
EMPTY_VALUES = {"", "n/a", "na", "none", "-", "null", "no", "tbd"}
MEDIUM_ORDER = ["Audio", "Video", "Newsletter", "Livestream"]


# ---------- reading the sheet ----------

def load_rows(source):
    if not source:
        sys.exit("SHEET_CSV_URL is not set.")
    if re.match(r"^https?://", source):
        req = urllib.request.Request(source, headers={"User-Agent": "creator-directory-builder"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8-sig")
    else:
        with open(source, encoding="utf-8-sig") as f:
            text = f.read()
    rows = []
    for raw in csv.DictReader(io.StringIO(text)):
        # Header matching ignores case and extra spaces.
        rows.append({re.sub(r"\s+", " ", (k or "")).strip().lower(): (v or "").strip()
                     for k, v in raw.items() if k is not None})
    return rows


def col(row, name):
    return row.get(name.lower(), "")


def is_blank(value):
    return (value or "").strip().lower() in EMPTY_VALUES


def is_yes(value):
    return (value or "").strip().lower() in {"yes", "y", "true", "x"}


def parse_date(value):
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime((value or "").strip(), fmt)
        except ValueError:
            continue
    return datetime.min


def dedupe(rows):
    latest = {}
    for row in rows:
        if is_blank(col(row, "Show Name")) or is_blank(col(row, "Name")):
            continue
        key = re.sub(r"\s+", " ", col(row, "Show Name").lower()).strip()
        if key not in latest or parse_date(col(row, "Date of Submission/Renewal")) >= parse_date(
                col(latest[key], "Date of Submission/Renewal")):
            latest[key] = row
    return sorted(latest.values(), key=lambda r: re.sub(r"^the\s+", "", col(r, "Show Name").lower()))


# ---------- cleaning values ----------

def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "show"


def to_url(value, handle_pattern=None):
    v = (value or "").strip().strip("<>")
    if is_blank(v):
        return None
    if re.match(r"^https?://", v, re.I):
        return v
    if re.match(r"^(www\.)?([\w-]+\.)+[a-z]{2,}(/\S*)?$", v, re.I):
        return "https://" + v
    handle = v.lstrip("@").strip("/")
    if handle_pattern and re.match(r"^[\w.\-]+$", handle):
        return handle_pattern.format(handle)
    return None


def site_label(url):
    host = urllib.parse.urlparse(url).netloc.lower()
    host = re.sub(r"^(www\.|m\.)", "", host)
    for domain, label in KNOWN_SITES:
        if host == domain or host.endswith("." + domain):
            return label
    parts = host.split(".")
    name = parts[-2] if len(parts) >= 2 else host
    return name.capitalize() or "Link"


def split_other_links(value):
    links = []
    for token in re.split(r"[\s,;|]+", value or ""):
        url = to_url(token.rstrip(".)"))
        if url:
            links.append((site_label(url), url))
    return links


def split_list(value):
    return [p.strip() for p in re.split(r"[,;/]", value or "") if not is_blank(p)]


def flag_label(value, yes_label):
    """Yes -> standard label. Other text (besides blank/No) is shown as written."""
    v = (value or "").strip()
    if is_blank(v):
        return None
    return yes_label if is_yes(v) else v


def normalize_url(url):
    return re.sub(r"^https?://(www\.)?", "", url.lower()).rstrip("/")


# ---------- building one creator ----------

def build_creator(row, used_slugs):
    slug = slugify(col(row, "Show Name"))
    base, n = slug, 2
    while slug in used_slugs:
        slug, n = f"{base}-{n}", n + 1
    used_slugs.add(slug)

    links, seen = [], set()

    def add(label, url):
        key = normalize_url(url)
        if key not in seen:
            seen.add(key)
            links.append((label, url))

    for column, label, pattern in LINK_COLUMNS:
        url = to_url(col(row, column), pattern)
        if url:
            add(label, url)
    rss = to_url(col(row, "RSS"))  # never shown; only marks the show as Audio
    for label, url in split_other_links(col(row, "Other Links")):
        add(label, url)

    # Medium is worked out from the links.
    labels = {lbl for lbl, _ in links}
    medium = []
    if rss or "Listen" in labels or labels & {"Spotify", "Apple Podcasts", "Amazon Music"}:
        medium.append("Audio")
    if "YouTube" in labels or "Rumble" in labels:
        medium.append("Video")
    if "Newsletter" in labels or labels & {"Substack", "Patreon", "Medium"}:
        medium.append("Newsletter")
    if "Twitch" in labels or "Kick" in labels:
        medium.append("Livestream")

    style_raw = col(row, "Show Style") or col(row, "Format")
    styles = []
    for s in [p.strip() for p in re.split(r"[,;]", style_raw or "") if not is_blank(p)]:
        label = STYLE_LABELS.get(s.lower(), s)
        if label not in styles:
            styles.append(label)

    showcase = to_url(col(row, "Showcase Video"))
    return {
        "slug": slug,
        "name": col(row, "Name"),
        "show": col(row, "Show Name"),
        "description": "" if is_blank(col(row, "Show Description")) else col(row, "Show Description"),
        "styles": styles,
        "topic": "" if is_blank(col(row, "Primary Topic")) else col(row, "Primary Topic"),
        "faith": flag_label(col(row, "Faith"), "Faith-based"),
        "politics": flag_label(col(row, "Politics"), "Political show"),
        "medium": medium,
        "showcase": showcase,
        "links": links,
    }


# ---------- building the page ----------

def card_html(c):
    e = html.escape
    tags = [f'<span class="tag tag-medium">{e(m)}</span>' for m in c["medium"]]
    tags += [f'<span class="tag">{e(s)}</span>' for s in c["styles"]]
    if c["topic"]:
        tags.append(f'<span class="tag tag-topic">{e(c["topic"])}</span>')
    if c["faith"]:
        tags.append(f'<span class="tag tag-flag">{e(c["faith"])}</span>')
    if c["politics"]:
        tags.append(f'<span class="tag tag-flag">{e(c["politics"])}</span>')
    link_items = "".join(
        f'<li><a href="{e(url, quote=True)}" rel="noopener" target="_blank">{e(label)}</a></li>'
        for label, url in c["links"])
    showcase = (f'<a class="showcase" href="{e(c["showcase"], quote=True)}" rel="noopener" target="_blank">'
                f'&#9654; Watch the Showcase</a>' if c["showcase"] else "")
    search = " ".join([c["show"], c["name"], c["description"], c["topic"],
                       " ".join(c["styles"]), " ".join(c["medium"])]).lower()
    data = {
        "medium": "|".join(m.lower() for m in c["medium"]),
        "style": "|".join(s.lower() for s in c["styles"]),
        "topic": c["topic"].lower(),
        "faith": "1" if c["faith"] else "0",
        "politics": "1" if c["politics"] else "0",
        "search": search,
    }
    attrs = " ".join(f'data-{k}="{e(v, quote=True)}"' for k, v in data.items())
    return f"""
      <article class="card" id="{c['slug']}" {attrs}>
        <h2 class="show"><a href="#{c['slug']}">{e(c['show'])}</a></h2>
        <p class="host">Hosted by {e(c['name'])}</p>
        <div class="tags">{''.join(tags)}</div>
        {f'<p class="desc">{e(c["description"])}</p>' if c['description'] else ''}
        {showcase}
        {f'<ul class="links" aria-label="Where to find {e(c["show"], quote=True)}">{link_items}</ul>' if link_items else ''}
      </article>"""


def structured_data(creators):
    items = []
    for i, c in enumerate(creators, start=1):
        work = {
            "@type": "PodcastSeries" if "Audio" in c["medium"] else "CreativeWorkSeries",
            "name": c["show"],
            "author": {"@type": "Person", "name": c["name"]},
        }
        if c["description"]:
            work["description"] = c["description"]
        if c["topic"]:
            work["genre"] = c["topic"]
        urls = [u for _, u in c["links"]]
        if urls:
            work["url"] = urls[0]
            if len(urls) > 1:
                work["sameAs"] = urls[1:]
        if SITE_URL:
            work["@id"] = f"{SITE_URL}/#{c['slug']}"
        items.append({"@type": "ListItem", "position": i, "item": work})
    data = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": SITE_TITLE,
        "description": SITE_DESCRIPTION,
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": items},
    }
    if SITE_URL:
        data["url"] = SITE_URL + "/"
    text = json.dumps(data, ensure_ascii=False, indent=1)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def analytics_tag():
    if not GA_MEASUREMENT_ID:
        return ""
    return (f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>\n'
            "<script>window.dataLayer = window.dataLayer || [];"
            "function gtag(){dataLayer.push(arguments);}"
            f"gtag('js', new Date());gtag('config', '{GA_MEASUREMENT_ID}');</script>")


def select_html(el_id, label, all_text, values):
    if not values:
        return ""
    opts = "".join(f'<option value="{html.escape(v.lower(), quote=True)}">{html.escape(v)}</option>' for v in values)
    return (f'<select id="{el_id}" aria-label="{html.escape(label, quote=True)}">'
            f'<option value="">{html.escape(all_text)}</option>{opts}</select>')


def flag_select(el_id, noun):
    return (f'<select id="{el_id}" aria-label="{noun}">'
            f'<option value="">{noun}: show all</option>'
            f'<option value="only">{noun}: only these</option>'
            f'<option value="hide">{noun}: hide these</option></select>')


def build_page(creators):
    e = html.escape
    media = [m for m in MEDIUM_ORDER if any(m in c["medium"] for c in creators)]
    styles = sorted({s for c in creators for s in c["styles"]}, key=str.lower)
    topic_counts = Counter(c["topic"].lower() for c in creators if c["topic"])
    topic_names = {}
    for c in creators:
        if c["topic"] and topic_counts[c["topic"].lower()] >= 2:
            topic_names.setdefault(c["topic"].lower(), c["topic"])
    topics = sorted(topic_names.values(), key=str.lower)
    faith_filter = flag_select("f-faith", "Faith-based shows") if any(c["faith"] for c in creators) else ""
    politics_filter = flag_select("f-politics", "Political shows") if any(c["politics"] for c in creators) else ""
    updated = datetime.now(timezone.utc).strftime("%B %-d, %Y")
    canonical = f'<link rel="canonical" href="{e(SITE_URL)}/">' if SITE_URL else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(SITE_TITLE)}</title>
<meta name="description" content="{e(SITE_DESCRIPTION, quote=True)}">
{canonical}
<meta property="og:title" content="{e(SITE_TITLE, quote=True)}">
<meta property="og:description" content="{e(SITE_DESCRIPTION, quote=True)}">
<meta property="og:type" content="website">
{analytics_tag()}
<script type="application/ld+json">
{structured_data(creators)}
</script>
<style>
  :root {{
    --bg: #faf8f5; --surface: #ffffff; --text: #1f1d1a; --muted: #6b655d;
    --line: #e7e2da; --accent: #b4304a; --accent-text: #ffffff;
    --tag: #f3eee7; --tag-text: #4a443c; --tag-medium: #e9eef6; --tag-medium-text: #2f4566;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #171513; --surface: #211f1c; --text: #f2eee8; --muted: #a8a196;
      --line: #36322d; --accent: #f08aa0; --accent-text: #1f1d1a;
      --tag: #2c2925; --tag-text: #d9d3c9; --tag-medium: #23303f; --tag-medium-text: #c5d6ee;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text);
    font: 16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }}
  .wrap {{ max-width: 1120px; margin: 0 auto; padding: 40px 16px 64px; }}
  header h1 {{ font-size: clamp(1.8rem, 4vw, 2.6rem); line-height: 1.15; margin: 0 0 8px; letter-spacing: -0.01em; }}
  header p {{ color: var(--muted); max-width: 62ch; margin: 0 0 24px; }}
  .filters {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
  .filters input, .filters select {{ font: inherit; padding: 9px 12px; border: 1px solid var(--line);
    border-radius: 8px; background: var(--surface); color: var(--text); min-width: 0; max-width: 100%; }}
  .filters input {{ flex: 1 1 240px; }}
  .count {{ color: var(--muted); font-size: 0.9rem; margin: 12px 0 20px; }}
  .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }}
  .card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 20px;
    display: flex; flex-direction: column; gap: 8px; scroll-margin-top: 16px; }}
  .card:target {{ outline: 2px solid var(--accent); }}
  .card[hidden] {{ display: none; }}
  .show {{ font-size: 1.15rem; margin: 0; line-height: 1.3; }}
  .show a {{ color: inherit; text-decoration: none; }}
  .show a:hover {{ color: var(--accent); }}
  .host {{ margin: 0; color: var(--muted); font-size: 0.92rem; }}
  .tags {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .tag {{ background: var(--tag); color: var(--tag-text); border-radius: 999px; padding: 2px 10px; font-size: 0.8rem; }}
  .tag-medium {{ background: var(--tag-medium); color: var(--tag-medium-text); }}
  .tag-topic {{ font-weight: 600; }}
  .tag-flag {{ border: 1px solid var(--line); background: transparent; }}
  .desc {{ margin: 4px 0 0; font-size: 0.95rem; }}
  .showcase {{ align-self: flex-start; margin-top: 4px; background: var(--accent); color: var(--accent-text);
    padding: 6px 12px; border-radius: 8px; font-size: 0.88rem; font-weight: 600; text-decoration: none; }}
  .showcase:hover {{ filter: brightness(1.08); }}
  .links {{ list-style: none; padding: 8px 0 0; margin: auto 0 0; display: flex; flex-wrap: wrap; gap: 6px 14px; }}
  .links a {{ color: var(--accent); font-size: 0.9rem; font-weight: 600; text-decoration: none; }}
  .links a:hover {{ text-decoration: underline; }}
  footer {{ margin-top: 48px; color: var(--muted); font-size: 0.85rem; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>{e(SITE_TITLE)}</h1>
    <p>{e(SITE_DESCRIPTION)}</p>
  </header>
  <div class="filters" role="search">
    <input type="search" id="f-search" placeholder="Search shows, hosts, topics" aria-label="Search the directory">
    {select_html("f-medium", "Filter by format", "All formats", media)}
    {select_html("f-style", "Filter by show style", "All styles", styles)}
    {select_html("f-topic", "Filter by topic", "All topics", topics)}
    {faith_filter}
    {politics_filter}
  </div>
  <p class="count" id="count">{len(creators)} shows</p>
  <main class="grid">{''.join(card_html(c) for c in creators)}
  </main>
  <footer>Updated {updated}.</footer>
</div>
<script>
(function () {{
  var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
  function el(id) {{ return document.getElementById(id); }}
  var q = el('f-search'), medium = el('f-medium'), style = el('f-style'), topic = el('f-topic'),
      faith = el('f-faith'), politics = el('f-politics'), count = el('count');
  function val(x) {{ return x ? x.value : ''; }}
  function flagOk(mode, has) {{ return !mode || (mode === 'only' ? has === '1' : has === '0'); }}
  function apply() {{
    var s = q.value.trim().toLowerCase(), m = val(medium), st = val(style), t = val(topic), n = 0;
    cards.forEach(function (c) {{
      var d = c.dataset;
      var ok = (!s || d.search.indexOf(s) > -1)
        && (!m || d.medium.split('|').indexOf(m) > -1)
        && (!st || d.style.split('|').indexOf(st) > -1)
        && (!t || d.topic === t)
        && flagOk(val(faith), d.faith)
        && flagOk(val(politics), d.politics);
      c.hidden = !ok; if (ok) n++;
    }});
    count.textContent = n + (n === 1 ? ' show' : ' shows');
  }}
  [q, medium, style, topic, faith, politics].forEach(function (x) {{ if (x) x.addEventListener('input', apply); }});
}})();
</script>
</body>
</html>
"""


def main():
    rows = load_rows(SHEET_CSV_URL)
    used = set()
    creators = [build_creator(r, used) for r in dedupe(rows)]
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_page(creators))
    if SITE_URL:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with open(os.path.join(OUT_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                    f"  <url><loc>{html.escape(SITE_URL)}/</loc><lastmod>{today}</lastmod></url>\n"
                    "</urlset>\n")
    with open(os.path.join(OUT_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n" + (f"Sitemap: {SITE_URL}/sitemap.xml\n" if SITE_URL else ""))
    if CUSTOM_DOMAIN:
        with open(os.path.join(OUT_DIR, "CNAME"), "w", encoding="utf-8") as f:
            f.write(CUSTOM_DOMAIN + "\n")
    print(f"Built directory with {len(creators)} shows from {len(rows)} sheet rows.")


if __name__ == "__main__":
    main()
