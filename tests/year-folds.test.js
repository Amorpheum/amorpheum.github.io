// Source: cailab-website/tests/year-folds.test.js (canonical; synced 2026-11-20), copied unchanged below this line.
// Behaviour of assets/js/year-folds.js, the Publications page's year folds and its filter and search.
// Run: bun test tests/year-folds.test.js
// The script is a classic script, so it is evaluated against a minimal stand-in for `document` and `window`
// (the DOM is the boundary; the layout and real deep links are checked in a real browser). The stand-in
// understands only the selectors the script uses and throws on any other, so a new selector fails loudly here.
import { beforeEach, expect, test } from "bun:test";
import { readFileSync } from "node:fs";

const SOURCE = readFileSync(new URL("../assets/js/year-folds.js", import.meta.url), "utf8");

let page, win;

const el = (tag, { id, classes = [], attrs = {}, parent = null, text = "" } = {}) => {
  const handlers = {};
  const n = {
    tagName: tag.toUpperCase(),
    id,
    classes: new Set(classes),
    attrs: { ...attrs },
    parentElement: parent,
    children: [],
    handlers,
    hidden: false,
    open: false,
    value: "",
    textContent: text,
    scrolled: 0,
    focused: 0,
    focus() { this.focused += 1; },
    getAttribute(name) { return name in this.attrs ? this.attrs[name] : null; },
    setAttribute(name, value) { this.attrs[name] = String(value); },
    scrollIntoView() { this.scrolled += 1; },
    addEventListener(type, fn) { (handlers[type] ||= []).push(fn); },
    fire(type, event = {}) { (handlers[type] || []).forEach(fn => fn(event)); },
    matches(selector) {
      const m = /^([a-z]*)(?:\.([\w-]+))?$/.exec(selector);
      if (!m) throw new Error(`stand-in does not support selector: ${selector}`);
      return (!m[1] || this.tagName === m[1].toUpperCase()) && (!m[2] || this.classes.has(m[2]));
    },
    descendants() { return this.children.flatMap(c => [c, ...c.descendants()]); },
    querySelectorAll(selector) { return this.descendants().filter(d => d.matches(selector)); },
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; },
    closest(selector) {
      for (let x = this; x; x = x.parentElement) if (x.matches(selector)) return x;
      return null;
    },
  };
  n.classList = {
    add: c => n.classes.add(c),
    remove: c => n.classes.delete(c),
    contains: c => n.classes.has(c),
    toggle(c, force) {
      const on = force === undefined ? !n.classes.has(c) : force;
      if (on) n.classes.add(c); else n.classes.delete(c);
      return on;
    },
  };
  if (parent) parent.children.push(n);
  return n;
};

const ROWS = [
  { year: 2026, id: "pub-2026-a", type: "journal", areas: "care", text: "peer supporters and experts. ada lovelace. pacm hci (cscw'26)" },
  { year: 2026, id: "pub-2026-b", type: "extended", areas: "multimodal", text: "sketch with speech. simon perrault, télécom paris. dis'26 pwip" },
  { year: 2025, id: "pub-2025-a", type: "conference", areas: "care", text: "agents for decisions. grace hopper. chi'25" },
  { year: 2025, id: "pub-2025-b", type: "preprint", areas: "other", text: "gaze patterns. alan turing. arxiv" },
  { year: 2024, id: "pub-2024-a", type: "journal", areas: "responsible-ai", text: "toxic cloaking. edsger dijkstra. emnlp'24" },
];
const CHIPS = {
  type: ["journal", "conference", "extended", "preprint"],
  area: ["care", "multimodal", "responsible-ai", "other"],
};
const COUNT_TEXT = { 2026: "2 publications", 2025: "2 publications", 2024: "1 publication" };

// `phone: true` makes matchMedia('(max-width: 640px)') report a phone, as the page does below 640px.
const load = (hash = "", search = "", { phone = false } = {}) => {
  const root = el("body");
  const bar = el("div", { classes: ["pub-filters"], parent: root });
  bar.hidden = true;
  const input = el("input", { id: "pub-search", parent: bar });
  // The Filters toggle (phones only, in CSS) controls the panel that holds the menus, Clear and Expand all.
  const toggle = el("button", { classes: ["pub-filters__toggle"], attrs: { "aria-expanded": "false", "aria-controls": "pub-filters-panel" }, parent: bar, text: "Filters" });
  const toggleCount = el("span", { classes: ["pub-menu__count"], parent: toggle });
  toggleCount.hidden = true;
  const filtersPanel = el("div", { id: "pub-filters-panel", classes: ["pub-filters__panel"], parent: bar });
  const button = el("button", { classes: ["year-controls__all"], parent: filtersPanel, text: "Expand all" });
  button.hidden = true;
  // Type and area chips live in a <details class="pub-menu">.
  const menus = {};
  for (const name of ["type", "area"]) {
    const details = el("details", { classes: ["pub-menu"], attrs: { "data-menu": name }, parent: filtersPanel });
    const summary = el("summary", { parent: details });
    const count = el("span", { classes: ["pub-menu__count"], parent: summary });
    count.hidden = true;
    const panel = el("div", { classes: ["pub-menu__panel"], parent: details });
    menus[name] = { details, summary, count, panel };
  }
  const chips = {};
  for (const [group, values] of Object.entries(CHIPS)) {
    for (const value of values) {
      chips[`${group}:${value}`] = el("button", {
        classes: ["chip"],
        attrs: { "data-filter": group, "data-value": value, "aria-pressed": "false" },
        parent: menus[group].panel,
      });
    }
  }
  const clear = el("button", { classes: ["pub-filters__clear"], parent: filtersPanel });
  clear.hidden = true;
  const status = el("p", { classes: ["pub-filters__status"], parent: bar });

  const years = {};
  const rows = {};
  for (const year of [2026, 2025, 2024]) {
    const section = el("section", { id: String(year), classes: ["section--year"], parent: root });
    const details = el("details", { classes: ["year"], parent: section });
    details.open = year === 2026;
    const summary = el("summary", { parent: details });
    const count = el("span", { classes: ["year__count"], parent: summary, text: COUNT_TEXT[year] });
    const types = el("span", { classes: ["year__types"], parent: summary, text: "breakdown" });
    const list = el("ul", { parent: details });
    years[year] = { section, details, count, types, rows: [] };
  }
  for (const r of ROWS) {
    const row = el("li", {
      id: r.id,
      classes: ["publication-row"],
      attrs: { "data-type": r.type, "data-areas": r.areas, "data-text": r.text },
      parent: years[r.year].details.children.find(c => c.tagName === "UL"),
    });
    rows[r.id] = row;
    years[r.year].rows.push(row);
  }
  for (const y of Object.values(years)) y.row = y.rows[0];

  const all = root.descendants();
  const byId = Object.fromEntries(all.filter(n => n.id).map(n => [n.id, n]));
  const winHandlers = {};
  const docHandlers = {};
  const mqHandlers = [];
  const mq = { matches: phone, addEventListener(type, fn) { if (type === "change") mqHandlers.push(fn); } };
  win = {
    matchMedia: query => {
      if (query !== "(max-width: 640px)") throw new Error(`stand-in does not support media query: ${query}`);
      return mq;
    },
    setPhone(on) { mq.matches = on; mqHandlers.forEach(fn => fn({ matches: on })); },
    location: { hash, search, pathname: "/publications/" },
    history: { urls: [], replaceState(_state, _title, url) { this.urls.push(url); } },
    addEventListener(type, fn) { (winHandlers[type] ||= []).push(fn); },
    fire(type) { (winHandlers[type] || []).forEach(fn => fn()); },
  };
  const document = {
    querySelectorAll: selector => root.querySelectorAll(selector),
    querySelector: selector => root.querySelector(selector),
    getElementById: id => byId[id] || null,
    addEventListener(type, fn) { (docHandlers[type] ||= []).push(fn); },
    fire(type, event = {}) { (docHandlers[type] || []).forEach(fn => fn(event)); },
  };
  new Function("document", "window", SOURCE)(document, win);
  page = { years, rows, button, bar, input, chips, status, clear, menus, document, toggle, toggleCount };
};

const openYears = () => Object.entries(page.years).filter(([, y]) => y.details.open).map(([year]) => year).sort();
const visibleRows = () => Object.entries(page.rows).filter(([, r]) => !r.hidden).map(([id]) => id).sort();
const visibleYears = () => Object.entries(page.years).filter(([, y]) => !y.section.hidden).map(([year]) => year).sort();
const press = (group, value) => page.chips[`${group}:${value}`].fire("click");
const pressed = (group, value) => page.chips[`${group}:${value}`].getAttribute("aria-pressed");
const search = q => { page.input.value = q; page.input.fire("input"); };
const lastUrl = () => win.history.urls.at(-1);
const queryOf = url => new URLSearchParams((url.split("?")[1] || "").split("#")[0]);

beforeEach(() => load());

// ---- year folds ----

test("with no hash, nothing opens or scrolls and the Expand all button is revealed", () => {
  expect(openYears()).toEqual(["2026"]);
  expect(page.button.hidden).toBe(false);
  expect(page.button.textContent).toBe("Expand all");
  Object.values(page.years).forEach(y => expect(y.row.scrolled + y.section.scrolled).toBe(0));
});

test("a link to a paper in a closed year opens that year and scrolls to the paper", () => {
  load("#pub-2024-a");
  expect(openYears()).toEqual(["2024", "2026"]);
  expect(page.years[2024].row.scrolled).toBe(1);
});

test("a link to a year opens that year and scrolls to it", () => {
  load("#2025");
  expect(openYears()).toEqual(["2025", "2026"]);
  expect(page.years[2025].section.scrolled).toBe(1);
});

test("a link to a paper in the year that is already open changes nothing and does not re-scroll", () => {
  load("#pub-2026-a");
  expect(openYears()).toEqual(["2026"]);
  expect(page.years[2026].row.scrolled).toBe(0);
});

test("an unknown, empty or malformed hash does nothing and does not throw", () => {
  for (const hash of ["#nope", "#", "", "#%E0%A4%A"]) {
    expect(() => load(hash)).not.toThrow();
    expect(openYears()).toEqual(["2026"]);
  }
});

test("a later hashchange reveals the new target", () => {
  win.location.hash = "#pub-2025-a";
  win.fire("hashchange");
  expect(openYears()).toEqual(["2025", "2026"]);
  expect(page.years[2025].row.scrolled).toBe(1);
});

test("Expand all opens every year, and the same button then collapses them all", () => {
  page.button.fire("click");
  expect(openYears()).toEqual(["2024", "2025", "2026"]);
  expect(page.button.textContent).toBe("Collapse all");
  page.button.fire("click");
  expect(openYears()).toEqual([]);
  expect(page.button.textContent).toBe("Expand all");
});

test("the button label follows years opened or closed by hand", () => {
  page.years[2025].details.open = true;
  page.years[2025].details.fire("toggle");
  expect(page.button.textContent).toBe("Expand all");
  page.years[2024].details.open = true;
  page.years[2024].details.fire("toggle");
  expect(page.button.textContent).toBe("Collapse all");
  page.years[2024].details.open = false;
  page.years[2024].details.fire("toggle");
  expect(page.button.textContent).toBe("Expand all");
});

// ---- filter and search ----

test("the filter bar is revealed, and with no filter active every row shows and Clear stays hidden", () => {
  expect(page.bar.hidden).toBe(false);
  expect(page.clear.hidden).toBe(true);
  expect(visibleRows()).toHaveLength(5);
  expect(visibleYears()).toEqual(["2024", "2025", "2026"]);
  expect(page.status.textContent).toBe("");
});

test("a type chip keeps that type, hides years with no match, and opens the years that match", () => {
  press("type", "journal");
  expect(pressed("type", "journal")).toBe("true");
  expect(visibleRows()).toEqual(["pub-2024-a", "pub-2026-a"]);
  expect(visibleYears()).toEqual(["2024", "2026"]);
  expect(openYears()).toEqual(["2024", "2026"]);
  expect(page.status.textContent).toBe("2 of 5 publications");
  expect(page.clear.hidden).toBe(false);
  expect(page.button.hidden).toBe(true);
});

test("chips in one group add up (OR); chips in different groups narrow (AND)", () => {
  press("type", "journal");
  press("type", "conference");
  expect(visibleRows()).toEqual(["pub-2024-a", "pub-2025-a", "pub-2026-a"]);
  press("area", "care");
  expect(visibleRows()).toEqual(["pub-2025-a", "pub-2026-a"]);
  press("type", "journal");
  expect(visibleRows()).toEqual(["pub-2025-a"]);
  press("area", "care");
  expect(visibleRows()).toEqual(["pub-2025-a"]);
});

test("the Other area chip keeps the papers that sit in no research area", () => {
  press("area", "other");
  expect(visibleRows()).toEqual(["pub-2025-b"]);
});

test("search matches title, author and venue, ignoring case and accents, every word required", () => {
  search("TELECOM");
  expect(visibleRows()).toEqual(["pub-2026-b"]);
  search("dijkstra");
  expect(visibleRows()).toEqual(["pub-2024-a"]);
  search("CHI'25");
  expect(visibleRows()).toEqual(["pub-2025-a"]);
  search("  Ada   hci ");
  expect(visibleRows()).toEqual(["pub-2026-a"]);
  search("ada emnlp");
  expect(visibleRows()).toEqual([]);
  search("télécom");
  expect(visibleRows()).toEqual(["pub-2026-b"]);
});

test("search and chips combine; no match says so and hides every year", () => {
  search("gaze");
  press("type", "journal");
  expect(visibleRows()).toEqual([]);
  expect(visibleYears()).toEqual([]);
  expect(page.status.textContent).toBe("No publications match.");
  press("type", "journal");
  expect(visibleRows()).toEqual(["pub-2025-b"]);
});

test("while filtering each year reads n of m and drops its type breakdown; clearing restores both", () => {
  press("type", "journal");
  expect(page.years[2026].count.textContent).toBe("1 of 2 publications");
  expect(page.years[2024].count.textContent).toBe("1 of 1 publication");
  expect(page.years[2026].types.hidden).toBe(true);
  page.clear.fire("click");
  expect(page.years[2026].count.textContent).toBe("2 publications");
  expect(page.years[2024].count.textContent).toBe("1 publication");
  expect(page.years[2026].types.hidden).toBe(false);
});

test("Clear restores every row and year, the newest year open, Expand all, and empty controls", () => {
  press("type", "journal");
  press("area", "care");
  search("ada");
  page.clear.fire("click");
  expect(visibleRows()).toHaveLength(5);
  expect(visibleYears()).toEqual(["2024", "2025", "2026"]);
  expect(openYears()).toEqual(["2026"]);
  expect(page.input.value).toBe("");
  expect(pressed("type", "journal")).toBe("false");
  expect(pressed("area", "care")).toBe("false");
  expect(page.clear.hidden).toBe(true);
  expect(page.button.hidden).toBe(false);
  expect(page.status.textContent).toBe("");
});

test("undoing the last chip by hand ends the filter the same way Clear does", () => {
  press("type", "journal");
  press("type", "journal");
  expect(visibleRows()).toHaveLength(5);
  expect(openYears()).toEqual(["2026"]);
  expect(page.clear.hidden).toBe(true);
  expect(page.button.hidden).toBe(false);
});

// ---- the Type and Research area menus ----

test("a menu shows how many of its chips are on, and nothing when none are", () => {
  expect(page.menus.type.count.hidden).toBe(true);
  press("type", "journal");
  press("type", "conference");
  press("area", "care");
  expect(page.menus.type.count.hidden).toBe(false);
  expect(page.menus.type.count.textContent).toBe("2");
  expect(page.menus.area.count.textContent).toBe("1");
  press("type", "journal");
  expect(page.menus.type.count.textContent).toBe("1");
  page.clear.fire("click");
  expect(page.menus.type.count.hidden).toBe(true);
  expect(page.menus.area.count.hidden).toBe(true);
});

test("a filter restored from the address shows its menu counts on load", () => {
  load("", "?type=journal,conference&area=care");
  expect(page.menus.type.count.textContent).toBe("2");
  expect(page.menus.area.count.textContent).toBe("1");
});

test("opening one menu closes the other", () => {
  page.menus.type.details.open = true;
  page.menus.type.details.fire("toggle");
  page.menus.area.details.open = true;
  page.menus.area.details.fire("toggle");
  expect(page.menus.type.details.open).toBe(false);
  expect(page.menus.area.details.open).toBe(true);
});

test("a click outside an open menu closes it; a click inside, on its chips or its summary, does not", () => {
  page.menus.type.details.open = true;
  page.document.fire("click", { target: page.chips["type:journal"] });
  page.document.fire("click", { target: page.menus.type.summary });
  expect(page.menus.type.details.open).toBe(true);
  page.document.fire("click", { target: page.years[2026].row });
  expect(page.menus.type.details.open).toBe(false);
});

test("Escape closes an open menu and returns focus to its summary", () => {
  page.menus.area.details.open = true;
  page.document.fire("keydown", { key: "Enter" });
  expect(page.menus.area.details.open).toBe(true);
  page.document.fire("keydown", { key: "Escape" });
  expect(page.menus.area.details.open).toBe(false);
  expect(page.menus.area.summary.focused).toBe(1);
});

// ---- phones: the menus sit behind one Filters button ----

const panelOpen = () => page.bar.classList.contains("is-open");

test("the Filters toggle flips the bar's open state and aria-expanded", () => {
  expect(panelOpen()).toBe(false);
  expect(page.toggle.getAttribute("aria-expanded")).toBe("false");
  page.toggle.fire("click");
  expect(panelOpen()).toBe(true);
  expect(page.toggle.getAttribute("aria-expanded")).toBe("true");
  page.toggle.fire("click");
  expect(panelOpen()).toBe(false);
  expect(page.toggle.getAttribute("aria-expanded")).toBe("false");
});

test("on a phone, opening the panel opens both menus so its chips show at once", () => {
  load("", "", { phone: true });
  page.toggle.fire("click");
  expect(page.menus.type.details.open).toBe(true);
  expect(page.menus.area.details.open).toBe(true);
});

test("on a desktop width, opening the toggle leaves the menus alone", () => {
  page.toggle.fire("click");
  expect(page.menus.type.details.open).toBe(false);
  expect(page.menus.area.details.open).toBe(false);
});

test("on a phone, opening one menu does not close the other, and an outside click closes nothing", () => {
  load("", "", { phone: true });
  page.toggle.fire("click");
  page.menus.type.details.fire("toggle");
  page.menus.area.details.fire("toggle");
  expect(page.menus.type.details.open && page.menus.area.details.open).toBe(true);
  page.document.fire("click", { target: page.years[2026].row });
  expect(page.menus.type.details.open && page.menus.area.details.open).toBe(true);
});

test("on a phone, a menu closed by hand while the panel is open reopens", () => {
  load("", "", { phone: true });
  page.toggle.fire("click");
  page.menus.type.details.open = false;
  page.menus.type.details.fire("toggle");
  expect(page.menus.type.details.open).toBe(true);
});

test("on a phone, Escape closes the panel and returns focus to the toggle", () => {
  load("", "", { phone: true });
  page.toggle.fire("click");
  page.document.fire("keydown", { key: "Escape" });
  expect(panelOpen()).toBe(false);
  expect(page.toggle.getAttribute("aria-expanded")).toBe("false");
  expect(page.toggle.focused).toBe(1);
});

test("the Filters badge counts chips on across both groups, ignores search text, and hides at zero", () => {
  expect(page.toggleCount.hidden).toBe(true);
  search("ada");
  expect(page.toggleCount.hidden).toBe(true);
  press("type", "journal");
  press("type", "conference");
  press("area", "care");
  expect(page.toggleCount.hidden).toBe(false);
  expect(page.toggleCount.textContent).toBe("3");
  press("type", "journal");
  expect(page.toggleCount.textContent).toBe("2");
  page.clear.fire("click");
  expect(page.toggleCount.hidden).toBe(true);
});

test("a filter restored from the address shows the Filters badge on load", () => {
  load("", "?type=journal&area=care");
  expect(page.toggleCount.hidden).toBe(false);
  expect(page.toggleCount.textContent).toBe("2");
});

test("crossing the breakpoint closes the panel and every menu, in both directions", () => {
  load("", "", { phone: true });
  page.toggle.fire("click");
  win.setPhone(false);
  expect(panelOpen()).toBe(false);
  expect(page.toggle.getAttribute("aria-expanded")).toBe("false");
  expect(page.menus.type.details.open || page.menus.area.details.open).toBe(false);

  load("", "", { phone: false });
  page.menus.type.details.open = true;
  win.setPhone(true);
  expect(page.menus.type.details.open).toBe(false);
  expect(panelOpen()).toBe(false);
});

// ---- the query string ----

test("the filter is written to the query string and the hash is kept", () => {
  win.location.hash = "#top";
  press("type", "journal");
  press("type", "conference");
  press("area", "care");
  search("ada");
  const q = queryOf(lastUrl());
  expect(q.get("type")).toBe("journal,conference");
  expect(q.get("area")).toBe("care");
  expect(q.get("q")).toBe("ada");
  expect(lastUrl().startsWith("/publications/?")).toBe(true);
  expect(lastUrl().endsWith("#top")).toBe(true);
});

test("clearing leaves a bare address", () => {
  press("type", "journal");
  page.clear.fire("click");
  expect(lastUrl()).toBe("/publications/");
});

test("a shared address restores the filter on load", () => {
  load("", "?type=journal&area=care&q=ada");
  expect(pressed("type", "journal")).toBe("true");
  expect(pressed("area", "care")).toBe("true");
  expect(page.input.value).toBe("ada");
  expect(visibleRows()).toEqual(["pub-2026-a"]);
  expect(openYears()).toEqual(["2026"]);
});

test("values the page does not offer in the query string are ignored, including the dropped selected=1", () => {
  expect(() => load("", "?type=bogus&area=<script>&q=&selected=1")).not.toThrow();
  expect(visibleRows()).toHaveLength(5);
  expect(page.clear.hidden).toBe(true);
  expect(openYears()).toEqual(["2026"]);
});

// ---- deep links under a filter ----

test("a link to a paper the filter hides clears the filter, then reveals the paper", () => {
  load("#pub-2025-a", "?type=journal");
  expect(visibleRows()).toHaveLength(5);
  expect(pressed("type", "journal")).toBe("false");
  expect(openYears()).toEqual(["2025", "2026"]);
  expect(page.years[2025].row.scrolled).toBe(1);
  expect(lastUrl()).toBe("/publications/#pub-2025-a");
});

test("a link to a paper the filter shows keeps the filter and opens its year", () => {
  load("#pub-2024-a", "?type=journal");
  expect(visibleRows()).toEqual(["pub-2024-a", "pub-2026-a"]);
  expect(openYears()).toEqual(["2024", "2026"]);
  expect(page.years[2024].row.scrolled).toBe(1);
});

test("a hashchange to a hidden paper clears the filter and reveals the paper", () => {
  press("type", "journal");
  win.location.hash = "#pub-2025-b";
  win.fire("hashchange");
  expect(visibleRows()).toHaveLength(5);
  expect(openYears()).toEqual(["2025", "2026"]);
  expect(page.rows["pub-2025-b"].scrolled).toBe(1);
});

test("a link to a year the filter has emptied clears the filter and opens that year", () => {
  load("#2025", "?type=journal");
  expect(visibleRows()).toHaveLength(5);
  expect(openYears()).toEqual(["2025", "2026"]);
  expect(page.years[2025].section.scrolled).toBe(1);
});
