"""Self-contained inspector for the start-state budget and sensitivity runs."""

import json


def write(folder, summary, provinces, locations):
    payload = json.dumps(
        {"summary": summary, "provinces": provinces, "locations": locations},
        separators=(",", ":"),
    ).replace("<", "\\u003c")
    page = r"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Starting food and logistics</title><style>
:root{color-scheme:dark}body{background:#101b22;color:#e6efec;font:15px/1.5 system-ui;margin:0;padding:32px;max-width:1450px;margin:auto}h1{font-size:34px;margin:0}h2{margin-top:32px}p{max-width:1050px;color:#b7c8c8}label{margin-right:24px}input,select{padding:9px;background:#1c303b;color:inherit;border:1px solid #526870;border-radius:6px}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:8px;border-bottom:1px solid #2a414c}th{color:#9cc1bc}td.num{text-align:right}.cards{display:flex;flex-wrap:wrap;gap:12px;margin:20px 0}.card{background:#1c303b;border-radius:10px;padding:16px;min-width:180px}.card b{font-size:24px;display:block}.bad{color:#ffad94}.good{color:#9cdfbb}.scroll{max-height:550px;overflow:auto}a{color:#9cdbdb}svg{background:#142730;width:100%;border-radius:8px}small{color:#a0b5b9}
</style><h1>Starting food and logistics</h1><p>Cap-checked starting buildings and a monthly food budget. Change subsistence to compare the <b>same placement</b> under different yields. This is an offline estimate: it does not simulate RGO hiring, market prices, seasonal harvests or the engine’s exact market borders.</p>
<div id="cards" class="cards"></div>
<label>Subsistence <select id="factor"></select></label><label>Find region, province or owner <input id="search" placeholder="e.g. london, england or CHI"></label><label><input type="checkbox" id="short" checked> Shortages only</label>
<h2>Province food coverage</h2><p>Dots are province centres. Red means food missing; amber is fed but below the reserve target; green meets the target. Hover for province details.</p><svg id="map" viewBox="0 0 1080 450" role="img" aria-label="World distribution of projected food shortages"></svg>
<div class="scroll"><table><thead><tr><th>Province</th><th>Owner</th><th>Region</th><th>Trade catchment</th><th>Demand</th><th>Supply</th><th>Missing</th><th>Coverage</th></tr></thead><tbody id="provinces"></tbody></table></div>
<h2>Import and export infrastructure</h2><p>Live caps include initialized navigation bonuses. Starting caps use the safe pre-initialization limit. Both market types transfer the same food per fully staffed level; imports are backed by exports within the estimated catchment.</p><div class="scroll"><table><thead><tr><th>Location</th><th>Rank</th><th>Region</th><th>Import levels / live cap</th><th>Export levels / live cap</th><th>Development</th></tr></thead><tbody id="locations"></tbody></table></div>
<h2>Audit and downloads</h2><div id="audit"></div><p><a href="provinces.csv">Province budget CSV</a> · <a href="building_caps.csv">Every placed building and cap</a> · <a href="clamped_buildings.csv">Removed excess starting levels</a> · <a href="subsistence_sensitivity.csv">Sensitivity CSV</a> · <a href="report.json">Full report</a></p>
<script id="data" type="application/json">PAYLOAD</script><script>
const D=JSON.parse(document.querySelector('#data').textContent),S=D.summary;
const n=x=>Number(x).toLocaleString(undefined,{maximumFractionDigits:2}),label=x=>String(x||'').replaceAll('_',' '),esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const select=document.querySelector('#factor');select.innerHTML=S.subsistence_sensitivity.map(x=>`<option value="${x.subsistence}" ${x.subsistence===S.subsistence_define?'selected':''}>${x.subsistence}</option>`).join('');
document.querySelector('#audit').innerHTML=`<p><b>${n(S.building_rows_audited)}</b> building rows checked; <b>${S.over_cap_rows}</b> above the evaluated cap. Removed ${n(S.clamped_levels)} excess levels. Import/export transfer: ${n(S.market_import_food)} food.</p><ul>${S.assumptions.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;
function draw(){const factor=Number(select.value),q=document.querySelector('#search').value.toLowerCase(),only=document.querySelector('#short').checked;
 const rows=D.provinces.map(r=>{const supply=r.supply+(factor-S.subsistence_define)*r.subsistence_workers_k;return {...r,supply,shortfall:Math.max(0,r.demand-supply),coverage:r.demand?supply/r.demand:1}});
 const shortage=rows.reduce((s,r)=>s+r.shortfall,0),demand=rows.reduce((s,r)=>s+r.demand,0);
 document.querySelector('#cards').innerHTML=[['Food requirement covered',n(100*(1-shortage/demand))+'%'],['Food missing / month',n(shortage)],['Province groups short',n(rows.filter(r=>r.shortfall>1e-6).length)],['Subsistence',n(factor)]].map(([k,v])=>`<div class="card"><b>${v}</b>${k}</div>`).join('');
 const filtered=rows.filter(r=>(!only||r.shortfall>1e-6)&&JSON.stringify(r).toLowerCase().includes(q)).sort((a,b)=>b.shortfall-a.shortfall||a.coverage-b.coverage);
 document.querySelector('#provinces').innerHTML=filtered.map(r=>`<tr><td>${esc(label(r.province))}</td><td>${esc(r.owner)}</td><td>${esc(label(r.region))}</td><td>${esc(label(r.catchment))}</td><td class="num">${n(r.demand)}</td><td class="num">${n(r.supply)}</td><td class="num bad">${n(r.shortfall)}</td><td class="num">${n(r.coverage*100)}%</td></tr>`).join('');
 let map='';for(let lon=-180;lon<=180;lon+=30){let x=(lon+180)*3;map+=`<path d="M${x} 0V450" stroke="#29414c" stroke-width=".4"/>`}for(let lat=-60;lat<=90;lat+=30){let y=(90-lat)*3;map+=`<path d="M0 ${y}H1080" stroke="#29414c" stroke-width=".4"/>`}
 for(const r of filtered){let x=(r.longitude+180)*3,y=(90-r.latitude)*3,color=r.shortfall>1e-6?'#ee997e':r.coverage<S.food_target_ratio?'#dcc379':'#71bba8';map+=`<circle cx="${x}" cy="${y}" r="${r.shortfall>1?2.5:1.4}" fill="${color}" opacity=".8"><title>${esc(label(r.province))} (${esc(r.owner)}): ${n(r.coverage*100)}%; missing ${n(r.shortfall)}</title></circle>`}document.querySelector('#map').innerHTML=map;
 document.querySelector('#locations').innerHTML=D.locations.filter(r=>(r.import_levels||r.export_levels)&&JSON.stringify(r).toLowerCase().includes(q)).sort((a,b)=>(b.import_levels+b.export_levels)-(a.import_levels+a.export_levels)).map(r=>`<tr><td>${esc(label(r.location_tag))}</td><td>${esc(label(r.rank))}</td><td>${esc(label(r.region))}</td><td>${r.import_levels} / ${r.import_cap}</td><td>${r.export_levels} / ${r.export_cap}</td><td>${n(r.development)}</td></tr>`).join('');}
for(const id of ['factor','search','short'])document.querySelector('#'+id).addEventListener('input',draw);draw();
</script></html>"""
    (folder / "index.html").write_text(
        page.replace("PAYLOAD", payload), encoding="utf-8"
    )
