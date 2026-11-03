# Story archive reader

The reference is [Dense Discovery issue 411](https://www.densediscovery.com/issues/411). REA browser scenarios verified desktop archive selection and mobile Browse issues selection, including the loaded issue state. The adaptation uses story titles, our reviewed summaries and our original artwork. It does not import the reference's scripts, artist images, branded logo, tracking or subscriptions.

## Reading and navigation

Python renders escaped reader fields into static HTML. Every story is present once and has a stable anchor derived from its existing revision-aware read identity. With JavaScript, the sidebar selects one story, remembers explicit read marks, filters the retained edition and navigates browser history. Without JavaScript, the title links jump to full stories; filters and read marking are unavailable.

Desktop has an independently scrolling story index and reading pane. Mobile has a Browse stories drawer with focus containment, Escape/close actions and focus return. Search, topic, geography, unread and seven-day filters retain the existing reader's useful controls. Automatic selection replaces the story URL; an explicit title selection adds a history entry. Dated archives retain their own paths even with a parent base URL.

The top-right Original action opens the first approved reporting source. Every source remains listed with its available publication/update dates. Opening a source does not mark the story read. The header pull quote is the first reviewed summary sentence, or the story title if that sentence exceeds 40 words. It is labelled “From this briefing”, without invented attribution. News prompts and retained factual content are unchanged.

## Artwork and logo

Issue 411 credits **Justina Leisyte** for its artwork. This investigation did not establish a shared reusable artwork library or permission to republish that art. The reader therefore uses three newly generated, original illustrations and a small original folded-paper/N logo drawn as inline SVG.

The illustrations were generated on 27 October 2026 with the image-generation tool. They are transparent PNGs, resized to 720 pixels on the longest edge with metadata removed. The current mapping is deliberately small: technology/AI, science/environment/geography, and other news. Artwork is thematic, not a depiction or evidence of the reported event. Story-specific artwork is a future design choice, not an automatic model call added to the pipeline.

| Asset | Subject prompt |
|---|---|
| `editorial-curiosity.png` | Curious human profile, fern and a magnifying-glass sun |
| `editorial-world.png` | Hands holding a globe, leaves and a bird |
| `editorial-technology.png` | Human profile, a constellation of dots, paper and fern |

Shared generation direction: a standalone illustration for a warm independent news reader; original editorial pen-and-ink drawing; flat near-black silhouettes with fine loose lines and generous negative space; human, simple and readable at 280 pixels; no text, logos, signatures, borders, photos, gradients, shading or website mockup; black ink on a fully transparent background, subject comfortably within a square composition, beside a quote on a flat peach or sage header. No reference artwork was supplied to the generator.

## Export and verification

`reader_assets.py` owns the three finite public artwork paths. Both private workflow previews and strict release exports use that set. Legacy release manifests remain verifiable; a new manifest must carry the complete new set, and mixed or partial asset sets are rejected. The render checkpoint version changes so an existing run does not reuse the former HTML.

Run the normal suite against a disposable loopback `news` database using `NEWS_TEST_DATABASE_URL`. Browser regression coverage is opt-in and uses the installed REA CLI and a Chromium executable:

```sh
NEWS_BROWSER_BINARY='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
python -m unittest tests.test_reader_browser
```

The test starts a temporary local fixture server and owned headless browser profiles, verifies desktop/mobile selection, filters, read persistence, historical deep links and native archive paths, and requires REA to report every declared step complete with owned-browser cleanup. It replaces the previous DOM-mock test of the old card-placement algorithm. Manual browser checks additionally cover Back/Forward and 320-pixel and short-height layouts.

## Preview boundary

The review preview uses the retained 26 October source-audited edition, not a newly generated news run. It is a presentation checkpoint. The feature PR leaves `site/`, main and the production publication receipt unchanged. An isolated `previews/pr-N/` directory on the existing Pages branch serves the preview. A later production publish can remove this temporary preview because the production workflow owns the Pages root.

## Sidebar refinement

The product name is **Daily News**. A ruled editorial dateline identifies the weekday's briefing and edition date. The secondary **As of** time uses Pacific/Auckland and represents the retained snapshot, not deployment completion; rebuilding HTML does not change it. The mobile header repeats the edition date while the drawer is closed.

**Browse editions** opens a seven-day publication calendar ending on the viewed edition's Auckland date. Available days reveal their individual publication times, with the selected edition highlighted. Missing days are disabled. An **Earlier editions** link bridges older retained windows, including gaps longer than a week; **Latest edition** returns to the current reader. Real links remain usable without scripts. **Reading preferences** is a separate disclosure.

Search and native topic/place selectors share dark outlines, white surfaces and larger touch targets. A left border reinforces the selected story. At 360px and below, selectors stack to keep longer place names readable. The sidebar retains its overall scroll path for short screens and expanded calendar and reading preferences.
