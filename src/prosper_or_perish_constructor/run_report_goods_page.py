"""The goods page of the run report (`goods.html`): one good at a time, what makes it and what uses it.

Static HTML + one script; the data comes from `goods/index.json`, `goods/summary.json` and one `goods/<n>.json` per
save (written by `run_report_goods`), fetched when needed, so the page itself stays small. Layout: the goods list on
the left (grouped, searchable, price badge), save / region / detail pickers on top, then for the chosen good its
figures, a flow chart (inputs -> producers -> good -> users -> products, by value at base price; any good in it
opens that good), producer and user tables (buildings that open into their production methods, with the recipe per
level), the run over time and the split by world region. State lives in the URL hash (#g=cloth&s=12&r=...&d=method).
"""

from __future__ import annotations

import html

from prosper_or_perish_constructor.run_report import ECHARTS_URL, PAGE_CSS

GOODS_CSS = r"""
body{margin:0}
.app{display:grid;grid-template-columns:272px minmax(0,1fr);min-height:100vh}
.side{position:sticky;top:0;height:100vh;overflow:auto;border-right:1px solid var(--line);background:var(--card);padding:14px 10px 30px}
.side .back{display:block;font-size:13px;margin:0 6px 4px;text-decoration:none}
.side .run{font-size:12px;color:var(--muted);margin:0 6px 10px}
.side input{width:100%;font:inherit;font-size:13px;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink)}
.glist h4{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:16px 6px 4px;display:flex;align-items:center;gap:6px}
.glist h4 i{display:inline-block;width:10px;height:10px;border-radius:2px}
.glist a{display:flex;align-items:center;gap:8px;padding:3px 6px;border-radius:6px;color:var(--ink);text-decoration:none;font-size:13px;line-height:22px}
.glist a:hover{background:var(--chip)} .glist a.on{background:var(--accent);color:#fff} .glist a.on .badge{color:#fff}
.glist img{width:20px;height:20px} .glist .noicon{display:inline-block;width:20px}
.glist h4 .gshare{margin-left:auto;font-variant-numeric:tabular-nums;letter-spacing:0;text-transform:none}
.glist .share{margin-left:auto;font-size:11px;font-variant-numeric:tabular-nums;color:var(--ink);min-width:38px;text-align:right}
.glist .badge{font-size:11px;font-variant-numeric:tabular-nums;color:var(--muted);min-width:36px;text-align:right}
.glist a.on .share{color:#fff} .glist .legend{display:flex;gap:6px;font-size:11px;color:var(--muted);margin:8px 6px 0}
.glist .legend span:first-child{margin-left:auto;min-width:38px;text-align:right} .glist .legend span:last-child{min-width:36px;text-align:right}
.badge.hi{color:var(--neg)!important} .badge.lo{color:var(--pos)!important}
.main{padding:0 22px 48px;min-width:0}
.bar{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;position:sticky;top:0;background:var(--bg);padding:12px 0 10px;z-index:5;border-bottom:1px solid var(--line);margin-bottom:16px;font-size:13px;color:var(--muted)}
.bar select,.bar button{font:inherit;font-size:13px;padding:4px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink)}
.bar button{cursor:pointer;min-width:30px} .bar label{display:flex;align-items:center;gap:6px}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:7px;overflow:hidden}
.seg button{border:none!important;border-radius:0!important;background:transparent!important;color:var(--muted)!important}
.seg button.on{background:var(--accent)!important;color:#fff!important}
.ghead{display:flex;align-items:center;gap:14px;margin:4px 0 6px} .ghead img{width:48px;height:48px}
.ghead h1{margin:0;font-size:26px} .ghead .muted{font-size:13px}
.chipg{display:inline-flex;align-items:center;gap:5px;padding:1px 8px;border-radius:999px;background:var(--chip);font-size:12px;color:var(--ink)}
.chipg i{display:inline-block;width:8px;height:8px;border-radius:2px}
.tiles{margin-top:12px} .tile .value{font-size:20px}
.split{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,600px),1fr));gap:16px;align-items:start}
table.gt{width:100%;border-collapse:collapse;font-size:13px}
table.gt th{cursor:default} table.gt td,table.gt th{padding:5px 10px}
table.gt tr.grp{cursor:pointer} table.gt tr.grp:hover td{background:var(--chip)}
table.gt tr.grp.flat{cursor:default} table.gt tr.grp.flat:hover td{background:transparent}
table.gt tr.sub td{font-size:12px;border-bottom:1px dashed var(--line);background:color-mix(in srgb,var(--chip) 45%,transparent)}
table.gt tr.sub td:first-child{padding-left:34px}
.tog{display:inline-block;width:16px;color:var(--muted);font-size:11px}
.cat{font-size:11px;color:var(--muted);margin-left:6px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin:0 6px 0 4px}
.recipe{display:flex;flex-wrap:wrap;align-items:center;gap:2px 6px;margin-top:3px;color:var(--muted);font-size:12px}
.recipe a{display:inline-flex;align-items:center;gap:3px;color:var(--ink);text-decoration:none;padding:0 4px;border-radius:4px}
.recipe a:hover{background:var(--chip)} .recipe img{width:16px;height:16px} .recipe .arrow{color:var(--muted)}
.sbar{display:inline-block;width:46px;height:6px;border-radius:3px;background:var(--chip);margin-right:8px;vertical-align:1px;overflow:hidden}
.sbar i{display:block;height:100%;background:var(--accent);opacity:.75}
tr.more-row td{text-align:center} tr.more-row button{font:inherit;font-size:13px;background:none;border:none;color:var(--accent);cursor:pointer;padding:4px}
.empty{padding:30px;text-align:center;color:var(--muted)}
.howto{font-size:13px;color:var(--muted);padding:6px 16px 14px;max-width:110ch} .howto b{color:var(--ink)}
.loading{opacity:.55;transition:opacity .2s}
@media (max-width:900px){.app{grid-template-columns:1fr}.side{position:static;height:auto;max-height:42vh;border-right:none;border-bottom:1px solid var(--line)}.main{padding:0 12px 40px}}
"""

GOODS_JS = r"""
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
  const rnum = v => (v == null || !isFinite(v)) ? '–' : Math.abs(v) >= 100 ? num(v) : String(Number(v.toPrecision(3)));
  const pct = f => (f == null || !isFinite(f)) ? '–' : (f * 100).toFixed(Math.abs(f) < 0.1 ? 1 : 0) + '%';
  const ratio = v => (v == null || !isFinite(v)) ? '–' : v.toFixed(2) + '×';

  let IX = null, SUM = null;
  const SAVES = new Map();
  const S = {g: 0, s: 0, r: -1, d: 'building', tv: 0};
  let goodIndex = new Map(), regionIndex = new Map(), TRADE = new Set(), charts = {};

  const goodName = i => (IX.goods[i] || {}).name || '?';
  const goodIcon = i => (IX.goods[i] || {}).icon;
  const goodPrice = i => (IX.goods[i] || {}).price || 1;
  const groupOf = i => IX.groups.find(g => g.key === (IX.goods[i] || {}).group) || {color: '#9a9a96', label: ''};
  const bName = i => (IX.buildings[i] || {}).name || '?';
  const mName = i => (IX.methods[i] || {}).name || '?';
  const imgHtml = (i, cls) => goodIcon(i) ? `<img${cls ? ` class=${cls}` : ''} src="${esc(goodIcon(i))}" alt="">` : '';
  const recipeGood = id => goodIndex.has(id) ? goodIndex.get(id) : null;

  // ---------------------------------------------------------------- data
  function prepare(raw) {
    const n = IX.goods.length;
    const by = Array.from({length: n}, () => ({p: [], c: [], d: [], s: [], m: []}));
    for (const k of ['p', 'c', 'd', 's', 'm']) for (const r of raw[k] || []) if (by[r[0]]) by[r[0]][k].push(r);
    const mIn = new Map(), mOut = new Map();
    for (const r of raw.c || []) if (r[2] >= 0) { if (!mIn.has(r[2])) mIn.set(r[2], []); mIn.get(r[2]).push(r); }
    for (const r of raw.p || []) if (r[2] >= 0) { if (!mOut.has(r[2])) mOut.set(r[2], []); mOut.get(r[2]).push(r); }
    const price = new Array(n).fill(null);
    for (let g = 0; g < n; g++) {
      let pv = 0, vol = 0;
      for (const r of by[g].m) { pv += r[2] || 0; vol += r[3] || 0; }
      if (vol > 0) price[g] = pv / vol / goodPrice(g);
    }
    return {by, mIn, mOut, price};
  }
  function loadSave(i) {
    if (!SAVES.has(i)) SAVES.set(i, fetch(IX.saves[i].file).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(prepare));
    return SAVES.get(i);
  }
  const inRegion = reg => S.r < 0 || reg === S.r;

  // what the chosen good's producers and users did in the chosen region
  function compute(D, g) {
    const rows = D.by[g];
    const prod = new Map(), cons = new Map();
    const add = (map, b, m, f) => {
      if (!map.has(b)) map.set(b, {b, t: {}, methods: new Map()});
      const e = map.get(b);
      f(e.t);
      const mk = m >= 0 ? m : -1;
      if (!e.methods.has(mk)) e.methods.set(mk, {m: mk, t: {}});
      f(e.methods.get(mk).t);
    };
    const inc = (t, k, v) => { t[k] = (t[k] || 0) + (v || 0); };
    for (const r of rows.p) if (inRegion(r[3])) add(prod, r[1], r[2], t => { inc(t, 'amount', r[4]); inc(t, 'levels', r[5]); inc(t, 'count', r[6]); inc(t, 'workers', r[7]); inc(t, 'recipe', r[8]); });
    for (const r of rows.c) if (inRegion(r[3])) add(cons, r[1], r[2], t => { inc(t, 'wanted', r[4]); inc(t, 'received', r[5]); inc(t, 'recipe', r[6]); });
    const dem = IX.demand.map(() => ({wanted: 0, received: 0})), sup = IX.supply.map(() => 0);
    for (const r of rows.d) if (inRegion(r[2])) { dem[r[1]].wanted += r[3] || 0; dem[r[1]].received += r[4] || 0; }
    for (const r of rows.s) if (inRegion(r[2])) sup[r[1]] += r[3] || 0;
    const mk = {pv: 0, vol: 0, supply: 0, demand: 0, stock: 0, short: 0, surplus: 0, markets: 0};
    for (const r of rows.m) if (inRegion(r[1])) {
      mk.pv += r[2] || 0; mk.vol += r[3] || 0; mk.supply += r[4] || 0; mk.demand += r[5] || 0; mk.stock += r[6] || 0;
      mk.short += r[7] || 0; mk.surplus += r[8] || 0; mk.markets += r[9] || 0;
    }
    const sorted = (map, key) => [...map.values()].sort((a, b) => (b.t[key] || 0) - (a.t[key] || 0));
    const producers = sorted(prod, 'amount'), consumers = sorted(cons, 'received');
    const made = producers.reduce((a, e) => a + (e.t.amount || 0), 0);
    const usedB = consumers.reduce((a, e) => a + (e.t.received || 0), 0);
    let usedD = 0, wanted = consumers.reduce((a, e) => a + (e.t.wanted || 0), 0);
    IX.demand.forEach((d, i) => { if (!TRADE.has(d.id)) { usedD += dem[i].received; wanted += dem[i].wanted; } });
    const tradeIn = IX.supply.reduce((a, s, i) => a + sup[i], 0);
    const tradeOut = IX.demand.reduce((a, d, i) => a + (TRADE.has(d.id) ? dem[i].received : 0), 0);
    const recipeMade = producers.filter(e => IX.buildings[e.b].id !== 'rgo' && IX.buildings[e.b].id !== '_other').reduce((a, e) => [a[0] + (e.t.amount || 0), a[1] + (e.t.recipe || 0)], [0, 0]);
    return {g, producers, consumers, dem, sup, mk, made, used: usedB + usedD, usedB, usedD, wanted, tradeIn, tradeOut,
            efficiency: recipeMade[1] > 0 ? recipeMade[0] / recipeMade[1] : null};
  }

  // ---------------------------------------------------------------- flow chart
  const COL = {producer: '#2a78d6', rgo: '#c98a00', other: '#9a9a96', consumer: '#eb6834', trade: '#5fb8c4', stock: '#8c8c88'};
  function flowOption(D, X) {
    const g = X.g, pg = goodPrice(g);
    const nodes = [], links = [], label = {}, title = {}, goodOf = {}, amounts = {};
    const node = (id, text, depth, color, full) => {
      if (label[id] != null) return;
      label[id] = text; title[id] = full || text;
      nodes.push({name: id, depth, itemStyle: {color}});
    };
    const link = (source, target, value, amt, good) => { if (value > 1e-9) links.push({source, target, value, amt, good}); };
    const byMethod = S.d === 'method';
    // producer nodes
    let pnodes = [];
    for (const e of X.producers) {
      const bid = IX.buildings[e.b].id, kind = bid === 'rgo' ? 'rgo' : bid === '_other' ? 'other' : 'producer';
      if (byMethod && kind === 'producer') for (const me of e.methods.values()) pnodes.push({id: 'pm' + me.m, text: mName(me.m), full: `${mName(me.m)} (${bName(e.b)})`, methods: [me.m], amount: me.t.amount || 0, color: COL.producer});
      else pnodes.push({id: 'pb' + e.b, text: bName(e.b), methods: [...e.methods.keys()].filter(m => m >= 0), amount: e.t.amount || 0, color: COL[kind]});
    }
    pnodes.sort((a, b) => b.amount - a.amount);
    const PMAX = 12;
    if (pnodes.length > PMAX + 1) {
      const rest = pnodes.splice(PMAX);
      pnodes.push({id: 'p_rest', text: `Other producers (${rest.length})`, methods: rest.flatMap(r => r.methods), amount: rest.reduce((a, r) => a + r.amount, 0), color: COL.other});
    }
    // user nodes: buildings, then demand types
    let cnodes = [];
    for (const e of X.consumers) {
      const bid = IX.buildings[e.b].id;
      if (byMethod && bid !== '_other') for (const me of e.methods.values()) cnodes.push({id: 'cm' + me.m, text: mName(me.m), full: `${mName(me.m)} (${bName(e.b)})`, methods: [me.m], amount: me.t.received || 0, color: COL.consumer});
      else cnodes.push({id: 'cb' + e.b, text: bid === '_other' ? 'Buildings without a recipe' : bName(e.b), methods: [...e.methods.keys()].filter(m => m >= 0), amount: e.t.received || 0, color: bid === '_other' ? COL.other : COL.consumer});
    }
    cnodes.sort((a, b) => b.amount - a.amount);
    const CMAX = 16;
    if (cnodes.length > CMAX + 1) {
      const rest = cnodes.splice(CMAX);
      cnodes.push({id: 'c_rest', text: `Other buildings (${rest.length})`, methods: rest.flatMap(r => r.methods), amount: rest.reduce((a, r) => a + r.amount, 0), color: COL.other});
    }
    const dnodes = [];
    IX.demand.forEach((d, i) => { if (!TRADE.has(d.id) && X.dem[i].received > 0) dnodes.push({id: 'd' + i, text: d.name, amount: X.dem[i].received, color: d.color}); });
    dnodes.sort((a, b) => b.amount - a.amount);
    // trade (a region only: net of in and out) and stock
    const extraIn = [], extraOut = [];
    if (S.r >= 0) {
      const net = X.tradeIn - X.tradeOut;
      if (net > 0) extraIn.push({id: 'x_in', text: 'Imports (net)', amount: net, color: COL.trade});
      else if (net < 0) extraOut.push({id: 'x_out', text: 'Exports (net)', amount: -net, color: COL.trade});
    }
    const inflow = X.made + extraIn.reduce((a, e) => a + e.amount, 0);
    const outflow = X.used + extraOut.reduce((a, e) => a + e.amount, 0);
    const diff = inflow - outflow;
    if (diff > 0.005 * Math.max(inflow, 1e-9)) extraOut.push({id: 'x_stock', text: 'Not taken (stock, unsold)', amount: diff, color: COL.stock});
    else if (diff < -0.005 * Math.max(outflow, 1e-9)) extraIn.push({id: 'x_from', text: 'From stock and trade', amount: -diff, color: COL.stock});

    // upstream: inputs of the producers' methods, the share that went into this good
    const ups = new Map();  // good -> Map(pnode -> value)
    for (const pn of pnodes) {
      for (const m of pn.methods) {
        const outs = (D.mOut.get(m) || []).filter(r => inRegion(r[3]));
        let total = 0, mine = 0;
        for (const r of outs) { const v = (r[4] || 0) * goodPrice(r[0]); total += v; if (r[0] === g) mine += v; }
        const share = total > 0 ? mine / total : 0;
        if (share <= 0) continue;
        for (const r of (D.mIn.get(m) || [])) {
          if (!inRegion(r[3]) || r[0] === g) continue;
          const v = (r[5] || 0) * goodPrice(r[0]) * share;
          if (!ups.has(r[0])) ups.set(r[0], new Map());
          const t = ups.get(r[0]); t.set(pn.id, (t.get(pn.id) || 0) + v);
          amounts['in' + r[0] + '>' + pn.id] = (amounts['in' + r[0] + '>' + pn.id] || 0) + (r[5] || 0) * share;
        }
      }
    }
    // downstream: what the users made, the share of it that came from this good
    const downs = new Map();
    for (const cn of cnodes) {
      for (const m of cn.methods || []) {
        const ins = (D.mIn.get(m) || []).filter(r => inRegion(r[3]));
        let total = 0, mine = 0;
        for (const r of ins) { const v = (r[5] || 0) * goodPrice(r[0]); total += v; if (r[0] === g) mine += v; }
        const share = total > 0 ? mine / total : 0;
        if (share <= 0) continue;
        for (const r of (D.mOut.get(m) || [])) {
          if (!inRegion(r[3]) || r[0] === g) continue;
          const v = (r[4] || 0) * goodPrice(r[0]) * share;
          if (!downs.has(r[0])) downs.set(r[0], new Map());
          const t = downs.get(r[0]); t.set(cn.id, (t.get(cn.id) || 0) + v);
          amounts[cn.id + '>out' + r[0]] = (amounts[cn.id + '>out' + r[0]] || 0) + (r[4] || 0) * share;
        }
      }
    }
    const topGoods = (map, n) => {
      const totals = [...map.entries()].map(([k, t]) => [k, [...t.values()].reduce((a, v) => a + v, 0)]).sort((a, b) => b[1] - a[1]);
      return [totals.slice(0, n).map(e => e[0]), totals.slice(n).map(e => e[0])];
    };
    const [upTop, upRest] = topGoods(ups, 8), [downTop, downRest] = topGoods(downs, 8);
    const wide = upTop.length + downTop.length > 0;
    const dIn = upTop.length ? 0 : -1, dP = dIn + 1, dG = dP + 1, dC = dG + 1, dOut = dC + 1;

    for (const k of upTop) { node('in' + k, goodName(k), dIn, groupOf(k).color); goodOf['in' + k] = k; }
    if (upRest.length) node('in_rest', `Other inputs (${upRest.length})`, dIn, COL.other);
    for (const e of extraIn) node(e.id, e.text, dP, e.color);
    for (const pn of pnodes) node(pn.id, pn.text, dP, pn.color, pn.full);
    node('g', goodName(g), dG, groupOf(g).color); goodOf.g = g;
    for (const cn of cnodes) node(cn.id, cn.text, dC, cn.color, cn.full);
    for (const dn of dnodes) node(dn.id, dn.text, dC, dn.color);
    for (const e of extraOut) node(e.id, e.text, dC, e.color);
    for (const k of downTop) { node('out' + k, goodName(k), dOut, groupOf(k).color); goodOf['out' + k] = k; }
    if (downRest.length) node('out_rest', `Other products (${downRest.length})`, dOut, COL.other);

    for (const [k, t] of ups) for (const [pid, v] of t) link(upTop.includes(k) ? 'in' + k : 'in_rest', pid, v, upTop.includes(k) ? amounts['in' + k + '>' + pid] : null, upTop.includes(k) ? k : null);
    for (const e of extraIn) link(e.id, 'g', e.amount * pg, e.amount, g);
    for (const pn of pnodes) link(pn.id, 'g', pn.amount * pg, pn.amount, g);
    for (const cn of cnodes) link('g', cn.id, cn.amount * pg, cn.amount, g);
    for (const dn of dnodes) link('g', dn.id, dn.amount * pg, dn.amount, g);
    for (const e of extraOut) link('g', e.id, e.amount * pg, e.amount, g);
    for (const [k, t] of downs) for (const [cid, v] of t) link(cid, downTop.includes(k) ? 'out' + k : 'out_rest', v, downTop.includes(k) ? amounts[cid + '>out' + k] : null, downTop.includes(k) ? k : null);

    // merge parallel links (Other inputs / products)
    const merged = new Map();
    for (const l of links) {
      const key = l.source + '|' + l.target;
      if (!merged.has(key)) merged.set(key, {...l}); else { const m = merged.get(key); m.value += l.value; m.amt = (m.amt || 0) + (l.amt || 0); }
    }
    const used = new Set(); for (const l of merged.values()) { used.add(l.source); used.add(l.target); }
    const keep = nodes.filter(nd => used.has(nd.name));
    // labels: truncated to the room their column has (the full name is in the tooltip)
    const lastDepth = Math.max(...keep.map(nd => nd.depth));
    const centre = Math.max(1e-9, ...['g'].map(id => [...links].filter(l => l.target === id).reduce((a, l) => a + l.value, 0)));
    const nodeValue = id => Math.max([...links].filter(l => l.target === id).reduce((a, l) => a + l.value, 0), [...links].filter(l => l.source === id).reduce((a, l) => a + l.value, 0));
    for (const nd of keep) if (nd.name !== 'g') nd.label = {width: nd.depth === lastDepth ? 130 : 190, overflow: 'truncate', show: nodeValue(nd.name) >= 0.006 * centre};
    const perColumn = {}; for (const nd of keep) perColumn[nd.depth] = (perColumn[nd.depth] || 0) + 1;
    const height = Math.max(400, Math.max(...Object.values(perColumn), 1) * 38 + 60);
    const totalIn = (id) => [...merged.values()].filter(l => l.target === id).reduce((a, l) => a + l.value, 0);
    const totalOut = (id) => [...merged.values()].filter(l => l.source === id).reduce((a, l) => a + l.value, 0);
    const option = {
      backgroundColor: 'transparent',
      tooltip: {trigger: 'item', confine: true, formatter: p => {
        if (p.dataType === 'edge') {
          const d = p.data;
          const what = d.good != null ? `${num(d.amt)} ${esc(goodName(d.good))} · ` : '';
          return `${esc(title[d.source])} → ${esc(title[d.target])}<br>${what}<b>${num(d.value)}</b> gold / month at base price`;
        }
        const v = Math.max(totalIn(p.name), totalOut(p.name));
        const hint = goodOf[p.name] != null && p.name !== 'g' ? '<br><span style="opacity:.7">click to open this good</span>' : '';
        return `<b>${esc(title[p.name])}</b><br>${num(v)} gold / month at base price${hint}`;
      }},
      series: [{
        type: 'sankey', left: 4, right: wide ? 150 : 210, top: 8, bottom: 8, nodeWidth: 12, nodeGap: 14, layoutIterations: 0,
        draggable: false, emphasis: {focus: 'adjacency'},
        label: {color: INK, fontSize: 11, formatter: p => p.name === 'g'
          ? `{b|${label.g}}\n${num(X.made)} / mo · ${num(Math.max(totalIn('g'), totalOut('g')))} gold`
          : `${num(Math.max(totalIn(p.name), totalOut(p.name)))}  ${label[p.name]}`,
          rich: {b: {fontWeight: 'bold', fontSize: 13, color: INK}}},
        lineStyle: {color: 'gradient', curveness: 0.5, opacity: dark ? 0.45 : 0.32},
        data: keep, links: [...merged.values()],
      }],
    };
    return {option, height, goodOf};
  }

  // ---------------------------------------------------------------- tables
  function recipeHtml(m) {
    const me = IX.methods[m];
    if (!me) return '';
    const chip = ([id, amt]) => {
      const gi = recipeGood(id);
      const name = gi != null ? goodName(gi) : id.replace(/_/g, ' ');
      const body = `${gi != null ? imgHtml(gi) : ''}${rnum(amt)}${gi != null && goodIcon(gi) ? '' : ' ' + esc(name)}`;
      return gi != null ? `<a href="#" data-good="${gi}" title="${esc(name)}">${body}</a>` : `<span title="${esc(name)}">${body}</span>`;
    };
    const ins = (me.in || []).map(chip).join('<span class=arrow>+</span>');
    const outs = (me.out || []).map(chip).join('<span class=arrow>+</span>');
    return `<div class=recipe>${ins || '<span>no inputs</span>'}<span class=arrow>→</span>${outs || '<span>no output</span>'}<span>per level</span></div>`;
  }
  const sbar = f => `<span class=sbar><i style="width:${Math.max(0, Math.min(100, (f || 0) * 100)).toFixed(1)}%"></i></span>`;
  const LIMIT = 25;
  // rows past the first LIMIT groups are hidden behind a "Show all" row
  function capped(groups, columns) {
    if (groups.length <= LIMIT) return groups.join('');
    const hidden = groups.slice(LIMIT).map(g => g.replace(/<tr class="grp/g, '<tr data-extra hidden class="grp')).join('');
    return groups.slice(0, LIMIT).join('') + hidden + `<tr class=more-row><td colspan=${columns}><button type=button data-more>Show all ${groups.length}</button></td></tr>`;
  }
  function producersTable(X) {
    const total = X.made || 1, pg = goodPrice(X.g);
    if (!X.producers.length) return '<div class=empty>Nothing makes this good here in this save.</div>';
    const groups = [];
    let h = `<table class=gt><thead><tr><th>Producer</th><th class=num>Per month</th><th class=num>Value</th><th class=num>Share</th><th class=num title="Building levels running these methods">Levels</th><th class=num>Buildings</th><th class=num title="Workers, thousands">Workers</th><th class=num title="What they made ÷ their recipe (output per level × levels × staffing): production efficiency, output modifiers, throughput, input shortages and market access, roughly">Output ÷ recipe</th></tr></thead><tbody>`;
    X.producers.forEach((e, k) => {
      let h = '';
      const bid = IX.buildings[e.b].id, rgo = bid === 'rgo', other = bid === '_other';
      const t = e.t, methods = [...e.methods.values()].filter(me => me.m >= 0).sort((a, b) => (b.t.amount || 0) - (a.t.amount || 0));
      const flat = !methods.length;
      const cat = IX.buildings[e.b].cat ? `<span class=cat>${esc(IX.buildings[e.b].cat.replace(/_/g, ' '))}</span>` : '';
      h += `<tr class="grp${flat ? ' flat' : ''}" data-k="p${k}"><td><span class=tog>${flat ? '' : '▸'}</span>${esc(bName(e.b))}${rgo ? `<span class=cat>raw material, ${esc(goodName(X.g))}</span>` : cat}</td>` +
        `<td class=num>${num(t.amount)}</td><td class=num>${num((t.amount || 0) * pg)}</td><td class=num>${sbar((t.amount || 0) / total)}${pct((t.amount || 0) / total)}</td>` +
        `<td class=num>${rgo || other ? '–' : num(t.levels)}</td><td class=num>${other ? '–' : num(t.count)}${rgo ? '<span class=cat>locations</span>' : ''}</td><td class=num>${other ? '–' : num(t.workers)}</td>` +
        `<td class=num title="${rgo ? 'per 1,000 RGO workers' : ''}">${other ? '–' : ratio(t.recipe > 0 ? t.amount / t.recipe : null)}</td></tr>`;
      for (const me of methods) {
        const mt = me.t;
        h += `<tr class=sub data-p="p${k}" hidden><td>${esc(mName(me.m))}${recipeHtml(me.m)}</td><td class=num>${num(mt.amount)}</td><td class=num>${num((mt.amount || 0) * pg)}</td><td class=num>${pct((mt.amount || 0) / total)}</td>` +
          `<td class=num>${num(mt.levels)}</td><td class=num>${num(mt.count)}</td><td class=num>${num(mt.workers)}</td><td class=num>${ratio(mt.recipe > 0 ? mt.amount / mt.recipe : null)}</td></tr>`;
      }
      groups.push(h);
    });
    return h + capped(groups, 8) + '</tbody></table>';
  }
  function consumersTable(X) {
    const pg = goodPrice(X.g);
    const rows = [];
    X.consumers.forEach((e, k) => rows.push({kind: 'b', e, k, received: e.t.received || 0, wanted: e.t.wanted || 0}));
    IX.demand.forEach((d, i) => { if (!TRADE.has(d.id) && (X.dem[i].received > 0 || X.dem[i].wanted > 0)) rows.push({kind: 'd', d, received: X.dem[i].received, wanted: X.dem[i].wanted}); });
    if (S.r >= 0) {
      const ex = IX.demand.reduce((a, d, i) => a + (TRADE.has(d.id) ? X.dem[i].received : 0), 0);
      const exW = IX.demand.reduce((a, d, i) => a + (TRADE.has(d.id) ? X.dem[i].wanted : 0), 0);
      if (ex > 0) rows.push({kind: 'x', received: ex, wanted: exW});
    }
    rows.sort((a, b) => b.received - a.received);
    const total = rows.reduce((a, r) => a + r.received, 0) || 1;
    if (!rows.length) return '<div class=empty>Nothing uses this good here in this save.</div>';
    const groups = [];
    let h = `<table class=gt><thead><tr><th>User</th><th class=num>Received / month</th><th class=num>Value</th><th class=num>Share</th><th class=num title="What they wanted">Wanted</th><th class=num title="Received ÷ wanted">Got</th></tr></thead><tbody>`;
    for (const r of rows) {
      let h = '';
      const cells = `<td class=num>${num(r.received)}</td><td class=num>${num(r.received * pg)}</td><td class=num>${sbar(r.received / total)}${pct(r.received / total)}</td><td class=num>${num(r.wanted)}</td><td class=num>${pct(r.wanted > 0 ? r.received / r.wanted : null)}</td>`;
      if (r.kind === 'd') { groups.push(`<tr class="grp flat"><td><span class=tog></span><i class=dot style="background:${r.d.color}"></i>${esc(r.d.name)}</td>${cells}</tr>`); continue; }
      if (r.kind === 'x') { groups.push(`<tr class="grp flat"><td><span class=tog></span><i class=dot style="background:#5fb8c4"></i>Exports and burgher trade out</td>${cells}</tr>`); continue; }
      const e = r.e, bid = IX.buildings[e.b].id;
      const methods = [...e.methods.values()].filter(me => me.m >= 0).sort((a, b) => (b.t.received || 0) - (a.t.received || 0));
      const flat = !methods.length;
      const cat = IX.buildings[e.b].cat ? `<span class=cat>${esc(IX.buildings[e.b].cat.replace(/_/g, ' '))}</span>` : '';
      h += `<tr class="grp${flat ? ' flat' : ''}" data-k="c${r.k}"><td><span class=tog>${flat ? '' : '▸'}</span>${bid === '_other' ? 'Buildings without a recipe' : esc(bName(e.b))}${cat}</td>${cells}</tr>`;
      for (const me of methods) {
        const mt = me.t;
        h += `<tr class=sub data-p="c${r.k}" hidden><td>${esc(mName(me.m))}${recipeHtml(me.m)}</td><td class=num>${num(mt.received)}</td><td class=num>${num((mt.received || 0) * pg)}</td><td class=num>${pct((mt.received || 0) / total)}</td><td class=num>${num(mt.wanted)}</td><td class=num>${pct(mt.wanted > 0 ? mt.received / mt.wanted : null)}</td></tr>`;
      }
      groups.push(h);
    }
    return h + capped(groups, 6) + '</tbody></table>';
  }

  // ---------------------------------------------------------------- over the run, by region
  const saveTime = i => { const d = String(IX.saves[i].date || IX.saves[i].label).split('.').map(Number); return Date.UTC(d[0], (d[1] || 1) - 1, d[2] || 1); };
  const PALETTE = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948', '#9a9a96'];
  function timeOption(g) {
    const e = SUM && SUM[IX.goods[g].id];
    if (!e) return null;
    const xs = IX.saves.map((s, i) => saveTime(i));
    const marker = {silent: true, symbol: 'none', label: {show: false}, lineStyle: {type: 'dashed', color: MUTED, width: 1}, data: [{xAxis: xs[S.s]}]};
    const seriesOf = (obj, nameOf) => Object.keys(obj).map((k, i) => ({
      type: 'line', name: nameOf(k), stack: 'total', areaStyle: {opacity: 0.85}, lineStyle: {width: 0.6}, showSymbol: false, emphasis: {focus: 'series'},
      color: k === '_rest' ? '#9a9a96' : PALETTE[i % PALETTE.length], data: obj[k].map((v, j) => [xs[j], v])}));
    const keyName = k => k === '_rest' ? 'Other' : k.startsWith('@') ? ((IX.demand.find(d => d.id === k.slice(1)) || {}).name || k.slice(1)) :
      (IX.buildings.find(b => b.id === k) || {}).name || k;
    const base = {
      backgroundColor: 'transparent', tooltip: {trigger: 'axis', confine: true, valueFormatter: v => num(v)},
      legend: {type: 'scroll', top: 0, left: 0, right: 0, textStyle: {color: INK}},
      grid: {left: 8, right: 16, top: 40, bottom: 30, containLabel: true},
      xAxis: {type: 'time', min: xs[0], max: xs[xs.length - 1], axisLabel: {formatter: v => String(new Date(v).getUTCFullYear()), hideOverlap: true}},
    };
    const views = [
      {...base, yAxis: {type: 'value', axisLabel: {formatter: v => num(v)}}, series: seriesOf(e.made_by || {}, keyName)},
      {...base, yAxis: {type: 'value', axisLabel: {formatter: v => num(v)}}, series: seriesOf(e.used_by || {}, keyName)},
      {...base, yAxis: [{type: 'value', axisLabel: {formatter: v => num(v)}}, {type: 'value', name: 'price ÷ base', axisLabel: {formatter: v => v.toFixed(1) + '×'}, splitLine: {show: false}}],
       series: [
         {type: 'line', name: 'Made', showSymbol: false, color: '#2a78d6', lineStyle: {width: 2.5}, data: e.made.map((v, j) => [xs[j], v])},
         {type: 'line', name: 'Used', showSymbol: false, color: '#eb6834', lineStyle: {width: 2.5}, data: e.used.map((v, j) => [xs[j], v])},
         {type: 'line', name: 'Price ÷ base', yAxisIndex: 1, showSymbol: false, color: INK, lineStyle: {width: 1.5, type: 'dashed'},
          data: e.price.map((v, j) => [xs[j], v == null ? null : v / goodPrice(g)])}]},
    ];
    const option = views[S.tv];
    option.series.forEach((s, i) => { if (i === 0) s.markLine = marker; });
    return option;
  }
  function regionOption(D, g) {
    const rows = D.by[g], pg = goodPrice(g);
    const made = new Map(), used = new Map();
    const add = (map, r, v) => map.set(r, (map.get(r) || 0) + v);
    for (const r of rows.p) add(made, r[3], (r[4] || 0) * pg);
    for (const r of rows.c) add(used, r[3], (r[5] || 0) * pg);
    for (const r of rows.d) if (!TRADE.has(IX.demand[r[1]].id)) add(used, r[2], (r[4] || 0) * pg);
    const regions = IX.regions.map((x, i) => i).filter(i => (made.get(i) || 0) + (used.get(i) || 0) > 0)
      .sort((a, b) => (made.get(b) || 0) + (used.get(b) || 0) - (made.get(a) || 0) - (used.get(a) || 0));
    const names = regions.map(i => IX.regions[i].name);
    const chosen = S.r >= 0 ? IX.regions[S.r].name : null;
    return {
      height: Math.max(260, regions.length * 26 + 70), regions,
      option: {
        backgroundColor: 'transparent', tooltip: {trigger: 'axis', axisPointer: {type: 'shadow'}, confine: true, valueFormatter: v => num(v) + ' gold'},
        legend: {top: 0, left: 0, textStyle: {color: INK}}, grid: {left: 8, right: 24, top: 32, bottom: 8, containLabel: true},
        xAxis: {type: 'value', axisLabel: {formatter: v => num(v)}},
        yAxis: {type: 'category', data: names, inverse: true, axisLabel: {color: INK, formatter: v => v === chosen ? `{on|▶ ${v}}` : v, rich: {on: {fontWeight: 'bold', color: '#2a78d6'}}}},
        series: [
          {type: 'bar', name: 'Made (gold / month)', color: '#2a78d6', data: regions.map(i => made.get(i) || 0), barMaxWidth: 12},
          {type: 'bar', name: 'Used (gold / month)', color: '#eb6834', data: regions.map(i => used.get(i) || 0), barMaxWidth: 12}],
      }};
  }

  // ---------------------------------------------------------------- page
  function chart(id) {
    if (!charts[id]) {
      const el = document.getElementById(id);
      charts[id] = echarts.init(el, dark ? 'dark' : null);
      new ResizeObserver(() => charts[id].resize()).observe(el);
    }
    return charts[id];
  }
  function writeHash() {
    const r = S.r >= 0 ? IX.regions[S.r].id : 'world';
    const h = `#g=${encodeURIComponent(IX.goods[S.g].id)}&s=${S.s}&r=${encodeURIComponent(r)}&d=${S.d}`;
    if (location.hash !== h) history.replaceState(null, '', h);
  }
  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    if (p.has('g') && goodIndex.has(p.get('g'))) S.g = goodIndex.get(p.get('g'));
    if (p.has('s')) { const s = Number(p.get('s')); if (s >= 0 && s < IX.saves.length) S.s = s; }
    if (p.has('r')) S.r = regionIndex.has(p.get('r')) ? regionIndex.get(p.get('r')) : -1;
    if (p.get('d') === 'method' || p.get('d') === 'building') S.d = p.get('d');
  }
  function select(g, push = true) {
    if (g == null || !IX.goods[g]) return;
    S.g = g;
    if (push) history.pushState(null, '', location.hash);
    render();
    window.scrollTo({top: 0});
    const el = document.querySelector(`.glist a[data-i="${g}"]`);
    const side = document.querySelector('.side');
    if (el && side) {
      const top = el.offsetTop - side.offsetTop, view = side.scrollTop;
      if (top < view + 60 || top > view + side.clientHeight - 60) side.scrollTop = top - side.clientHeight / 2;
    }
  }
  // each good's share of all output (production value at base price) and its price ÷ base, in the chosen region
  function outputShares(D) {
    const n = IX.goods.length, made = new Array(n).fill(0), price = new Array(n).fill(null);
    let total = 0;
    for (let g = 0; g < n; g++) {
      const pg = goodPrice(g);
      for (const r of D.by[g].p) if (inRegion(r[3])) made[g] += (r[4] || 0) * pg;
      total += made[g];
      let pv = 0, vol = 0;
      for (const r of D.by[g].m) if (inRegion(r[1])) { pv += r[2] || 0; vol += r[3] || 0; }
      if (vol > 0) price[g] = pv / vol / pg;
    }
    return {share: made.map(v => total > 0 ? v / total : 0), price, total};
  }
  const shareText = f => f >= 0.0995 ? (f * 100).toFixed(0) + '%' : f >= 0.00095 ? (f * 100).toFixed(1) + '%' : f > 0 ? '<0.1%' : '–';
  function buildList(D) {
    const q = $('#search').value.trim().toLowerCase();
    const where = S.r >= 0 ? IX.regions[S.r].name : 'the world';
    const O = D ? outputShares(D) : null;
    let h = `<div class=legend title="Share: the good's production value at base price ÷ the value of everything produced in ${esc(where)}. Price: price ÷ base price."><span>share</span><span>price</span></div>`;
    for (const grp of IX.groups) {
      let items = IX.goodOrder.filter(i => IX.goods[i].group === grp.key && (!q || IX.goods[i].name.toLowerCase().includes(q)));
      if (!items.length) continue;
      if (O) items = items.slice().sort((a, b) => O.share[b] - O.share[a] || goodName(a).localeCompare(goodName(b)));
      const gshare = O ? IX.goodOrder.filter(i => IX.goods[i].group === grp.key).reduce((a, i) => a + O.share[i], 0) : null;
      h += `<h4><i style="background:${grp.color}"></i>${esc(grp.label)}<span class=gshare title="share of all output in ${esc(where)}">${gshare == null ? '' : shareText(gshare)}</span></h4>`;
      for (const i of items) {
        const pr = O ? O.price[i] : null, sh = O ? O.share[i] : null;
        const cls = pr == null ? '' : pr > 1.25 ? ' hi' : pr < 0.8 ? ' lo' : '';
        h += `<a href="#" data-i="${i}" class="${i === S.g ? 'on' : ''}" title="${esc(goodName(i))}: ${sh == null ? '' : shareText(sh) + ' of all output in ' + esc(where) + ', '}price ${pr == null ? '–' : pr.toFixed(2) + '× base'}">` +
          `${imgHtml(i) || '<span class=noicon></span>'}<span>${esc(IX.goods[i].name)}</span><span class=share>${sh == null ? '' : shareText(sh)}</span><span class="badge${cls}">${pr == null ? '' : pr.toFixed(2) + '×'}</span></a>`;
      }
    }
    $('#goodlist').innerHTML = h || '<div class=empty>No good matches.</div>';
  }
  function tiles(X, D) {
    const pg = goodPrice(X.g);
    const O = outputShares(D);
    const priceRatio = X.mk.vol > 0 ? X.mk.pv / X.mk.vol / pg : null;
    const unmet = X.wanted > 0 ? 1 - X.used / X.wanted : null;
    const t = [
      ['Made', num(X.made) + ' / mo', num(X.made * pg) + ' gold at base price'],
      ['Share of output', shareText(O.share[X.g]), `of everything made in ${S.r >= 0 ? IX.regions[S.r].name : 'the world'} (${num(O.total)} gold / mo)`],
      ['Used', num(X.used) + ' / mo', `${num(X.usedB)} by buildings · ${num(X.usedD)} other`],
      ['Unmet demand', pct(unmet), `${num(Math.max(0, X.wanted - X.used))} / mo wanted but not received`],
      ['Price ÷ base', ratio(priceRatio), `base price ${num(pg)} gold`],
      ['Output ÷ recipe', ratio(X.efficiency), 'buildings, roughly: efficiency, modifiers, inputs, access'],
      ['Markets', `${X.mk.short} short`, `${X.mk.surplus} in surplus of ${X.mk.markets}`],
      ['Stockpile', num(X.mk.stock), 'in the markets'],
    ];
    if (S.r >= 0) t.push(['Trade', num(X.tradeIn - X.tradeOut) + ' net', `${num(X.tradeIn)} in · ${num(X.tradeOut)} out`]);
    return t.map(([a, b, c]) => `<div class=tile><div class=label>${esc(a)}</div><div class=value>${esc(b)}</div><div class=sub>${esc(c)}</div></div>`).join('');
  }
  let renderToken = 0;
  async function render() {
    const token = ++renderToken;
    writeHash();
    $('#save').value = String(S.s);
    $('#region').value = String(S.r);
    document.querySelectorAll('#detail button').forEach(b => b.classList.toggle('on', b.dataset.v === S.d));
    document.querySelectorAll('#timeviews button').forEach((b, i) => b.classList.toggle('on', i === S.tv));
    $('.main').classList.add('loading');
    let D;
    try { D = await loadSave(S.s); } catch (err) { $('#head').innerHTML = `<div class=empty>Could not load ${esc(IX.saves[S.s].file)} (${esc(err.message)}).</div>`; return; }
    if (token !== renderToken) return;
    $('.main').classList.remove('loading');
    buildList(D);
    const g = S.g, X = compute(D, g), grp = groupOf(g);
    const where = S.r >= 0 ? IX.regions[S.r].name : 'World';
    document.title = `${goodName(g)} · Goods · ${IX.run}`;
    $('#head').innerHTML = `<div class=ghead>${imgHtml(g)}<div><h1>${esc(goodName(g))}</h1><div class=muted><span class=chipg><i style="background:${grp.color}"></i>${esc(grp.label)}</span> · ${esc(where)} · save ${esc(IX.saves[S.s].label)}</div></div></div><div class=tiles>${tiles(X, D)}</div>`;
    const flow = flowOption(D, X);
    const el = document.getElementById('sankey');
    el.style.height = flow.height + 'px';
    const sk = chart('sankey');
    sk.resize();
    sk.setOption(flow.option, true);
    sk.off('click');
    sk.on('click', p => { if (p.dataType === 'node' && flow.goodOf[p.name] != null && p.name !== 'g') select(flow.goodOf[p.name]); });
    $('#ptable').innerHTML = producersTable(X);
    $('#ctable').innerHTML = consumersTable(X);
    $('#pcount').textContent = `${num(X.made)} / month`;
    $('#ccount').textContent = `${num(X.used)} / month`;
    if (SUM) {
      const opt = timeOption(g);
      if (opt) chart('time').setOption(opt, true);
    }
    const reg = regionOption(D, g);
    document.getElementById('regions').style.height = reg.height + 'px';
    const rc = chart('regions');
    rc.resize();
    rc.setOption(reg.option, true);
    rc.off('click');
    rc.on('click', p => { const i = reg.regions[p.dataIndex]; if (i != null) { S.r = S.r === i ? -1 : i; render(); } });
    // prefetch the neighbouring saves
    if (S.s > 0) loadSave(S.s - 1);
    if (S.s < IX.saves.length - 1) loadSave(S.s + 1);
  }

  async function init() {
    try {
      IX = await fetch('goods/index.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
    } catch (err) {
      $('#head').innerHTML = '<div class=empty>The goods data did not load. This page reads files next to it, so open it from the published site or over a local web server (not as a file).</div>';
      return;
    }
    IX.goods.forEach((g, i) => goodIndex.set(g.id, i));
    IX.regions.forEach((r, i) => regionIndex.set(r.id, i));
    TRADE = new Set(IX.demand.filter(d => d.id === 'Trade' || d.id === 'BurgherTrades').map(d => d.id));
    S.s = IX.saves.length - 1;
    S.g = goodIndex.has('cloth') ? goodIndex.get('cloth') : IX.goodOrder[0];
    readHash();
    $('#runname').textContent = `${IX.run} · ${IX.years[0]}–${IX.years[1]}`;
    $('#save').innerHTML = IX.saves.map((s, i) => `<option value="${i}">${esc(s.label)}</option>`).join('');
    $('#region').innerHTML = '<option value="-1">World</option>' + IX.regions.map((r, i) => `<option value="${i}">${esc(r.name)}</option>`).join('');
    $('#save').addEventListener('change', e => { S.s = Number(e.target.value); render(); });
    $('#prev').addEventListener('click', () => { if (S.s > 0) { S.s--; render(); } });
    $('#next').addEventListener('click', () => { if (S.s < IX.saves.length - 1) { S.s++; render(); } });
    $('#region').addEventListener('change', e => { S.r = Number(e.target.value); render(); });
    document.querySelectorAll('#detail button').forEach(b => b.addEventListener('click', () => { S.d = b.dataset.v; render(); }));
    document.querySelectorAll('#timeviews button').forEach((b, i) => b.addEventListener('click', () => { S.tv = i; render(); }));
    $('#search').addEventListener('input', () => loadSave(S.s).then(buildList));
    $('#search').addEventListener('keydown', e => {
      const items = [...document.querySelectorAll('.glist a')];
      if (!items.length) return;
      const at = items.findIndex(a => Number(a.dataset.i) === S.g);
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); const next = items[Math.max(0, Math.min(items.length - 1, at + (e.key === 'ArrowDown' ? 1 : -1)))] || items[0]; select(Number(next.dataset.i)); }
      if (e.key === 'Enter') { e.preventDefault(); select(Number((at >= 0 ? items[at] : items[0]).dataset.i)); }
    });
    document.addEventListener('click', e => {
      const a = e.target.closest('.glist a[data-i]');
      if (a) { e.preventDefault(); select(Number(a.dataset.i)); return; }
      const g = e.target.closest('[data-good]');
      if (g) { e.preventDefault(); select(Number(g.dataset.good)); return; }
      const more = e.target.closest('[data-more]');
      if (more) {
        const body = more.closest('tbody');
        body.querySelectorAll('tr[data-extra]').forEach(r => { r.hidden = false; });
        more.closest('tr').remove();
        return;
      }
      const row = e.target.closest('tr.grp:not(.flat)');
      if (row) {
        const open = row.classList.toggle('open');
        row.querySelector('.tog').textContent = open ? '▾' : '▸';
        row.closest('tbody').querySelectorAll(`tr[data-p="${row.dataset.k}"]`).forEach(r => { r.hidden = !open; });
      }
    });
    window.addEventListener('popstate', () => { readHash(); render(); });
    window.addEventListener('hashchange', () => { readHash(); render(); });
    render();
    fetch('goods/summary.json').then(r => r.json()).then(s => { SUM = s; const opt = timeOption(S.g); if (opt) chart('time').setOption(opt, true); }).catch(() => {});
  }
  init();
})();
"""


def goods_page_html(run_name: str, years: tuple[int, int]) -> str:
    esc = html.escape
    title = f"Goods · {esc(run_name)} · {years[0]}–{years[1]} · Prosper or Perish"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="robots" content="noindex">
<style>{PAGE_CSS}{GOODS_CSS}</style></head><body>
<div class=app>
<aside class=side>
  <a class=back href="index.html">← Run report</a>
  <div class=run id=runname></div>
  <input id=search type=search placeholder="Find a good (↑ ↓ Enter)" aria-label="Find a good" autocomplete=off>
  <div class=glist id=goodlist role=navigation></div>
</aside>
<div class=main>
  <div class=bar>
    <label>Save <button id=prev type=button title="Previous save">‹</button><select id=save></select><button id=next type=button title="Next save">›</button></label>
    <label>Region <select id=region></select></label>
    <label>Flow by <span class=seg id=detail><button type=button data-v=building>Building</button><button type=button data-v=method>Method</button></span></label>
  </div>
  <section id=head></section>
  <section class=card><header><h3>Where it comes from and where it goes</h3></header>
    <div id=sankey class=chart style="height:420px"></div>
    <p class=caption>Left to right: the goods the producers use, the producers, this good, its users and the goods they make, in gold per
    month at base price (hover for amounts). Inputs and products count the share of a method that belongs to this good. Click a
    good to open it. Amounts per building are the market's exact totals split by recipe (output per level × levels × staffing),
    with one rough efficiency factor per good for buildings and one for RGOs.</p></section>
  <div class=split>
    <section class=card><header><h3>Producers</h3><span class=muted id=pcount></span></header><div class=table-wrap id=ptable></div>
      <p class=caption>Click a building to see its production methods and their recipe per level. Output ÷ recipe: what they made
      against their recipe, i.e. production efficiency, output modifiers, throughput, input shortages and market access together,
      roughly. RGOs: units per 1,000 workers.</p></section>
    <section class=card><header><h3>Users</h3><span class=muted id=ccount></span></header><div class=table-wrap id=ctable></div>
      <p class=caption>Buildings (by method) and the other demand of the markets: pops, construction, armies and navies (upkeep and
      new units), roads. Got: what they received ÷ what they wanted.</p></section>
  </div>
  <section class=card><header><h3>Over the run</h3><div class=views id=timeviews><button type=button>Producers</button><button type=button>Users</button><button type=button>Made, used, price</button></div></header>
    <div id=time class=chart style="height:400px"></div>
    <p class=caption>World totals per save, the eight largest producers or users and the rest. The dashed line marks the chosen save.</p></section>
  <section class=card><header><h3>By world region</h3></header><div id=regions class=chart style="height:320px"></div>
    <p class=caption>Value made and used per world region in the chosen save. Click a region to show only it (again for the world).</p></section>
</div>
</div>
<script src="{ECHARTS_URL}"></script>
<script>{GOODS_JS}</script>
</body></html>
"""
