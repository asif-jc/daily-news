"""Public reader contracts and publication boundaries, without network services."""

import copy
import json
import unittest

from news.render import render_edition, reader_snapshot


def edition():
    return {
        "schema_version": 3,
        "run_id": "run-1",
        "generated_at": "2026-10-19T01:00:00Z",
        "publication_status": "preview",
        "private_audit": "DO_NOT_PUBLISH",
        "stories": [
            {
                "event_id": "event-1",
                "title": "A <new> event",
                "summary": "Facts & context",
                "why_matters": "",
                "topics": ["Science"],
                "geography": ["NZ"],
                "importance": "notable",
                "freshness": "new",
                "featured": True,
                "support": "PRIVATE_SUPPORT",
                "sources": [
                    {
                        "source": "BBC",
                        "url": "https://www.bbc.com/news",
                        "published": "2026-10-18T23:00:00Z",
                        "evidence_basis": "feed_summary",
                        "used_in_summary": True,
                        "raw_text": "PRIVATE_SOURCE",
                    }
                ],
            }
        ],
    }


class ReaderTests(unittest.TestCase):
    def test_fallback_contains_one_story_and_warm_reader(self):
        page = render_edition(edition(), [])
        self.assertIn("assets/editorial-", page)
        self.assertIn("AJC Analytics Limited", page)
        self.assertEqual(page.count('class="article reader-story'), 1)
        self.assertIn("A &lt;new&gt; event", page)
        self.assertIn("RSS-summary evidence", page)
        self.assertIn("Review preview", page)
        self.assertIn('id="topic-filter"', page)
        self.assertIn('id="geography-filter"', page)
        self.assertIn('id="unread-filter"', page)
        self.assertIn('id="reset-read"', page)

    def test_geographic_aliases_share_one_filter(self):
        item = edition()
        item["stories"][0]["geography"] = [
            "US",
            "U.S.",
            "USA",
            "United States",
            "New Zealand",
        ]
        self.assertEqual(
            reader_snapshot(item)["stories"][0]["geography"], ["United States", "NZ"]
        )

    def test_snapshot_whitelists_and_sanitizes_fields(self):
        item = edition()
        item["stories"][0]["sources"].append(
            {"source": "Unsafe", "url": "javascript:alert(1)"}
        )
        snapshot = reader_snapshot(item)
        serialized = json.dumps(snapshot)
        for secret in (
            "DO_NOT_PUBLISH",
            "PRIVATE_SUPPORT",
            "PRIVATE_SOURCE",
            "javascript:",
        ):
            self.assertNotIn(secret, serialized)
        self.assertEqual(len(snapshot["stories"][0]["sources"]), 1)

    def test_public_snapshot_is_safe_to_render_again(self):
        snapshot = reader_snapshot(edition())
        self.assertEqual(reader_snapshot(snapshot), snapshot)
        self.assertIn("RSS-summary evidence", render_edition(snapshot, []))

    def test_unsafe_source_schemes_and_credentials_are_removed(self):
        item = edition()
        for url in (
            "data:text/html,bad",
            "//example.com/news",
            "https://user:secret@example.com/news",
            "https://[invalid",
        ):
            item["stories"][0]["sources"] = [{"source": "Unsafe", "url": url}]
            self.assertEqual(reader_snapshot(item)["stories"][0]["sources"], [])

    def test_empty_summary_exposes_processing_boundary(self):
        item = edition()
        item["stories"][0]["summary"] = ""
        self.assertIn("Summary unavailable", render_edition(item, []))

    def test_story_markup_cannot_close_script_and_no_duplicate_payload(self):
        item = edition()
        item["stories"][0]["summary"] = '</script><img src=x onerror="alert(1)">'
        page = render_edition(item, [])
        self.assertNotIn("<img src=x", page)
        self.assertIn(
            "&lt;/script&gt;&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", page
        )
        self.assertNotIn('id="reader-data"', page)
        self.assertEqual(page.count("</script>"), 1)

    def test_same_event_update_identity_ignores_placement_and_freshness(self):
        item = edition()
        first = reader_snapshot(item)["stories"][0]["read_key"]
        item["stories"][0].update(featured=False, freshness="previously_featured")
        self.assertEqual(reader_snapshot(item)["stories"][0]["read_key"], first)
        item["stories"][0]["summary"] = "A material update"
        self.assertNotEqual(reader_snapshot(item)["stories"][0]["read_key"], first)

    def test_lineage_revision_preserves_read_identity_across_editorial_wording(self):
        item = edition()
        item["stories"][0]["revision_key"] = "revision-1"
        snapshot = reader_snapshot(item)
        self.assertEqual(snapshot["stories"][0]["read_key"], "event-1:revision-1")
        self.assertEqual(reader_snapshot(snapshot), snapshot)
        item["stories"][0].update(
            summary="Same facts, clearer wording",
            title="A clearer title",
            featured=False,
            freshness="catch_up",
        )
        self.assertEqual(
            reader_snapshot(item)["stories"][0]["read_key"], "event-1:revision-1"
        )
        item["stories"][0]["revision_key"] = "revision-2"
        self.assertEqual(
            reader_snapshot(item)["stories"][0]["read_key"], "event-1:revision-2"
        )

    def test_week_deduplicates_same_lineage_with_different_summary_wording(self):
        item = edition()
        item["stories"][0]["revision_key"] = "revision-1"
        old = copy.deepcopy(item)
        old.update(run_id="run-0", generated_at="2026-10-18T01:00:00Z")
        old["stories"][0]["summary"] = "Earlier wording of unchanged facts"
        page = render_edition(item, [old])
        self.assertEqual(page.count('class="article reader-story'), 1)
        old["stories"][0]["revision_key"] = "revision-0"
        page = render_edition(item, [old])
        self.assertEqual(page.count('class="article reader-story'), 2)

    def test_archive_paths_are_bounded_and_week_deduplicates_updates(self):
        old = copy.deepcopy(edition())
        old.update(
            run_id="run-0",
            generated_at="2026-10-18T01:00:00Z",
            publication_status="published",
        )
        bad = dict(old, run_id="../private")
        page = render_edition(edition(), [old, bad])
        self.assertIn('href="archive/run-0.html"', page)
        self.assertNotIn('href="archive/../', page)
        self.assertEqual(page.count('class="article reader-story'), 1)
        old["stories"][0]["summary"] = "Earlier report"
        page = render_edition(edition(), [old])
        self.assertEqual(page.count('class="article reader-story'), 2)
        self.assertIn("Earlier report", page)

    def test_week_excludes_old_editions_but_keeps_date_navigation(self):
        old = copy.deepcopy(edition())
        old.update(run_id="old", generated_at="2026-09-01T01:00:00Z")
        old["stories"][0]["summary"] = "Outside the week"
        page = render_edition(edition(), [old])
        self.assertIn('href="archive/old.html"', page)
        self.assertNotIn("Outside the week", page)

    def test_absent_sources_and_bad_dates_remain_readable(self):
        item = edition()
        item["stories"][0]["sources"] = []
        item["generated_at"] = "unknown"
        self.assertIn("Facts &amp; context", render_edition(item, []))


if __name__ == "__main__":
    unittest.main()


class ArchiveWindowTests(unittest.TestCase):
    def test_seven_day_window_includes_more_than_seven_editions_and_excludes_stale(
        self,
    ):
        current = edition()
        archives = []
        for n in range(9):
            old = edition()
            old["run_id"] = f"old-{n}"
            old["generated_at"] = f"2026-10-18T{n:02}:00:00Z"
            old["stories"][0]["event_id"] = f"event-old-{n}"
            old["stories"][0]["title"] = f"Historic report {n}"
            archives.append(old)
        stale = copy.deepcopy(archives[-1])
        stale["run_id"] = "stale"
        stale["generated_at"] = "2026-10-01T00:00:00Z"
        stale["stories"][0]["title"] = "Stale report"
        page = render_edition(current, archives + [stale])
        self.assertIn("Historic report 8", page)
        self.assertNotIn("Stale report", page)
