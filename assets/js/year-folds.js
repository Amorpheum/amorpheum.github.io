// Source: cailab-website/assets/js/year-folds.js (canonical; synced 2026-11-20), copied unchanged below this line.
// A change belongs in the lab file first; tests/site_test.rb compares the two when that repo sits beside this one.
// The Publications page: year folds, plus filter and search. Behaviour is covered by tests/year-folds.test.js.
//
// Year folds. Each year is a native <details class="year">; only the newest starts open. A link such as
// /publications/#pub-<id> (from /research/, /join-us/) can point into a closed year, which the browser cannot
// scroll to, so on load and on hashchange this opens the folds around the target and scrolls again. The
// Expand all button and the filter bar are hidden in the HTML and revealed here, so without JavaScript there
// are no dead controls: the whole list is there and the folds still open by hand.
//
// Filter and search. Each row carries data-type, data-areas and data-text (see _includes/publication-row.html).
// Chips in one group add up (OR), different groups narrow (AND), and every word typed must appear in the row's
// title, authors or venue, ignoring case and accents. The state lives in the chips' aria-pressed and the input,
// is mirrored to the query string (?type=journal,conference&area=care&q=llm) so a filtered view can be linked,
// and is read back from it on load. Values the page does not offer are ignored. A link to a paper or year the
// filter is hiding clears the filter first. Below 640px the Type and Research area menus, Clear and Expand all
// sit behind one Filters button (see setPanel) so the controls take one row of a phone screen when closed.
(() => {
  const folds = Array.from(document.querySelectorAll('details.year'));
  if (!folds.length) return;
  const button = document.querySelector('.year-controls__all');
  const bar = document.querySelector('.pub-filters');
  const input = document.getElementById('pub-search');
  const chips = Array.from(document.querySelectorAll('button.chip'));
  const clearButton = document.querySelector('.pub-filters__clear');
  const status = document.querySelector('.pub-filters__status');
  const menus = Array.from(document.querySelectorAll('details.pub-menu'));
  const toggle = document.querySelector('.pub-filters__toggle');
  const phone = window.matchMedia('(max-width: 640px)');

  const fold = text => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const plural = n => (n === 1 ? 'publication' : 'publications');

  const rows = Array.from(document.querySelectorAll('li.publication-row')).map(el => ({
    el,
    type: el.getAttribute('data-type'),
    areas: (el.getAttribute('data-areas') || '').split(' '),
    text: fold(el.getAttribute('data-text') || ''),
  }));
  const rowOf = new Map(rows.map(row => [row.el, row]));
  const years = folds.map(details => ({
    details,
    section: details.closest('section'),
    count: details.querySelector('.year__count'),
    types: details.querySelector('.year__types'),
    countText: details.querySelector('.year__count').textContent,
    rows: Array.from(details.querySelectorAll('li.publication-row')).map(el => rowOf.get(el)),
  }));

  const allOpen = () => folds.every(f => f.open);
  const syncButton = () => {
    if (button) button.textContent = allOpen() ? 'Collapse all' : 'Expand all';
  };

  // ---- filter state: the chips and the input are the source of truth ----
  const chosen = group => chips
    .filter(c => c.getAttribute('data-filter') === group && c.getAttribute('aria-pressed') === 'true')
    .map(c => c.getAttribute('data-value'));
  const current = () => ({
    type: chosen('type'),
    area: chosen('area'),
    q: input.value.trim(),
  });
  const isActive = f => f.type.length > 0 || f.area.length > 0 || f.q.length > 0;

  const matcher = f => {
    const words = fold(f.q).split(/\s+/).filter(Boolean);
    return row =>
      (!f.type.length || f.type.includes(row.type)) &&
      (!f.area.length || row.areas.some(a => f.area.includes(a))) &&
      words.every(w => row.text.includes(w));
  };

  // Each menu's summary shows how many of its chips are on, so a closed menu still says it is filtering. The
  // Filters toggle (phones) shows the total across both menus; search text is not counted, it is in plain sight.
  const showCount = (el, n) => {
    el.textContent = n ? String(n) : '';
    el.hidden = n === 0;
  };
  const pressedIn = scope => scope.filter(c => c.getAttribute('aria-pressed') === 'true').length;
  const syncMenus = () => {
    menus.forEach(menu => showCount(menu.querySelector('.pub-menu__count'), pressedIn(Array.from(menu.querySelectorAll('button.chip')))));
    showCount(toggle.querySelector('.pub-menu__count'), pressedIn(chips));
  };

  const applyFilter = () => {
    const f = current();
    const active = isActive(f);
    const match = matcher(f);
    let shown = 0;
    rows.forEach(row => { row.el.hidden = active && !match(row); });
    years.forEach((year, index) => {
      const n = year.rows.filter(row => !row.el.hidden).length;
      shown += n;
      if (active) {
        year.section.hidden = n === 0;
        year.details.open = n > 0;
        year.count.textContent = `${n} of ${year.rows.length} ${plural(year.rows.length)}`;
      } else {
        year.section.hidden = false;
        year.details.open = index === 0;
        year.count.textContent = year.countText;
      }
      if (year.types) year.types.hidden = active;
    });
    status.textContent = !active ? '' : shown ? `${shown} of ${rows.length} ${plural(rows.length)}` : 'No publications match.';
    clearButton.hidden = !active;
    if (button) button.hidden = active;
    syncMenus();
    syncButton();
    return active;
  };

  const writeUrl = () => {
    const f = current();
    const params = new URLSearchParams();
    if (f.type.length) params.set('type', f.type.join(','));
    if (f.area.length) params.set('area', f.area.join(','));
    if (f.q) params.set('q', f.q);
    const query = params.toString().replace(/%2C/g, ',');
    window.history.replaceState(null, '', window.location.pathname + (query ? `?${query}` : '') + window.location.hash);
  };

  const refilter = () => {
    applyFilter();
    writeUrl();
  };

  const clearAll = () => {
    chips.forEach(c => c.setAttribute('aria-pressed', 'false'));
    input.value = '';
    refilter();
  };

  const readUrl = () => {
    const params = new URLSearchParams(window.location.search);
    chips.forEach(c => {
      const group = c.getAttribute('data-filter');
      const value = c.getAttribute('data-value');
      const on = (params.get(group) || '').split(',').includes(value);
      c.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    input.value = params.get('q') || '';
  };

  // ---- deep links ----
  const hiddenNow = node => {
    for (let n = node; n; n = n.parentElement) if (n.hidden) return true;
    return false;
  };

  // `relayout`: the layout already changed under the browser's own jump to the fragment (a filter was applied
  // on load), so scroll again even if no fold needed opening.
  const reveal = (hash, relayout) => {
    let id;
    try {
      id = decodeURIComponent(hash.replace(/^#/, ''));
    } catch (error) {
      return;
    }
    const target = id && document.getElementById(id);
    if (!target) return;

    let changed = relayout;
    if (isActive(current()) && hiddenNow(target)) {
      clearAll();
      changed = true;
    }

    const open = f => {
      if (!f.open) {
        f.open = true;
        changed = true;
      }
    };
    for (let node = target; node; node = node.parentElement) {
      if (node.tagName === 'DETAILS') open(node);
    }
    // A year anchor (#2025) names the section, which holds the fold.
    const inner = target.querySelector && target.querySelector('details.year');
    if (inner) open(inner);

    syncButton();
    if (changed) target.scrollIntoView();
  };

  // ---- wiring ----
  if (button) {
    button.addEventListener('click', () => {
      const open = !allOpen();
      folds.forEach(f => { f.open = open; });
      syncButton();
    });
  }
  chips.forEach(chip => chip.addEventListener('click', () => {
    chip.setAttribute('aria-pressed', chip.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
    refilter();
  }));
  input.addEventListener('input', refilter);
  clearButton.addEventListener('click', clearAll);
  // Phones (max-width 640px): the two menus sit behind one Filters button. Opening its panel opens both menus,
  // since their chips are what the panel shows. Above 640px the toggle is hidden (CSS) and the menus are popovers.
  const setPanel = open => {
    bar.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (phone.matches) menus.forEach(menu => { menu.open = open; });
  };
  toggle.addEventListener('click', () => setPanel(toggle.getAttribute('aria-expanded') !== 'true'));
  // Crossing the breakpoint (rotating, resizing): start over, panel and menus closed.
  phone.addEventListener('change', () => {
    setPanel(false);
    menus.forEach(menu => { menu.open = false; });
  });
  // Popovers: one menu open at a time; a click outside or Escape closes it (Escape returns focus to its summary).
  // On a phone the panel shows both menus at once, so none of that applies and a menu closed by hand reopens.
  menus.forEach(menu => menu.addEventListener('toggle', () => {
    if (phone.matches) {
      if (!menu.open && bar.classList.contains('is-open')) menu.open = true;
      return;
    }
    if (menu.open) menus.forEach(other => { if (other !== menu) other.open = false; });
  }));
  document.addEventListener('click', event => {
    if (phone.matches) return;
    const inside = event.target.closest('details.pub-menu');
    menus.forEach(menu => { if (menu !== inside) menu.open = false; });
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    if (phone.matches) {
      if (bar.classList.contains('is-open')) {
        setPanel(false);
        toggle.focus();
      }
      return;
    }
    const open = menus.find(menu => menu.open);
    if (!open) return;
    open.open = false;
    open.querySelector('summary').focus();
  });
  folds.forEach(f => f.addEventListener('toggle', syncButton));
  window.addEventListener('hashchange', () => reveal(window.location.hash));

  readUrl();
  const filtered = isActive(current());
  if (filtered) applyFilter();
  bar.hidden = false;
  if (button) button.hidden = filtered;
  clearButton.hidden = !filtered;
  syncButton();
  reveal(window.location.hash, filtered);
})();
