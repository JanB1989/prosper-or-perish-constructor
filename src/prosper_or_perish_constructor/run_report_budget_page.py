"""The budget page of the run report (`budget.html`): where the money comes from, who gets it, where it goes.

Static HTML + one script; the data comes from `budget/index.js`, `budget/summary.js` and one `budget/<n>.js` per save
(written by `run_report_budget`). Layout as the goods page: the world, the regions and the largest countries on the left,
the save and how to show the sources on top, then for the chosen scope its figures, the flow chart (sources -> tax base ->
estates -> state -> uses; a good opens the goods page), the tables, the run over time and the split by region or country.
State lives in the URL hash (#k=world&s=12&d=good&tv=0).
"""

from __future__ import annotations

import html

from prosper_or_perish_constructor.run_report import ECHARTS_URL, PAGE_CSS
from prosper_or_perish_constructor.run_report_data import LOADER_JS
from prosper_or_perish_constructor.run_report_goods_page import GOODS_CSS

BUDGET_CSS = r"""
.klist h4{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:16px 6px 4px;display:flex;align-items:center;gap:6px}
.klist a{display:flex;align-items:center;gap:8px;padding:3px 6px;border-radius:6px;color:var(--ink);text-decoration:none;font-size:13px;line-height:22px}
.klist a:hover{background:var(--chip)} .klist a.on{background:var(--accent);color:#fff} .klist a.on .badge,.klist a.on .share{color:#fff!important}
.klist a i{display:inline-block;width:10px;height:10px;border-radius:2px;flex:none}
.klist a span:first-of-type{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.klist .share{margin-left:auto;font-size:11px;font-variant-numeric:tabular-nums;color:var(--ink);min-width:38px;text-align:right;flex:none}
.klist .badge{font-size:11px;font-variant-numeric:tabular-nums;color:var(--muted);min-width:44px;text-align:right;flex:none}
.klist .legend{display:flex;gap:8px;font-size:11px;color:var(--muted);margin:8px 6px 0}
.klist .legend span:first-child{margin-left:auto;min-width:38px;text-align:right} .klist .legend span:last-child{min-width:44px;text-align:right}
td img.gi{width:18px;height:18px;vertical-align:-4px;margin-right:6px}
td a.goodlink{color:var(--ink);text-decoration:none} td a.goodlink:hover{text-decoration:underline}
tr.sum td{font-weight:600;border-top:1px solid var(--line)}
"""

BUDGET_JS = r"""
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

  let IX = null, SUM = null;
  const SAVES = new Map();
  const S = {k: 0, s: 0, d: 'good', tv: 0};
  let F = {}, EF = {}, scopeIndex = new Map(), charts = {};

  const scope = i => IX.scopes[i] || {name: '?'};
  const goodName = i => i >= 0 ? (IX.goods[i] || {}).name || '?' : '';
  const groupOf = i => IX.groups.find(g => g.key === (IX.goods[i] || {}).group) || {color: '#9a9a96', label: 'Other'};
  const imgHtml = i => (IX.goods[i] || {}).icon ? `<img class=gi src="${esc(IX.goods[i].icon)}" alt="">` : '';
  const bName = i => i >= 0 ? (IX.buildings[i] || {}).name || '?' : 'Smaller sources';
  const isRgo = i => i >= 0 && (IX.buildings[i] || {}).id === 'rgo';

  // ---------------------------------------------------------------- data
  function prepare(raw) {
    const scopes = new Map();
    for (const [k, v] of Object.entries(raw.scopes || {})) {
      const L = {};
      IX.fields.forEach((f, i) => { L[f] = v.L[i] || 0; });
      L.stock = v.stock;
      const E = (v.E || []).map(r => { const e = {i: r[0]}; IX.estateFields.forEach((f, j) => { e[f] = r[j + 1] || 0; }); return e; });
      scopes.set(Number(k), {L, E, G: v.G || [], T: v.T || []});
    }
    return {scopes, top: raw.top || [], regionOf: raw.regionOf || {}};
  }
  function loadSave(i) {
    if (!SAVES.has(i)) SAVES.set(i, loadData(IX.saves[i].file).then(prepare));
    return SAVES.get(i);
  }

  // what the page shows of one scope in one save
  const STATE_IN = [['tax', 'Taxes', '#2a78d6'], ['trade', 'Trade', '#5fb8c4'], ['tariff', 'Tariffs', '#00a3a3'], ['foreign', 'Foreign buildings', '#7d8b2a'], ['rest', 'Coin minting, unlabelled', '#c9a227']];
  const STATE_OUT = [['upkeep', 'Building upkeep', '#a0522d'], ['navy', 'Navy', '#2a78d6'], ['army', 'Army', '#e34948'], ['court', 'Court', '#e87ba4'], ['fort', 'Forts', '#8c8c88'], ['diplomatic', 'Diplomacy', '#4a3aa7'],
    ['colonial', 'Colonies', '#1baf7a'], ['exploration', 'Exploration', '#5fb8c4'], ['cultural', 'Culture', '#00a3a3'], ['food', 'Food', '#7d8b2a'], ['mercenaries', 'Mercenaries', '#eb6834'], ['other_budget', 'Other, unlabelled', '#9a9a96']];
  const ESTATE_OUT = [['pop_expense', 'Pop needs', '#1baf7a'], ['build', 'Estate buildings', '#a0522d'], ['infra_expense', 'Roads, infrastructure', '#7d8b2a'], ['others', 'Orders, rebels, armies', '#9a9a96']];
  const estateBuild = e => (e.building_expense || 0) + (e.invest_expense || 0);
  const estateOthers = e => (e.io_expense || 0) + (e.rebel_expense || 0) + (e.food_expense || 0) + (e.private_army_expense || 0);
  const estateName = e => (IX.estates[e.i] || {}).name || '?';
  const estateColor = e => (IX.estates[e.i] || {}).color || '#9a9a96';

  // the sources of a scope, by the chosen detail
  function sourceRows(X) {
    const rows = new Map();
    const add = (key, name, color, v, st, good, building) => {
      if (!rows.has(key)) rows.set(key, {key, name, color, v: 0, st: 0, good, building});
      const r = rows.get(key); r.v += v || 0; r.st += st || 0;
    };
    for (const [g, b, v, st] of X.G) {
      if (S.d === 'building') add('b' + b, b >= 0 ? (isRgo(b) ? 'RGOs' : bName(b)) : 'Smaller sources', isRgo(b) ? '#c98a00' : b >= 0 ? '#2a78d6' : '#9a9a96', v, st, null, b);
      else if (S.d === 'group') {
        if (g >= 0) { const gr = groupOf(g); add('g' + gr.key, gr.label, gr.color, v, st, null, null); }
        else add(b >= 0 ? 'services' : 'small', b >= 0 ? 'Services, no goods' : 'Smaller sources', b >= 0 ? '#00a3a3' : '#9a9a96', v, st, null, null);
      }
      else if (g >= 0) add('g' + g, goodName(g), groupOf(g).color, v, st, g, null);
      else add('x' + b, b >= 0 ? bName(b) : 'Smaller sources', b >= 0 ? '#00a3a3' : '#9a9a96', v, st, null, b);
    }
    return [...rows.values()].filter(r => r.v > 0).sort((a, b) => b.v - a.v);
  }

  // ---------------------------------------------------------------- flow chart
  function flowOption(X) {
    const L = X.L;
    const nodes = [], links = [], label = {}, goodOf = {};
    const node = (id, text, depth, color) => { if (label[id] == null) { label[id] = text; nodes.push({name: id, depth, itemStyle: {color}}); } };
    const link = (source, target, value) => { if (value > 1e-6) links.push({source, target, value}); };
    node('base', 'Tax base', 1, '#8c8c88');
    // sources
    let rows = sourceRows(X);
    const MAX = 24;
    if (rows.length > MAX + 1) {
      const rest = rows.splice(MAX);
      rows.push({key: 'rest', name: `Other sources (${rest.length})`, color: '#9a9a96', v: rest.reduce((a, r) => a + r.v, 0)});
    }
    for (const r of rows) {
      node('s' + r.key, r.name, 0, r.color);
      if (r.good != null) goodOf['s' + r.key] = r.good;
      link('s' + r.key, 'base', r.v);
    }
    // estates
    const trade = X.E.reduce((a, e) => a + e.trade_income, 0);
    if (trade > 0) node('etrade', 'Trade, to the estates', 1, '#5fb8c4');
    if (X.E.some(e => e.tariff_income + e.interest_income + e.other > 0)) node('eother', 'Tariffs, interest, other', 1, '#00a3a3');
    const budget = STATE_OUT.reduce((a, [k]) => a + (L[k] || 0), 0);
    node('state', 'State', 3, '#1d1d1b');
    if (dark) nodes[nodes.length - 1].itemStyle.color = '#eceef0';
    for (const e of X.E) {
      const id = 'e' + e.i;
      const income = e.taxable_income + e.uncontrolled_income;
      const flow = income + e.trade_income + e.tariff_income + e.interest_income + e.other;
      const spend = e.paid_taxes + e.pop_expense + estateBuild(e) + e.infra_expense + estateOthers(e);
      if (flow <= 0 && spend <= 0) continue;
      node(id, estateName(e), 2, estateColor(e));
      link('base', id, income);
      link('etrade', id, e.trade_income);
      link('eother', id, e.tariff_income + e.interest_income + e.other);
      if (e.balance < 0) { node('eabove', 'Spent above income', 1, '#e34948'); link('eabove', id, -e.balance); }
      link(id, 'state', e.paid_taxes);
      link(id, 'upop_expense', e.pop_expense);
      link(id, 'ubuild', estateBuild(e));
      link(id, 'uinfra_expense', e.infra_expense);
      link(id, 'uothers', estateOthers(e));
      if (e.balance > 0) link(id, 'usave', e.balance);
    }
    for (const [k, name, color] of ESTATE_OUT) node('u' + k, name, 4, color);
    node('usave', 'Into estate gold', 4, '#c9a227');
    // the state's other income and its spending
    for (const [k, name, color] of STATE_IN) if (k !== 'tax') { node('i' + k, name, 2, color); link('i' + k, 'state', L[k]); }
    const big = budget * 0.012;
    let small = 0;
    for (const [k, name, color] of STATE_OUT) {
      if ((L[k] || 0) >= big) { node('b' + k, name, 4, color); link('state', 'b' + k, L[k]); } else small += L[k] || 0;
    }
    if (small > 0) { node('bsmall', 'Smaller budget lines', 4, '#9a9a96'); link('state', 'bsmall', small); }
    const had = L.has_previous > 0;
    if (L.off_budget > 0) { node('off', had ? 'Construction, other off budget' : 'Off budget (no earlier save)', 4, '#eda100'); link('state', 'off', L.off_budget); }
    if (L.off_budget < 0) { node('offin', 'Other income, off budget', 2, '#eda100'); link('offin', 'state', -L.off_budget); }
    if (L.treasury > 0) { node('tre', 'Into the treasury', 4, '#c9a227'); link('state', 'tre', L.treasury); }
    if (L.treasury < 0) { node('from', 'From the treasury', 2, '#c9a227'); link('from', 'state', -L.treasury); }

    const used = new Set(); for (const l of links) { used.add(l.source); used.add(l.target); }
    const keep = nodes.filter(nd => used.has(nd.name));
    const total = id => Math.max(links.filter(l => l.target === id).reduce((a, l) => a + l.value, 0), links.filter(l => l.source === id).reduce((a, l) => a + l.value, 0));
    const top = Math.max(1e-9, ...keep.map(nd => total(nd.name)));
    const lastDepth = 4;
    for (const nd of keep) nd.label = {width: nd.depth === lastDepth ? 170 : 150, overflow: 'truncate', show: total(nd.name) >= 0.004 * top};
    const perColumn = {}; for (const nd of keep) perColumn[nd.depth] = (perColumn[nd.depth] || 0) + 1;
    const height = Math.max(460, Math.max(...Object.values(perColumn), 1) * 38 + 60);
    return {
      height, goodOf,
      option: {
        backgroundColor: 'transparent',
        tooltip: {trigger: 'item', confine: true, formatter: p => {
          if (p.dataType === 'edge') return `${esc(label[p.data.source])} → ${esc(label[p.data.target])}<br><b>${num(p.data.value)}</b> gold / month`;
          const hint = goodOf[p.name] != null ? '<br><span style="opacity:.7">click to open this good</span>' : '';
          return `<b>${esc(label[p.name])}</b><br>${num(total(p.name))} gold / month${hint}`;
        }},
        series: [{
          type: 'sankey', left: 4, right: 170, top: 8, bottom: 8, nodeWidth: 12, nodeGap: 14, layoutIterations: 0,
          draggable: false, emphasis: {focus: 'adjacency'},
          label: {color: INK, fontSize: 11, formatter: p => `${num(total(p.name))}  ${label[p.name]}`},
          lineStyle: {color: 'gradient', curveness: 0.5, opacity: dark ? 0.45 : 0.32},
          data: keep, links,
        }],
      },
    };
  }

  // ---------------------------------------------------------------- tables
  const sbar = f => `<span class=sbar><i style="width:${Math.max(0, Math.min(100, (f || 0) * 100)).toFixed(1)}%"></i></span>`;
  const LIMIT = 25;
  function capped(groups, columns) {
    if (groups.length <= LIMIT) return groups.join('');
    const hidden = groups.slice(LIMIT).map(g => g.replace(/<tr class="grp/g, '<tr data-extra hidden class="grp')).join('');
    return groups.slice(0, LIMIT).join('') + hidden + `<tr class=more-row><td colspan=${columns}><button type=button data-more>Show all ${groups.length}</button></td></tr>`;
  }
  function sourcesTable(X) {
    const goods = new Map(), loose = [];
    for (const [g, b, v, st] of X.G) {
      if (g >= 0) {
        if (!goods.has(g)) goods.set(g, {g, v: 0, st: 0, b: []});
        const e = goods.get(g); e.v += v || 0; e.st += st || 0; e.b.push([b, v || 0, st || 0]);
      } else loose.push({b, v: v || 0, st: st || 0});
    }
    const trade = new Map(); let looseTrade = 0;
    for (const [g, v] of X.T) { if (g >= 0) trade.set(g, v); else looseTrade += v || 0; }
    const total = [...goods.values()].reduce((a, e) => a + e.v, 0) + loose.reduce((a, e) => a + e.v, 0) || 1;
    const rows = [...goods.values()].map(e => ({...e, kind: 'good'})).concat(loose.map(e => ({...e, kind: 'loose'}))).sort((a, b) => b.v - a.v);
    if (!rows.length) return '<div class=empty>No tax base here in this save.</div>';
    const head = `<table class=gt><thead><tr><th>Source</th><th class=num title="Gold per month">Tax base</th><th class=num>Share</th><th class=num title="What the state's tax takes of it">To the state</th><th class=num title="Trade income on this good, estimated from the routes">Trade</th></tr></thead><tbody>`;
    const groups = rows.map((r, k) => {
      const cells = (v, st, tr) => `<td class=num>${num(v)}</td><td class=num>${sbar(v / total)}${pct(v / total)}</td><td class=num>${num(st)}</td><td class=num>${tr == null ? '–' : num(tr)}</td>`;
      if (r.kind === 'loose') return `<tr class="grp flat"><td><span class=tog></span>${esc(bName(r.b))}<span class=cat>${r.b >= 0 ? 'no goods' : ''}</span></td>${cells(r.v, r.st, null)}</tr>`;
      const subs = r.b.slice().sort((a, b) => b[1] - a[1]);
      let h = `<tr class="grp" data-k="s${k}"><td><span class=tog>▸</span>${imgHtml(r.g)}<a class=goodlink href="goods.html#g=${encodeURIComponent(IX.goods[r.g].id)}">${esc(goodName(r.g))}</a></td>${cells(r.v, r.st, trade.get(r.g))}</tr>`;
      for (const [b, v, st] of subs) h += `<tr class=sub data-p="s${k}" hidden><td>${esc(bName(b))}</td><td class=num>${num(v)}</td><td class=num>${pct(v / total)}</td><td class=num>${num(st)}</td><td class=num>–</td></tr>`;
      return h;
    });
    const noRoute = looseTrade > 0 ? `<tr class="grp flat"><td><span class=tog></span>Trade with no route to spread it over</td><td class=num>–</td><td class=num>–</td><td class=num>–</td><td class=num>${num(looseTrade)}</td></tr>` : '';
    return head + capped(groups, 5) + noRoute + '</tbody></table>';
  }
  function linesTable(lines, L, total, headName) {
    let h = `<table class=gt><thead><tr><th>${esc(headName)}</th><th class=num>Gold / month</th><th class=num>Share</th></tr></thead><tbody>`;
    for (const [k, name, color, value] of lines) {
      const v = value != null ? value : L[k] || 0;
      if (!v) continue;
      h += `<tr class="grp flat"><td><i class=dot style="background:${color}"></i>${esc(name)}</td><td class=num>${num(v)}</td><td class=num>${sbar(v / total)}${pct(v / total)}</td></tr>`;
    }
    return h + `<tr class=sum><td>Together</td><td class=num>${num(lines.reduce((a, [k, , , value]) => a + (value != null ? value : L[k] || 0), 0))}</td><td></td></tr></tbody></table>`;
  }
  function budgetTables(X) {
    const L = X.L;
    const had = L.has_previous > 0;
    const spending = [...STATE_OUT, ['off_budget', had ? 'Construction, other off budget' : 'Off budget (no earlier save)', '#eda100'], ['treasury', 'Into the treasury', '#c9a227']];
    return {income: linesTable(STATE_IN, L, L.income || 1, 'State income'), spending: linesTable(spending, L, L.income || 1, 'State spending')};
  }
  function estatesTable(X) {
    if (!X.E.length) return '<div class=empty>No estates here in this save.</div>';
    const rows = X.E.slice().sort((a, b) => (b.taxable_income + b.uncontrolled_income) - (a.taxable_income + a.uncontrolled_income));
    const col = [['Taxable', e => e.taxable_income, 'Income the state can tax'], ['Low control', e => e.uncontrolled_income, 'Income from what the state does not control: untaxed'],
      ['Trade, other', e => e.trade_income + e.tariff_income + e.interest_income + e.other, ''], ['Taxes', e => e.paid_taxes, 'Paid to the state'],
      ['Pop needs', e => e.pop_expense, ''], ['Buildings', estateBuild, 'Own buildings and investment in others'], ['Roads', e => e.infra_expense, ''],
      ['Other', estateOthers, 'Orders, rebels, food, private armies'], ['Balance', e => e.balance, 'All of the above; below zero: spent above income'], ['Gold', e => e.gold, 'What the estate holds']];
    const sum = f => rows.reduce((a, e) => a + f(e), 0);
    return `<table class=gt><thead><tr><th>Estate</th>${col.map(c => `<th class=num title="${esc(c[2])}">${c[0]}</th>`).join('')}</tr></thead><tbody>` +
      rows.map(e => `<tr class="grp flat"><td><i class=dot style="background:${estateColor(e)}"></i>${esc(estateName(e))}</td>${col.map(c => `<td class=num>${num(c[1](e))}</td>`).join('')}</tr>`).join('') +
      `<tr class=sum><td>Together</td>${col.map(c => `<td class=num>${num(sum(c[1]))}</td>`).join('')}</tr></tbody></table>`;
  }

  // ---------------------------------------------------------------- over the run
  const saveTime = i => { const d = String(IX.saves[i].date || IX.saves[i].label).split('.').map(Number); return Date.UTC(d[0], (d[1] || 1) - 1, d[2] || 1); };
  function timeOption() {
    const e = SUM && SUM[String(S.k)];
    if (!e) return null;
    const xs = IX.saves.map((s, i) => saveTime(i));
    const marker = {silent: true, symbol: 'none', label: {show: false}, lineStyle: {type: 'dashed', color: MUTED, width: 1}, data: [{xAxis: xs[S.s]}]};
    const L = e.L;
    const stack = (name, color, values) => ({type: 'line', name, stack: 'total', areaStyle: {opacity: 0.85}, lineStyle: {width: 0.6}, showSymbol: false, emphasis: {focus: 'series'}, color, data: values.map((v, j) => [xs[j], v == null ? null : v])});
    const line = (name, color, values) => ({type: 'line', name, showSymbol: false, color, lineStyle: {width: 2.5}, data: values.map((v, j) => [xs[j], v == null ? null : v])});
    const add = (...keys) => xs.map((_, j) => keys.reduce((a, k) => a + ((L[k] || [])[j] || 0), 0));
    const pos = values => values.map(v => (v == null ? null : Math.max(0, v)));
    const per = key => xs.map((_, j) => (L.population || [])[j] > 0 ? ((L[key] || [])[j] || 0) / L.population[j] * 1000 : null);
    const views = [
      () => STATE_IN.map(([k, n, c]) => stack(n, c, L[k] || [])),
      () => [...STATE_OUT.map(([k, n, c]) => stack(n, c, L[k] || [])), stack('Construction, other off budget', '#eda100', pos(L.off_budget || [])), stack('Into the treasury', '#c9a227', pos(L.treasury || []))],
      () => [stack('Taxable', '#2a78d6', L.e_taxable_income || []), stack('Low control', '#4a3aa7', L.e_uncontrolled_income || []), stack('Trade', '#5fb8c4', L.e_trade_income || []), stack('Tariffs, interest, other', '#00a3a3', add('e_tariff_income', 'e_interest_income', 'e_other'))],
      () => [stack('Taxes to the state', '#2a78d6', L.e_paid_taxes || []), stack('Pop needs', '#1baf7a', L.e_pop_expense || []), stack('Buildings', '#a0522d', add('e_building_expense', 'e_invest_expense')), stack('Roads', '#7d8b2a', L.e_infra_expense || []), stack('Other', '#9a9a96', add('e_io_expense', 'e_rebel_expense', 'e_food_expense', 'e_private_army_expense'))],
      () => {
        const goods = Object.keys(e.goods || {});
        const series = goods.map(g => stack(goodName(Number(g)), groupOf(Number(g)).color, e.goods[g]));
        series.forEach((s, i) => { s.itemStyle = {opacity: 1 - 0.05 * i}; s.color = undefined; });
        series.push(stack('Other goods', '#9a9a96', e.rest || []));
        return series;
      },
      () => [stack('Treasuries', '#c9a227', L.gold || []), ...Object.keys(e.gold || {}).map(k => stack((IX.estates[Number(k)] || {}).name || k, (IX.estates[Number(k)] || {}).color, e.gold[k]))],
      () => [stack('Treasuries', '#c9a227', L.gold || []), stack('Estate gold', '#4a3aa7', L.e_gold || []), stack('Goods in markets', '#1baf7a', L.stock || []), stack('Buildings at list price', '#a0522d', L.capital || []), line('Debt', '#e34948', L.debt || [])],
      () => [line('State income', '#2a78d6', per('income')), line('State budget spending', '#eb6834', per('expense')), line('Estate taxable income', '#4a3aa7', per('e_taxable_income'))],
    ];
    const series = views[S.tv]();
    if (!series.length) return null;
    series[0].markLine = marker;
    return {
      backgroundColor: 'transparent', tooltip: {trigger: 'axis', confine: true, valueFormatter: v => num(v)},
      legend: {type: 'scroll', top: 0, left: 0, right: 0, textStyle: {color: INK}},
      grid: {left: 8, right: 16, top: 40, bottom: 30, containLabel: true},
      xAxis: {type: 'time', min: xs[0], max: xs[xs.length - 1], axisLabel: {formatter: v => String(new Date(v).getUTCFullYear()), hideOverlap: true}},
      yAxis: {type: 'value', axisLabel: {formatter: v => num(v)}},
      series,
    };
  }
  function partsOption(D) {
    const kind = scope(S.k).kind;
    if (kind === 'country') return null;
    const members = kind === 'world' ? IX.scopes.map((s, i) => i).filter(i => IX.scopes[i].kind === 'region' && D.scopes.has(i))
      : D.top.filter(i => D.regionOf[String(i)] === S.k && D.scopes.has(i));
    const rows = members.map(i => ({i, L: D.scopes.get(i).L})).sort((a, b) => b.L.income - a.L.income);
    if (!rows.length) return null;
    return {
      height: Math.max(260, rows.length * 26 + 70), rows,
      option: {
        backgroundColor: 'transparent', tooltip: {trigger: 'axis', axisPointer: {type: 'shadow'}, confine: true, valueFormatter: v => num(v) + ' gold'},
        legend: {top: 0, left: 0, textStyle: {color: INK}}, grid: {left: 8, right: 24, top: 32, bottom: 8, containLabel: true},
        xAxis: {type: 'value', axisLabel: {formatter: v => num(v)}},
        yAxis: {type: 'category', data: rows.map(r => scope(r.i).name), inverse: true, axisLabel: {color: INK}},
        series: [
          {type: 'bar', name: 'State income', color: '#2a78d6', data: rows.map(r => r.L.income), barMaxWidth: 12},
          {type: 'bar', name: 'Budget spending', color: '#eb6834', data: rows.map(r => r.L.expense), barMaxWidth: 12},
          {type: 'bar', name: 'Off budget', color: '#eda100', data: rows.map(r => Math.max(0, r.L.off_budget)), barMaxWidth: 12},
          {type: 'bar', name: 'Estate taxable income', color: '#4a3aa7', data: rows.map(r => r.L.e_taxable_income), barMaxWidth: 12}],
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
    const h = `#k=${encodeURIComponent(scope(S.k).id)}&s=${S.s}&d=${S.d}&tv=${S.tv}`;
    if (location.hash !== h) history.replaceState(null, '', h);
  }
  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    if (p.has('k') && scopeIndex.has(p.get('k'))) S.k = scopeIndex.get(p.get('k'));
    if (p.has('s')) { const s = Number(p.get('s')); if (s >= 0 && s < IX.saves.length) S.s = s; }
    if (['good', 'group', 'building'].includes(p.get('d'))) S.d = p.get('d');
    if (p.has('tv')) { const tv = Number(p.get('tv')); if (tv >= 0 && tv < document.querySelectorAll('#timeviews button').length) S.tv = tv; }
  }
  function buildList(D) {
    const q = $('#search').value.trim().toLowerCase();
    const world = (D.scopes.get(0) || {L: {}}).L.income || 1;
    const item = i => {
      const X = D.scopes.get(i), s = IX.scopes[i];
      if (!X || (q && !s.name.toLowerCase().includes(q))) return '';
      const inc = X.L.income;
      return `<a href="#" data-k="${i}" class="${i === S.k ? 'on' : ''}" title="${esc(s.name)}: ${num(inc)} gold income a month">${s.color ? `<i style="background:${s.color}"></i>` : ''}<span>${esc(s.name)}</span><span class=share>${pct(inc / world)}</span><span class=badge>${num(inc)}</span></a>`;
    };
    const regions = IX.scopes.map((s, i) => i).filter(i => IX.scopes[i].kind === 'region' && D.scopes.has(i)).sort((a, b) => D.scopes.get(b).L.income - D.scopes.get(a).L.income);
    let h = `<div class=legend title="State income per month, and its share of the world's. A country counts in the region of its capital."><span>share</span><span>income</span></div>`;
    h += item(0);
    h += `<h4>World regions</h4>` + regions.map(item).join('');
    h += `<h4>Largest countries of this save</h4>` + D.top.map(item).join('');
    $('#scopelist').innerHTML = h;
  }
  function tiles(X) {
    const L = X.L;
    const base = L.e_taxable_income + L.e_uncontrolled_income;
    const per = v => L.population > 0 ? v / L.population * 1000 : null;
    const t = [
      ['State income', num(L.income) + ' / mo', `${num(per(L.income))} per million people`],
      ['Budget spending', num(L.expense) + ' / mo', `${pct(L.expense / L.income)} of income`],
      ['Off budget', num(L.off_budget) + ' / mo', L.has_previous > 0 ? 'mostly construction: earned above the budget, not kept' : 'no earlier save to compare the treasury with'],
      ['Tax base', num(base) + ' / mo', `${pct(L.e_uncontrolled_income / base)} of it out of the state's control`],
      ['Taxes paid', num(L.e_paid_taxes) + ' / mo', `${pct(L.e_paid_taxes / L.e_taxable_income)} of the estates' taxable income`],
      ['Estate spending', num(L.e_pop_expense) + ' / mo', `on pop needs; ${num(L.e_building_expense + L.e_invest_expense + L.e_infra_expense)} on buildings and roads`],
      ['Treasuries', num(L.gold), L.treasury >= 0 ? `+${num(L.treasury)} a month since the last save` : `${num(L.treasury)} a month since the last save`],
      ['Estate gold', num(L.e_gold), `${pct(L.e_gold / (L.e_gold + L.gold))} of all gold`],
      ['Buildings', num(L.capital), 'levels at list price'],
    ];
    if (L.stock != null) t.push(['Goods in markets', num(L.stock), 'stock at market price']);
    t.push(['Debt', num(L.debt), `${pct(L.debt / L.gold)} of the treasuries`]);
    return t.map(([a, b, c]) => `<div class=tile><div class=label>${esc(a)}</div><div class=value>${esc(b)}</div><div class=sub>${esc(c)}</div></div>`).join('');
  }
  let renderToken = 0;
  async function render() {
    const token = ++renderToken;
    writeHash();
    $('#save').value = String(S.s);
    document.querySelectorAll('#detail button').forEach(b => b.classList.toggle('on', b.dataset.v === S.d));
    document.querySelectorAll('#timeviews button').forEach((b, i) => b.classList.toggle('active', i === S.tv));
    $('.main').classList.add('loading');
    let D;
    try { D = await loadSave(S.s); } catch (err) { $('#head').innerHTML = `<div class=empty>Could not load ${esc(IX.saves[S.s].file)} (${esc(err.message)}).</div>`; return; }
    if (token !== renderToken) return;
    $('.main').classList.remove('loading');
    buildList(D);
    if (!D.scopes.has(S.k)) {
      $('#head').innerHTML = `<div class=ghead><div><h1>${esc(scope(S.k).name)}</h1><div class=muted>Not among the largest countries in ${esc(IX.saves[S.s].label)}. Pick another save or the world.</div></div></div>`;
      for (const id of ['sankey', 'parts']) if (charts[id]) charts[id].clear();
      for (const id of ['#stable', '#income', '#spending', '#etable']) $(id).innerHTML = '';
      if (SUM) { const opt = timeOption(); if (opt) chart('time').setOption(opt, true); }
      return;
    }
    const X = D.scopes.get(S.k);
    document.title = `${scope(S.k).name} · Budget · ${IX.run}`;
    $('#head').innerHTML = `<div class=ghead><div><h1>${esc(scope(S.k).name)}</h1><div class=muted>Budget · save ${esc(IX.saves[S.s].label)} · gold per month unless it is a stock</div></div></div><div class=tiles>${tiles(X)}</div>`;
    const flow = flowOption(X);
    const el = document.getElementById('sankey');
    el.style.height = flow.height + 'px';
    const sk = chart('sankey');
    sk.resize();
    sk.setOption(flow.option, true);
    sk.off('click');
    sk.on('click', p => { if (p.dataType === 'node' && flow.goodOf[p.name] != null) window.location.href = 'goods.html#g=' + encodeURIComponent(IX.goods[flow.goodOf[p.name]].id); });
    $('#stable').innerHTML = sourcesTable(X);
    const tables = budgetTables(X);
    $('#income').innerHTML = tables.income;
    $('#spending').innerHTML = tables.spending;
    $('#etable').innerHTML = estatesTable(X);
    if (SUM) { const opt = timeOption(); if (opt) chart('time').setOption(opt, true); }
    const parts = partsOption(D);
    $('#partscard').hidden = !parts;
    $('#partstitle').textContent = scope(S.k).kind === 'world' ? 'By world region' : 'The largest countries here';
    if (parts) {
      document.getElementById('parts').style.height = parts.height + 'px';
      const pc = chart('parts');
      pc.resize();
      pc.setOption(parts.option, true);
      pc.off('click');
      pc.on('click', p => { const r = parts.rows[p.dataIndex]; if (r) select(r.i); });
    }
    if (S.s > 0) loadSave(S.s - 1);
    if (S.s < IX.saves.length - 1) loadSave(S.s + 1);
  }
  function select(k) { S.k = k; render(); window.scrollTo({top: 0}); }

  async function init() {
    try {
      IX = await loadData('budget/index.js');
    } catch (err) {
      $('#head').innerHTML = '<div class=empty>The budget data did not load. This page reads files next to it, so open it from the published site or over a local web server.</div>';
      return;
    }
    IX.scopes.forEach((s, i) => scopeIndex.set(s.id, i));
    S.s = IX.saves.length - 1;
    readHash();
    $('#runname').textContent = `${IX.run} · ${IX.years[0]}–${IX.years[1]}`;
    $('#save').innerHTML = IX.saves.map((s, i) => `<option value="${i}">${esc(s.label)}</option>`).join('');
    $('#save').addEventListener('change', e => { S.s = Number(e.target.value); render(); });
    $('#prev').addEventListener('click', () => { if (S.s > 0) { S.s--; render(); } });
    $('#next').addEventListener('click', () => { if (S.s < IX.saves.length - 1) { S.s++; render(); } });
    document.querySelectorAll('#detail button').forEach(b => b.addEventListener('click', () => { S.d = b.dataset.v; render(); }));
    document.querySelectorAll('#timeviews button').forEach((b, i) => b.addEventListener('click', () => { S.tv = i; render(); }));
    $('#search').addEventListener('input', () => loadSave(S.s).then(buildList));
    document.addEventListener('click', e => {
      const a = e.target.closest('.klist a[data-k]');
      if (a) { e.preventDefault(); select(Number(a.dataset.k)); return; }
      const more = e.target.closest('[data-more]');
      if (more) {
        more.closest('tbody').querySelectorAll('tr[data-extra]').forEach(r => { r.hidden = false; });
        more.closest('tr').remove();
        return;
      }
      if (e.target.closest('a.goodlink')) return;
      const row = e.target.closest('tr.grp:not(.flat)');
      if (row) {
        const open = row.classList.toggle('open');
        row.querySelector('.tog').textContent = open ? '▾' : '▸';
        row.closest('tbody').querySelectorAll(`tr[data-p="${row.dataset.k}"]`).forEach(r => { r.hidden = !open; });
      }
    });
    window.addEventListener('hashchange', () => { readHash(); render(); });
    render();
    loadData('budget/summary.js').then(s => { SUM = s; const opt = timeOption(); if (opt) chart('time').setOption(opt, true); }).catch(() => {});
  }
  init();
})();
"""


def budget_page_html(run_name: str, years: tuple[int, int]) -> str:
    esc = html.escape
    title = f"Budget · {esc(run_name)} · {years[0]}–{years[1]} · Prosper or Perish"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="robots" content="noindex">
<style>{PAGE_CSS}{GOODS_CSS}{BUDGET_CSS}</style></head><body>
<div class=app>
<aside class=side>
  <a class=back href="index.html">← Run report</a>
  <div class=run id=runname></div>
  <input id=search type=search placeholder="Find a region or country" aria-label="Find a region or country" autocomplete=off>
  <div class=klist id=scopelist role=navigation></div>
</aside>
<div class=main>
  <div class=bar>
    <label>Save <button id=prev type=button title="Previous save">‹</button><select id=save></select><button id=next type=button title="Next save">›</button></label>
    <label>Sources by <span class=seg id=detail><button type=button data-v=good>Good</button><button type=button data-v=group>Goods group</button><button type=button data-v=building>Building</button></span></label>
  </div>
  <section id=head></section>
  <section class=card><header><h3>Where the money comes from, who gets it, where it goes</h3></header>
    <div class=scroll><div id=sankey class=chart style="height:520px"></div></div>
    <p class=caption>Left to right, in gold per month: what earns the tax base, the tax base, the estates, the state, and what they spend it on.
    Click a good to open it on the goods page. Booked by the game: the state's income and budget lines, every estate's ledger, each location's tax.
    Worked out: the split by good (a building's profit goes to its goods by output value, what is left of a location's tax base to its RGO, and
    Province Food stays with the crop); off the budget, which no line of the save holds (income - expense - the monthly change of the treasury since
    the last save; it follows the growth of building capital). "Spent above income": an estate's ledger below zero; peasants' gold stays near zero
    while their ledger runs far below it, so part of their pop needs is not really paid.</p></section>
  <section class=card><header><h3>Where the tax base comes from</h3></header><div class=table-wrap id=stable></div>
    <p class=caption>Click a good for the buildings behind it; a good's name opens it on the goods page. RGO: what a location's tax base holds above its buildings' profit.
    To the state: the tax of each location, shared out by its sources, at the rate its estates paid. Trade: profit on the routes by price gap, scaled to the trade income booked; an estimate.
    Buildings with no goods (Cookshops, logistics, labour yards, Taverns) stand on their own.</p></section>
  <div class=split>
    <section class=card><header><h3>State income</h3></header><div class=table-wrap id=income></div>
      <p class=caption>Coin minting, unlabelled: income no line of the save names, most of it coin minting.</p></section>
    <section class=card><header><h3>State spending</h3></header><div class=table-wrap id=spending></div>
      <p class=caption>The budget lines at their real cost last month; other, unlabelled: expense no line names. Off budget and the treasury: see above.</p></section>
  </div>
  <section class=card><header><h3>Estates</h3></header><div class=table-wrap id=etable></div>
    <p class=caption>Last month's ledger of the estates; balance = the incomes minus the expenses, exactly as the game books it. Gold is a stock.</p></section>
  <section class=card><header><h3>Over the run</h3><div class=views id=timeviews><button type=button>State income</button><button type=button>State spending</button><button type=button>Estate income</button><button type=button>Estate spending</button><button type=button>Tax base by good</button><button type=button>Gold held</button><button type=button>Wealth</button><button type=button>Per million people</button></div></header>
    <div id=time class=chart style="height:420px"></div>
    <p class=caption>Per save; the dashed line marks the chosen save. Gold held and wealth are stocks, the others gold per month. Goods in markets: world and regions only.
    Tax base by good: the ten largest goods of this scope.</p></section>
  <section class=card id=partscard><header><h3 id=partstitle>By world region</h3></header><div id=parts class=chart style="height:320px"></div>
    <p class=caption>A country counts in the region of its capital. Click to open it.</p></section>
</div>
</div>
<script src="{ECHARTS_URL}"></script>
<script>{LOADER_JS}{BUDGET_JS}</script>
</body></html>
"""
