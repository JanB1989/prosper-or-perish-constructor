"""The knowledge and work page of the run report (`knowledge.html`): technology, literacy, schools, classes and jobs.

Static HTML + one script; the data comes from `knowledge/index.js`, `knowledge/summary.js` (world and world regions) and
`knowledge/c<n>.js` per country, loaded when it is opened (written by `run_report_knowledge`). Layout as the budget
page: the world, the regions and the largest countries of the chosen save on the left, the save on top, then for the
chosen scope one card per block, each over the run with the tables at the chosen save. State lives in the URL hash.
"""

from __future__ import annotations

import html

from prosper_or_perish_constructor.run_report import ECHARTS_URL, PAGE_CSS
from prosper_or_perish_constructor.run_report_budget_page import BUDGET_CSS
from prosper_or_perish_constructor.run_report_data import LOADER_JS
from prosper_or_perish_constructor.run_report_goods_page import GOODS_CSS

KNOWLEDGE_CSS = r"""
.card .views + .views{margin-left:auto}
td.lead{white-space:nowrap}
"""

KNOWLEDGE_JS = r"""
(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const dark = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches;
  const INK = dark ? '#eceef0' : '#1d1d1b', MUTED = dark ? '#a0a6b0' : '#6b6b67', WORLD = dark ? '#eceef0' : '#1d1d1b';
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
  const lit = v => (v == null || !isFinite(v)) ? '–' : v.toFixed(1) + '%';  // literacy is 0..100
  const people = v => v == null ? '–' : num(v * 1000);  // the data is in thousands
  const FORMAT = {pct, lit, people, num};

  let IX = null, SUM = null;
  const SERIES = new Map();
  const S = {k: 0, s: 0, tv: 0, rv: 0, lv: 0, ev: 0, cv: 0, c: 'burghers'};
  const scopeIndex = new Map(), charts = {};
  const scope = i => IX.scopes[i] || {name: '?'};

  function seriesOf(k) {
    if (!SERIES.has(k)) {
      const sc = scope(k);
      SERIES.set(k, sc.file ? loadData(sc.file).catch(() => null) : Promise.resolve(SUM ? SUM[String(k)] || null : null));
    }
    return SERIES.get(k);
  }
  const at = (E, key, i = S.s) => (E && E[key] ? E[key][i] : null);

  // ---------------------------------------------------------------- charts
  const saveTime = i => { const d = String(IX.saves[i].date || IX.saves[i].label).split('.').map(Number); return Date.UTC(d[0], (d[1] || 1) - 1, d[2] || 1); };
  function chart(id) {
    if (!charts[id]) {
      const el = document.getElementById(id);
      charts[id] = echarts.init(el, dark ? 'dark' : null);
      new ResizeObserver(() => charts[id].resize()).observe(el);
    }
    return charts[id];
  }
  const line = (name, color, values, extra = {}) => ({name, color, values: values || [], ...extra});
  function lines(id, series, unit, opts = {}) {
    const el = chart(id);
    const xs = IX.saves.map((s, i) => saveTime(i));
    const fmt = FORMAT[unit] || num;
    const out = series.filter(s => s.values.some(v => v != null)).map(s => ({
      type: 'line', name: s.name, color: s.color, showSymbol: false, emphasis: {focus: 'series'},
      lineStyle: {width: s.width || 2, type: s.dashed ? 'dashed' : 'solid'},
      data: s.values.map((v, j) => [xs[j], v == null ? null : v]),
    }));
    if (!out.length) { el.clear(); el.setOption({title: {text: 'No data for this choice', left: 'center', top: 'middle', textStyle: {color: MUTED, fontSize: 13, fontWeight: 'normal'}}}, true); return; }
    out[0].markLine = {silent: true, symbol: 'none', label: {show: false}, lineStyle: {type: 'dashed', color: MUTED, width: 1}, data: [{xAxis: xs[S.s]}]};
    const y = {type: 'value', axisLabel: {formatter: v => fmt(v)}};
    if (opts.max != null) y.max = opts.max;
    if (opts.min != null) y.min = opts.min; else y.min = 0;
    el.setOption({
      backgroundColor: 'transparent', tooltip: {trigger: 'axis', confine: true, valueFormatter: v => fmt(v)},
      legend: {type: 'scroll', top: 0, left: 0, right: 0, textStyle: {color: INK}},
      grid: {left: 8, right: 16, top: 40, bottom: 30, containLabel: true},
      xAxis: {type: 'time', min: xs[0], max: xs[xs.length - 1], axisLabel: {formatter: v => String(new Date(v).getUTCFullYear()), hideOverlap: true}},
      yAxis: y, series: out,
    }, true);
  }
  const regions = () => IX.scopes.map((s, i) => i).filter(i => IX.scopes[i].kind === 'region' && SUM[String(i)]);

  // ---------------------------------------------------------------- technology
  function techChart(E) {
    const views = [
      () => lines('tech', [line('Research points held', '#2a78d6', E.tech_share, {width: 3}), line('Advances held', '#eb6834', (E.tech_held || []).map(v => v == null ? null : v / IX.tree.n))], 'pct', {max: 1}),
      () => lines('tech', IX.ages.map((a, i) => line(a.name, ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#4a3aa7'][i % 6], E['tech_age_' + i])), 'pct', {max: 1}),
      () => lines('tech', [line(scope(S.k).kind === 'country' ? 'Research points held' : 'Research points per person', '#2a78d6', E.tech_points, {width: 3})], 'num'),
    ];
    views[S.tv]();
  }
  function regionChart() {
    const key = ['tech_share', 'tech_points', 'lit_all', 'vs_share'][S.rv];
    const unit = ['pct', 'num', 'lit', 'pct'][S.rv];
    const W = SUM['0'] || {};
    lines('regions', [line('World', WORLD, W[key], {width: 3}), ...regions().map(i => line(scope(i).name, scope(i).color, SUM[String(i)][key], {width: 1.6}))], unit, S.rv === 1 ? {} : {max: unit === 'lit' ? 100 : 1});
  }
  function spreadChart(E) {
    const card = $('#spreadcard');
    card.hidden = scope(S.k).kind === 'country';
    if (card.hidden) return;
    const shades = ['#9ec5f4', '#6da7ec', WORLD, '#256abf', '#123055'];
    const labels = {q10: '10th percentile', q25: '25th percentile', q50: 'Median', q75: '75th percentile', q90: '90th percentile'};
    lines('spread', [line('Highest country', '#9a9a96', E.qmax, {dashed: true}), ...IX.quantiles.slice().reverse().map((q, j) => line(labels[q.id], shades[IX.quantiles.length - 1 - j], E[q.id], {width: q.id === 'q50' ? 3 : 1.8}))], 'pct', {max: 1});
  }
  function leadersTable() {
    const rows = IX.saves[S.s].leaders || [];
    if (!rows.length) return '<div class=empty>No researched advances in this save.</div>';
    return `<table class=gt><thead><tr><th>Country</th><th class=num>People</th><th class=num title="Research cost of every advance held, summed">Research points</th><th class=num title="Points held of the tree">Share of the tree</th><th class=num>Advances of the tree</th></tr></thead><tbody>` +
      rows.map(([name, pop, points, share, n]) => `<tr class="grp flat"><td>${esc(name)}</td><td class=num>${people(pop)}</td><td class=num>${num(points)}</td><td class=num>${sbar(share)}${pct(share)}</td><td class=num>${num(n)} of ${IX.tree.n}</td></tr>`).join('') + '</tbody></table>';
  }

  // ---------------------------------------------------------------- literacy
  function litChart(E) {
    if (S.lv === 0) lines('lit', [line('All people', WORLD, E.lit_all, {width: 3}), ...IX.popTypes.map(p => line(p.name, p.color, E['lit_' + p.id]))], 'lit', {max: 100});
    else lines('lit', [line('All people', WORLD, E.low_all, {width: 3}), ...IX.popTypes.map(p => line(p.name, p.color, E['low_' + p.id]))], 'pct', {max: 1});
  }
  function regionTable(cells) {
    const rows = [0, ...regions()].map(i => ({i, E: SUM[String(i)]})).filter(r => r.E);
    return rows.map(r => `<tr class="grp flat"><td class=lead>${scope(r.i).color ? `<i class=dot style="background:${scope(r.i).color}"></i>` : ''}${esc(scope(r.i).name)}</td>${cells(r.E)}</tr>`).join('');
  }
  function litTable() {
    const head = `<table class=gt><thead><tr><th>Region</th><th class=num>All people</th>${IX.popTypes.map(p => `<th class=num>${esc(p.name)}</th>`).join('')}<th class=num title="Share of all people at ${IX.lowLiteracy} % literacy or less">At ${IX.lowLiteracy} % or less</th></tr></thead><tbody>`;
    return head + regionTable(E => `<td class=num>${lit(at(E, 'lit_all'))}</td>${IX.popTypes.map(p => `<td class=num>${lit(at(E, 'lit_' + p.id))}</td>`).join('')}<td class=num>${pct(at(E, 'low_all'))}</td>`) + '</tbody></table>';
  }

  // ---------------------------------------------------------------- schools
  function schoolChart(E) {
    if (S.ev === 0) lines('schools', IX.schools.map(s => line(s.name, s.color, E['lv_' + s.id])), 'num');
    else {
      const W = SUM['0'] || {};
      const series = [line(scope(S.k).name, '#1baf7a', E.vs_share, {width: 3})];
      if (S.k !== 0) series.push(line('World', WORLD, W.vs_share, {dashed: true}));
      lines('schools', series, 'pct', {max: 1});
    }
  }
  function schoolTable() {
    const head = `<table class=gt><thead><tr><th>Region</th>${IX.schools.map(s => `<th class=num>${esc(s.name)}</th>`).join('')}<th class=num title="Owned locations with at least one Village School level">Locations with a Village School</th></tr></thead><tbody>`;
    return head + regionTable(E => `${IX.schools.map(s => `<td class=num>${num(at(E, 'lv_' + s.id))}</td>`).join('')}<td class=num>${sbar(at(E, 'vs_share'))}${pct(at(E, 'vs_share'))}</td>`) + '</tbody></table>';
  }

  // ---------------------------------------------------------------- classes and jobs
  const className = c => (IX.classes.find(x => x.id === c) || {name: c}).name;
  function classChart(E) {
    const c = S.c;
    if (S.cv === 0) lines('classes', [
      line('People', WORLD, E['pop_' + c], {width: 3}), line('At work', '#1baf7a', E['work_' + c]), line('Idle', '#e34948', E['idle_' + c]),
      line('Jobs', '#2a78d6', E['jobs_' + c], {width: 2.5}), line('Jobs filled', '#6da7ec', E['filled_' + c]), line('Jobs unfilled', '#eda100', E['unfilled_' + c]),
      line('Jobs in closed buildings', '#9a9a96', E['closed_jobs_' + c], {dashed: true})], 'people');
    else if (S.cv === 1) lines('classes', IX.classes.map(x => line(x.name, x.color, E['share_' + x.id])), 'pct');
    else lines('classes', IX.classes.map(x => line(x.name, x.color, (E['jobs_' + x.id] || []).map((j, i) => j ? (E['filled_' + x.id][i] || 0) / j : null))), 'pct', {max: 1});
  }
  function classTable(E) {
    const col = [['People', c => people(at(E, 'pop_' + c))], ['Share of all', c => pct(at(E, 'share_' + c))], ['At work', c => people(at(E, 'work_' + c))],
      ['Idle', c => people(at(E, 'idle_' + c))], ['Jobs', c => people(at(E, 'jobs_' + c))], ['Filled', c => people(at(E, 'filled_' + c))],
      ['Unfilled', c => people(at(E, 'unfilled_' + c))], ['Filled share', c => { const j = at(E, 'jobs_' + c); return j ? pct((at(E, 'filled_' + c) || 0) / j) : '–'; }],
      ['In closed buildings', c => people(at(E, 'closed_jobs_' + c))], ['Closed buildings', c => num(at(E, 'closed_' + c))]];
    return `<table class=gt><thead><tr><th>Class</th>${col.map(([h]) => `<th class=num>${esc(h)}</th>`).join('')}</tr></thead><tbody>` +
      IX.classes.map(x => `<tr class="grp flat"><td class=lead><i class=dot style="background:${x.color}"></i>${esc(x.name)}</td>${col.map(([, f]) => `<td class=num>${f(x.id)}</td>`).join('')}</tr>`).join('') + '</tbody></table>';
  }
  const sbar = f => `<span class=sbar><i style="width:${Math.max(0, Math.min(100, (f || 0) * 100)).toFixed(1)}%"></i></span>`;

  // ---------------------------------------------------------------- page
  function tiles(E) {
    const t = [
      ['Share of the tree', pct(at(E, 'tech_share')), `research points held; ${num(at(E, 'tech_held'))} of ${IX.tree.n} advances`],
      ['Literacy', lit(at(E, 'lit_all')), `all people; ${pct(at(E, 'low_all'))} at ${IX.lowLiteracy} % or less`],
      ['Village Schools', num(at(E, 'lv_pp_village_school')), `levels; in ${pct(at(E, 'vs_share'))} of owned locations`],
      ['Burgher jobs filled', (() => { const j = at(E, 'jobs_burghers'); return j ? pct((at(E, 'filled_burghers') || 0) / j) : '–'; })(), `${people(at(E, 'idle_burghers'))} burghers idle`],
      ['Laborer jobs filled', (() => { const j = at(E, 'jobs_laborers'); return j ? pct((at(E, 'filled_laborers') || 0) / j) : '–'; })(), `${people(at(E, 'idle_laborers'))} laborers idle`],
      ['People', people(at(E, 'people')), ''],
    ];
    return t.map(([a, b, c]) => `<div class=tile><div class=label>${esc(a)}</div><div class=value>${esc(b)}</div><div class=sub>${esc(c)}</div></div>`).join('');
  }
  function buildList() {
    const q = $('#search').value.trim().toLowerCase();
    const item = i => {
      const s = scope(i);
      if (q && !s.name.toLowerCase().includes(q)) return '';
      const E = s.kind === 'country' ? null : SUM[String(i)];
      if (s.kind === 'region' && !E) return '';
      const share = E ? pct(at(E, 'tech_share')) : '';
      const pop = E ? people(at(E, 'people')) : '';
      return `<a href="#" data-k="${i}" class="${i === S.k ? 'on' : ''}" title="${esc(s.name)}">${s.color ? `<i style="background:${s.color}"></i>` : ''}<span>${esc(s.name)}</span><span class=share>${share}</span><span class=badge>${pop}</span></a>`;
    };
    let h = `<div class=legend title="Share of the tree held (research points) and people"><span>tree</span><span>people</span></div>`;
    h += item(0) + '<h4>World regions</h4>' + regions().map(item).join('');
    h += '<h4>Largest countries of this save</h4>' + (IX.saves[S.s].top || []).map(item).join('');
    $('#scopelist').innerHTML = h;
  }
  function writeHash() {
    const h = `#k=${encodeURIComponent(scope(S.k).id)}&s=${S.s}&tv=${S.tv}&rv=${S.rv}&lv=${S.lv}&ev=${S.ev}&cv=${S.cv}&c=${S.c}`;
    if (location.hash !== h) history.replaceState(null, '', h);
  }
  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    if (p.has('k') && scopeIndex.has(p.get('k'))) S.k = scopeIndex.get(p.get('k'));
    if (p.has('s')) { const s = Number(p.get('s')); if (s >= 0 && s < IX.saves.length) S.s = s; }
    for (const [key, id] of [['tv', '#techviews'], ['rv', '#regionviews'], ['lv', '#litviews'], ['ev', '#schoolviews'], ['cv', '#classviews']]) {
      if (p.has(key)) { const v = Number(p.get(key)); if (v >= 0 && v < document.querySelectorAll(id + ' button').length) S[key] = v; }
    }
    if (IX.classes.some(c => c.id === p.get('c'))) S.c = p.get('c');
  }
  const VIEWS = [['tv', '#techviews'], ['rv', '#regionviews'], ['lv', '#litviews'], ['ev', '#schoolviews'], ['cv', '#classviews']];
  let token = 0;
  async function render() {
    const mine = ++token;
    writeHash();
    $('#save').value = String(S.s);
    for (const [key, id] of VIEWS) document.querySelectorAll(id + ' button').forEach((b, i) => b.classList.toggle('active', i === S[key]));
    document.querySelectorAll('#classpick button').forEach(b => b.classList.toggle('active', b.dataset.c === S.c));
    buildList();
    const E = await seriesOf(S.k);
    if (mine !== token) return;
    const sc = scope(S.k);
    document.title = `${sc.name} · Knowledge and work · ${IX.run}`;
    if (!E) {
      $('#head').innerHTML = `<div class=ghead><div><h1>${esc(sc.name)}</h1><div class=muted>No figures for this choice.</div></div></div>`;
      return;
    }
    const absent = sc.kind === 'country' && at(E, 'people') == null;
    $('#head').innerHTML = `<div class=ghead><div><h1>${esc(sc.name)}</h1><div class=muted>Knowledge and work · save ${esc(IX.saves[S.s].label)}${absent ? ' · owns no land in this save' : ''}</div></div></div><div class=tiles>${tiles(E)}</div>`;
    techChart(E);
    regionChart();
    spreadChart(E);
    $('#leaders').innerHTML = leadersTable();
    litChart(E);
    $('#littable').innerHTML = litTable();
    schoolChart(E);
    $('#schooltable').innerHTML = schoolTable();
    $('#classtitle').textContent = `Classes and jobs: ${className(S.c)}`;
    classChart(E);
    $('#classtable').innerHTML = classTable(E);
  }
  function select(k) { S.k = k; render(); window.scrollTo({top: 0}); }

  async function init() {
    try {
      IX = await loadData('knowledge/index.js');
      SUM = await loadData('knowledge/summary.js');
    } catch (err) {
      $('#head').innerHTML = '<div class=empty>The knowledge data did not load. This page reads files next to it, so open it from the published site or over a local web server.</div>';
      return;
    }
    IX.scopes.forEach((s, i) => scopeIndex.set(s.id, i));
    S.s = IX.saves.length - 1;
    readHash();
    $('#runname').textContent = `${IX.run} · ${IX.years[0]}–${IX.years[1]}`;
    $('#treenote').textContent = `${IX.tree.n} advances, ${num(IX.tree.points)} research points`;
    $('#save').innerHTML = IX.saves.map((s, i) => `<option value="${i}">${esc(s.label)}</option>`).join('');
    $('#save').addEventListener('change', e => { S.s = Number(e.target.value); render(); });
    $('#prev').addEventListener('click', () => { if (S.s > 0) { S.s--; render(); } });
    $('#next').addEventListener('click', () => { if (S.s < IX.saves.length - 1) { S.s++; render(); } });
    for (const [key, id] of VIEWS) document.querySelectorAll(id + ' button').forEach((b, i) => b.addEventListener('click', () => { S[key] = i; render(); }));
    $('#classpick').innerHTML = IX.classes.map(c => `<button type=button data-c="${c.id}">${esc(c.name)}</button>`).join('');
    document.querySelectorAll('#classpick button').forEach(b => b.addEventListener('click', () => { S.c = b.dataset.c; S.cv = 0; render(); }));
    $('#search').addEventListener('input', buildList);
    document.addEventListener('click', e => {
      const a = e.target.closest('.klist a[data-k]');
      if (a) { e.preventDefault(); select(Number(a.dataset.k)); }
    });
    window.addEventListener('hashchange', () => { readHash(); render(); });
    render();
  }
  init();
})();
"""


def knowledge_page_html(run_name: str, years: tuple[int, int]) -> str:
    esc = html.escape
    title = f"Knowledge and work · {esc(run_name)} · {years[0]}–{years[1]} · Prosper or Perish"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="robots" content="noindex">
<style>{PAGE_CSS}{GOODS_CSS}{BUDGET_CSS}{KNOWLEDGE_CSS}</style></head><body>
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
    <span>The tree: <span id=treenote></span></span>
  </div>
  <section id=head></section>

  <h2 id=technology>Technology</h2>
  <p class=lead>Research points are the research cost of every advance a country holds, summed (the cost while the advance's
  age is current). The tree is every advance any country can research: the general advances of all ages, free or gated
  by an institution (or by an institution or geography). Advances locked to countries, cultures, religions or governments
  are not in it; a country holding some counts them in its points, not in its share of the tree. World and regions: the
  mean over the people of the owned land, each location counting its owner.</p>
  <section class=card><header><h3>Technology over the run</h3><div class=views id=techviews><button type=button>Share of the tree</button><button type=button>By age</button><button type=button>Research points</button></div></header>
    <div id=tech class=chart style="height:400px"></div>
    <p class=caption>Share of the tree: the research points held of the tree's points, and the advances held of its advances. By age:
    the points held of each age's part of the tree. Research points: all points held, advances outside the tree included (world and regions: per person).
    The dashed line marks the chosen save.</p></section>
  <section class=card><header><h3>World regions compared</h3><div class=views id=regionviews><button type=button>Share of the tree</button><button type=button>Research points per person</button><button type=button>Literacy</button><button type=button>Village Schools</button></div></header>
    <div id=regions class=chart style="height:460px"></div>
    <p class=caption>The world and every world region over the run, whichever scope is chosen: the tree share and research points of the owners (per person), the literacy of all people, the share of owned locations with a Village School.</p></section>
  <section class=card id=spreadcard><header><h3>How evenly the people share the tree</h3></header>
    <div id=spread class=chart style="height:380px"></div>
    <p class=caption>The people of the chosen scope ranked by their owner's share of the tree: a tenth of them live under owners with at most
    the 10th percentile's share, half with at most the median's. Dashed: the highest any owner holds there.</p></section>
  <section class=card><header><h3>Leading countries at the chosen save</h3></header><div class=table-wrap id=leaders></div>
    <p class=caption>The countries with the most research points of the tree; land owners only, between equal points the larger country first.</p></section>

  <h2 id=literacy>Literacy</h2>
  <p class=lead>The literacy of the pops, weighted by their size; unowned land counts.</p>
  <section class=card><header><h3>Literacy by pop type</h3><div class=views id=litviews><button type=button>Literacy</button><button type=button>At 5 % or less</button></div></header>
    <div id=lit class=chart style="height:420px"></div>
    <p class=caption>Literacy: each pop type's mean literacy and that of all people. At 5 % or less: the share of each pop type's people whose pop has a literacy of 5 % or less.</p></section>
  <section class=card><header><h3>Literacy by world region at the chosen save</h3></header><div class=table-wrap id=littable></div>
    <p class=caption>Mean literacy per pop type; the last column is the share of all people at 5 % or less.</p></section>

  <h2 id=education>Education buildings</h2>
  <p class=lead>Levels of the schools and places of learning, and how many owned locations have a Village School.</p>
  <section class=card><header><h3>Schools over the run</h3><div class=views id=schoolviews><button type=button>Levels</button><button type=button>Locations with a Village School</button></div></header>
    <div id=schools class=chart style="height:400px"></div>
    <p class=caption>Levels: the building levels standing (open or closed). Locations with a Village School: the share of owned locations with at least one level.</p></section>
  <section class=card><header><h3>Schools by world region at the chosen save</h3></header><div class=table-wrap id=schooltable></div>
    <p class=caption>Building levels per region; the last column is the share of the region's owned locations with a Village School.</p></section>

  <h2 id=jobs>Classes and jobs</h2>
  <p class=lead>Each class's people, how many work and how many are idle, and the jobs open to them. A building's jobs are its level times
  its employment size for the class it employs; its workers fill them, and a closed building's jobs stay unfilled. The RGOs' places count as
  laborer jobs (slaves fill some of them where they may work there). The share of all people is what promotion and demotion leave; the
  saves hold no promotion or demotion flows by cause.</p>
  <section class=card><header><h3 id=classtitle>Classes and jobs</h3><div class=views id=classpick></div><div class=views id=classviews><button type=button>People and jobs</button><button type=button>Share of all people</button><button type=button>Jobs filled</button></div></header>
    <div id=classes class=chart style="height:440px"></div>
    <p class=caption>People and jobs (for the class picked): its people, those at work and those idle, its jobs, filled and unfilled, and the jobs in closed buildings.
    Share of all people: every class. Jobs filled: the filled share of every class's jobs.</p></section>
  <section class=card><header><h3>Classes at the chosen save</h3></header><div class=table-wrap id=classtable></div>
    <p class=caption>At work = people - idle. Jobs in closed buildings count as unfilled; closed buildings: how many buildings of the class are closed.</p></section>
</div>
</div>
<script src="{ECHARTS_URL}"></script>
<script>{LOADER_JS}{KNOWLEDGE_JS}</script>
</body></html>
"""
