/* Navigation changes the selected story; only an explicit action changes read state. */
(() => {
  "use strict";
  const storageKey = "daily-news-library-read-v1";
  const browser = document.getElementById("story-browser");
  const browseButton = document.getElementById("browse-stories");
  const collapseButton = document.getElementById("collapse-browser");
  const backdrop = document.getElementById("browser-backdrop");
  const mobile = window.matchMedia("(max-width: 760px)");
  const controls = Object.fromEntries(["story-search", "topic-filter", "geography-filter", "unread-filter", "history-filter"].map(id => [id, document.getElementById(id)]));
  const search = controls["story-search"], topic = controls["topic-filter"], geography = controls["geography-filter"];
  const unread = controls["unread-filter"], history = controls["history-filter"];
  const status = document.getElementById("storage-status");
  const editionDays = [...document.querySelectorAll("a.calendar-day")];
  const editionPanels = [...document.querySelectorAll(".edition-panel")];
  function selectEditionDay(day) {
    editionDays.forEach(link => {
      if (link === day) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    });
    editionPanels.forEach(panel => { panel.hidden = "#" + panel.id !== day.hash; });
  }
  const selectedDay = editionDays.find(day => day.hash === location.hash) || editionDays.find(day => day.hasAttribute("aria-current"));
  if (selectedDay) selectEditionDay(selectedDay);
  editionDays.forEach(day => day.addEventListener("click", event => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    selectEditionDay(day);
  }));
  const stories = [...document.querySelectorAll(".reader-story")].map(article => ({
    article,
    id: article.id,
    key: article.dataset.readKey,
    topics: JSON.parse(article.dataset.topics),
    geography: JSON.parse(article.dataset.geography),
    historic: article.dataset.historic === "true",
    text: article.querySelector(".story-body").textContent.toLocaleLowerCase(),
    link: document.querySelector(`.story-link[data-story-id="${article.id}"]`),
    button: article.querySelector(".read-toggle"),
    matches: true,
  }));
  let read = new Set(), storageAvailable = true, active = null;
  let drawerOpen = false, collapsed = false;
  try {
    const value = JSON.parse(localStorage.getItem(storageKey) || "[]");
    if (Array.isArray(value)) read = new Set(value.filter(key => typeof key === "string"));
  } catch (_) { storageAvailable = false; }

  function showStorageStatus() {
    status.textContent = storageAvailable
      ? "Read state stays in this browser. Opening a source does not mark a story read."
      : "Browser storage is unavailable. Read state lasts for this page only; reading and filters still work.";
  }
  function persist() {
    try { localStorage.setItem(storageKey, JSON.stringify([...read])); }
    catch (_) { storageAvailable = false; }
    showStorageStatus();
  }
  function setDrawer(open, restoreFocus = true) {
    drawerOpen = mobile.matches && open;
    document.body.classList.toggle("browser-open", drawerOpen);
    browseButton.setAttribute("aria-expanded", String(drawerOpen));
    backdrop.hidden = !drawerOpen;
    const unavailable = mobile.matches ? !drawerOpen : collapsed;
    browser.inert = unavailable;
    browser.setAttribute("aria-hidden", String(unavailable));
    document.getElementById("reader-content").inert = drawerOpen;
    if (drawerOpen) {
      browser.setAttribute("role", "dialog");
      browser.setAttribute("aria-modal", "true");
      search.focus();
    } else {
      browser.removeAttribute("role");
      browser.removeAttribute("aria-modal");
    }
    if (!drawerOpen && restoreFocus && mobile.matches) browseButton.focus();
  }
  function choose(story, {push = false, replace = false, focus = false} = {}) {
    const changed = active !== (story || null);
    active = story || null;
    stories.forEach(item => {
      const selected = item === active;
      item.article.hidden = !selected;
      item.link.classList.toggle("is-active", selected);
      if (selected) item.link.setAttribute("aria-current", "true");
      else item.link.removeAttribute("aria-current");
    });
    document.getElementById("reader-empty").hidden = Boolean(active);
    const hash = active ? "#" + active.id : "";
    if ((push || replace) && location.hash !== hash) {
      // Include the current pathname because archive pages have a root-relative base.
      window.history[push ? "pushState" : "replaceState"](null, "", location.pathname + location.search + hash);
    }
    if (changed) document.getElementById("reader-content").scrollTop = 0;
    if (active && focus) {
      active.article.focus({preventScroll: true});
      document.getElementById("reader-content").scrollTop = 0;
      if (mobile.matches) window.scrollTo({top: 0, behavior: "instant"});
    }
  }
  function update({focus = false, syncUrl = true} = {}) {
    const query = search.value.trim().toLocaleLowerCase();
    stories.forEach(item => {
      const isRead = read.has(item.key);
      item.matches = (!query || item.text.includes(query)) &&
        (!topic.value || item.topics.includes(topic.value)) &&
        (!geography.value || item.geography.includes(geography.value)) &&
        (!unread.checked || !isRead) && (!item.historic || history.checked);
      item.link.hidden = !item.matches;
      item.article.classList.toggle("is-read", isRead);
      item.link.classList.toggle("is-read", isRead);
      item.button.textContent = isRead ? "Mark unread" : "Mark read";
      item.button.setAttribute("aria-pressed", String(isRead));
      item.article.querySelector(".read-label").textContent = isRead ? "Read" : "Unread";
      item.link.querySelector(".story-read-indicator").hidden = !isRead;
    });
    document.querySelectorAll(".story-group").forEach(group => {
      group.hidden = ![...group.querySelectorAll(".story-link")].some(link => !link.hidden);
    });
    const matches = stories.filter(item => item.matches);
    document.getElementById("result-count").textContent = `${matches.length} ${matches.length === 1 ? "story" : "stories"}`;
    document.getElementById("browser-empty").hidden = matches.length > 0;
    choose(active?.matches ? active : matches[0], {focus, replace: syncUrl});
  }
  function clearFilters() {
    search.value = topic.value = geography.value = "";
    unread.checked = history.checked = false;
  }
  function fromLocation() {
    const selected = location.hash
      ? stories.find(item => "#" + item.id === location.hash)
      : stories.find(item => !item.historic);
    if (!selected) return;
    if (!selected.matches) {
      clearFilters();
      history.checked = selected.historic;
      update({syncUrl: false});
    }
    choose(selected, {focus: true});
  }
  stories.forEach(item => {
    item.button.hidden = false;
    item.button.addEventListener("click", () => {
      if (read.has(item.key)) read.delete(item.key); else read.add(item.key);
      persist();
      update({focus: !item.matches || unread.checked});
      if (!active) document.getElementById("clear-filters").focus();
    });
    item.link.addEventListener("click", event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      setDrawer(false, false);
      choose(item, {push: true, focus: true});
    });
  });
  search.addEventListener("input", () => update());
  [topic, geography, unread, history].forEach(control => control.addEventListener("change", () => update()));
  browseButton.addEventListener("click", () => setDrawer(!drawerOpen));
  document.getElementById("close-browser").addEventListener("click", () => setDrawer(false));
  backdrop.addEventListener("click", () => setDrawer(false));
  collapseButton.addEventListener("click", () => {
    collapsed = !collapsed;
    document.body.classList.toggle("browser-collapsed", collapsed);
    collapseButton.setAttribute("aria-label", collapsed ? "Expand story browser" : "Collapse story browser");
    collapseButton.setAttribute("aria-expanded", String(!collapsed));
    collapseButton.firstElementChild.textContent = collapsed ? "»" : "«";
    setDrawer(false, false);
  });
  document.addEventListener("keydown", event => {
    if (!drawerOpen) return;
    if (event.key === "Escape") { event.preventDefault(); setDrawer(false); }
    if (event.key !== "Tab") return;
    const focusable = [...browser.querySelectorAll("a[href],button,input,select,summary")].filter(el => el.getClientRects().length && !el.disabled);
    const first = focusable[0], last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  mobile.addEventListener("change", () => setDrawer(false, false));
  window.addEventListener("popstate", fromLocation);
  window.addEventListener("hashchange", fromLocation);
  window.addEventListener("storage", event => {
    if (event.key !== storageKey && event.key !== null) return;
    try {
      const value = JSON.parse(event.newValue || "[]");
      if (Array.isArray(value)) read = new Set(value.filter(key => typeof key === "string"));
      update();
    } catch (_) { /* Keep valid in-memory marks if another tab stores malformed data. */ }
  });
  document.getElementById("clear-filters").addEventListener("click", () => { clearFilters(); update({focus: true}); });
  const reset = document.getElementById("reset-read");
  reset.hidden = false;
  reset.addEventListener("click", () => { read.clear(); persist(); update(); });
  document.querySelector(".reader-controls").hidden = false;
  collapseButton.hidden = false;
  document.body.classList.add("reader-ready");
  showStorageStatus();
  update({syncUrl: false});
  fromLocation();
  setDrawer(false, false);
})();
