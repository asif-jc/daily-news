"""Contracts for a story-first archive reader, including script-free navigation."""

import copy
import unittest

from bs4 import BeautifulSoup

from news.render import render_edition
from tests.test_render import edition


class StoryNavigationTests(unittest.TestCase):
    def page(self, item=None, **kwargs):
        return BeautifulSoup(render_edition(item or edition(), **kwargs), "html.parser")

    def test_every_story_has_one_real_anchor_and_one_article(self):
        item = edition()
        other = copy.deepcopy(item["stories"][0])
        other.update(event_id="second", title="Second story", featured=False)
        item["stories"].append(other)
        page = self.page(item)
        links = page.select(".story-link")
        articles = page.select("article.reader-story")
        self.assertEqual(len(links), 2)
        self.assertEqual(len(articles), 2)
        self.assertEqual(
            {link["href"].split("#")[1] for link in links},
            {article["id"] for article in articles},
        )
        self.assertTrue(all(not article.has_attr("hidden") for article in articles))
        self.assertIn("Browse stories", page.get_text())

    def test_source_action_is_reporting_not_a_fake_copy_control(self):
        page = self.page()
        link = page.select_one(".story-original")
        self.assertEqual(link["href"], "https://www.bbc.com/news")
        self.assertIn("original", link["aria-label"].lower())
        self.assertIn("noopener", link["rel"])
        self.assertEqual(page.select_one(".story-title").get_text(), "A <new> event")

    def test_header_pull_quote_is_existing_briefing_text_without_attribution(self):
        item = edition()
        item["stories"][0]["summary"] = "A reviewed opening sentence. Supporting detail follows."
        page = self.page(item)
        self.assertEqual(page.select_one(".briefing-quote").get_text(strip=True), "A reviewed opening sentence.")
        self.assertIn("From this briefing", page.get_text())
        self.assertIsNone(page.select_one(".briefing-quote cite"))
        self.assertTrue(page.select_one(".editorial-art")["src"].startswith("assets/editorial-"))

    def test_archive_story_links_stay_in_the_selected_edition(self):
        page = self.page(archive=True)
        self.assertTrue(page.select_one(".story-link")["href"].startswith("archive/run-1.html#story-"))

    def test_search_and_mobile_browser_have_explicit_labels(self):
        page = self.page()
        self.assertEqual(page.select_one("#story-search")["type"], "search")
        self.assertEqual(page.select_one(".reader-brand").get_text(strip=True), "Daily News")
        self.assertNotIn("Daily News Reader", page.get_text())
        refreshed = page.select_one(".edition-date")
        self.assertEqual(refreshed["datetime"], "2026-10-19T01:00:00+00:00")
        self.assertEqual(refreshed.select_one(".refresh-date").get_text(), "19 October 2026")
        self.assertIn("As of 2:00 pm NZDT", refreshed.get_text())
        self.assertIn("Monday’s briefing", page.get_text())
        self.assertNotIn("Last refreshed", page.get_text())
        self.assertEqual(page.select_one("#browse-stories")["aria-controls"], "story-browser")
        self.assertIsNotNone(page.select_one("#close-browser"))
        self.assertIsNotNone(page.select_one("#reader-empty"))
        self.assertIsNotNone(page.select_one("#topic-filter"))
        self.assertIsNotNone(page.select_one("#geography-filter"))

    def test_no_related_story_or_subscription_noise(self):
        page = self.page()
        self.assertIsNone(page.select_one("form"))
        self.assertNotIn("Related stories", page.get_text())
        self.assertIn("Briefing produced", page.get_text())

    def test_calendar_groups_editions_by_auckland_day_and_keeps_both_times(self):
        current = edition()
        current.update(generated_at="2026-11-03T02:00:00Z", publication_status="published")
        morning = copy.deepcopy(current)
        morning.update(run_id="morning", generated_at="2026-11-02T14:00:00Z")
        page = self.page(current, archives=[morning])
        panel = page.select_one('#edition-day-2026-11-03')
        self.assertEqual(len(panel.select('a')), 2)
        self.assertIn('3:00 am NZDT', panel.get_text())
        self.assertIn('3:00 pm NZDT', panel.get_text())
        self.assertEqual(panel.select_one('[aria-current="page"]')['href'], 'index.html')
        self.assertEqual(panel.select_one('a[href="archive/morning.html"]').get_text(strip=True), '3:00 am NZDT')
        self.assertEqual(len(page.select('.calendar-day')), 7)

    def test_calendar_handles_month_boundary_gaps_and_seven_day_limit(self):
        current = edition()
        current.update(generated_at="2026-11-02T14:00:00Z")
        recent = copy.deepcopy(current)
        recent.update(run_id="recent", generated_at="2026-10-29T14:00:00Z")
        stale = copy.deepcopy(current)
        stale.update(run_id="stale", generated_at="2026-10-26T14:00:00Z")
        invalid = copy.deepcopy(recent)
        invalid.update(run_id="invalid", generated_at="bad-date")
        page = self.page(current, archives=[recent, recent, stale, invalid])
        calendar = page.select_one('.edition-calendar')
        self.assertIn('28 Oct', calendar.get_text())
        self.assertEqual(len(calendar.select('a[href="archive/recent.html"]')), 1)
        self.assertEqual(calendar.select_one('.calendar-earlier')['href'], 'archive/stale.html')
        self.assertIsNone(calendar.select_one('#edition-day-2026-10-27'))
        self.assertIsNone(calendar.select_one('a[href="archive/invalid.html"]'))
        self.assertEqual(len(calendar.select('.calendar-day.is-empty')), 5)
        self.assertTrue(all(not p.has_attr('hidden') for p in calendar.select('.edition-panel')))

    def test_archive_calendar_marks_current_page_and_preserves_latest_link(self):
        page = self.page(archive=True)
        self.assertEqual(page.select_one('.edition-panel [aria-current="page"]')['href'], 'archive/run-1.html')
        self.assertEqual(page.select_one('.calendar-latest')['href'], 'index.html')
        self.assertEqual(page.select_one('a.calendar-day')['href'], 'archive/run-1.html#edition-day-2026-10-19')
        self.assertIn('Review preview', page.select_one('.edition-panel').get_text())

    def test_earlier_link_bridges_gaps_between_retained_calendar_windows(self):
        september = copy.deepcopy(edition())
        september.update(run_id="september", generated_at="2026-09-20T01:00:00Z")
        oldest = copy.deepcopy(september)
        oldest.update(run_id="oldest", generated_at="2026-09-01T01:00:00Z")
        page = self.page(archives=[oldest, september])
        self.assertEqual(page.select_one('.calendar-earlier')['href'], 'archive/september.html')
        previous = self.page(september, archives=[oldest], archive=True)
        self.assertEqual(previous.select_one('.calendar-earlier')['href'], 'archive/oldest.html')

    def test_undated_edition_keeps_a_useful_archive_fallback(self):
        current = edition()
        current['generated_at'] = 'unknown'
        page = self.page(current)
        self.assertIn('Date unavailable', page.get_text())
        self.assertEqual(page.select_one('.calendar-latest')['href'], 'index.html')


if __name__ == "__main__":
    unittest.main()
