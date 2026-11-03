"""Opt-in real-browser regressions through REA's declared browser scenarios.

Set NEWS_BROWSER_BINARY to a Chromium executable and put rea on PATH.
The fixture server, browser profile and captures are disposable and local.
"""

import copy
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import Thread
import unittest

from news.reader_assets import write_reader_assets
from news.render import reader_snapshot, render_edition, story_id
from tests.test_render import edition


@unittest.skipUnless(os.getenv("NEWS_BROWSER_BINARY") and shutil.which("rea"),
                     "Set NEWS_BROWSER_BINARY and install REA for browser checks")
class ReaderBrowserTests(unittest.TestCase):
    def test_desktop_and_mobile_story_browsing(self):
        item = edition()
        other = copy.deepcopy(item["stories"][0])
        other.update(event_id="second", title="Second report", featured=False,
                     topics=["Politics"], geography=["United States"])
        item["stories"].append(other)
        first, second = [story_id(s) for s in reader_snapshot(item)["stories"]]
        old = copy.deepcopy(edition())
        old.update(run_id="11111111-1111-4111-8111-111111111111", generated_at="2026-10-18T01:00:00Z")
        old["stories"][0].update(event_id="historic", title="Earlier report")
        historic = story_id(reader_snapshot(old)["stories"][0])

        def step(action, selector, **values):
            return dict(action=action, locator={"kind": "css", "selector": selector},
                        timeout_ms=5000, **values)

        def wait(selector):
            return step("wait_for", selector, state="visible")

        def click(selector):
            return step("click", selector)

        def value(action, selector, text):
            return step(action, selector, value={"source": "literal", "value": text})

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # A fixture-only control invokes the same history API as the browser Back button.
            back = '<button id="test-back" style="position:fixed;right:0;bottom:0;z-index:100" onclick="window.history.back()">Back test</button>'
            (root / "index.html").write_text(render_edition(item, [old]).replace("</body>", back + "</body>"))
            (root / "archive").mkdir()
            archive = render_edition(old, archive=True).replace("<head>", '<head><base href="../">', 1)
            (root / "archive" / (old["run_id"] + ".html")).write_text(archive)
            write_reader_assets(root)

            class QuietHandler(SimpleHTTPRequestHandler):
                def log_message(self, *args):
                    pass

            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=root))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_port}/index.html"
            try:
                scenarios = {
                    "desktop": (1440, 1000, [
                        click('.edition-calendar summary'),
                        click('a.calendar-day[href="#edition-day-2026-10-18"]'),
                        wait('#edition-day-2026-10-18:not([hidden])'),
                        click('#edition-day-2026-10-18 a'),
                        wait(f'.story-link[href^="archive/{old["run_id"]}.html#"]'),
                        click('.edition-calendar summary'),
                        wait('.edition-panel a[aria-current="page"]'),
                        click('.calendar-latest'),
                        wait(f'#{first}:not([hidden])'),
                        click(f'.story-link[data-story-id="{second}"]'),
                        value("fill", "#story-search", "Second report"),
                        click("#test-back"),
                        wait(f'#{first}:not([hidden])'),
                        click(f'.story-link[data-story-id="{second}"]'),
                        value("fill", "#story-search", "nothing matches this news"),
                        wait("#reader-empty:not([hidden])"),
                        click("#test-back"),
                        wait(f'#{first}:not([hidden])'),
                        click(f'.story-link[data-story-id="{second}"]'),
                        wait(f'#{second}:not([hidden])'),
                        click(f'#{second} .read-toggle'),
                        wait(f'#{second} .read-toggle[aria-pressed="true"]'),
                        step("check", "#unread-filter"),
                        wait(f'#{first}:not([hidden])'),
                        value("select_option", "#topic-filter", "Politics"),
                        wait("#reader-empty:not([hidden])"),
                        click("#clear-filters"),
                        click("#collapse-browser"),
                        wait('body.browser-collapsed #collapse-browser[aria-expanded="false"]'),
                        click("#collapse-browser"),
                        value("fill", "#story-search", "Second report"),
                        wait(f'#{second}:not([hidden])'),
                        {"action": "goto", "destination": {"url": url + "#" + second}, "wait_until": "load"},
                        wait(f'#{second}:not([hidden]) .read-toggle[aria-pressed="true"]'),
                        value("fill", "#story-search", ""),
                        step("check", "#history-filter"),
                        click(f'.story-link[data-story-id="{historic}"]'),
                        wait(f'#{historic}:not([hidden])'),
                        {"action": "goto", "destination": {"url": url + "#" + historic}, "wait_until": "load"},
                        wait('#history-filter:checked'),
                        wait(f'#{historic}:not([hidden])'),
                        {"action": "goto", "destination": {"url": url.rsplit("/", 1)[0] + "/archive/" + old["run_id"] + ".html"}, "wait_until": "load"},
                        click(f'.story-link[data-story-id="{historic}"]'),
                        wait(f'#{historic}:not([hidden])'),
                    ]),
                    "mobile": (390, 844, [
                        click("#browse-stories"),
                        click('.edition-calendar summary'),
                        click('a.calendar-day[href="#edition-day-2026-10-18"]'),
                        wait('#edition-day-2026-10-18:not([hidden])'),
                        click('a.calendar-day[href="#edition-day-2026-10-19"]'),
                        wait('#edition-day-2026-10-19:not([hidden])'),
                        click('.edition-calendar summary'),
                        wait('#story-browser[role="dialog"][aria-modal="true"]'),
                        wait('#reader-content[inert]'),
                        value("select_option", "#topic-filter", "Politics"),
                        click(f'.story-link[data-story-id="{second}"]'),
                        wait(f'#{second}:not([hidden])'),
                        wait('#browse-stories[aria-expanded="false"]'),
                        click("#browse-stories"),
                        step("press", "#story-search", key="Escape"),
                        wait('#browse-stories[aria-expanded="false"]'),
                        click("#browse-stories"),
                        value("fill", "#story-search", "no matching news"),
                        wait("#browser-empty:not([hidden])"),
                        value("fill", "#story-search", ""),
                        click(f'.story-link[data-story-id="{second}"]'),
                        wait(f'#{second}:not([hidden])'),
                    ]),
                }
                for name, (width, height, actions) in scenarios.items():
                    with self.subTest(viewport=name):
                        for index, action in enumerate(actions):
                            action["step_id"] = f"step_{index}"
                        scenario = {
                            "browser": {"mode": "launch", "headless": True,
                                        "executable_path": os.environ["NEWS_BROWSER_BINARY"]},
                            "start_url": {"url": url},
                            "environment": {"viewport": {"width": width, "height": height}},
                            "actions": actions,
                            "capture": {"after_each_step": ["url"], "at_end": ["url", "dom", "screenshot"]},
                        }
                        path = root / (name + ".json")
                        path.write_text(json.dumps(scenario))
                        result = subprocess.run(["rea", "capture-browser-scenario", str(path), "--json"],
                                                capture_output=True, text=True, timeout=120)
                        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-4000:])
                        evidence = json.loads(result.stdout)["normalized_result"]
                        failures = [(s["step_id"], s.get("error")) for s in evidence["steps"] if s["status"] != "completed"]
                        self.assertFalse(failures, failures)
                        if name == "desktop":
                            search_index = next(i for i, a in enumerate(actions)
                                                if a["action"] == "fill" and a["value"]["value"] == "Second report"
                                                and actions[i + 1]["action"] == "wait_for")
                            search_step = next(s for s in evidence["steps"] if s["step_id"] == f"step_{search_index + 1}")
                            self.assertTrue(search_step["artifacts"]["url"]["value"]["url"].endswith("#" + second), search_step["artifacts"]["url"]["value"])
                        self.assertEqual(len(evidence["steps"]), len(actions) + 1)
                        self.assertEqual(evidence["browser"]["cleanup"], "terminated-owned-process")
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
