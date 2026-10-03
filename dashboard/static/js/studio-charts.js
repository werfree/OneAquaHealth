// Shared by the dashboard and standalone Surveillance Studio.
export function createChartRenderer({ add, tip }) {
const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=n=>n==null?"—":Math.abs(n)>=10000?Math.round(n).toLocaleString():Math.abs(n)>=100?String(Math.round(n)):String(+n.toFixed(2));
const hover=(el,html)=>{el.addEventListener("mousemove",e=>{tip.innerHTML=html;
  tip.style.left=Math.min(innerWidth-240,e.clientX+13)+"px";tip.style.top=Math.max(0,e.clientY-8)+"px";tip.classList.add("on");});
  el.addEventListener("mouseleave",()=>tip.classList.remove("on"));};
const LBL={faecal_coliform:"Faecal coliform",bod:"BOD",dissolved_oxygen:"Dissolved oxygen",
  ammoniacal_nitrogen:"Ammoniacal N",ph:"pH",chromium_total:"Chromium",
  acute_diarrhoeal_disease:"Acute diarrhoeal disease"};
const SHORT={faecal_coliform:"Coliform",bod:"BOD",dissolved_oxygen:"DO",ammoniacal_nitrogen:"NH₃-N",ph:"pH",chromium_total:"Cr"};
const RAMP=["--s1","--s2","--s3","--s4","--s5","--s6"];

function shell(title,caption,body,legend){
  return `<div class="viz"><div class="viz-h"><div class="viz-t">${esc(title)}</div>
    ${caption?`<div class="viz-c">${esc(caption)}</div>`:""}</div>
    <div class="viz-b">${body}</div>${legend?`<div class="legend">${legend}</div>`:""}</div>`;
}

function draw(s){
  if(s.type==="stats")   return drawStats(s);
  if(s.type==="matrix")  return drawMatrix(s);
  if(s.type==="ranking") return drawRanking(s);
  if(s.type==="trend")   return drawTrend(s);
  if(s.type==="scatter") return drawScatter(s);
  if(s.type==="profile") return drawProfile(s);
  if(s.type==="persistence") return drawPersistence(s);
}

/* River longitudinal profile. Stations in flow order on a distance axis, with
   the step between consecutive stations called out — that step is what names
   the stretch a load enters on. Log scale because coliform spans two orders of
   magnitude along one river and a linear axis flattens the upstream station to
   the floor. */
function drawProfile(s){
  const d=s.data||{},pts=(d.points||[]).filter(p=>p.mean!=null);
  if(pts.length<2){add(shell("River profile",s.caption,'<div style="color:var(--label-3)">Not enough stations with readings on this river.</div>'));return;}
  const W=820,H=300,L=60,R=130,T=24,B=48;
  const lg=v=>Math.log10(Math.max(v,1));
  const vals=pts.map(p=>p.mean).concat(d.threshold?[d.threshold]:[]);
  const lo=lg(Math.min(...vals))-.25, hi=lg(Math.max(...vals))+.25;
  const kms=pts.map(p=>p.flow_km||0), kmax=Math.max(...kms)||1;
  const X=k=>L+(k/kmax)*(W-L-R), Y=v=>T+(1-(lg(v)-lo)/(hi-lo))*(H-T-B);
  const ticks=[];for(let e=Math.floor(lo);e<=Math.ceil(hi);e++)ticks.push(Math.pow(10,e));

  const el=add(shell(`${esc(d.river)} — ${esc(LBL[d.indicator]||d.indicator)} in flow order`,s.caption,
    `<svg class="v" viewBox="0 0 ${W} ${H}">
      ${ticks.filter(t=>lg(t)>=lo&&lg(t)<=hi).map(t=>
        `<line class="gl" x1="${L}" y1="${Y(t).toFixed(1)}" x2="${W-R}" y2="${Y(t).toFixed(1)}"/>
         <text class="ax" x="${L-8}" y="${(Y(t)+3.5).toFixed(1)}" text-anchor="end">${fmt(t)}</text>`).join("")}
      ${d.threshold?`<line class="thr" stroke="var(--critical)" x1="${L}" y1="${Y(d.threshold).toFixed(1)}" x2="${W-R}" y2="${Y(d.threshold).toFixed(1)}"/>
        <text class="ax" fill="var(--critical)" x="${W-R+6}" y="${(Y(d.threshold)+3.5).toFixed(1)}">Criterion ${fmt(d.threshold)}</text>`:""}
      <path d="${pts.map((p,i)=>`${i?"L":"M"}${X(p.flow_km||0).toFixed(1)},${Y(p.mean).toFixed(1)}`).join(" ")}"
        fill="none" stroke="var(--water)" stroke-width="2.5" stroke-linejoin="round"/>
      ${pts.map(p=>{const x=X(p.flow_km||0),y=Y(p.mean);
        const c=p.exceeds?(p.factor>=4?"var(--critical)":"var(--warning)"):"var(--good)";
        return `<g data-t="${esc(p.name)}<br>${fmt(p.mean)} ${esc(d.unit||"")}${p.factor?` · ${p.factor}× criterion`:" · within criteria"}<br>${esc(p.position_note||"")}">
          <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="7" fill="${c}" stroke="#fff" stroke-width="2.5"/>
          <text class="ax" x="${x.toFixed(1)}" y="${(y-14).toFixed(1)}" text-anchor="middle" fill="var(--label)" font-weight="600">${fmt(p.mean)}</text>
          <text class="ax" x="${x.toFixed(1)}" y="${H-B+16}" text-anchor="middle">${esc((p.name.split(" at ")[1]||p.name).slice(0,14))}</text>
          <text class="ax" x="${x.toFixed(1)}" y="${H-B+29}" text-anchor="middle" fill="var(--label-3)">${p.flow_km||0} km</text>
        </g>`;}).join("")}
      ${pts.slice(1).map((p,i)=>{const st=d.points.find(q=>q.site_id===p.site_id)?.step_from_previous;
        if(!st||!st.ratio||st.ratio<1.5)return "";
        const x0=X(pts[i].flow_km||0),x1=X(p.flow_km||0),ym=Math.min(Y(pts[i].mean),Y(p.mean))-30;
        return `<g><line x1="${x0}" y1="${ym+8}" x2="${x1}" y2="${ym+8}" stroke="var(--critical)" stroke-width="1.5"/>
          <text class="ax" x="${((x0+x1)/2).toFixed(1)}" y="${ym+3}" text-anchor="middle" fill="var(--critical)" font-weight="600">×${st.ratio} over ${st.reach_km} km</text></g>`;}).join("")}
      <text class="ax" x="${L+(W-L-R)/2}" y="${H-6}" text-anchor="middle">downstream distance →</text>
    </svg>`,
    `<span class="lg"><span class="sq" style="border-radius:50%;background:var(--good)"></span>within criteria</span>
     <span class="lg"><span class="sq" style="border-radius:50%;background:var(--warning)"></span>exceeds</span>
     <span class="lg"><span class="sq" style="border-radius:50%;background:var(--critical)"></span>≥4× criterion</span>
     <span class="lg">log scale</span>
     <span class="lg" style="flex-basis:100%;color:var(--label-3)">${esc(d.note||"")}</span>`));
  el.querySelectorAll("g[data-t]").forEach(g=>hover(g,g.dataset.t));
}

/* Day-by-day strip per station: a one-off exceedance and a month-long condition
   look identical in a latest-value view and call for different responses. */
function drawPersistence(s){
  const d=s.data||{},st=(d.stations||[]).filter(x=>x.days_measured);
  if(!st.length){add(shell("Persistence",s.caption,'<div style="color:var(--label-3)">No readings in this window.</div>'));return;}
  const el=add(shell(`Days above criterion — ${esc(LBL[d.indicator]||d.indicator)}`,s.caption,
    `<div style="display:flex;flex-direction:column;gap:9px">
      ${st.map(x=>`<div style="display:flex;align-items:center;gap:10px">
        <div style="width:150px;flex:none;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(x.name)}</div>
        <div style="flex:1;display:flex;gap:2px;min-width:0" data-t="${esc(x.name)}<br>${x.days_over} of ${x.days_measured} sampling days above criterion<br>longest run ${x.longest_run} days">
          ${x.daily.map(c=>`<div style="flex:1;height:18px;border-radius:2px;min-width:2px;
            background:${c.over?"var(--critical)":"var(--ok-w)"}" title="${esc(c.date)}: ${fmt(c.value)}"></div>`).join("")}
        </div>
        <div style="width:96px;flex:none;text-align:right;font-size:12px;font-variant-numeric:tabular-nums">
          <b style="color:${x.pct_over>70?"var(--critical)":x.pct_over>0?"var(--warning)":"var(--good)"}">${x.days_over}/${x.days_measured}</b>
          <span style="color:var(--label-3)"> days</span></div>
      </div>`).join("")}
    </div>`,
    `<span class="lg"><span class="sq" style="background:var(--critical)"></span>above criterion</span>
     <span class="lg"><span class="sq" style="background:var(--ok-w)"></span>within</span>
     <span class="lg" style="color:var(--label-3)">each cell is one sampling day, oldest at left</span>
     <span class="lg" style="flex-basis:100%;color:var(--label-3)">${esc(d.threshold_basis||"")}</span>`));
  el.querySelectorAll("[data-t]").forEach(g=>hover(g,g.dataset.t));
}

function drawStats(s){
  add(shell("Headline figures",s.caption,
    `<div class="tiles">${(s.items||[]).map(i=>`<div class="tile">
      <div class="tile-l">${esc(i.label)}</div>
      <div class="tile-v"${i.alarm?' style="color:var(--critical)"':""}>${esc(i.value)}</div>
      ${i.detail?`<div class="tile-d">${esc(i.detail)}</div>`:""}</div>`).join("")}</div>`));
}

function drawMatrix(s){
  const inds=s.indicators||[];
  const bg=f=>f==null?"var(--ok-w)":`var(${RAMP[f<1.5?0:f<2.5?1:f<4?2:f<6?3:f<10?4:5]})`;
  const fg=f=>(f!=null&&f>=4)?"#fff":"var(--label)";
  const el=add(shell("Severity matrix",s.caption,
    `<div style="overflow-x:auto"><table class="mx"><thead><tr><th></th>
      ${inds.map(i=>`<th>${esc(SHORT[i]||i)}</th>`).join("")}<th>ADD Δ</th></tr></thead><tbody>
      ${(s.rows||[]).map(r=>`<tr><td class="lbl">${esc(r.name)}</td>
        ${inds.map(i=>{const v=(r.readings||{})[i];
          if(!v) return `<td class="cell na" data-t="not measured">–</td>`;
          return `<td class="cell" style="background:${bg(v.factor)};color:${fg(v.factor)}"
            data-t="${esc(r.name)} · ${esc(LBL[i]||i)}<br>${fmt(v.value)} ${esc(v.unit||"")}${v.factor?` · ${v.factor}× criterion`:" · within criteria"}">
            ${v.factor?v.factor+"×":"✓"}</td>`;}).join("")}
        <td class="cell" style="background:${r.add_change_pct>15?"var(--crit-w)":r.add_change_pct>0?"var(--warn-w)":"var(--bg-2)"};
            color:${r.add_change_pct>15?"var(--critical)":"var(--label)"}" data-t="change in notified ADD">
          ${r.add_change_pct==null?"–":(r.add_change_pct>0?"+":"")+r.add_change_pct+"%"}</td></tr>`).join("")}
    </tbody></table></div>`,
    `<span class="lg"><span class="sq" style="background:var(--ok-w)"></span>within criteria</span>`+
    [["<1.5×","--s1"],["2.5×","--s2"],["4×","--s3"],["6×","--s4"],["10×","--s5"],["≥10×","--s6"]]
      .map(([l,v])=>`<span class="lg"><span class="sq" style="background:var(${v})"></span>${l}</span>`).join("")));
  el.querySelectorAll(".cell[data-t]").forEach(c=>hover(c,c.dataset.t));
}

function drawRanking(s){
  const w=s.wards||[]; if(!w.length) return;
  const worst=x=>Math.max(0,...(x.exceedances||[]).map(e=>e.factor||0));
  const mx=Math.max(1,...w.map(worst)), W=820,L=170,R=58,H=w.length*36+30;
  const el=add(shell("Wards by worst exceedance",s.caption,
    `<svg class="v" viewBox="0 0 ${W} ${H}">
      ${[0,.5,1].map(t=>{const x=L+t*(W-L-R);return `<line class="gl" x1="${x}" y1="16" x2="${x}" y2="${H-12}"/>
        <text class="ax" x="${x}" y="11" text-anchor="middle">${(t*mx).toFixed(1)}×</text>`;}).join("")}
      ${w.map((x,i)=>{const y=30+i*36,f=worst(x),bw=(f/mx)*(W-L-R);
        const c=f>=4?"var(--critical)":f>=2?"var(--warning)":f>0?"var(--s3)":"var(--sep)";
        const ch=x.add_change_pct;
        return `<g data-t="${esc(x.name)}<br>${(x.exceedances||[]).length} exceedance(s) · ADD ${ch==null?"–":ch+"%"}">
          <text class="axb" x="${L-10}" y="${y+4}" text-anchor="end">${esc(x.name.length>25?x.name.slice(0,24)+"…":x.name)}</text>
          <line x1="${L}" y1="${y}" x2="${L+Math.max(bw,1)}" y2="${y}" stroke="${c}" stroke-width="7" stroke-linecap="round"/>
          <circle cx="${L+Math.max(bw,1)}" cy="${y}" r="6" fill="${c}" stroke="#fff" stroke-width="2"/>
          <text class="ax" x="${L+Math.max(bw,1)+13}" y="${y+3.5}" fill="var(--label-2)">${f?f.toFixed(1)+"×":"ok"}</text>
          <text class="ax" x="${W-6}" y="${y+3.5}" text-anchor="end" font-weight="600"
            fill="${ch>15?"var(--critical)":ch>0?"var(--warning)":"var(--label-3)"}">${ch==null?"–":(ch>0?"+":"")+ch+"%"}</text>
        </g>`;}).join("")}
    </svg>`,
    `<span class="lg"><span class="sw" style="background:var(--critical)"></span>≥4× criterion</span>
     <span class="lg"><span class="sw" style="background:var(--warning)"></span>≥2×</span>
     <span class="lg">right column = change in notified ADD</span>`));
  el.querySelectorAll("g[data-t]").forEach(g=>hover(g,g.dataset.t));
}

/* Two aligned panels on one shared time axis — never a dual y-axis. Coliform
   runs to tens of thousands and case rate to tens; one scale would flatten a
   series onto the baseline and make the comparison a lie. */
function drawTrend(s){
  const wt=s.water||{},ht=s.health||{},ws=wt.series||[],hs=ht.series||[];
  if(!ws.length){add(shell("Trend",s.caption,'<div style="color:var(--label-3)">No readings in this window.</div>'));return;}
  const W=860,H=300,L=56,R=16,T=18,GAP=36,PH=(H-T-GAP-24)/2;
  const top={y:T,h:PH},bot={y:T+PH+GAP,h:PH};
  const dates=[...new Set([...ws.map(p=>p.date),...hs.map(p=>p.date)])].sort();
  const X=d=>L+(dates.indexOf(d)/Math.max(1,dates.length-1))*(W-L-R);
  const sc=(p,pn,thr)=>{const v=p.map(x=>x.value).filter(x=>x!=null);if(thr!=null)v.push(thr);if(!v.length)v.push(0,1);
    let lo=Math.min(...v),hi=Math.max(...v);if(lo===hi){lo*=.9;hi=hi*1.1||1;}
    const pad=(hi-lo)*.14;lo=Math.max(0,lo-pad);hi+=pad;
    return{lo,hi,y:x=>pn.y+pn.h-((x-lo)/(hi-lo))*pn.h};};
  const thr=typeof wt.threshold==="number"?wt.threshold:null;
  const A=sc(ws,top,thr),B=sc(hs,bot,null);
  const base=hs.find(p=>p.baseline!=null)?.baseline??null;
  const path=(p,s2)=>p.filter(x=>x.value!=null).map((x,i)=>`${i?"L":"M"}${X(x.date).toFixed(1)},${s2.y(x.value).toFixed(1)}`).join(" ");
  const tk=s2=>[0,.5,1].map(t=>s2.lo+(s2.hi-s2.lo)*t);
  const step=Math.max(1,Math.ceil(dates.length/8));

  const el=add(shell(`${LBL[wt.indicator]||wt.indicator} at ${wt.site_id}`,s.caption,
    `<svg class="v" viewBox="0 0 ${W} ${H}">
      ${[top,bot].map((pn,k)=>{const s2=k?B:A;return tk(s2).map(v=>
        `<line class="gl" x1="${L}" y1="${s2.y(v).toFixed(1)}" x2="${W-R}" y2="${s2.y(v).toFixed(1)}"/>
         <text class="ax" x="${L-8}" y="${(s2.y(v)+3.5).toFixed(1)}" text-anchor="end">${fmt(v)}</text>`).join("");}).join("")}
      <text class="axb" x="${L}" y="${top.y-6}">${esc(LBL[wt.indicator]||wt.indicator)} <tspan class="ax">${esc(wt.unit||"")}</tspan></text>
      <text class="axb" x="${L}" y="${bot.y-6}">Acute diarrhoeal disease <tspan class="ax">per 100,000 · weekly</tspan></text>
      ${thr!=null?`<line class="thr" stroke="var(--critical)" x1="${L}" y1="${A.y(thr).toFixed(1)}" x2="${W-R}" y2="${A.y(thr).toFixed(1)}"/>
        <text class="ax" fill="var(--critical)" x="${W-R}" y="${(A.y(thr)-5).toFixed(1)}" text-anchor="end">Criterion ${fmt(thr)}</text>`:""}
      ${base!=null?`<line class="thr" stroke="var(--label-3)" x1="${L}" y1="${B.y(base).toFixed(1)}" x2="${W-R}" y2="${B.y(base).toFixed(1)}"/>
        <text class="ax" x="${W-R}" y="${(B.y(base)-5).toFixed(1)}" text-anchor="end">baseline ${fmt(base)}</text>`:""}
      <path d="${path(ws,A)}" fill="none" stroke="var(--water)" stroke-width="2" stroke-linejoin="round"/>
      <path d="${path(hs,B)}" fill="none" stroke="var(--health)" stroke-width="2" stroke-linejoin="round"/>
      ${hs.filter(p=>p.value!=null).map(p=>`<circle cx="${X(p.date).toFixed(1)}" cy="${B.y(p.value).toFixed(1)}" r="4"
        fill="var(--health)" stroke="#fff" stroke-width="2"/>`).join("")}
      ${dates.filter((_,i)=>i%step===0||i===dates.length-1).map(d=>
        `<text class="ax" x="${X(d).toFixed(1)}" y="${H-6}" text-anchor="middle">${d.slice(5)}</text>`).join("")}
      <line class="cx" x1="0" y1="${T}" x2="0" y2="${bot.y+bot.h}" stroke="var(--label-3)" stroke-width="1" opacity="0"/>
      <rect class="hit" x="${L}" y="${T}" width="${W-L-R}" height="${bot.y+bot.h-T}" fill="transparent"/>
    </svg>`,
    `<span class="lg"><span class="sw" style="background:var(--water)"></span>${esc(LBL[wt.indicator]||wt.indicator)} — daily</span>
     <span class="lg"><span class="sw" style="background:var(--health)"></span>Acute diarrhoeal disease — weekly</span>
     ${thr!=null?'<span class="lg" style="color:var(--critical)"><span class="sw d"></span>Screening criterion</span>':""}
     ${wt.threshold_basis?`<span class="lg" style="flex-basis:100%;color:var(--label-3)">${esc(wt.threshold_basis)}</span>`:""}`));

  const svg=el.querySelector("svg"),hit=el.querySelector(".hit"),cx=el.querySelector(".cx");
  hit.onmousemove=ev=>{const r=svg.getBoundingClientRect();
    const i=Math.round(((ev.clientX-r.left)/r.width*W-L)/(W-L-R)*(dates.length-1));
    const d=dates[Math.max(0,Math.min(dates.length-1,i))];if(!d)return;
    cx.setAttribute("x1",X(d));cx.setAttribute("x2",X(d));cx.setAttribute("opacity",".3");
    const a=ws.find(p=>p.date===d),b=hs.find(p=>p.date===d);
    tip.innerHTML=`<div style="opacity:.65;margin-bottom:2px">${esc(d)}</div>`+
      (a?`<div>${esc(LBL[wt.indicator]||wt.indicator)} <b>${fmt(a.value)}</b></div>`:"")+
      (b?`<div>ADD <b>${fmt(b.value)}</b>/100k${b.cases?` · ${b.cases} cases`:""}</div>`:"");
    tip.style.left=Math.min(innerWidth-230,ev.clientX+13)+"px";tip.style.top=(ev.clientY-8)+"px";tip.classList.add("on");};
  hit.onmouseleave=()=>{cx.setAttribute("opacity","0");tip.classList.remove("on");};
}

function drawScatter(s){
  const w=(s.wards||[]).filter(x=>x.add_change_pct!=null); if(!w.length) return;
  const worst=x=>Math.max(0,...(x.exceedances||[]).map(e=>e.factor||0));
  const W=820,H=360,L=56,R=24,T=20,B=44;
  const mx=Math.max(2,...w.map(worst))*1.1;
  const cs=w.map(x=>x.add_change_pct),lo=Math.min(-10,...cs)*1.15,hi=Math.max(20,...cs)*1.15;
  const X=f=>L+(f/mx)*(W-L-R),Y=p=>T+(1-(p-lo)/(hi-lo))*(H-T-B);
  const col=x=>x.severity==="HIGH"?"var(--critical)":x.severity==="MODERATE"?"var(--warning)":"var(--good)";
  const el=add(shell("Exceedance against change in notifications",s.caption,
    `<svg class="v" viewBox="0 0 ${W} ${H}">
      <rect x="${X(1)}" y="${T}" width="${W-R-X(1)}" height="${Y(15)-T}" fill="var(--crit-w)" opacity=".55"/>
      <text class="ax" x="${W-R-6}" y="${T+13}" text-anchor="end" fill="var(--critical)">exceeds criteria and notifications rising</text>
      ${[0,.5,1].map(t=>{const x=L+t*(W-L-R);return `<line class="gl" x1="${x}" y1="${T}" x2="${x}" y2="${H-B}"/>
        <text class="ax" x="${x}" y="${H-B+14}" text-anchor="middle">${(t*mx).toFixed(1)}×</text>`;}).join("")}
      ${[lo,0,hi].map(v=>`<line class="gl" x1="${L}" y1="${Y(v).toFixed(1)}" x2="${W-R}" y2="${Y(v).toFixed(1)}" ${v===0?'stroke="var(--sep)"':""}/>
        <text class="ax" x="${L-8}" y="${(Y(v)+3.5).toFixed(1)}" text-anchor="end">${v>0?"+":""}${Math.round(v)}%</text>`).join("")}
      <text class="ax" x="${L+(W-L-R)/2}" y="${H-8}" text-anchor="middle">worst exceedance (multiple of criterion) →</text>
      ${w.map(x=>{const cx=X(worst(x)),cy=Y(x.add_change_pct);
        return `<g data-t="${esc(x.name)}<br>${worst(x).toFixed(1)}× criterion · ADD ${x.add_change_pct>0?"+":""}${x.add_change_pct}%">
          <circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${x.co_located?11:8}" fill="${col(x)}"
            fill-opacity="${x.co_located?".95":".7"}" stroke="#fff" stroke-width="2"/>
          <text class="ax" x="${(cx+14).toFixed(1)}" y="${(cy+3.5).toFixed(1)}" fill="var(--label)">${esc((x.name.split(" at ")[1]||x.name).slice(0,18))}</text>
        </g>`;}).join("")}
    </svg>`,
    `<span class="lg"><span class="sq" style="border-radius:50%;background:var(--critical)"></span>HIGH</span>
     <span class="lg"><span class="sq" style="border-radius:50%;background:var(--warning)"></span>MODERATE</span>
     <span class="lg"><span class="sq" style="border-radius:50%;background:var(--good)"></span>within criteria</span>
     <span class="lg">larger point = water and cases together</span>
     <span class="lg" style="flex-basis:100%;color:var(--label-3)">Association only — position in the shaded quadrant is a reason to sample, not evidence of causation.</span>`));
  el.querySelectorAll("g[data-t]").forEach(g=>hover(g,g.dataset.t));
}


return draw;
}
