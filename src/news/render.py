"""Render reader-safe snapshots, cards and dated edition navigation."""

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import html

from .analysis import TOPICS
from .urls import allowed_publisher_url

def escape(value):
    return html.escape(str(value), quote=True)


def safe_link(url):
    return url if allowed_publisher_url(url) else None


GEOGRAPHY_ALIASES = {
    "US": "United States",
    "U.S.": "United States",
    "USA": "United States",
    "U.S.A.": "United States",
    "New Zealand": "NZ",
    "UK": "United Kingdom",
    "U.K.": "United Kingdom",
}
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")


def _timestamp(value):
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _date(value):
    timestamp = _timestamp(value)
    return (
        timestamp.astimezone(ZoneInfo("Pacific/Auckland")).strftime(
            "%d %b %Y, %-I:%M %p %Z"
        )
        if timestamp
        else "Date unavailable"
    )


def reader_snapshot(edition):
    """Whitelist only intended reader fields, including source URLs and dates."""
    stories = []
    for story in edition.get("stories", []):
        sources = []
        for source in story.get("sources", []):
            url = safe_link(source.get("url", ""))
            if not url:
                continue
            sources.append(
                {
                    "source": str(source.get("source", "Source")),
                    "url": url,
                    "published": str(source.get("published") or ""),
                    "updated": str(source.get("updated") or ""),
                    "rss_only": bool(
                        source.get("rss_only")
                        or (
                            source.get("used_in_summary")
                            and source.get("evidence_basis") == "feed_summary"
                        )
                    ),
                }
            )
        clean = {
            key: str(story.get(key) or "")
            for key in ("event_id", "title", "summary", "why_matters")
        }
        clean["sources"] = sources
        clean["topics"] = [tag for tag in story.get("topics", []) if tag in TOPICS]
        clean["geography"] = list(
            dict.fromkeys(
                GEOGRAPHY_ALIASES.get(tag, tag)
                for tag in story.get("geography", [])
                if isinstance(tag, str)
            )
        )
        clean["importance"] = (
            story.get("importance")
            if story.get("importance") in ("major", "notable", "useful")
            else "useful"
        )
        clean["freshness"] = (
            story.get("freshness")
            if story.get("freshness")
            in ("new", "updated", "catch_up", "previously_featured")
            else "new"
        )
        clean["featured"] = bool(story.get("featured"))
        revision = story.get("revision_key")
        clean["revision_key"] = revision if isinstance(revision, str) else ""
        # Material-update lineage survives harmless summary rewrites. Older editions
        # have no lineage key, so their factual content supplies a conservative fallback.
        content = [
            clean[key] for key in ("event_id", "title", "summary", "why_matters")
        ]
        signature = hashlib.sha256(
            json.dumps(content, ensure_ascii=False).encode()
        ).hexdigest()[:24]
        identity = clean["event_id"] or signature
        clean["read_key"] = identity + ":" + (clean["revision_key"] or signature)
        stories.append(clean)
    status = edition.get("publication_status")
    return {
        "run_id": str(edition.get("run_id", "")),
        "generated_at": str(edition.get("generated_at", "")),
        "publication_status": "published" if status == "published" else "preview",
        "stories": stories,
    }


def story_id(story):
    return "story-" + hashlib.sha256(story["read_key"].encode()).hexdigest()[:20]


def _theme(story):
    topics = set(story["topics"])
    if topics & {"AI", "Technology"}:
        return "technology", "lilac"
    if topics & {"Science", "Environment", "Geography"}:
        return "curiosity", "sage"
    return "world", "peach"


LOGO = '<svg class="reader-mark" viewBox="0 0 52 52" aria-hidden="true"><path fill="currentColor" d="M7 5h24l14 14v28H7z"/><path fill="none" stroke="white" stroke-width="3" stroke-linejoin="round" d="M31 5v14h14M16 35V22l12 13V22M16 41h20"/></svg>'


def _pull_quote(story):
    # Reuse reviewed prose rather than invent a quotation or introduce a new claim.
    opening = re.split(r"(?<=[.!?])\s+", story["summary"].strip())[0]
    return opening if opening and len(opening.split()) <= 40 else story["title"]


def _sources(story):
    links = []
    for source in story["sources"]:
        dates = " · ".join(
            f"{label} {_date(source[key])}"
            for key, label in (("published", "Published"), ("updated", "Updated"))
            if source[key]
            and (key != "updated" or _timestamp(source[key]) != _timestamp(source["published"]))
        )
        links.append(
            '<li><a href="' + escape(source["url"])
            + '" target="_blank" rel="noopener noreferrer">'
            + escape(source["source"]) + ' <span aria-hidden="true">↗</span></a>'
            + (f'<span class="source-date">{escape(dates)}</span>' if dates else "")
            + '</li>'
        )
    evidence = '<p class="evidence-note">Includes RSS-summary evidence.</p>' if any(s["rss_only"] for s in story["sources"]) else ""
    return '<section class="story-sources"><h2>Original reporting</h2><ul>' + ''.join(links) + '</ul>' + evidence + '</section>' if links else '<p class="evidence-note">Original source links are unavailable for this report.</p>'


def _story(story, generated_at, historic=False):
    artwork, tone = _theme(story)
    identifier = story_id(story)
    topics = " · ".join(story["topics"]) or "News"
    tags = " · ".join(filter(None, [" · ".join(story["geography"]), story["importance"].capitalize(), story["freshness"].replace("_", " ").capitalize()]))
    original = ""
    if story["sources"]:
        source = story["sources"][0]
        original = (
            f'<a class="story-original" href="{escape(source["url"])}" target="_blank" rel="noopener noreferrer" aria-label="Read original reporting from {escape(source["source"])}">'
            '<span>Original</span> <span aria-hidden="true">↗</span></a>'
        )
    paragraphs = ''.join(f'<p>{escape(p.strip())}</p>' for p in story["summary"].split("\n\n") if p.strip())
    if not paragraphs:
        paragraphs = '<p>Summary unavailable: this report has not completed evidence review.</p>'
    why = f'<section class="story-context"><h2>Why it matters</h2><p>{escape(story["why_matters"])}</p></section>' if story["why_matters"] else ""
    return (
        f'<article class="article reader-story tone-{tone}" id="{identifier}" tabindex="-1" data-read-key="{escape(story["read_key"])}" data-topics="{escape(json.dumps(story["topics"]))}" data-geography="{escape(json.dumps(story["geography"]))}" data-historic="{str(historic).lower()}">'
        f'<div class="story-hero">{original}<div class="hero-inner"><div class="hero-quote"><span class="eyebrow">From this briefing</span><blockquote class="briefing-quote">{escape(_pull_quote(story))}</blockquote></div>'
        f'<img class="editorial-art" src="assets/editorial-{artwork}.png" alt="Original editorial illustration about {artwork}" width="480" height="480" loading="lazy"></div></div>'
        f'<div class="story-body"><div class="story-signature">{LOGO}<span>Daily News</span></div>'
        f'<p class="eyebrow story-topic">{escape(topics)}</p><h1 class="story-title">{escape(story["title"])}</h1><p class="story-metadata">{escape(tags)}</p>'
        f'<p class="produced-date">Briefing produced {_date(generated_at)}</p><section class="story-summary" aria-label="Summary">{paragraphs}</section>{why}{_sources(story)}'
        '<div class="story-reading"><button class="read-toggle" type="button" hidden>Mark read</button><span class="read-label" aria-live="polite"></span></div></div></article>'
    )


def _story_link(story, date, page_path, historic=False):
    identifier = story_id(story)
    _, tone = _theme(story)
    return (
        f'<a class="story-link tone-{tone}" href="{escape(page_path)}#{identifier}" data-story-id="{identifier}">'
        f'<span class="story-link-meta">{escape(" · ".join(story["topics"]) or "News")}<span class="story-read-indicator" hidden>Read</span></span>'
        f'<span class="story-link-title">{escape(story["title"])}</span>'
        f'<span class="story-link-date">{escape(_date(date).split(",")[0])}{" · Earlier edition" if historic else ""}</span></a>'
    )


def _edition_calendar(current, history, archive):
    """Use Auckland dates and real edition links; scripts only collapse day panels."""
    latest_link = '<a class="calendar-latest" href="index.html">Back to the latest edition <span aria-hidden="true">↗</span></a>'
    timestamp = _timestamp(current["generated_at"])
    if not timestamp:
        return f'<details class="edition-calendar"><summary>Browse editions</summary><p>Date unavailable</p>{latest_link}</details>'
    end = timestamp.astimezone(ZoneInfo("Pacific/Auckland")).date()
    start = end - timedelta(days=6)
    days = {start + timedelta(days=i): [] for i in range(7)}
    seen = set()
    for item in [current, *history]:
        date = _timestamp(item["generated_at"])
        if not date or not RUN_ID.fullmatch(item["run_id"]) or item["run_id"] in seen:
            continue
        seen.add(item["run_id"])
        date = date.astimezone(ZoneInfo("Pacific/Auckland"))
        if date.date() in days:
            days[date.date()].append((date, item))
    cells, panels = [], []
    for day, editions in days.items():
        label = day.strftime("%A, %-d %B %Y")
        face = f'<span>{day:%a}</span><strong>{day.day}</strong>'
        if not editions:
            cells.append(f'<button class="calendar-day is-empty" type="button" disabled aria-label="No editions for {label}">{face}<span class="calendar-marks" aria-hidden="true">&nbsp;</span></button>')
            continue
        panel_id = f'edition-day-{day.isoformat()}'
        selected = ' aria-current="true"' if day == end else ''
        count = f'{len(editions)} edition' + ('s' if len(editions) != 1 else '')
        cells.append(f'<a class="calendar-day" href="#{panel_id}" aria-controls="{panel_id}" aria-label="{label}, {count}"{selected}>{face}<span class="calendar-marks" aria-hidden="true">{"·" * min(len(editions), 3)}</span></a>')
        links = []
        for date, item in sorted(editions, key=lambda pair: pair[0]):
            is_current = item["run_id"] == current["run_id"]
            href = "index.html" if is_current and not archive else f'archive/{item["run_id"]}.html'
            marker = ' aria-current="page"' if is_current else ''
            preview = ' <span class="calendar-preview">Review preview</span>' if item['publication_status'] != 'published' else ''
            time = date.strftime("%-I:%M %p").lower() + date.strftime(" %Z")
            links.append(f'<a href="{escape(href)}"{marker}>{time}{preview}</a>')
        panels.append(f'<section class="edition-panel" id="{panel_id}" aria-label="{label}"><p>{day:%A}, {day.day} {day:%B}</p><nav aria-label="Editions for {label}">{"".join(links)}</nav></section>')
    return f'''<details class="edition-calendar"><summary><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6m10-6v6M3 11h18"/></svg>Browse editions<span class="calendar-summary-note">Past 7 days</span></summary>
<div class="calendar-heading"><strong>{start.day} {start:%b} – {end.day} {end:%b}</strong><span>{end.year}</span></div>
<div class="calendar-days" role="group" aria-label="Publication dates">{"".join(cells)}</div>
<div class="calendar-panels">{"".join(panels)}</div>{latest_link}</details>'''


def render_edition(edition, archives=(), *, archive=False):
    """Render a static archive reader; anchors remain usable without JavaScript."""
    current = reader_snapshot(edition)
    generated = _timestamp(current["generated_at"])
    history = [
        reader_snapshot(item) for item in archives
        if RUN_ID.fullmatch(str(item.get("run_id", ""))) and item.get("run_id") != current["run_id"]
    ]
    stories = current["stories"]
    seen = {story["read_key"] for story in stories}
    historic = []
    for item in history:
        timestamp = _timestamp(item["generated_at"])
        if not generated or not timestamp or not generated - timedelta(days=7) <= timestamp <= generated:
            continue
        for story in item["stories"]:
            if story["read_key"] not in seen:
                historic.append((story, item["generated_at"]))
                seen.add(story["read_key"])
    all_stories = stories + [story for story, _ in historic]
    page_path = f'archive/{current["run_id"]}.html' if archive else "index.html"
    status = "Published edition" if current["publication_status"] == "published" else "Review preview - not published"
    topic_options = ''.join(f'<option>{escape(tag)}</option>' for tag in TOPICS if any(tag in s["topics"] for s in all_stories))
    geography_options = ''.join(f'<option>{escape(tag)}</option>' for tag in sorted({tag for s in all_stories for tag in s["geography"]}))
    calendar = _edition_calendar(current, history, archive)
    featured = [s for s in stories if s["featured"]]
    remaining = [s for s in stories if not s["featured"]]
    sidebar_stories = ''
    for label, group in [("Featured", featured), ("More to explore", remaining)]:
        if group:
            sidebar_stories += f'<div class="story-group"><h2>{label}</h2>' + ''.join(_story_link(s, current["generated_at"], page_path) for s in group) + '</div>'
    if historic:
        sidebar_stories += '<div class="story-group history-group"><h2>Seven-day overview</h2>' + ''.join(_story_link(s, date, page_path, True) for s, date in historic) + '</div>'
    local_date = generated.astimezone(ZoneInfo("Pacific/Auckland")) if generated else None
    refresh_date = local_date.strftime("%-d %B %Y") if local_date else "Date unavailable"
    refresh_time = local_date.strftime("%-I:%M %p").lower() + local_date.strftime(" %Z") if local_date else ""
    briefing_label = local_date.strftime("%A") + "’s briefing" if local_date else "Your daily briefing"
    refresh_datetime = f' datetime="{escape(generated.isoformat())}"' if generated else ""
    body = f'''
<a class="skip-link" href="{escape(page_path)}#reader-content">Skip to story</a>
<header class="mobile-header">{LOGO}<span class="mobile-brand"><strong>Daily News</strong><time{refresh_datetime}>{escape(refresh_date)}</time></span><button id="browse-stories" type="button" aria-controls="story-browser" aria-expanded="false">Browse stories</button></header>
<aside id="story-browser" aria-label="Story browser">
  <div class="browser-intro"><a class="reader-brand" href="index.html" aria-label="Daily News, latest edition">{LOGO}<strong>Daily News</strong></a><button id="close-browser" type="button" aria-label="Close story browser">×</button>
  <div class="edition-refresh"><span class="eyebrow">{briefing_label}</span><time class="edition-date"{refresh_datetime}><span class="refresh-date">{escape(refresh_date)}</span><span class="refresh-time">As of {escape(refresh_time)}</span></time><span class="edition-status">{status}</span>{calendar}</div></div>
  <div class="reader-controls" hidden><label class="search-label" for="story-search">Search stories</label><div class="search-field"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6.5"/><path d="m15 15 6 6"/></svg><input id="story-search" type="search" placeholder="Find something to read…" autocomplete="off"></div>
    <div class="filter-row"><label>Topic<select id="topic-filter"><option value="">All topics</option>{topic_options}</select></label><label>Geography<select id="geography-filter"><option value="">All places</option>{geography_options}</select></label></div>
    <div class="filter-checks"><label><input id="unread-filter" type="checkbox"> Unread only</label><label><input id="history-filter" type="checkbox"> Include past 7 days</label></div>
  </div>
  <div class="browser-list"><div class="browser-list-heading"><strong>Browse stories</strong><span id="result-count" role="status"></span></div><nav class="story-list" aria-label="Stories">{sidebar_stories}</nav><p id="browser-empty" hidden>No stories match. Try another topic or clear the search.</p></div>
  <details class="browser-options"><summary>Reading preferences</summary><p id="storage-status" role="status">Read state stays in this browser. Opening a source does not mark a story read.</p><button id="reset-read" type="button" hidden>Reset read state</button><p class="publisher-credit">AJC Analytics Limited</p></details>
</aside>
<button class="browser-backdrop" id="browser-backdrop" type="button" aria-label="Close story browser" tabindex="-1" hidden></button>
<button id="collapse-browser" type="button" aria-label="Collapse story browser" aria-controls="story-browser" aria-expanded="true" hidden><span aria-hidden="true">«</span></button>
<main id="reader-content" tabindex="-1"><noscript><p class="no-script">Choose a title to jump to its story. All summaries are readable below. Filters and read marks need JavaScript.</p></noscript>
{''.join(_story(s, current['generated_at']) for s in featured + remaining)}
{''.join(_story(s, date, True) for s, date in historic)}
<section id="reader-empty" hidden><span class="eyebrow">Nothing here yet</span><h1>No stories match these filters.</h1><p>Try a different topic or clear your search.</p><button id="clear-filters" type="button">Clear filters</button></section>
</main>'''
    directory = Path(__file__).parent
    css = directory.joinpath("reader.css").read_text()
    script = directory.joinpath("reader.js").read_text()
    return f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta name="color-scheme" content="light"><title>Daily News - {escape(_date(current["generated_at"]))}</title><style>{css}</style></head><body>{body}<script>{script}</script></body></html>'
