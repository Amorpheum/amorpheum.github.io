// Copied from cailab-website/assets/js/rings.js (canonical; synced 2026-11-19). Change it there first.
// Draws the name-seeded ring graphs: <svg data-ring="Name" [data-base="0..5"]>.
// Same rule as the approved design: FNV-1a hash seeds a mulberry32 stream.
(() => {
  const NS = 'http://www.w3.org/2000/svg';

  const fnv = s => {
    let h = 2166136261;
    for (const b of new TextEncoder().encode(s)) h = Math.imul(h ^ b, 16777619) >>> 0;
    return h;
  };

  const mulberry = seed => {
    let a = seed;
    return () => {
      a = (a + 0x6D2B79F5) >>> 0;
      let t = Math.imul(a ^ (a >>> 15), a | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };

  const el = (name, attrs) => {
    const node = document.createElementNS(NS, name);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    return node;
  };

  const draw = svg => {
    const h = fnv(svg.dataset.ring);
    const rng = mulberry(h);
    const n = 7 + (h % 5);
    const base = svg.dataset.base === undefined ? h % 6 : Number(svg.dataset.base);
    const R = 38 + rng() * 4;
    const pts = [];
    for (let i = 0; i < n; i++) {
      const a = ((i + (rng() - 0.5) * 0.5) / n) * 2 * Math.PI - Math.PI / 2;
      const rr = R + (rng() - 0.5) * 5;
      const r = 1.9 + rng() * 1.9;
      pts.push({ x: 50 + rr * Math.cos(a), y: 50 + rr * Math.sin(a), c: ((base + Math.floor((i * 3) / n)) % 6) + 1, r });
    }
    const edges = new Set();
    const add = (a, b) => edges.add(a + ',' + b);
    for (let i = 0; i < n; i++) {
      add(i, (i + 1) % n);
      if (rng() < 0.55) add(i, (i + 2) % n);
      if (rng() < 0.3) add(i, (i + Math.floor(n / 2)) % n);
    }
    const sorted = [...edges].map(e => e.split(',').map(Number)).sort((p, q) => p[0] - q[0] || p[1] - q[1]);
    svg.replaceChildren();
    for (const [a, b] of sorted) {
      svg.append(el('line', { class: 'c' + pts[a].c, x1: pts[a].x.toFixed(1), y1: pts[a].y.toFixed(1), x2: pts[b].x.toFixed(1), y2: pts[b].y.toFixed(1) }));
    }
    for (const p of pts) {
      svg.append(el('circle', { class: 'c' + p.c, cx: p.x.toFixed(1), cy: p.y.toFixed(1), r: p.r.toFixed(1) }));
    }
  };

  document.querySelectorAll('svg[data-ring]').forEach(draw);
})();
