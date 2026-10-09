"""The food page of the run report (`food.html`): how food reaches the province food stores and where it goes.

Static HTML + one script, data fetched when needed: `food/index.json`, `food/summary.json`, `food/<n>.json` per save,
`food/provinces.json` (when a province is opened) and the goods page's `goods/index.json` and `goods/<n>.json` (the
buildings, methods, goods and regions, and what each method bought and made).

The flow chart has the province food store in the middle and reads in two layers:
- left, what fills it: its three sources as the engine adds them (Province Food the good, monthly food flat, subsistence),
  behind them who makes each (farms' Provisioning and Taverns; RGO levels, farms' and Cookshops' food per level;
  idle peasants and slaves), behind those what they buy (goods), and behind victuals who packs them (Victualling Yards,
  Granges) and what the Yards buy; Cookshops open into their recipes;
- right, what empties it: consumption (by pop type), spoilage, and the Granges with the victuals they pack.
Below it: consumption from need (pops x food rate) through the Cookshops' and the other modifiers to what was eaten,
the months-stored map, the stores over the run, the provinces and the food buildings. State lives in the URL hash
(#s=12&r=<region> or #s=12&p=<province>).
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
.scroll{overflow-x:auto} .scroll .chart{min-width:980px}
.legend2{display:flex;flex-wrap:wrap;gap:4px 18px;padding:0 16px 8px;font-size:12px;color:var(--muted)}
.legend2 b{color:var(--ink);font-weight:600}
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
  const signed = v => (v > 0 ? '+' : '') + num(v);
  const pct = f => (f == null || !isFinite(f)) ? '–' : (f * 100).toFixed(Math.abs(f) < 0.1 ? 1 : 0) + '%';
  const months = v => (v == null || !isFinite(v)) ? '–' : v.toFixed(v < 10 ? 1 : 0);
  const mClass = v => v == null ? '' : v < 3 ? 'm-low' : v >= 12 ? 'm-high' : 'm-ok';
  const people = k => num((k || 0) * 1000);
  // goods that are bookkeeping, not inputs worth showing
  const DUMMY = new Set(['offset', 'logistics', 'local_food', 'manual_labor', 'province_food_sales', 'province_food_purchase']);
  const SRC = {pf: {id: 'src_pf', name: 'Province Food (the good)', color: '#1baf7a'},
               flat: {id: 'src_flat', name: 'Monthly food (flat)', color: '#c98a00'},
               sub: {id: 'src_sub', name: 'Subsistence', color: '#9c7a3c'}};

  let GI, FI, FS = null, FP = null;
  const SAVES = new Map();
  const S = {s: 0, r: -1, p: -1, recipes: false, tv: 0, sort: 'months', asc: true, all: false, query: ''};
  let goodIdx = new Map(), regionIdx = new Map(), P = {}, charts = {};
  const goodName = i => (GI.goods[i] || {}).name || '?';
  const goodPrice = i => (GI.goods[i] || {}).price || 1;
  const goodIcon = i => (GI.goods[i] || {}).icon;
  const goodColor = i => (GI.groups.find(g => g.key === (GI.goods[i] || {}).group) || {}).color || '#9a9a96';
  const bName = i => i < 0 ? '' : (GI.buildings[i] || {}).name || '?';
  const mName = i => i < 0 ? 'Food per level (flat)' : (GI.methods[i] || {}).name || '?';
  const catIdx = id => FI.categories.findIndex(c => c.id === id);
  const imgHtml = i => goodIcon(i) ? `<img class=gi src="${esc(goodIcon(i))}" alt="">` : '';
  const isDummy = g => DUMMY.has((GI.goods[g] || {}).id);

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
    const bIn = new Map(), bOut = new Map(), mIn = new Map();  // building -> inputs / outputs, method -> inputs (goods data)
    const push = (map, k, r) => { if (!map.has(k)) map.set(k, []); map.get(k).push(r); };
    for (const r of (g && g.c) || []) { push(bIn, r[1], r); if (r[2] >= 0) push(mIn, r[2], r); }
    for (const r of (g && g.p) || []) push(bOut, r[1], r);
    return {...f, bIn, bOut, mIn};
  }
  const inScope = reg => S.r < 0 || reg === S.r;
  const poolsInScope = D => S.p >= 0 ? D.pools.filter(r => r[P.province] === S.p) : D.pools.filter(r => inScope(r[P.region]));
  const SUMS = ['pop', 'stock', 'cap', 'change', 'structural', 'base', 'spoil', 'sub', 'rgos', 'farms_pf', 'farms_flat', 'kitchens', 'taverns',
                'other', 'taken', 'unexplained', 'need', 'cook_saving'];
  function totals(rows) {
    const t = {};
    for (const k of SUMS) t[k] = 0;
    let fw = 0;
    for (const r of rows) { for (const k of SUMS) t[k] += r[P[k]] || 0; fw += (r[P.factor] || 0) * (r[P.pop] || 0); }
    t.factor = t.pop > 0 ? fw / t.pop : null;
    t.pf = t.farms_pf + t.taverns;
    t.flat = t.rgos + t.farms_flat + t.kitchens + t.other;
    t.made = t.pf + t.flat + t.sub;
    t.months = t.base > 0 ? t.stock / t.base : null;
    t.pools = rows.length;
    return t;
  }
  // a building's inputs (non-bookkeeping goods) in scope, as shares of their value: [[good, share, amount]]
  function inputShares(rows) {
    const by = new Map();
    for (const r of rows || []) if (inScope(r[3]) && !isDummy(r[0])) {
      const e = by.get(r[0]) || {v: 0, a: 0};
      e.v += (r[5] || 0) * goodPrice(r[0]); e.a += r[5] || 0; by.set(r[0], e);
    }
    const total = [...by.values()].reduce((a, e) => a + e.v, 0);
    return total > 0 ? [...by.entries()].map(([g, e]) => [g, e.v / total, e.a]) : [];
  }

  // ---------------------------------------------------------------- flow chart
  // columns: 0 what the Yards buy, 1 who packs victuals / recipe inputs, 2 goods the makers buy / recipes, 3 makers,
  // 4 the three sources, 5 the store, 6 consumption / spoilage / Granges, 7 pop types / victuals packed
  function flowOption(D, T) {
    const nodes = [], links = [], label = {}, title = {}, goodOf = {}, toggles = {};
    const node = (id, text, col, color, full) => { if (label[id] != null) return; label[id] = text; title[id] = full || text; nodes.push({name: id, depth: col, itemStyle: {color}}); };
    const link = (source, target, value, note) => { if (value > 1e-6) links.push({source, target, value, note}); };
    const province = S.p >= 0;
    for (const k of ['pf', 'flat', 'sub']) node(SRC[k].id, SRC[k].name, 4, SRC[k].color);
    const makers = [];  // {id, text, full, color, src, food, inputs: [[good, share, amount]], kitchen}
    if (province) {
      makers.push({id: 'mk_farms_pf', text: 'Farms (Provisioning)', src: 'pf', food: T.farms_pf, color: '#1baf7a'});
      makers.push({id: 'mk_taverns', text: 'Taverns', src: 'pf', food: T.taverns, color: '#2a78d6'});
      makers.push({id: 'mk_rgos', text: 'RGO levels', src: 'flat', food: T.rgos, color: '#c98a00'});
      makers.push({id: 'mk_farms_flat', text: 'Farms (food per level)', src: 'flat', food: T.farms_flat, color: '#5fd1a2'});
      makers.push({id: 'mk_kitchens', text: 'Cookshops & kitchens', src: 'flat', food: T.kitchens, color: '#e8692e'});
      makers.push({id: 'mk_other', text: 'Other flat food & modifiers', src: 'flat', food: T.other, color: '#9a9a96'});
      makers.push({id: 'mk_idle', text: 'Idle peasants & slaves', src: 'sub', food: T.sub, color: '#c8b27a'});
    } else {
      const pf = new Map(), fl = new Map(), ck = new Map();
      let rgos = 0, other = 0, sub = 0;
      const cSub = catIdx('subsistence'), cRgo = catIdx('rgos'), cOther = catIdx('other'), cKit = catIdx('kitchens');
      for (const r of D.makers) {
        if (!inScope(r[0])) continue;
        const v = r[4] || 0;
        if (r[1] === cSub) sub += v;
        else if (r[1] === cRgo) rgos += v;
        else if (r[1] === cOther) other += v;
        else if (r[1] === cKit) ck.set(r[2], (ck.get(r[2]) || 0) + v);
        else if (r[3] >= 0) pf.set(r[2], (pf.get(r[2]) || 0) + v);
        else fl.set(r[2], (fl.get(r[2]) || 0) + v);
      }
      const top = (map, n, idOf, textOf, color, src, restText, withInputs) => {
        const list = [...map.entries()].sort((a, b) => b[1] - a[1]);
        list.slice(0, n).forEach(([b, v]) => makers.push({id: idOf(b), text: textOf(b), src, food: v, color, b, inputs: withInputs ? inputShares(D.bIn.get(b)) : null}));
        const rest = list.slice(n);
        if (rest.length) {
          const restInputs = new Map();
          let total = rest.reduce((a, e) => a + e[1], 0);
          if (withInputs) for (const [b, v] of rest) for (const [g, sh, am] of inputShares(D.bIn.get(b))) {
            const e = restInputs.get(g) || [0, 0]; e[0] += sh * v / total; e[1] += am; restInputs.set(g, e);
          }
          makers.push({id: idOf('rest'), text: `${restText} (${rest.length})`, src, food: total, color: '#9a9a96',
                       inputs: withInputs ? [...restInputs.entries()].map(([g, e]) => [g, e[0], e[1]]) : null});
        }
      };
      top(pf, 10, b => 'pf' + b, b => bName(b), '#1baf7a', 'pf', 'Other buildings', true);
      if (rgos > 0) makers.push({id: 'mk_rgos', text: 'RGO levels', src: 'flat', food: rgos, color: '#c98a00'});
      top(fl, 6, b => 'fl' + b, b => bName(b) + ' (per level)', '#5fd1a2', 'flat', 'Other buildings per level', false);
      for (const [b, v] of [...ck.entries()].sort((a, c) => c[1] - a[1])) {
        makers.push({id: 'ck' + b, text: bName(b), src: 'flat', food: v, color: '#e8692e', b, kitchen: true, inputs: inputShares(D.bIn.get(b))});
        toggles['ck' + b] = 'recipes';
      }
      if (other > 0) makers.push({id: 'mk_other', text: 'Other flat food & modifiers', src: 'flat', food: other, color: '#9a9a96'});
      if (sub > 0) makers.push({id: 'mk_idle', text: 'Idle peasants & slaves', src: 'sub', food: sub, color: '#c8b27a'});
    }
    for (const mk of makers) if (mk.food > 0) { node(mk.id, mk.text, 3, mk.color, mk.full); link(mk.id, SRC[mk.src].id, mk.food); }

    // goods the makers buy (column 2) and Cookshop recipes (column 2, their inputs in column 1)
    const goods2 = new Map();  // good -> Map(maker -> food)
    const add = (map, g, target, v, amount) => { if (!map.has(g)) map.set(g, new Map()); const t = map.get(g); const e = t.get(target) || [0, 0]; e[0] += v; e[1] += amount || 0; t.set(target, e); };
    const goods1 = new Map();
    for (const mk of makers) {
      if (!mk.inputs || !mk.food) continue;
      if (mk.kitchen && S.recipes) {
        // the Cookshop's food split over its recipes by the value each bought
        const recipes = new Map();
        for (const r of D.bIn.get(mk.b) || []) if (inScope(r[3]) && r[2] >= 0 && !isDummy(r[0])) recipes.set(r[2], (recipes.get(r[2]) || 0) + (r[5] || 0) * goodPrice(r[0]));
        const total = [...recipes.values()].reduce((a, v) => a + v, 0);
        const sorted = [...recipes.entries()].sort((a, b) => b[1] - a[1]);
        sorted.forEach(([m, v], k) => {
          const rid = k < 12 ? 'rc' + m : 'rc_rest' + mk.b;
          const food = mk.food * v / total;
          node(rid, k < 12 ? mName(m) : `Other recipes (${sorted.length - 12})`, 2, '#f39a5b', k < 12 ? `${mName(m)} (${bName(mk.b)})` : null);
          toggles[rid] = 'recipes';
          link(rid, mk.id, food);
          for (const [g, sh, am] of inputShares((D.mIn.get(m) || []))) add(goods1, g, rid, food * sh, am);
        });
      } else {
        for (const [g, sh, am] of mk.inputs) add(goods2, g, mk.id, mk.food * sh, am);
      }
    }
    const placeGoods = (map, col, prefix, limit) => {
      const totals_ = [...map.entries()].map(([g, t]) => [g, [...t.values()].reduce((a, e) => a + e[0], 0)]).sort((a, b) => b[1] - a[1]);
      const keep = new Set(totals_.slice(0, limit).map(e => e[0]));
      for (const [g, t] of map) {
        const id = keep.has(g) ? prefix + g : prefix + 'rest';
        if (keep.has(g)) { node(id, goodName(g), col, goodColor(g)); goodOf[id] = g; }
        else node(id, `Other goods (${totals_.length - keep.size})`, col, '#9a9a96');
        for (const [target, [v, am]] of t) link(id, target, v, keep.has(g) ? `${num(am)} ${goodName(g)} bought per month` : null);
      }
    };
    placeGoods(goods2, 2, 'g2_', 12);
    placeGoods(goods1, 1, 'g1_', 10);

    // victuals: who packed them (column 1) and what the Victualling Yards bought (column 0)
    const vi = goodIdx.get('victuals');
    if (!province && vi != null && goods2.has(vi)) {
      const used = [...goods2.get(vi).values()].reduce((a, e) => a + e[0], 0);
      const packers = new Map();
      for (const [b, rows] of D.bOut) for (const r of rows) if (r[0] === vi && inScope(r[3])) packers.set(b, (packers.get(b) || 0) + (r[4] || 0));
      const total = [...packers.values()].reduce((a, v) => a + v, 0);
      if (total > 0) for (const [b, amount] of packers) {
        const share = amount / total, id = 'vp' + b, kind = (GI.buildings[b] || {}).id, grange = kind === 'grange';
        const idle = kind === '_idle', other = kind === '_other';
        node(id, grange ? 'Granges (from the stores)' : idle ? 'Idle peasants (base production)' : other ? 'Victuals from elsewhere (no recipe)' : bName(b), 1,
             grange ? '#a0522d' : idle ? '#9c7a3c' : other ? '#9a9a96' : '#7d8b2a');
        link(id, label['g2_' + vi] != null ? 'g2_' + vi : 'g2_rest', used * share, `${num(amount)} victuals ${idle ? 'made' : 'packed'} per month`);
        if (!grange && !idle) for (const [g, sh, am] of inputShares(D.bIn.get(b))) {
          const gid = 'g0_' + g;
          node(gid, goodName(g), 0, goodColor(g)); goodOf[gid] = g;
          link(gid, id, used * share * sh, `${num(am)} ${goodName(g)} bought per month`);
        }
      }
    }

    // the store and what empties it
    node('store', province ? 'Province food store' : 'Province food stores', 5, '#8c6d3f');
    for (const k of ['pf', 'flat', 'sub']) link(SRC[k].id, 'store', k === 'sub' ? T.sub : T[k]);
    node('cons', 'Consumption', 6, '#1baf7a');
    link('store', 'cons', T.base);
    if (!province) {
      const eat = new Map();
      for (const r of D.eat) if (inScope(r[0])) eat.set(r[1], (eat.get(r[1]) || 0) + (r[2] || 0));
      const PCOL = ['#e87ba4', '#4a3aa7', '#eda100', '#2a78d6', '#e34948', '#5fd1a2', '#7d5a5a', '#9c7a3c'];
      for (const [t, v] of [...eat.entries()].sort((a, b) => b[1] - a[1])) if (v > 0) { node('pt' + t, FI.popTypes[t].name, 7, PCOL[t % PCOL.length]); link('cons', 'pt' + t, v); }
    }
    node('spoil', 'Spoilage & overflow', 6, '#9a9a96');
    link('store', 'spoil', T.spoil);
    if (T.taken > 0) {
      node('grange', 'Granges (packing)', 6, '#a0522d');
      link('store', 'grange', T.taken);
      if (!province && vi != null) {
        const g = GI.buildings.findIndex(b => b.id === 'grange');
        const packed = (D.bOut.get(g) || []).filter(r => r[0] === vi && inScope(r[3])).reduce((a, r) => a + (r[4] || 0), 0);
        node('vict', 'Victuals', 7, goodColor(vi)); goodOf.vict = vi;
        link('grange', 'vict', T.taken, `${num(packed)} victuals packed per month`);
      }
    }
    if (T.unexplained > 0) { node('unexpl', 'Other draws (armies, unexplained)', 6, '#d8c9c6'); link('store', 'unexpl', T.unexplained); }

    // merge parallel links, drop unused nodes, close the gaps between columns
    const merged = new Map();
    for (const l of links) { const k = l.source + '|' + l.target; if (merged.has(k)) merged.get(k).value += l.value; else merged.set(k, {...l}); }
    const usedIds = new Set(); for (const l of merged.values()) { usedIds.add(l.source); usedIds.add(l.target); }
    const keep = nodes.filter(n => usedIds.has(n.name));
    const cols = [...new Set(keep.map(n => n.depth))].sort((a, b) => a - b);
    const remap = new Map(cols.map((c, i) => [c, i]));
    for (const n of keep) n.depth = remap.get(n.depth);
    const flow = id => Math.max([...merged.values()].filter(l => l.target === id).reduce((a, l) => a + l.value, 0),
                                [...merged.values()].filter(l => l.source === id).reduce((a, l) => a + l.value, 0));
    const store = Math.max(1e-9, flow('store'));
    const last = cols.length - 1;
    for (const n of keep) if (n.name !== 'store') n.label = {width: n.depth === last ? 120 : 165, overflow: 'truncate', show: flow(n.name) >= 0.004 * store};
    const per = {}; for (const n of keep) per[n.depth] = (per[n.depth] || 0) + 1;
    const height = Math.max(440, Math.max(...Object.values(per), 1) * 34 + 80);
    const option = {
      backgroundColor: 'transparent',
      tooltip: {trigger: 'item', confine: true, formatter: p => {
        if (p.dataType === 'edge') {
          const d = p.data;
          return `${esc(title[d.source])} → ${esc(title[d.target])}<br><b>${num(d.value)}</b> food / month${d.note ? '<br>' + esc(d.note) : ''}`;
        }
        let extra = '';
        if (p.name === 'store') extra = `<br>stock ${num(T.stock)} of ${num(T.cap)} · ${months(T.months)} months<br>${T.change >= 0 ? 'grows' : 'shrinks'} ${num(Math.abs(T.change))} / month after spoilage`;
        if (p.name === 'cons') extra = `<br>need (pops × food rate) ${num(T.need)}<br>Cookshops & kitchens −${num(T.cook_saving)}<br>other modifiers ${signed(T.base - T.need + T.cook_saving)}`;
        if (p.name === 'src_pf' || p.name === 'src_flat' || p.name === 'src_sub') extra = `<br>${pct(T.made > 0 ? flow(p.name) / T.made : null)} of the food made`;
        const hint = toggles[p.name] ? `<br><span style="opacity:.7">click to ${S.recipes ? 'close' : 'open'} the recipes</span>` :
          goodOf[p.name] != null ? '<br><span style="opacity:.7">click to open this good on the goods page</span>' : '';
        return `<b>${esc(title[p.name])}</b><br>${num(flow(p.name))} food / month${extra}${hint}`;
      }},
      series: [{
        type: 'sankey', left: 4, right: 130, top: 8, bottom: 8, nodeWidth: 12, nodeGap: 12, layoutIterations: 0,
        draggable: false, emphasis: {focus: 'adjacency'},
        label: {color: INK, fontSize: 11, formatter: p => p.name === 'store'
          ? `{b|${label.store}}\n${num(T.stock)} stored · ${months(T.months)} months\n${signed(T.change)} / month`
          : `${num(flow(p.name))}  ${label[p.name]}${toggles[p.name] ? (S.recipes ? '  ▾' : '  ▸') : ''}`,
          rich: {b: {fontWeight: 'bold', fontSize: 13, color: INK}}},
        lineStyle: {color: 'gradient', curveness: 0.5, opacity: dark ? 0.45 : 0.32},
        data: keep, links: [...merged.values()],
      }],
    };
    return {option, height, goodOf, toggles};
  }

  // ---------------------------------------------------------------- consumption: need -> modifiers -> eaten
  function consumptionOption(T) {
    const other = T.base - T.need + T.cook_saving;
    const afterCook = T.need - T.cook_saving;
    const steps = [
      ['Need (pops × food rate)', 0, T.need, '#9a9a96'],
      ['Cookshops & kitchens', afterCook, T.cook_saving, '#1baf7a'],
      [other >= 0 ? 'Other modifiers (more)' : 'Other modifiers (less)', other >= 0 ? afterCook : afterCook + other, Math.abs(other), other >= 0 ? '#e34948' : '#1baf7a'],
      ['Eaten', 0, T.base, '#2a78d6'],
    ];
    const labels = [num(T.need), '−' + num(T.cook_saving), signed(other), num(T.base)];
    return {
      backgroundColor: 'transparent', grid: {left: 8, right: 60, top: 8, bottom: 8, containLabel: true},
      tooltip: {trigger: 'axis', axisPointer: {type: 'shadow'}, confine: true, formatter: ps => {
        const i = ps[0].dataIndex;
        return `<b>${esc(steps[i][0])}</b><br>${labels[i]} food / month` + (i === 2 ? '<br>land (abundant, available, overpopulation), devastation, laws, advances' : '');
      }},
      xAxis: {type: 'value', axisLabel: {formatter: v => num(v)}},
      yAxis: {type: 'category', inverse: true, data: steps.map(s => s[0]), axisLabel: {color: INK}},
      series: [
        {type: 'bar', stack: 'w', itemStyle: {color: 'transparent'}, emphasis: {disabled: true}, data: steps.map(s => s[1])},
        {type: 'bar', stack: 'w', barMaxWidth: 22, data: steps.map((s, i) => ({value: s[2], itemStyle: {color: s[3]}, label: {show: true, position: 'right', color: INK, formatter: labels[i]}}))},
      ],
    };
  }

  // ---------------------------------------------------------------- tables
  function mainSource(r) {
    const parts = [['Subsistence', r[P.sub], '#9c7a3c'], ['RGO levels', r[P.rgos], '#c98a00'], ['Farms', (r[P.farms_pf] || 0) + (r[P.farms_flat] || 0), '#1baf7a'],
                   ['Cookshops', r[P.kitchens], '#e8692e'], ['Taverns', r[P.taverns], '#2a78d6'], ['Other', r[P.other], '#9a9a96']];
    return parts.reduce((a, p) => (p[1] || 0) > (a ? a[1] : 0) ? p : a, null);
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
    const th = (k, text, isNum, tip) => `<th class="sortable${isNum ? ' num' : ''}${S.sort === k ? ' sorted' + (S.asc ? ' asc' : '') : ''}" data-sort="${k}"${tip ? ` title="${esc(tip)}"` : ''}>${text}</th>`;
    let h = `<table class=gt><thead><tr>${th('province', 'Province')}<th>Owner</th>${th('people', 'People', 1)}${th('months', 'Months', 1, 'stock ÷ monthly consumption')}${th('fill', 'Store', 1, 'stock ÷ capacity')}` +
      `${th('made', 'Made', 1)}${th('eaten', 'Eaten', 1)}${th('net', 'Net', 1, 'change of the store per month (after spoilage)')}<th>Main source</th>${th('taken', 'Granges', 1, 'food the Granges take to pack victuals')}${th('factor', 'Food modifier', 1, 'fitted: actual ÷ estimate (climate, arid rows, store lever, other modifiers)')}</tr></thead><tbody>`;
    for (const {r, m} of rows) {
      const src = mainSource(r), fill = r[P.cap] > 0 ? r[P.stock] / r[P.cap] : 0;
      h += `<tr class=click data-province="${r[P.province]}"><td>${esc(FI.provinces[r[P.province]])}</td><td>${esc(FI.countries[r[P.country]] || '')}</td><td class=num>${people(r[P.pop])}</td>` +
        `<td class="num months ${mClass(m)}">${months(m)}</td><td class=num><span class=fill><i style="width:${(Math.min(1, fill) * 100).toFixed(0)}%"></i></span>${pct(fill)}</td>` +
        `<td class=num>${num(r[P.structural] + r[P.base])}</td><td class=num>${num(r[P.base])}</td><td class="num ${r[P.change] < 0 ? 'neg' : 'pos'}">${signed(r[P.change])}</td>` +
        `<td>${src ? `<i class=dot style="background:${src[2]}"></i>${esc(src[0])}` : ''}</td><td class=num>${num(r[P.taken])}</td><td class=num>${r[P.factor] == null ? '–' : r[P.factor].toFixed(2) + '×'}</td></tr>`;
    }
    h += '</tbody></table>';
    if (total > 40) h += `<button type=button class=more data-all>${S.all ? 'Show fewer' : `Show all ${total}`}</button>`;
    return h;
  }
  const chipList = list => list.slice(0, 4).map(([g, v]) => `<a href="goods.html#g=${encodeURIComponent(GI.goods[g].id)}" title="${esc(goodName(g))}" class=chip>${imgHtml(g)}${num(v)}</a>`).join(' ');
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
      for (const r of D.bIn.get(e.b) || []) if (inScope(r[3]) && !isDummy(r[0])) buys.set(r[0], (buys.get(r[0]) || 0) + (r[5] || 0));
      for (const r of D.bOut.get(e.b) || []) if (inScope(r[3]) && !isDummy(r[0])) makes.set(r[0], (makes.get(r[0]) || 0) + (r[4] || 0));
      const sorted = m => [...m.entries()].sort((a, b) => b[1] - a[1]);
      h += `<tr><td>${esc(bName(e.b))}</td><td class=num>${num(e.levels)}</td><td class=num>${num(e.count)}</td><td class=num>${num(e.workers)}</td>` +
        `<td class="num ${e.food < 0 ? 'neg' : ''}">${e.food ? signed(e.food) : '–'}</td><td class=goods>${chipList(sorted(buys))}</td><td class=goods>${chipList(sorted(makes))}</td>` +
        `<td class="num ${e.profit < 0 ? 'neg' : ''}">${num(e.profit)}</td><td class=num>${e.levels ? num(e.profit / e.levels) : '–'}</td></tr>`;
    }
    return h + '</tbody></table>';
  }

  // ---------------------------------------------------------------- over the run
  const saveTime = i => { const d = String(GI.saves[i].date || GI.saves[i].label).split('.').map(Number); return Date.UTC(d[0], (d[1] || 1) - 1, d[2] || 1); };
  function timeOption() {
    const xs = GI.saves.map((s, i) => saveTime(i));
    const marker = {silent: true, symbol: 'none', label: {show: false}, lineStyle: {type: 'dashed', color: MUTED, width: 1}, data: [{xAxis: xs[S.s]}]};
    const line = (name, values, color, extra) => ({type: 'line', name, showSymbol: xs.length <= 3, color, connectNulls: false, lineStyle: {width: 2}, emphasis: {focus: 'series'}, data: values.map((v, j) => [xs[j], v]), ...(extra || {})});
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
        {...base, series: [line('Made', e.made, '#2a78d6'), line('Eaten', e.base, '#eb6834'), line('Need (pops × food rate)', e.need, MUTED, {lineStyle: {type: 'dashed', width: 1.5}}),
                           line('Spoiled', e.spoil, '#9a9a96'), line('Taken by Granges', e.taken, '#a0522d')]},
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
    if (p.has('s')) { const s = Number(p.get('s')); if (s >= 0 && s < GI.saves.length && FI.saves[s]) S.s = s; }
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
      seen.add(r[P.province]); out.push(r);
      if (out.length >= 14) break;
    }
    $('#results').innerHTML = out.map(r => `<a href="#" data-province="${r[P.province]}">${esc(FI.provinces[r[P.province]])} <small>${esc(FI.countries[r[P.country]] || '')} · ${months(r[P.base] ? r[P.stock] / r[P.base] : null)} mo</small></a>`).join('') || '<small>No province matches.</small>';
  }
  function tiles(T) {
    const mods = T.need > 0 ? T.base / T.need - 1 : null;
    const t = [
      ['Made', num(T.made) + ' / mo', `${num(T.pf)} Province Food · ${num(T.flat)} flat · ${num(T.sub)} subsistence`],
      ['Eaten', num(T.base) + ' / mo', `need ${num(T.need)}, modifiers ${mods == null ? '–' : (mods > 0 ? '+' : '') + pct(mods)}`],
      ['Spoilage & overflow', num(T.spoil) + ' / mo', `${pct(T.stock > 0 ? T.spoil / T.stock : null)} of the stock`],
      ['Granges', num(T.taken) + ' / mo', 'food packed into victuals'],
      ['Store change', signed(T.change) + ' / mo', 'made − eaten − spoiled − Granges'],
      ['Stock', num(T.stock), `${pct(T.cap > 0 ? T.stock / T.cap : null)} of ${num(T.cap)} capacity`],
      ['Months stored', months(T.months), `${people(T.pop)} people`],
      ['Food modifier', T.factor == null ? '–' : T.factor.toFixed(2) + '×', 'fitted on the sources, people-weighted'],
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
    document.querySelectorAll('#detail button').forEach(b => { b.disabled = S.p >= 0; b.classList.toggle('on', (b.dataset.v === 'recipes') === S.recipes); });
    if (!rows.length) { $('#sankey').style.height = '120px'; chart('sankey').clear(); }
    else {
      const flow = flowOption(D, T);
      $('#sankey').style.height = flow.height + 'px';
      const sk = chart('sankey'); sk.resize(); sk.setOption(flow.option, true);
      sk.off('click');
      sk.on('click', p => {
        if (p.dataType !== 'node') return;
        if (flow.toggles[p.name]) { S.recipes = !S.recipes; render(); return; }
        if (flow.goodOf[p.name] != null) window.location.href = 'goods.html#g=' + encodeURIComponent(GI.goods[flow.goodOf[p.name]].id);
      });
      const c = chart('consumption'); c.resize(); c.setOption(consumptionOption(T), true);
    }
    $('#sankeynote').textContent = S.p >= 0 ? 'One province shows its sources without the goods behind them; open a world region for buildings, goods, recipes and victuals.' : '';
    $('#ptable').innerHTML = provinceTable(D);
    $('#pcard').hidden = S.p >= 0;
    $('#btable').innerHTML = buildingsTable(D);
    $('#bcard').hidden = S.p >= 0;
    timeButtons();
    if (S.p >= 0 && !FP) { FP = await fetch('food/provinces.json').then(r => r.json()).catch(() => ({})); if (my !== token) return; }
    const opt = FS ? timeOption() : null;
    if (opt) chart('time').setOption(opt, true); else chart('time').clear();
    if (S.s > 0 && FI.saves[S.s - 1]) loadSave(S.s - 1);
    if (S.s < GI.saves.length - 1 && FI.saves[S.s + 1]) loadSave(S.s + 1);
  }

  async function init() {
    try {
      [GI, FI] = await Promise.all(['goods/index.json', 'food/index.json'].map(u => fetch(u).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })));
    } catch (err) {
      $('#head').innerHTML = '<div class=empty>The food data did not load. This page reads files next to it, so open it from the published site or over a local web server (not as a file).</div>';
      return;
    }
    FI.poolColumns.forEach((c, i) => { P[c] = i; });
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
    document.querySelectorAll('#detail button').forEach(b => b.addEventListener('click', () => { S.recipes = b.dataset.v === 'recipes'; render(); }));
    $('#psearch').addEventListener('input', () => loadSave(S.s).then(D => D && searchResults(D)));
    $('#pfilter').addEventListener('input', e => { S.query = e.target.value; loadSave(S.s).then(D => { if (D) $('#ptable').innerHTML = provinceTable(D); }); });
    document.addEventListener('click', e => {
      const sc = e.target.closest('[data-scope]');
      if (sc) { e.preventDefault(); setScope(Number(sc.dataset.scope), -1); return; }
      const pr = e.target.closest('[data-province]');
      if (pr) { e.preventDefault(); $('#psearch').value = ''; setScope(S.r, Number(pr.dataset.province)); return; }
      const so = e.target.closest('th[data-sort]');
      if (so) { const k = so.dataset.sort; if (S.sort === k) S.asc = !S.asc; else { S.sort = k; S.asc = ['months', 'province', 'fill', 'net'].includes(k); } loadSave(S.s).then(D => { if (D) $('#ptable').innerHTML = provinceTable(D); }); return; }
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
    <label>Cookshops <span class=seg id=detail><button type=button data-v=buildings>as buildings</button><button type=button data-v=recipes>by recipe</button></span></label>
  </div>
  <section id=head></section>
  <section class=card><header><h3>Province food: where it comes from and where it goes</h3></header>
    <div class=legend2><span><b>Left:</b> what fills the stores, read right to left: the three sources the engine adds (Province Food,
    monthly food, subsistence), who makes each, what they buy, and who packs the victuals the Taverns buy.</span>
    <span><b>Right:</b> what empties them: consumption by pop type, spoilage, and the Granges with the victuals they pack.</span></div>
    <div class=scroll><div id=sankey class=chart style="height:480px"></div></div>
    <p class=note id=sankeynote></p>
    <p class=caption>Food per month. The stores' figures are exact from the save (made, eaten, spoiled, stock); the split of what was
    made between the sources is an estimate (subsistence per idle peasant, food per RGO level, the buildings' recipes and food per
    level, by staffing) fitted to each store's exact total with one factor per province, its food modifiers. Goods count as the food
    made from them (a building's food split over what it bought, by value); hover for the amounts bought. Click a Cookshop to see its
    recipes, a good to open it on the goods page.</p></section>
  <section class=card><header><h3>Consumption: need, modifiers, eaten</h3></header>
    <div id=consumption class=chart style="height:220px"></div>
    <p class=caption>Need: the pops times their food rate. Cookshops and Public Kitchens lower peasants' consumption by 1 % per staffed
    level in their location; the rest of the difference to what was eaten (exact from the save) is the other modifiers: abundant or
    available land, overpopulation, devastation, laws and advances.</p></section>
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
