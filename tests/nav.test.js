// Behaviour of assets/js/nav.js, the phone Menu button. Run: bun test tests/nav.test.js
// nav.js is a classic script, so it is evaluated against a minimal stand-in for `document` (the DOM is the
// boundary; the layout itself is checked in a real browser).
import { beforeEach, expect, test } from "bun:test";
import { readFileSync } from "node:fs";

const SOURCE = readFileSync(new URL("../assets/js/nav.js", import.meta.url), "utf8");

let nav, button;

const fakeElement = () => {
  const handlers = {};
  return {
    handlers,
    attrs: {},
    focused: false,
    hidden: true,
    classes: new Set(),
    classList: null,
    setAttribute(name, value) { this.attrs[name] = value; },
    addEventListener(type, fn) { (handlers[type] ||= []).push(fn); },
    fire(type, event = {}) { (handlers[type] || []).forEach(fn => fn(event)); },
    focus() { this.focused = true; },
  };
};

const load = () => {
  nav = fakeElement();
  button = fakeElement();
  nav.classList = {
    add: name => nav.classes.add(name),
    contains: name => nav.classes.has(name),
    toggle: (name, force) => {
      const on = force === undefined ? !nav.classes.has(name) : force;
      on ? nav.classes.add(name) : nav.classes.delete(name);
      return on;
    },
  };
  nav.querySelector = selector => (selector === ".nav__toggle" ? button : null);
  const document = { querySelector: selector => (selector === ".nav" ? nav : null) };
  new Function("document", SOURCE)(document);
};

beforeEach(load);

test("on load the button is revealed and the bar switches to menu mode", () => {
  expect(button.hidden).toBe(false);
  expect(nav.classes.has("is-js")).toBe(true);
  expect(nav.classes.has("is-open")).toBe(false);
});

test("clicking the button opens the menu, clicking again closes it", () => {
  button.fire("click");
  expect(nav.classes.has("is-open")).toBe(true);
  expect(button.attrs["aria-expanded"]).toBe("true");
  button.fire("click");
  expect(nav.classes.has("is-open")).toBe(false);
  expect(button.attrs["aria-expanded"]).toBe("false");
});

test("Escape closes an open menu and puts focus back on the button", () => {
  button.fire("click");
  nav.fire("keydown", { key: "Escape" });
  expect(nav.classes.has("is-open")).toBe(false);
  expect(button.attrs["aria-expanded"]).toBe("false");
  expect(button.focused).toBe(true);
});

test("other keys, and Escape on a closed menu, do nothing", () => {
  nav.fire("keydown", { key: "Escape" });
  expect(button.focused).toBe(false);
  button.fire("click");
  nav.fire("keydown", { key: "a" });
  expect(nav.classes.has("is-open")).toBe(true);
});

test("a page without the button is left alone", () => {
  const document = { querySelector: selector => (selector === ".nav" ? { querySelector: () => null, classList: { add() { throw new Error("touched"); } } } : null) };
  expect(() => new Function("document", SOURCE)(document)).not.toThrow();
});
