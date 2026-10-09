"""The food page of the run report (`food.html`): how food reaches the province stores and where it goes.

Static HTML + one script, data fetched when needed: `food/index.json`, `food/summary.json`, `food/<n>.json` per save,
`food/provinces.json` (when a province is opened) and the goods page's `goods/index.json` and `goods/<n>.json` (the
buildings, methods, goods and regions, and what each method bought and made). Layout: the scope list on the left
(world, world regions, a province search), save picker and Categories / Buildings / Recipes on top, then the
figures, the flow chart (what the makers use -> who makes food -> the province stores -> who eats it, spoilage,
Granges -> victuals; categories and buildings open on click, Cookshops into their recipes), the months-stored map,
the stores over the run, the provinces and the food buildings. State lives in the URL hash (#s=12&r=<region> or
#s=12&p=<province>).
"""

from __future__ import annotations

import html

from prosper_or_perish_constructor.run_report import ECHARTS_URL, PAGE_CSS
from prosper_or_perish_constructor.run_report_goods_page import GOODS_CSS

FOOD_CSS = r"""
.scopes a{display:flex;align-items:center;gap:8px;padding:4px 6px;border-radius:6px;color:var(--ink);text-decoration:none;font-size:13px;line-height:20px}
.scopes a:hover{background:var(--chip)} .scopes a.on{background:var(--accent);color:#fff} .scopes a.on .badge{color:#fff}
.scopes .dot{margin:0 2px 0 0} .scopes .badge{margin-left:auto}
.side h4{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:16px 6px 4px}
.results a{display:block;padding:3px 6px;border-radius:6px;color:var(--ink);text-decoration:none;font-size:13px}
.results a:hover{background:var(--chip)} .results small{color:var(--muted)}
.months{font-variant-numeric:tabular-nums} .m-low{color:var(--neg)} .m-ok{color:var(--ink)} .m-high{color:var(--pos)}
table.gt th.sortable{cursor:pointer} table.gt tr.click{cursor:pointer} table.gt tr.click:hover td{background:var(--chip)}
.fill{display:inline-block;width:46px;height:6px;border-radius:3px;background:var(--chip);margin-right:8px;vertical-align:1px;overflow:hidden}
.fill i{display:block;height:100%;background:#1baf7a}
.note{font-size:12px;color:var(--muted);padding:0 16px 10px}
.vid video{display:block;width:100%;height:auto;background:#12161c}
a.chip{display:inline-flex;align-items:center;gap:3px;color:var(--ink);text-decoration:none;margin-right:8px;font-variant-numeric:tabular-nums}
a.chip:hover{text-decoration:underline} a.chip img.gi{width:16px;height:16px}
"""

FOOD_JS = r"""
(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const dark = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches;
  const INK = dark ? '#eceef0' : '#1d1d1b', MUTED = dark ? '#a0a6b0' : '#6b6b67';
  const num = v => {
    if (v == null || !isFinite(v)) return '–';
    const a = Math.abs(v);
    if (a < 0.005) return '0';
    if (a >= 1e9) return (v / 1e9).toFixed(1) + 'B';
    if (a >= 1e6) return (v / 1e6).toFixed(1) + 'M';
    if (a >= 1e4) return (v / 1e3).toFixed(0) + 'k';
    if (a >= 1e3) return (v / 1e3).toFixed(1) + 'k';
    return a >= 100 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : v.toFixed(2);
  };
  const pct = f => (f == null || !isFinite(f)) ? '–' : (f * 100).toFixed(Math.abs(f) < 0.1 ? 1 : 0) + '%';
  const months = v => (v == null || !isFinite(v)) ? '–' : v.toFixed(v < 10 ? 1 : 0);
  const mClass = v => v == null ? '' : v < 3 ? 'm-low' : v >= 12 ? 'm-high' : 'm-ok';
  const people = k => num((k || 0) * 1000);
  // goods that are bookkeeping, not food inputs
  const DUMMY = new Set(['offset', 'logistics', 'local_food', 'manual_labor', 'province_food_sales', 'province_food_purchase']);

  let GI, FI, FS = null, FP = null;
  const SAVES = new Map();
  const S = {s: 0, r: -1, p: -1, open: new Set(), tv: 0, sort: 'months', asc: true, all: false, query: ''};
  let goodIdx = new Map(), regionIdx = new Map(), P = {}, charts = {};
  const goodName = i => (GI.goods[i] || {}).name || '?';
  const goodPrice = i => (GI.goods[i] || {}).price || 1;
  const goodIcon = i => (GI.goods[i] || {}).icon;
  const goodColor = i => (GI.groups.find(g => g.key === (GI.goods[i] || {}).group) || {}).color || '#9a9a96';
  const bName = i => i < 0 ? '' : (GI.buildings[i] || {}).name || '?';
  const mName = i => i < 0 ? 'Food per level (flat)' : (GI.methods[i] || {}).name || '?';
  const cat = i => FI.categories[i];
  const catIdx = id => FI.categories.findIndex(c => c.id === id);
  const imgHtml = i => goodIcon(i) ? `<img class=gi src="${esc(goodIcon(i))}" alt="">` : '';
  const shade = (hex, k) => {  // lighten a colour (k 0..1) for the nodes under a category
    const n = parseInt(hex.slice(1), 16), mix = c => Math.round(c + (255 - c) * k);
    return '#' + [mix(n >> 16 & 255), mix(n >> 8 & 255), mix(n & 255)].map(c => c.toString(16).padStart(2, '0')).join('');
  };

  // ---------------------------------------------------------------- data
  function loadSave(i) {
    if (!SAVES.has(i)) {
      const food = FI.saves[i] ? fetch(FI.saves[i]).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }) : Promise.resolve(null);
      const goods = fetch(GI.saves[i].file).then(r => r.ok ? r.json() : null).catch(() => null);
      SAVES.set(i, Promise.all([food, goods]).then(([f, g]) => prepare(f, g)));
    }
    return SAVES.get(i);
  }
  function prepare(f, g) {
    if (!f) return null;
    const cIn = new Map(), pOut = new Map();  // method -> goods rows (inputs received, outputs made) from the goods data
    for (const r of (g && g.c) || []) if (r[2] >= 0) { if (!cIn.has(r[2])) cIn.set(r[2], []); cIn.get(r[2]).push(r); }
    for (const r of (g && g.p) || []) { const k = r[1]; if (!pOut.has(k)) pOut.set(k, []); pOut.get(k).push(r); }
    const byBuildingIn = new Map();
    for (const r of (g && g.c) || []) { const k = r[1]; if (!byBuildingIn.has(k)) byBuildingIn.set(k, []); byBuildingIn.get(k).push(r); }
    return {...f, cIn, pOut, byBuildingIn};
  }
  const inScope = reg => S.r < 0 || reg === S.r;
  function poolsInScope(D) {
    if (S.p >= 0) return D.pools.filter(r => r[P.province] === S.p);
    return D.pools.filter(r => inScope(r[P.region]));
  }
  function totals(rows) {
    const t = {};
    for (const k of FI.poolColumns.slice(3)) t[k] = 0;
    let fw = 0;
    for (const r of rows) {
      for (const k of FI.poolColumns.slice(3)) if (k !== 'factor' && k !== 'growth_storage' && k !== 'growth_surplus') t[k] += r[P[k]] || 0;
      fw += (r[P.factor] || 0) * (r[P.pop] || 0);
    }
    t.factor = t.pop > 0 ? fw / t.pop : null;
    t.made = t.sub + t.rgos + t.farms + t.kitchens + t.taverns + t.other - t.taken - t.unexplained;
    t.months = t.base > 0 ? t.stock / t.base : null;
    t.pools = rows.length;
    return t;
  }

  // ---------------------------------------------------------------- the makers tree (world / region)
  // categories -> buildings -> methods; Cookshop and Public Kitchen food (flat per level) split over their recipes
  // by the value of what each recipe bought
  function makersTree(D) {
    const tree = new Map();
    for (const r of D.makers) {
      if (!inScope(r[0])) continue;
      const c = r[1];
      if (!tree.has(c)) tree.set(c, {c, food: 0, buildings: new Map()});
      const ct = tree.get(c);
      ct.food += r[4] || 0;
      if (r[2] < 0) continue;
      if (!ct.buildings.has(r[2])) ct.buildings.set(r[2], {b: r[2], food: 0, methods: new Map()});
      const bt = ct.buildings.get(r[2]);
      bt.food += r[4] || 0;
      bt.methods.set(r[3], (bt.methods.get(r[3]) || 0) + (r[4] || 0));
    }
    const kitchens = catIdx('kitchens');
    if (tree.has(kitchens)) for (const bt of tree.get(kitchens).buildings.values()) {
      const flat = bt.methods.get(-1) || 0;
      if (!flat) continue;
      const recipes = new Map();
      for (const r of D.byBuildingIn.get(bt.b) || []) {
        if (!inScope(r[3]) || r[2] < 0 || DUMMY.has(GI.goods[r[0]].id)) continue;
        recipes.set(r[2], (recipes.get(r[2]) || 0) + (r[5] || 0) * goodPrice(r[0]));
      }
      const total = [...recipes.values()].reduce((a, v) => a + v, 0);
      if (total <= 0) continue;
      bt.methods.delete(-1);
      for (const [m, v] of recipes) bt.methods.set(m, (bt.methods.get(m) || 0) + flat * v / total);
    }
    return tree;
  }
  // what a method bought, as food: its food split over its (non-bookkeeping) inputs by value
  function inputsOf(D, m, food) {
    const rows = (D.cIn.get(m) || []).filter(r => inScope(r[3]) && !DUMMY.has(GI.goods[r[0]].id));
    const total = rows.reduce((a, r) => a + (r[5] || 0) * goodPrice(r[0]), 0);
    if (total <= 0) return [];
    return rows.map(r => ({g: r[0], food: food * (r[5] || 0) * goodPrice(r[0]) / total, amount: (r[5] || 0)}));
  }

  // ---------------------------------------------------------------- flow chart
  function flowOption(D, rows, T) {
    const nodes = [], links = [], label = {}, title = {}, goodOf = {}, toggles = {};
    const node = (id, text, depth, color, full) => { if (label[id] != null) return; label[id] = text; title[id] = full || text; nodes.push({name: id, depth, itemStyle: {color}}); };
    const link = (source, target, value, extra) => { if (value > 1e-6) links.push({source, target, value, ...(extra || {})}); };
    const province = S.p >= 0;
    // makers
    const makers = [];  // {id, text, full, color, food, methods: [[m, food]], toggle}
    if (province) {
      for (const c of FI.categories) {
        const food = c.id === 'subsistence' ? T.sub : T[c.id] || 0;
        if (food > 0) makers.push({id: 'c' + c.id, text: c.name, color: c.color, food, methods: [], sub: c.id === 'subsistence'});
      }
    } else {
      const tree = makersTree(D);
      for (let ci = 0; ci < FI.categories.length; ci++) {
        const ct = tree.get(ci);
        if (!ct || ct.food <= 0) continue;
        const c = cat(ci), bs = [...ct.buildings.values()].sort((a, b) => b.food - a.food);
        if (!S.open.has('c' + ci) || !bs.length) {
          makers.push({id: 'c' + ci, text: c.name, color: c.color, food: ct.food, toggle: bs.length ? 'c' + ci : null,
                       methods: bs.flatMap(bt => [...bt.methods.entries()]), sub: c.id === 'subsistence'});
          continue;
        }
        const LIMIT = 10;
        bs.forEach((bt, k) => {
          if (k >= LIMIT) return;
          const key = 'b' + bt.b, methods = [...bt.methods.entries()].sort((a, b) => b[1] - a[1]);
          if (S.open.has(key) && methods.length > 1) {
            const MLIMIT = 14;
            for (const [m, f] of methods.slice(0, MLIMIT)) makers.push({id: 'm' + m + '_' + bt.b, text: mName(m), full: `${mName(m)} (${bName(bt.b)})`, color: shade(c.color, 0.35), food: f, methods: [[m, f]], toggle: key});
            if (methods.length > MLIMIT) {
              const rest = methods.slice(MLIMIT);
              makers.push({id: 'mr_' + bt.b, text: `Other recipes (${rest.length})`, full: `Other recipes of ${bName(bt.b)} (${rest.length})`, color: shade(c.color, 0.55),
                           food: rest.reduce((a, e) => a + e[1], 0), methods: rest, toggle: key});
            }
          } else {
            makers.push({id: key, text: bName(bt.b), color: shade(c.color, 0.15), food: bt.food, methods, toggle: methods.length > 1 ? key : null});
          }
        });
        if (bs.length > LIMIT) {
          const rest = bs.slice(LIMIT);
          makers.push({id: 'r' + ci, text: `Other ${c.name.toLowerCase()} (${rest.length})`, color: shade(c.color, 0.5), food: rest.reduce((a, b) => a + b.food, 0),
                       methods: rest.flatMap(bt => [...bt.methods.entries()])});
        }
      }
    }
    // inputs of the makers (goods bought, as food made from them)
    const ins = new Map();
    for (const mk of makers) {
      if (mk.sub) { ins.set('idle', (ins.get('idle') || new Map()).set(mk.id, T.sub)); continue; }
      for (const [m, f] of mk.methods) {
        if (m < 0) continue;
        for (const it of inputsOf(D, m, f)) {
          if (!ins.has(it.g)) ins.set(it.g, new Map());
          const t = ins.get(it.g); t.set(mk.id, (t.get(mk.id) || 0) + it.food);
        }
      }
    }
    const inTotals = [...ins.entries()].map(([g, t]) => [g, [...t.values()].reduce((a, v) => a + v, 0)]).sort((a, b) => b[1] - a[1]);
    const inTop = new Set(inTotals.slice(0, 10).map(e => e[0]));
    const hasIn = inTotals.length > 0;
    const dIn = hasIn ? 0 : -1, dM = dIn + 1, dS = dM + 1, dO = dS + 1, dV = dO + 1;
    for (const [g] of inTotals) {
      if (!inTop.has(g)) continue;
      if (g === 'idle') node('in_idle', 'Idle peasants & slaves', dIn, '#c8b27a');
      else { node('in' + g, goodName(g), dIn, goodColor(g)); goodOf['in' + g] = g; }
    }
    if (inTotals.length > inTop.size) node('in_rest', `Other inputs (${inTotals.length - inTop.size})`, dIn, '#9a9a96');
    if (T.change < 0) node('from_store', 'Drawn from the stores', dM, '#5fb8c4');
    for (const mk of makers) { node(mk.id, mk.text, dM, mk.color, mk.full); if (mk.toggle) toggles[mk.id] = mk.toggle; }
    const where = S.p >= 0 ? 'Province store' : 'Province stores';
    node('store', where, dS, '#8c6d3f');
    // outflows
    const eat = new Map();
    if (province) eat.set(-1, T.base);
    else for (const r of D.eat) if (inScope(r[0])) eat.set(r[1], (eat.get(r[1]) || 0) + (r[2] || 0));
    const PCOL = ['#e87ba4', '#4a3aa7', '#eda100', '#2a78d6', '#e34948', '#1baf7a', '#7d5a5a', '#9c7a3c'];
    const eats = [...eat.entries()].filter(e => e[1] > 0).sort((a, b) => b[1] - a[1]);
    for (const [t] of eats) node('e' + t, t < 0 ? 'Eaten by pops' : FI.popTypes[t].name, dO, t < 0 ? '#1baf7a' : PCOL[t % PCOL.length]);
    node('spoil', 'Spoilage & overflow', dO, '#9a9a96');
    if (T.taken > 0) { node('grange', 'Granges (packing)', dO, '#a0522d'); }
    if (T.change > 0) node('into_store', 'Into the stores', dO, '#5fb8c4');
    if (T.unexplained > 0) node('unexpl', 'Unexplained loss', dO, '#d8c9c6');
    // Granges' victuals (goods data, world / region only)
    let victuals = null;
    const vi = goodIdx.get('victuals');
    if (T.taken > 0 && vi != null && !province) {
      const grange = GI.buildings.findIndex(b => b.id === 'grange');
      victuals = (D.pOut.get(grange) || []).filter(r => r[0] === vi && inScope(r[3])).reduce((a, r) => a + (r[4] || 0), 0);
      node('victuals', 'Victuals', dV, goodColor(vi)); goodOf.victuals = vi;
    }
    // links
    for (const [g, t] of ins) for (const [mid, v] of t) {
      const src = inTop.has(g) ? (g === 'idle' ? 'in_idle' : 'in' + g) : 'in_rest';
      link(src, mid, v);
    }
    if (T.change < 0) link('from_store', 'store', -T.change);
    for (const mk of makers) link(mk.id, 'store', mk.food);
    for (const [t, v] of eats) link('store', 'e' + t, v);
    link('store', 'spoil', T.spoil);
    if (T.taken > 0) link('store', 'grange', T.taken);
    if (T.change > 0) link('store', 'into_store', T.change);
    if (T.unexplained > 0) link('store', 'unexpl', T.unexplained);
    if (victuals != null) link('grange', 'victuals', T.taken, {note: `${num(victuals)} victuals packed per month`});
    // merge parallel links, drop unused nodes
    const merged = new Map();
    for (const l of links) { const k = l.source + '|' + l.target; if (merged.has(k)) merged.get(k).value += l.value; else merged.set(k, {...l}); }
    const used = new Set(); for (const l of merged.values()) { used.add(l.source); used.add(l.target); }
    const keep = nodes.filter(n => used.has(n.name));
    const flow = id => Math.max([...merged.values()].filter(l => l.target === id).reduce((a, l) => a + l.value, 0),
                                [...merged.values()].filter(l => l.source === id).reduce((a, l) => a + l.value, 0));
    const store = Math.max(1e-9, flow('store'));
    const lastDepth = Math.max(...keep.map(n => n.depth));
    for (const n of keep) if (n.name !== 'store') n.label = {width: n.depth === lastDepth ? 140 : 190, overflow: 'truncate', show: flow(n.name) >= 0.004 * store};
    const per = {}; for (const n of keep) per[n.depth] = (per[n.depth] || 0) + 1;
    const height = Math.max(420, Math.max(...Object.values(per), 1) * 36 + 70);
    const option = {
      backgroundColor: 'transparent',
      tooltip: {trigger: 'item', confine: true, formatter: p => {
        if (p.dataType === 'edge') {
          const d = p.data;
          return `${esc(title[d.source])} → ${esc(title[d.target])}<br><b>${num(d.value)}</b> food / month${d.note ? '<br>' + esc(d.note) : ''}`;
        }
        const hint = toggles[p.name] ? `<br><span style="opacity:.7">click to ${S.open.has(toggles[p.name]) ? 'close' : 'open'}</span>` :
          goodOf[p.name] != null ? '<br><span style="opacity:.7">click to open this good on the goods page</span>' : '';
        const extra = p.name === 'store' ? `<br>stock ${num(T.stock)} of ${num(T.cap)} · ${months(T.months)} months` : '';
        return `<b>${esc(title[p.name])}</b><br>${num(flow(p.name))} food / month${extra}${hint}`;
      }},
      series: [{
        type: 'sankey', left: 4, right: 160, top: 8, bottom: 8, nodeWidth: 12, nodeGap: 12, layoutIterations: 0,
        draggable: false, emphasis: {focus: 'adjacency'},
        label: {color: INK, fontSize: 11, formatter: p => p.name === 'store'
          ? `{b|${label.store}}\n${num(T.stock)} stored · ${months(T.months)} months`
          : `${num(flow(p.name))}  ${label[p.name]}${toggles[p.name] ? (S.open.has(toggles[p.name]) ? '  ▾' : '  ▸') : ''}`,
          rich: {b: {fontWeight: 'bold', fontSize: 13, color: INK}}},
        lineStyle: {color: 'gradient', curveness: 0.5, opacity: dark ? 0.45 : 0.32},
        data: keep, links: [...merged.values()],
      }],
    };
    return {option, height, goodOf, toggles};
  }

  // ---------------------------------------------------------------- tables
  function mainSource(r) {
    let best = null, v = 0;
    for (const c of FI.categories) { const x = r[P[c.id === 'subsistence' ? 'sub' : c.id]] || 0; if (x > v) { v = x; best = c; } }
    return best;
  }
  function provinceTable(D) {
    if (S.p >= 0) return '';
    let rows = D.pools.filter(r => inScope(r[P.region]) && (r[P.base] || 0) > 0).map(r => ({r, m: r[P.stock] / r[P.base]}));
    const q = S.query.trim().toLowerCase();
    if (q) rows = rows.filter(x => FI.provinces[x.r[P.province]].toLowerCase().includes(q) || (FI.countries[x.r[P.country]] || '').toLowerCase().includes(q));
    const key = {months: x => x.m, people: x => x.r[P.pop], made: x => x.r[P.structural] + x.r[P.base], eaten: x => x.r[P.base],
                 net: x => x.r[P.change], fill: x => x.r[P.cap] > 0 ? x.r[P.stock] / x.r[P.cap] : 0, taken: x => x.r[P.taken], factor: x => x.r[P.factor],
                 province: x => FI.provinces[x.r[P.province]]}[S.sort] || (x => x.m);
    rows.sort((a, b) => { const x = key(a), y = key(b); const c = typeof x === 'string' ? x.localeCompare(y) : (x || 0) - (y || 0); return S.asc ? c : -c; });
    const total = rows.length;
    if (!S.all) rows = rows.slice(0, 40);
    const th = (k, text, num_, tip) => `<th class="sortable${num_ ? ' num' : ''}${S.sort === k ? ' sorted' + (S.asc ? ' asc' : '') : ''}" data-sort="${k}"${tip ? ` title="${esc(tip)}"` : ''}>${text}</th>`;
    let h = `<table class=gt><thead><tr>${th('province', 'Province')}<th>Owner</th>${th('people', 'People', 1)}${th('months', 'Months', 1, 'stock ÷ monthly consumption')}${th('fill', 'Store', 1, 'stock ÷ capacity')}` +
      `${th('made', 'Made', 1)}${th('eaten', 'Eaten', 1)}${th('net', 'Net', 1, 'change of the store per month (after spoilage)')}<th>Main source</th>${th('taken', 'Granges', 1, 'food the Granges take to pack victuals')}${th('factor', 'Food modifier', 1, 'fitted: actual ÷ estimate (climate, arid rows, store lever, other modifiers)')}</tr></thead><tbody>`;
    for (const {r, m} of rows) {
      const src = mainSource(r), fill = r[P.cap] > 0 ? r[P.stock] / r[P.cap] : 0;
      h += `<tr class=click data-province="${r[P.province]}"><td>${esc(FI.provinces[r[P.province]])}</td><td>${esc(FI.countries[r[P.country]] || '')}</td><td class=num>${people(r[P.pop])}</td>` +
        `<td class="num months ${mClass(m)}">${months(m)}</td><td class=num><span class=fill><i style="width:${(Math.min(1, fill) * 100).toFixed(0)}%"></i></span>${pct(fill)}</td>` +
        `<td class=num>${num(r[P.structural] + r[P.base])}</td><td class=num>${num(r[P.base])}</td><td class="num ${r[P.change] < 0 ? 'neg' : 'pos'}">${(r[P.change] > 0 ? '+' : '') + num(r[P.change])}</td>` +
        `<td>${src ? `<i class=dot style="background:${src.color}"></i>${esc(src.name)}` : ''}</td><td class=num>${num(r[P.taken])}</td><td class=num>${r[P.factor] == null ? '–' : r[P.factor].toFixed(2) + '×'}</td></tr>`;
    }
    h += '</tbody></table>';
    if (total > 40) h += `<button type=button class=more data-all>${S.all ? 'Show fewer' : `Show all ${total}`}</button>`;
    return h;
  }
  function chipList(list) {
    return list.slice(0, 4).map(([g, v]) => `<a href="goods.html#g=${encodeURIComponent(GI.goods[g].id)}" title="${esc(goodName(g))}" class=chip>${imgHtml(g)}${num(v)}</a>`).join(' ');
  }
  function buildingsTable(D) {
    if (S.p >= 0) return '';
    const by = new Map();
    const get = b => { if (!by.has(b)) by.set(b, {b, levels: 0, count: 0, workers: 0, profit: 0, food: 0}); return by.get(b); };
    for (const r of D.buildings) if (inScope(r[0])) { const e = get(r[1]); e.levels += r[2] || 0; e.count += r[3] || 0; e.workers += r[4] || 0; e.profit += r[5] || 0; }
    for (const r of D.makers) if (inScope(r[0]) && r[2] >= 0) get(r[2]).food += r[4] || 0;
    for (const r of D.takers) if (inScope(r[0])) get(r[1]).food -= r[2] || 0;
    const rows = [...by.values()].filter(e => e.levels > 0).sort((a, b) => Math.abs(b.food) - Math.abs(a.food) || b.levels - a.levels);
    let h = `<table class=gt><thead><tr><th>Building</th><th class=num>Levels</th><th class=num>Buildings</th><th class=num title="thousands">Workers</th><th class=num title="food added to (+) or taken from (−) the stores per month">Food</th><th>Buys</th><th>Makes</th><th class=num title="last month, all levels">Profit</th><th class=num>Per level</th></tr></thead><tbody>`;
    for (const e of rows) {
      const buys = new Map(), makes = new Map();
      for (const r of D.byBuildingIn.get(e.b) || []) if (inScope(r[3]) && !DUMMY.has(GI.goods[r[0]].id)) buys.set(r[0], (buys.get(r[0]) || 0) + (r[5] || 0));
      for (const r of D.pOut.get(e.b) || []) if (inScope(r[3]) && !DUMMY.has(GI.goods[r[0]].id)) makes.set(r[0], (makes.get(r[0]) || 0) + (r[4] || 0));
      const sorted = m => [...m.entries()].sort((a, b) => b[1] - a[1]);
      h += `<tr><td>${esc(bName(e.b))}</td><td class=num>${num(e.levels)}</td><td class=num>${num(e.count)}</td><td class=num>${num(e.workers)}</td>` +
        `<td class="num ${e.food < 0 ? 'neg' : ''}">${e.food ? (e.food > 0 ? '+' : '') + num(e.food) : '–'}</td><td class=goods>${chipList(sorted(buys))}</td><td class=goods>${chipList(sorted(makes))}</td>` +
        `<td class="num ${e.profit < 0 ? 'neg' : ''}">${num(e.profit)}</td><td class=num>${e.levels ? num(e.profit / e.levels) : '–'}</td></tr>`;
    }
    return h + '</tbody></table>';
  }

  // ---------------------------------------------------------------- over the run
  const saveTime = i => { const d = String(GI.saves[i].date || GI.saves[i].label).split('.').map(Number); return Date.UTC(d[0], (d[1] || 1) - 1, d[2] || 1); };
  function timeOption() {
    const xs = GI.saves.map((s, i) => saveTime(i));
    const marker = {silent: true, symbol: 'none', label: {show: false}, lineStyle: {type: 'dashed', color: MUTED, width: 1}, data: [{xAxis: xs[S.s]}]};
    const line = (name, values, color, extra) => ({type: 'line', name, showSymbol: false, color, connectNulls: false, lineStyle: {width: 2}, emphasis: {focus: 'series'}, data: values.map((v, j) => [xs[j], v]), ...(extra || {})});
    const area = (name, values, color) => line(name, values, color, {stack: 'total', areaStyle: {opacity: 0.85}, lineStyle: {width: 0.6}});
    const base = {backgroundColor: 'transparent', tooltip: {trigger: 'axis', confine: true, valueFormatter: v => num(v)},
                  legend: {type: 'scroll', top: 0, left: 0, right: 0, textStyle: {color: INK}}, grid: {left: 8, right: 16, top: 40, bottom: 30, containLabel: true},
                  xAxis: {type: 'time', min: xs[0], max: xs[xs.length - 1], axisLabel: {formatter: v => String(new Date(v).getUTCFullYear()), hideOverlap: true}},
                  yAxis: {type: 'value', axisLabel: {formatter: v => num(v)}}};
    let views;
    if (S.p >= 0) {
      const e = FP && FP[String(S.p)];
      if (!e) return null;
      const capMonths = e.cap.map((c, j) => (c != null && e.eaten[j]) ? c / e.eaten[j] : null);
      views = [
        {...base, yAxis: {type: 'value', name: 'months'}, series: [line('Months stored', e.months, '#1baf7a'), line('Capacity in months', capMonths, MUTED, {lineStyle: {type: 'dashed', width: 1.5}})]},
        {...base, series: [line('Stock', e.stock, '#8c6d3f'), line('Capacity', e.cap, MUTED, {lineStyle: {type: 'dashed', width: 1.5}})]},
        {...base, series: [line('Made', e.made, '#2a78d6'), line('Eaten', e.eaten, '#eb6834')]},
      ];
    } else {
      const e = S.r >= 0 ? FS.regions[String(S.r)] : FS.world;
      if (!e) return null;
      const BAND = ['#8f1f1f', '#d9534f', '#eda100', '#d8c9c6', '#6da7ec', '#184f95'];
      const bandName = b => b === FI.bands.length - 1 ? `${FI.bands[b]}+ months` : `${FI.bands[b]}–${FI.bands[b + 1]} months`;
      const capMonths = e.cap.map((c, j) => (c != null && e.base[j]) ? c / e.base[j] : null);
      views = [
        {...base, yAxis: {type: 'value', axisLabel: {formatter: v => people(v)}}, tooltip: {...base.tooltip, valueFormatter: v => people(v) + ' people'},
         series: e.bands.map((vals, b) => area(bandName(b), vals, BAND[b]))},
        {...base, yAxis: {type: 'value', name: 'months'}, series: [line('Months stored', e.months, '#1baf7a'), line('Capacity in months', capMonths, MUTED, {lineStyle: {type: 'dashed', width: 1.5}})]},
        {...base, series: FI.categories.map(c => area(c.name, e[c.id === 'subsistence' ? 'sub' : c.id], c.color))},
        {...base, series: [line('Made', e.made, '#2a78d6'), line('Eaten', e.base, '#eb6834'), line('Spoiled', e.spoil, '#9a9a96'), line('Taken by Granges', e.taken, '#a0522d')]},
      ];
    }
    const option = views[Math.min(S.tv, views.length - 1)];
    option.series.forEach((s, i) => { if (i === 0) s.markLine = marker; });
    return option;
  }
  function timeButtons() {
    const names = S.p >= 0 ? ['Months stored', 'Stock & capacity', 'Made & eaten'] : ['People by months stored', 'Months stored', 'Sources', 'Made, eaten, spoiled'];
    if (S.tv >= names.length) S.tv = 0;
    $('#timeviews').innerHTML = names.map((n, i) => `<button type=button class="${i === S.tv ? 'active' : ''}" data-tv="${i}">${n}</button>`).join('');
  }

  // ---------------------------------------------------------------- page
  function chart(id) {
    if (!charts[id]) { const el = document.getElementById(id); charts[id] = echarts.init(el, dark ? 'dark' : null); new ResizeObserver(() => charts[id].resize()).observe(el); }
    return charts[id];
  }
  function writeHash() {
    const scope = S.p >= 0 ? `p=${S.p}` : S.r >= 0 ? `r=${encodeURIComponent(GI.regions[S.r].id)}` : 'r=world';
    const h = `#s=${S.s}&${scope}`;
    if (location.hash !== h) history.replaceState(null, '', h);
  }
  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    if (p.has('s')) { const s = Number(p.get('s')); if (s >= 0 && s < GI.saves.length) S.s = s; }
    S.p = p.has('p') ? Number(p.get('p')) : -1;
    S.r = p.has('r') && regionIdx.has(p.get('r')) ? regionIdx.get(p.get('r')) : -1;
  }
  function setScope(r, p) { S.r = r; S.p = p; S.all = false; history.pushState(null, '', location.hash); render(); window.scrollTo({top: 0}); }
  function sidebar(D) {
    const byRegion = new Map();
    for (const r of D.pools) { const k = r[P.region]; if (!byRegion.has(k)) byRegion.set(k, []); byRegion.get(k).push(r); }
    const W = totals(D.pools);
    let h = `<a href="#" data-scope="-1" class="${S.r < 0 && S.p < 0 ? 'on' : ''}"><span>World</span><span class="badge months ${mClass(W.months)}" title="months stored">${months(W.months)} mo</span></a>`;
    const regions = [...byRegion.keys()].filter(k => k >= 0 && GI.regions[k]).sort((a, b) => GI.regions[a].name.localeCompare(GI.regions[b].name));
    for (const k of regions) {
      const t = totals(byRegion.get(k));
      h += `<a href="#" data-scope="${k}" class="${S.r === k && S.p < 0 ? 'on' : ''}"><i class=dot style="background:${GI.regions[k].color}"></i><span>${esc(GI.regions[k].name)}</span><span class="badge months ${mClass(t.months)}" title="months stored · ${people(t.pop)} people">${months(t.months)} mo</span></a>`;
    }
    $('#scopes').innerHTML = h;
  }
  function searchResults(D) {
    const q = $('#psearch').value.trim().toLowerCase();
    if (q.length < 2) { $('#results').innerHTML = ''; return; }
    const seen = new Set(), out = [];
    for (const r of D.pools) {
      const name = FI.provinces[r[P.province]];
      if (seen.has(r[P.province]) || !name.toLowerCase().includes(q)) continue;
      seen.add(r[P.province]);
      out.push(r);
      if (out.length >= 14) break;
    }
    $('#results').innerHTML = out.map(r => `<a href="#" data-province="${r[P.province]}">${esc(FI.provinces[r[P.province]])} <small>${esc(FI.countries[r[P.country]] || '')} · ${months(r[P.base] ? r[P.stock] / r[P.base] : null)} mo</small></a>`).join('') || '<small>No province matches.</small>';
  }
  function tiles(T) {
    const t = [
      ['Made', num(T.made) + ' / mo', `${num(T.sub)} subsistence · ${num(T.rgos)} RGOs · ${num(T.farms + T.kitchens + T.taverns)} buildings`],
      ['Eaten', num(T.base) + ' / mo', `${people(T.pop)} people`],
      ['Spoilage & overflow', num(T.spoil) + ' / mo', `${pct(T.stock > 0 ? T.spoil / T.stock : null)} of the stock`],
      [T.change >= 0 ? 'Into the stores' : 'Drawn from the stores', num(Math.abs(T.change)) + ' / mo', 'after spoilage'],
      ['Stock', num(T.stock), `${pct(T.cap > 0 ? T.stock / T.cap : null)} of ${num(T.cap)} capacity`],
      ['Months stored', months(T.months), 'stock ÷ monthly consumption'],
      ['Granges', num(T.taken) + ' / mo', 'food packed into victuals'],
      ['Food modifier', T.factor == null ? '–' : T.factor.toFixed(2) + '×', 'fitted, people-weighted: climate, store lever, other modifiers'],
    ];
    return t.map(([a, b, c]) => `<div class=tile><div class=label>${esc(a)}</div><div class=value>${esc(b)}</div><div class=sub>${esc(c)}</div></div>`).join('');
  }
  let token = 0;
  async function render() {
    const my = ++token;
    writeHash();
    $('#save').value = String(S.s);
    $('.main').classList.add('loading');
    let D;
    try { D = await loadSave(S.s); } catch (err) { $('#head').innerHTML = `<div class=empty>Could not load this save (${esc(err.message)}).</div>`; return; }
    if (my !== token) return;
    $('.main').classList.remove('loading');
    if (!D) { $('#head').innerHTML = '<div class=empty>This save has no province food data.</div>'; return; }
    sidebar(D);
    searchResults(D);
    const rows = poolsInScope(D), T = totals(rows);
    const owners = S.p >= 0 ? [...new Set(rows.map(r => FI.countries[r[P.country]]))].join(', ') : '';
    const title = S.p >= 0 ? FI.provinces[S.p] : S.r >= 0 ? GI.regions[S.r].name : 'World';
    document.title = `Food · ${title} · ${GI.run}`;
    $('#head').innerHTML = `<div class=ghead><div><h1>${esc(title)}</h1><div class=muted>${S.p >= 0 ? esc(owners) + ' · ' : ''}${T.pools} province store${T.pools === 1 ? '' : 's'} · save ${esc(GI.saves[S.s].label)}${S.p >= 0 ? ' · <a href="#" data-scope="-1">back to the world</a>' : ''}</div></div></div><div class=tiles>${tiles(T)}</div>`;
    document.querySelectorAll('#detail button').forEach(b => b.disabled = S.p >= 0);
    if (!rows.length) { $('#sankey').style.height = '120px'; chart('sankey').clear(); }
    else {
      const flow = flowOption(D, rows, T);
      $('#sankey').style.height = flow.height + 'px';
      const sk = chart('sankey'); sk.resize(); sk.setOption(flow.option, true);
      sk.off('click');
      sk.on('click', p => {
        if (p.dataType !== 'node') return;
        const key = flow.toggles[p.name];
        if (key) { if (S.open.has(key)) S.open.delete(key); else S.open.add(key); render(); return; }
        if (flow.goodOf[p.name] != null) window.location.href = 'goods.html#g=' + encodeURIComponent(GI.goods[flow.goodOf[p.name]].id);
      });
    }
    $('#sankeynote').textContent = S.p >= 0 ? 'A single province shows its sources by category; open a world region for buildings and recipes.' : '';
    $('#ptable').innerHTML = provinceTable(D);
    $('#pcard').hidden = S.p >= 0;
    $('#btable').innerHTML = buildingsTable(D);
    $('#bcard').hidden = S.p >= 0;
    timeButtons();
    if (S.p >= 0 && !FP) { FP = await fetch('food/provinces.json').then(r => r.json()).catch(() => ({})); if (my !== token) return; }
    const opt = FS ? timeOption() : null;
    if (opt) chart('time').setOption(opt, true); else chart('time').clear();
    if (S.s > 0) loadSave(S.s - 1);
    if (S.s < GI.saves.length - 1) loadSave(S.s + 1);
  }

  async function init() {
    try {
      [GI, FI] = await Promise.all(['goods/index.json', 'food/index.json'].map(u => fetch(u).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })));
    } catch (err) {
      $('#head').innerHTML = '<div class=empty>The food data did not load. This page reads files next to it, so open it from the published site or over a local web server (not as a file).</div>';
      return;
    }
    FI.poolColumns.forEach((c, i) => { P[c] = i; });
    P.province = 0; P.country = 1; P.region = 2;
    GI.goods.forEach((g, i) => goodIdx.set(g.id, i));
    GI.regions.forEach((r, i) => regionIdx.set(r.id, i));
    S.s = GI.saves.length - 1;
    while (S.s > 0 && !FI.saves[S.s]) S.s--;
    readHash();
    $('#runname').textContent = `${GI.run} · ${GI.years[0]}–${GI.years[1]}`;
    $('#save').innerHTML = GI.saves.map((s, i) => `<option value="${i}"${FI.saves[i] ? '' : ' disabled'}>${esc(s.label)}</option>`).join('');
    if (FI.video) $('#video').innerHTML = `<figure class="card vid"><video controls loop muted playsinline preload=metadata poster="${esc(FI.video.poster)}"><source src="${esc(FI.video.video)}" type="video/mp4"></video><figcaption><b>${esc(FI.video.title)}</b> · ${esc(FI.video.subtitle)} (red: under 3 months, blue: 18 and more) · <a href="${esc(FI.video.video)}" download>MP4</a></figcaption></figure>`;
    $('#save').addEventListener('change', e => { S.s = Number(e.target.value); render(); });
    $('#prev').addEventListener('click', () => { let s = S.s - 1; while (s >= 0 && !FI.saves[s]) s--; if (s >= 0) { S.s = s; render(); } });
    $('#next').addEventListener('click', () => { let s = S.s + 1; while (s < GI.saves.length && !FI.saves[s]) s++; if (s < GI.saves.length) { S.s = s; render(); } });
    document.querySelectorAll('#detail button').forEach(b => b.addEventListener('click', () => {
      S.open.clear();
      if (b.dataset.v !== 'categories') FI.categories.forEach((c, i) => S.open.add('c' + i));
      if (b.dataset.v === 'recipes') GI.buildings.forEach((x, i) => S.open.add('b' + i));
      render();
    }));
    $('#psearch').addEventListener('input', () => loadSave(S.s).then(D => D && searchResults(D)));
    $('#pfilter').addEventListener('input', e => { S.query = e.target.value; loadSave(S.s).then(D => { if (D) $('#ptable').innerHTML = provinceTable(D); }); });
    document.addEventListener('click', e => {
      const sc = e.target.closest('[data-scope]');
      if (sc) { e.preventDefault(); const r = Number(sc.dataset.scope); setScope(r, -1); return; }
      const pr = e.target.closest('[data-province]');
      if (pr) { e.preventDefault(); $('#psearch').value = ''; setScope(S.r, Number(pr.dataset.province)); return; }
      const so = e.target.closest('th[data-sort]');
      if (so) { const k = so.dataset.sort; if (S.sort === k) S.asc = !S.asc; else { S.sort = k; S.asc = k === 'months' || k === 'province' || k === 'fill' || k === 'net'; } loadSave(S.s).then(D => { if (D) $('#ptable').innerHTML = provinceTable(D); }); return; }
      if (e.target.closest('[data-all]')) { S.all = !S.all; loadSave(S.s).then(D => { if (D) $('#ptable').innerHTML = provinceTable(D); }); return; }
      const tv = e.target.closest('[data-tv]');
      if (tv) { S.tv = Number(tv.dataset.tv); timeButtons(); const opt = FS ? timeOption() : null; if (opt) chart('time').setOption(opt, true); }
    });
    window.addEventListener('popstate', () => { readHash(); render(); });
    render();
    fetch('food/summary.json').then(r => r.json()).then(s => { FS = s; const opt = timeOption(); if (opt) chart('time').setOption(opt, true); }).catch(() => {});
  }
  init();
})();
"""


def food_page_html(run_name: str, years: tuple[int, int]) -> str:
    esc = html.escape
    title = f"Food · {esc(run_name)} · {years[0]}–{years[1]} · Prosper or Perish"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="robots" content="noindex">
<style>{PAGE_CSS}{GOODS_CSS}{FOOD_CSS}</style></head><body>
<div class=app>
<aside class=side>
  <a class=back href="index.html">← Run report</a>
  <a class=back href="goods.html">Goods page →</a>
  <div class=run id=runname></div>
  <h4>Where</h4>
  <div class=scopes id=scopes></div>
  <h4>Province</h4>
  <input id=psearch type=search placeholder="Find a province" aria-label="Find a province" autocomplete=off>
  <div class=results id=results></div>
</aside>
<div class=main>
  <div class=bar>
    <label>Save <button id=prev type=button title="Previous save">‹</button><select id=save></select><button id=next type=button title="Next save">›</button></label>
    <label>Show <span class=seg id=detail><button type=button data-v=categories>Categories</button><button type=button data-v=buildings>Buildings</button><button type=button data-v=recipes>Recipes</button></span></label>
    <span class=muted>or click a source in the chart to open it</span>
  </div>
  <section id=head></section>
  <section class=card><header><h3>Where the food comes from and where it goes</h3></header>
    <div id=sankey class=chart style="height:460px"></div>
    <p class=note id=sankeynote></p>
    <p class=caption>Food per month. Left to right: what the makers bought (as the food made from it), who makes food (click a
    category or building to open it; Cookshops and Public Kitchens open into their recipes), the province stores, and who eats it,
    what spoils and what the Granges take to pack victuals. The stores' figures are exact from the save; the split between the
    sources is an estimate (subsistence, RGO levels, the buildings' recipes and flat food per level, by staffing) fitted to each
    store's exact total with one factor per province, which stands for its food modifiers.</p></section>
  <div id=video></div>
  <section class=card><header><h3>The stores over the run</h3><div class=views id=timeviews></div></header>
    <div id=time class=chart style="height:400px"></div>
    <p class=caption>People by months stored: everyone living in a province whose store holds that many months of its consumption.
    The dashed line marks the chosen save.</p></section>
  <section class=card id=pcard><header><h3>Provinces</h3><div class=controls><input id=pfilter type=search placeholder="Filter" aria-label="Filter provinces"></div></header>
    <div class=table-wrap id=ptable></div>
    <p class=caption>One row per province store (a province split between owners has one store per owner). Click a column to sort, a
    row to open the province.</p></section>
  <section class=card id=bcard><header><h3>Food buildings</h3></header><div class=table-wrap id=btable></div>
    <p class=caption>Buildings that add food to the stores or take it (Granges), and the Victualling Yards and Granaries. Buys and
    makes come from the goods page (per month; click a good to open it there).</p></section>
</div>
</div>
<script src="{ECHARTS_URL}"></script>
<script>{FOOD_JS}</script>
</body></html>
"""
