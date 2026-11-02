'use strict';
// Technology tree of the workshop: what is already in hand → what to learn next → what it opens.
const D=JSON.parse(document.getElementById('tech-data').textContent);
const TREE=D.tree,T=TREE.techs,ERAS=TREE.eras,FAM=TREE.families,COMBOS=TREE.combos;
const byId=Object.fromEntries(T.map(t=>[t.id,t]));
T.forEach(t=>{t.kids=[];t.have=t.have||[];t.buy=t.buy||[];t.steps=t.steps||[];t.projects=t.projects||[];t.optional=t.optional||[];});
T.forEach(t=>t.req.forEach(r=>byId[r].kids.push(t.id)));
const combosOf=Object.fromEntries(T.map(t=>[t.id,COMBOS.filter(c=>c.needs.includes(t.id))]));
const ACCESS_KEY='svoya-masterskaya-access-key',LOCAL_KEY='svoya-masterskaya-tech-v1',THEME_KEY='el-bolson-workshop-v3-theme';
const USD_PER_HOUR={cheap:40,balance:15,time:5};
const OWNED=new Set(['bought','built','tested','mastered','owned']);
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const round=x=>Math.round(x*10)/10;
const fmtH=h=>h>=100?Math.round(h)+' ч':round(h).toString().replace('.',',')+' ч';
const plural=(n,one,few,many)=>{const a=n%10,b=n%100;return n+' '+(a===1&&b!==11?one:a>=2&&a<=4&&(b<12||b>14)?few:many);};
const fmtUSD=x=>x==null?'—':'$'+Math.round(x).toLocaleString('ru-RU');

let state={schema:1,marks:{},target:'',money:'balance'};
let revision=0,mode='local',inventory=D.inventory,plan=null,view='tree',selected='',dirty=false,saving=false;

// ---------- live plan progress (same rules as the hours plan) ----------
function stepInfo(id){
  const s=plan?.steps?.[id];const base=D.steps[id];
  if(!s)return {hours:base.hours,percent:0,archived:false,title:base.title};
  let p=s.basePercent||0;
  (plan.entriesByStep[id]||[]).forEach(e=>{p=e.percent;});
  return {hours:s.hours,percent:p,archived:!!s.archived,title:s.title||base.title};
}
function techProgress(t){
  let total=0,earned=0;
  t.steps.forEach(id=>{const s=stepInfo(id);if(s.archived)return;total+=s.hours;earned+=s.hours*s.percent/100;});
  return total?{total,earned,percent:100*earned/total}:null;
}
function status(t){
  const m=state.marks[t.id];
  if(m==='done')return 'done';
  if(m==='active')return 'active';
  if(m!=='todo'){
    if(t.start==='done')return 'done';
    const p=techProgress(t);
    if(p&&p.percent>=100)return 'done';
    if((p&&p.percent>0)||t.start==='active')return 'active';
  }
  return t.req.every(r=>st(r)==='done')?'available':'locked';
}
let statusCache={};
function st(id){if(!(id in statusCache))statusCache[id]=status(byId[id]);return statusCache[id];}
function invalidate(){statusCache={};}

// ---------- money and hours ----------
function quoteUSD(q){if(!q||q.amount==null||q.exampleOnly)return null;const fx=plan?.fx||D.fx;return q.amount*(1+(q.tax||0)/100)*(q.quantity||1)/(q.currency==='ARS'?fx:1);}
function itemCost(id){
  const item=D.items[id],s=plan?.items?.[id]||{};
  if(s.exclude||OWNED.has(s.status)||item.kind==='have')return {value:0,owned:OWNED.has(s.status)||item.kind==='have',excluded:!!s.exclude,known:true};
  if(s.estimate!=null)return {value:s.estimate,known:true,own:true};
  const q=quoteUSD(item.quote);
  if(item.range){const low=Math.max(item.range[0],q||0),high=Math.max(item.range[1],low);return {value:(low+high)/2,low,high,known:true};}
  if(q==null&&D.estimates[id])return {value:D.estimates[id].usd,known:true,rough:true};
  return {value:q||0,known:q!=null};
}
function moneyLeft(t){
  let need=0,optional=0,unknown=0;
  t.buy.forEach(id=>{const c=itemCost(id);if(t.optional.includes(id)){optional+=c.value;return;}if(!c.known)unknown++;need+=c.value;});
  const own=t.usd&&st(t.id)!=='done'?t.usd:0;
  return {need:need+own,optional,unknown,own};
}
function hoursLeft(t){
  if(st(t.id)==='done')return 0;
  let h=0;t.steps.forEach(id=>{const s=stepInfo(id);if(!s.archived)h+=s.hours*(1-s.percent/100);});
  const own=t.hours||0;
  return h+own;
}
function hoursTotal(t){let h=t.hours||0;t.steps.forEach(id=>{const s=stepInfo(id);if(!s.archived)h+=s.hours;});return h;}
function toolStatus(id){return inventory?.[id]||'';}

// ---------- graph helpers ----------
function ancestors(id,acc=new Set()){byId[id].req.forEach(r=>{if(!acc.has(r)){acc.add(r);ancestors(r,acc);}});return acc;}
function descendants(id,acc=new Set()){byId[id].kids.forEach(k=>{if(!acc.has(k)){acc.add(k);descendants(k,acc);}});return acc;}
const DESC=Object.fromEntries(T.map(t=>[t.id,descendants(t.id).size]));
// Drawn links skip requirements already implied by another requirement (transitive reduction).
const LINKS=Object.fromEntries(T.map(t=>[t.id,t.req.filter(r=>!t.req.some(o=>o!==r&&ancestors(o).has(r)))]));
const LINK_KIDS=Object.fromEntries(T.map(t=>[t.id,T.filter(k=>LINKS[k.id].includes(t.id)).map(k=>k.id)]));

// ---------- recommended order: greedy value per effort, like choosing the next research ----------
function computeOrder(){
  const done=new Set(T.filter(t=>st(t.id)==='done').map(t=>t.id));
  const left=new Set(T.filter(t=>!done.has(t.id)).map(t=>t.id));
  const goal=state.target&&byId[state.target]?new Set([...ancestors(state.target),state.target]):null;
  const rate=USD_PER_HOUR[state.money]||15;
  const order=[];let cumH=0,cumUSD=0;
  while(left.size){
    let avail=[...left].filter(id=>byId[id].req.every(r=>done.has(r)));
    if(!avail.length)break;
    let inGoal=false;
    if(goal){const g=avail.filter(id=>goal.has(id));if(g.length){avail=g;inGoal=true;}}
    let best=null;
    for(const id of avail){const s=score(id,done,rate);if(!best||s.score>best.score)best=s;}
    best.goal=inGoal;cumH+=best.hours;cumUSD+=best.usd;best.cumH=cumH;best.cumUSD=cumUSD;
    order.push(best);done.add(best.id);left.delete(best.id);
  }
  return order;
}
function score(id,done,rate){
  const t=byId[id],hours=hoursLeft(t),money=moneyLeft(t),usd=money.need;
  const opens=t.kids.filter(k=>!done.has(k)&&byId[k].req.every(r=>r===id||done.has(r)));
  const completes=[];let comboGain=0;
  combosOf[id].forEach(c=>{const missing=c.needs.filter(n=>!done.has(n)).length;if(!missing)return;if(missing===1){completes.push(c);comboGain+=2.5;}else comboGain+=1/missing;});
  const started=st(id)==='active';
  let value=1+0.5*t.projects.length+(t.wonder?1.5:0)+0.8*opens.length+comboGain+0.15*DESC[id];
  if(started)value*=1.6;
  const cost=Math.max(2,hours)+usd/rate;
  const allHave=!usd&&!money.unknown;
  return {id,score:value/Math.pow(cost,0.75),hours,usd,opens,completes,started,allHave};
}
let ORDER=[],RANK={};
function recompute(){invalidate();ORDER=computeOrder();RANK=Object.fromEntries(ORDER.map((o,i)=>[o.id,i+1]));}

// ---------- layout: eras are column groups, depth inside an era gives columns ----------
const COL_W=252,NODE_W=212,ROW_H=86,HEAD_H=58,PAD=18;
let POS={},ERA_X=[];
function layout(){
  const topo=[],seen=new Set();
  const visit=id=>{if(seen.has(id))return;seen.add(id);byId[id].req.forEach(visit);topo.push(id);};
  T.forEach(t=>visit(t.id));
  const local={};
  topo.forEach(id=>{const t=byId[id];local[id]=Math.max(0,...t.req.filter(r=>byId[r].era===t.era).map(r=>local[r]+1));});
  let offset=0;ERA_X=[];const col={};
  ERAS.forEach(e=>{const ids=T.filter(t=>t.era===e.id).map(t=>t.id);const width=ids.length?Math.max(...ids.map(id=>local[id]))+1:1;ERA_X.push({era:e,start:offset,cols:width});ids.forEach(id=>col[id]=offset+local[id]);offset+=width;});
  const columns=[];T.forEach(t=>{(columns[col[t.id]]=columns[col[t.id]]||[]).push(t.id);});
  const famOrder=Object.keys(FAM);
  const y={};
  columns.forEach(ids=>{ids.sort((a,b)=>famOrder.indexOf(byId[a].family)-famOrder.indexOf(byId[b].family));ids.forEach((id,i)=>y[id]=i);});
  // Barycenter sweeps keep prerequisite chains roughly horizontal.
  for(let pass=0;pass<4;pass++){
    columns.forEach((ids,c)=>{
      const key=id=>{const near=pass%2===0?LINKS[id]:LINK_KIDS[id];const ys=near.map(n=>y[n]);return ys.length?ys.reduce((a,b)=>a+b,0)/ys.length:y[id];};
      const keys=Object.fromEntries(ids.map(id=>[id,key(id)]));
      ids.sort((a,b)=>keys[a]-keys[b]);
      let last=-Infinity;ids.forEach(id=>{const want=Math.max(keys[id],last+1);y[id]=want;last=want;});
    });
  }
  const minY=Math.min(...Object.values(y));
  POS={};T.forEach(t=>POS[t.id]={x:PAD+col[t.id]*COL_W,y:HEAD_H+PAD+(y[t.id]-minY)*ROW_H});
  return {width:PAD*2+offset*COL_W-(COL_W-NODE_W),height:HEAD_H+PAD*2+(Math.max(...Object.values(y))-minY+1)*ROW_H};
}
const SIZE=layout();

// ---------- rendering ----------
function nodeMeta(t){
  const s=st(t.id);
  if(s==='done')return 'изучено';
  const h=hoursLeft(t),m=moneyLeft(t);
  return [fmtH(h),m.need>0?fmtUSD(m.need):'без покупок'].join(' · ');
}
function renderTree(){
  const canvas=$('#canvas');
  canvas.style.width=SIZE.width+'px';canvas.style.height=SIZE.height+'px';
  const bands=ERA_X.map((e,i)=>`<div class="era-band" style="left:${PAD/2+e.start*COL_W}px;width:${e.cols*COL_W}px;${i%2?'background:color-mix(in srgb,var(--soft) 30%,transparent)':''}"><div class="era-head"><span>Эпоха ${i}</span><b>${esc(e.era.title)}</b></div></div>`).join('');
  const hot=selected?new Set([selected,...ancestors(selected)]):null;
  const hotKids=selected?new Set(byId[selected].kids):null;
  const goal=state.target&&byId[state.target]?new Set([state.target,...ancestors(state.target)]):null;
  let edges='';
  T.forEach(t=>LINKS[t.id].forEach(r=>{
    const a=POS[r],b=POS[t.id],x1=a.x+NODE_W,y1=a.y+34,x2=b.x,y2=b.y+34,dx=Math.max(40,(x2-x1)/2);
    let cls='edge';
    if(st(r)==='done')cls+=' e-done';
    if(hot){if((hot.has(t.id)&&hot.has(r))||(r===selected&&hotKids.has(t.id)))cls+=' hot';else cls+=' dim';}
    else if(goal){if(goal.has(t.id)&&goal.has(r))cls+=' hot';else cls+=' dim';}
    edges+=`<path class="${cls}" d="M${x1} ${y1} C${x1+dx} ${y1},${x2-dx} ${y2},${x2} ${y2}"/>`;
  }));
  const nodes=T.map(t=>{
    const s=st(t.id),p=techProgress(t),rank=RANK[t.id];
    let cls=`node s-${s}`;if(t.wonder)cls+=' wonder';if(t.new)cls+=' new';
    if(t.id===selected)cls+=' sel';
    if(t.id===state.target)cls+=' target';
    if(hot&&!hot.has(t.id)&&!hotKids.has(t.id))cls+=' dim';
    else if(!hot&&goal&&!goal.has(t.id))cls+=' dim';
    const tag=t.wonder?'большой проект':t.new?'новое':'';
    const bar=s==='active'&&p&&p.percent>0?`<span class="pb"><i style="width:${Math.max(3,p.percent)}%"></i></span>`:'';
    return `<button class="${cls}" style="left:${POS[t.id].x}px;top:${POS[t.id].y}px;--fam:${FAM[t.family].color}" data-id="${t.id}" aria-label="${esc(t.title)}">${rank?`<span class="ord">${rank}</span>`:''}${tag?`<span class="tag">${tag}</span>`:''}<span class="t">${esc(t.title)}</span><span class="m">${esc(nodeMeta(t))}</span>${bar}</button>`;
  }).join('');
  canvas.innerHTML=bands+`<svg width="${SIZE.width}" height="${SIZE.height}" aria-hidden="true">${edges}</svg>`+nodes;
}
function chip(id){const t=byId[id];return `<button class="chip c-${st(id)}" data-open="${id}">${esc(t.title)}${st(id)==='done'?' ✓':''}</button>`;}
const STATUS_LABEL={done:'изучено',active:'в работе',available:'доступно',locked:'пока закрыто'};
const RISK_LABEL={low:'низкий риск',care:'осторожно: инструмент',pro:'pro: специалист или обучение'};
const INV_LABEL={have:'✓ есть',borrow:'одолжить',want:'хочу',unknown:'не отмечено','':'нет в инвентаре'};
function renderPanel(){
  const panel=$('#panel');
  if(!selected){panel.classList.remove('open');return;}
  const t=byId[selected],s=st(t.id),p=techProgress(t),m=moneyLeft(t),mark=state.marks[t.id]||'';
  const o=ORDER.find(x=>x.id===t.id);
  const missing=t.req.filter(r=>st(r)!=='done');
  const tools=t.have.map(id=>{const v=toolStatus(id);return `<li><span>${esc(D.tools[id]||id)}</span><span class="${v==='have'?'ok':''}">${INV_LABEL[v]??v}</span></li>`;}).join('');
  const buys=t.buy.map(id=>{const it=D.items[id],c=itemCost(id),ps=plan?.items?.[id]?.status;
    const right=c.owned?'<span class="ok">✓ есть</span>':c.excluded?'исключено':(c.known?(c.rough?'≈ ':'')+fmtUSD(c.value):'цена не найдена')+(t.optional.includes(id)?' · по желанию':'');
    return `<li><span>${esc(it.title)}${it.kind==='diy'?' <span class="note">· сделать самому</span>':it.kind==='service'?' <span class="note">· услуга</span>':''}${ps&&!OWNED.has(ps)&&ps!=='planned'?` <span class="note">· ${esc(ps)}</span>`:''}</span><span>${right}</span></li>`;}).join('');
  const steps=t.steps.map(id=>{const si=stepInfo(id);return `<li><span>${esc(si.title)}${si.archived?' <span class="note">· в архиве</span>':''}</span><span>${si.percent?Math.round(si.percent)+'% · ':''}${fmtH(si.hours)}</span></li>`;}).join('');
  const combos=combosOf[t.id].map(c=>{const miss=c.needs.filter(n=>st(n)!=='done');return `<div class="combo-mini${miss.length?'':' open'}"><b>${esc(c.title)}</b><span class="note">${miss.length?'не хватает: '+miss.map(n=>esc(byId[n].title)).join(', '):'открыто ✓'}</span></div>`;}).join('');
  const stageLinks=(t.modules||[]).map(mid=>`<a href="/workshop/#stage=${encodeURIComponent(mid)}">${esc(D.modules[mid]||mid)} ↗</a>`).join(' · ');
  panel.innerHTML=`<button class="close" data-close aria-label="Закрыть">×</button>
  <div class="kicker">Эпоха ${t.era} · ${esc(ERAS[t.era].title)} · ${esc(FAM[t.family].title)}</div>
  <h2>${esc(t.title)}</h2>
  <div><span class="pill ${s}">${STATUS_LABEL[s]}</span> ${o?`<span class="pill available">№ ${RANK[t.id]} в порядке</span>`:''} ${t.new?'<span class="pill new">новое · нет в плане</span>':''} ${t.risk==='pro'?'<span class="pill pro">pro</span>':''}</div>
  <div class="status-row" role="group" aria-label="Отметка">
    <button data-mark="done" aria-pressed="${mark==='done'}">Изучено</button>
    <button data-mark="active" aria-pressed="${mark==='active'}">В работе</button>
    <button data-mark="todo" aria-pressed="${mark==='todo'}">Не начато</button>
    <button data-mark="" aria-pressed="${!mark}" title="По опыту и прогрессу плана">Авто</button>
  </div>
  <p class="note">«Авто» — статус по журналу опыта и готовности шагов плана.${p&&p.percent>0?` Сейчас готово ${Math.round(p.percent)}% плановых часов.`:''}</p>
  <h3>Что даёт</h3><p>${esc(t.gives)}</p>
  ${t.projects.length?`<h3>Открывает проекты</h3><ul class="list">${t.projects.map(x=>`<li><span>${esc(x)}</span><span></span></li>`).join('')}</ul>`:''}
  ${t.evidence?`<div class="callout">Уже есть: ${esc(t.evidence)}</div>`:''}
  ${t.note?`<div class="callout${t.risk==='pro'?' warn':''}">${esc(t.note)}</div>`:''}
  ${t.req.length?`<h3>Нужно изучить сначала</h3><div class="chips">${t.req.map(chip).join('')}</div>${missing.length?`<p class="note" style="margin-top:6px">Не хватает: ${missing.length}. Весь путь — ${plural(ancestors(t.id).size,'технология','технологии','технологий')}.</p>`:''}`:''}
  ${t.kids.length?`<h3>Ведёт к</h3><div class="chips">${t.kids.map(chip).join('')}</div>`:''}
  ${combos?`<h3>Открытия на стыке</h3>${combos}`:''}
  <h3>Усилие</h3><ul class="list"><li><span>Осталось часов</span><span>${fmtH(hoursLeft(t))} из ${fmtH(hoursTotal(t))}</span></li><li><span>Нужно купить</span><span>${m.need>0?fmtUSD(m.need):'ничего'}${m.unknown?' + '+m.unknown+' без цены':''}</span></li>${m.own?`<li><span>В том числе материалы (оценка дерева)</span><span>≈ ${fmtUSD(m.own)}</span></li>`:''}${m.optional?`<li><span>По желанию</span><span>${fmtUSD(m.optional)}</span></li>`:''}<li><span>Где</span><span>${esc(t.place)}</span></li><li><span>Риск</span><span>${RISK_LABEL[t.risk]}</span></li></ul>
  ${tools?`<h3>Инструменты из инвентаря</h3><ul class="list">${tools}</ul>`:''}
  ${buys?`<h3>Покупки и оснастка из плана</h3><ul class="list">${buys}</ul>${t.buy.filter(id=>D.estimates[id]&&itemCost(id).rough).map(id=>`<p class="note">≈ ${esc(D.estimates[id].note)}</p>`).join('')}`:''}
  ${steps?`<h3>Шаги плана</h3><ul class="list">${steps}</ul>`:t.new?'<p class="note">Шагов в плане пока нет: часы — грубая оценка.</p>':''}
  ${stageLinks?`<p class="note" style="margin-top:10px">В плане: ${stageLinks}</p>`:''}
  <p style="margin-top:16px"><button class="chip" data-target="${t.id}">${state.target===t.id?'Убрать цель':'Сделать целью — показать путь'}</button></p>`;
  panel.classList.add('open');
}
function renderFacts(){
  const done=T.filter(t=>st(t.id)==='done').length,active=T.filter(t=>st(t.id)==='active').length,avail=T.filter(t=>st(t.id)==='available').length;
  const openCombos=COMBOS.filter(c=>c.needs.every(n=>st(n)==='done')).length;
  const next=ORDER[0];
  const goal=state.target&&byId[state.target];
  const toGoal=goal?ORDER.filter(o=>o.goal||o.id===state.target):[];
  const gH=toGoal.reduce((a,o)=>a+o.hours,0),gU=toGoal.reduce((a,o)=>a+o.usd,0);
  $('#facts').innerHTML=`<div><strong>${done}<small style="font-size:15px;color:var(--muted)"> / ${T.length}</small></strong><span>изучено технологий</span></div>
  <div><strong>${active}</strong><span>в работе</span></div>
  <div><strong>${avail}</strong><span>доступно сейчас</span></div>
  <div><strong>${openCombos}<small style="font-size:15px;color:var(--muted)"> / ${COMBOS.length}</small></strong><span>открытий на стыке</span></div>
  <div class="next"><strong>${next?`<button data-open="${next.id}">1. ${esc(byId[next.id].title)}</button>`:'Всё изучено'}</strong><span>${goal?`путь к «${esc(goal.title)}»: ${plural(toGoal.length,'технология','технологии','технологий')} · ${fmtH(gH)} · ${fmtUSD(gU)}`:'следующее по пользе на час и доллар'}</span></div>`;
}
function reasons(o){
  const r=[];
  if(o.started)r.push('уже начато');
  if(o.allHave)r.push('всё нужное есть');
  if(o.goal)r.push('на пути к цели');
  if(o.completes.length)r.push('завершает открытие: '+o.completes.map(c=>'«'+c.title+'»').join(', '));
  if(o.opens.length)r.push('открывает: '+o.opens.slice(0,3).map(k=>byId[k].title).join(', ')+(o.opens.length>3?' и ещё '+(o.opens.length-3):''));
  if(!r.length)r.push(byId[o.id].gives);
  return r.join(' · ');
}
function renderOrder(){
  const goal=state.target&&byId[state.target];
  let rows='',sep=false;
  ORDER.forEach((o,i)=>{
    const t=byId[o.id];
    if(goal&&!o.goal&&!sep&&i>0){sep=true;rows+=`<div class="order-sep"><b>Цель достигнута.</b> Дальше — остальные технологии по пользе.</div>`;}
    if(!goal&&i===10)rows+=`<div class="order-sep"><b>Дальше</b> — порядок уточнится, когда отметишь первые десять.</div>`;
    rows+=`<div class="order-row" data-open="${t.id}" role="button" tabindex="0"><span class="n">${i+1}</span><span class="ttl">${esc(t.title)}<small>${esc(ERAS[t.era].title)}${t.new?' · новое':''}${st(t.id)==='active'?' · в работе':''}</small></span><span class="why">${esc(reasons(o))}</span><span class="num h">${fmtH(o.hours)}</span><span class="num u">${o.usd>0?fmtUSD(o.usd):'—'}</span><span class="cum">Σ ${fmtH(o.cumH)}<br>${fmtUSD(o.cumUSD)}</span></div>`;
  });
  const done=T.filter(t=>st(t.id)==='done');
  $('#view-order').innerHTML=`<p class="section-note">Порядок «следующего исследования»: из доступных сейчас выбирается технология с наибольшей пользой на час и доллар, затем расчёт повторяется. Польза — новые проекты, открываемые технологии, «открытия» на стыке (особенно когда не хватает одной технологии) и начатая работа. ${goal?`Сейчас выбрана цель «${esc(goal.title)}»: сначала кратчайший путь к ней.`:'Выбери цель вверху, чтобы получить путь к большому проекту.'}</p>
  <div class="order"><div class="order-head"><span>№</span><span>Технология</span><span>Почему сейчас</span><span style="text-align:right">Часы</span><span style="text-align:right">Покупки</span><span style="text-align:right">Нарастающим</span></div>${rows||'<div class="order-sep">Всё изучено.</div>'}</div>
  <p class="method">Изучено ${done.length}: ${done.map(t=>esc(t.title)).join(', ')||'пока ничего'}. Деньги переводятся в «часы» по выбранному режиму: экономить деньги — $40 за час, баланс — $15, экономить время — $5. Это способ сравнения, а не цена твоего времени.</p>`;
}
function renderCombos(){
  const rows=COMBOS.map(c=>{const miss=c.needs.filter(n=>st(n)!=='done');return {c,miss};}).sort((a,b)=>a.miss.length-b.miss.length);
  $('#view-combos').innerHTML=`<p class="section-note">Открытия — классы проектов, которые появляются только на стыке нескольких технологий. Так каждая освоенная технология увеличивает пользу всех предыдущих.</p><div class="combos">${rows.map(({c,miss})=>`<article class="combo${miss.length?miss.length===1?' near':'':' open'}"><span class="state">${miss.length?miss.length===1?'не хватает одной технологии':'не хватает: '+miss.length:'открыто'}</span><h3>${esc(c.title)}</h3><div class="chips">${c.needs.map(chip).join('')}</div><ul>${c.examples.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>${c.why?`<p>${esc(c.why)}</p>`:''}</article>`).join('')}</div>`;
}
function renderTargets(){
  const sel=$('#target');
  const wonders=T.filter(t=>t.wonder);
  sel.innerHTML=`<option value="">без цели — максимум пользы</option><optgroup label="Большие проекты">${wonders.map(t=>`<option value="${t.id}">${esc(t.title)}</option>`).join('')}</optgroup>`+ERAS.map(e=>`<optgroup label="${esc(e.title)}">${T.filter(t=>t.era===e.id&&!t.wonder).map(t=>`<option value="${t.id}">${esc(t.title)}</option>`).join('')}</optgroup>`).join('');
  sel.value=state.target||'';$('#money').value=state.money||'balance';
}
function render(){
  recompute();renderFacts();
  if(view==='tree')renderTree();
  if(view==='order')renderOrder();
  if(view==='combos')renderCombos();
  renderPanel();
}
function setView(v){
  view=v;['tree','order','combos'].forEach(x=>{$('#view-'+x).hidden=x!==v;$('#tab-'+x).setAttribute('aria-selected',x===v);});
  render();
}
function openTech(id,scroll=true){
  selected=id;render();
  if(view==='tree'&&scroll){const p=POS[id],box=$('#treebox');box.scrollTo({left:Math.max(0,p.x-box.clientWidth/2+NODE_W/2),top:Math.max(0,p.y-box.clientHeight/2+34),behavior:'smooth'});}
  $('#panel').focus({preventScroll:true});
}

// ---------- persistence: server first, browser copy as fallback ----------
function accessHeaders(){try{const k=localStorage.getItem(ACCESS_KEY);return k?{'X-Workshop-Key':k}:{};}catch{return {};}}
function setSave(text,warn){const el=$('#save');el.textContent=text;el.classList.toggle('warn',!!warn);}
function cleanState(s){
  const marks={};Object.entries(s?.marks||{}).forEach(([k,v])=>{if(byId[k]&&['done','active','todo'].includes(v))marks[k]=v;});
  return {schema:1,marks,target:byId[s?.target]?s.target:'',money:USD_PER_HOUR[s?.money]?s.money:'balance'};
}
function saveLocal(){try{localStorage.setItem(LOCAL_KEY,JSON.stringify(state));}catch{}}
function loadLocal(){try{const raw=localStorage.getItem(LOCAL_KEY);return raw?cleanState(JSON.parse(raw)):null;}catch{return null;}}
async function load(){
  try{
    const r=await fetch('/api/tech',{headers:accessHeaders(),cache:'no-store',signal:AbortSignal.timeout(12000)});
    if(!r.ok)throw Error(r.status===403?'Нужен ключ доступа: открой настройки ИИ в дереве навыков':'Сервер не ответил');
    const body=await r.json();
    mode='server';revision=body.revision||0;
    if(body.inventory)inventory={...D.inventory,...Object.fromEntries(Object.keys(D.inventory).map(k=>[k,body.inventory[k]||'']))};
    const local=loadLocal();
    state=body.state?cleanState(body.state):(local||state);
    setSave(body.state?`Сохранено на сервере · ревизия ${revision}`:'На сервере ещё нет отметок');
    if(!body.state&&local&&Object.keys(local.marks).length){dirty=true;queueSave();}
  }catch(e){
    mode='local';state=loadLocal()||state;
    setSave((e.message||'Сервер недоступен')+'. Отметки хранятся в этом браузере.',true);
  }
  try{
    const r=await fetch('/api/workshop',{headers:accessHeaders(),cache:'no-store',signal:AbortSignal.timeout(12000)});
    if(r.ok){const body=await r.json();const s=body.state;if(s){
      const entriesByStep={};s.entries.map((e,i)=>({...e,i})).filter(e=>e.percent!==null&&e.percent!==undefined).sort((a,b)=>a.month-b.month||a.i-b.i).forEach(e=>(entriesByStep[e.stepId]=entriesByStep[e.stepId]||[]).push(e));
      plan={steps:Object.fromEntries(s.steps.map(x=>[x.id,x])),entriesByStep,items:s.items||{},fx:s.config?.fx};
    }}
  }catch{}
  renderTargets();render();
}
let timer=null;
function queueSave(){saveLocal();clearTimeout(timer);timer=setTimeout(pushSave,500);}
async function pushSave(){
  if(mode!=='server'){setSave('Сохранено в этом браузере (сервер недоступен)',true);return;}
  if(saving){timer=setTimeout(pushSave,400);return;}
  saving=true;dirty=false;setSave('Сохраняю…');
  const request={state,baseRevision:revision,requestId:(crypto.randomUUID?crypto.randomUUID():String(Date.now())+Math.random().toString(16).slice(2))};
  try{
    const r=await fetch('/api/tech',{method:'POST',headers:{'Content-Type':'application/json',...accessHeaders()},body:JSON.stringify(request),signal:AbortSignal.timeout(12000)});
    const body=await r.json().catch(()=>({}));
    if(r.status===409){
      const fresh=await fetch('/api/tech',{headers:accessHeaders(),cache:'no-store'}).then(x=>x.json());
      revision=fresh.revision||0;state=cleanState(fresh.state);saveLocal();
      setSave('Отметки менялись на другом устройстве — загружена серверная версия',true);renderTargets();render();
    }else if(!r.ok){throw Error(body.error||'Не удалось сохранить');}
    else{revision=body.revision;setSave(`Сохранено на сервере · ревизия ${revision}`);}
  }catch(e){dirty=true;setSave((e.message||'Сеть недоступна')+'. Копия в браузере сохранена.',true);}
  finally{saving=false;}
}

// ---------- events ----------
document.addEventListener('click',e=>{
  const el=e.target.closest('[data-id],[data-open],[data-mark],[data-close],[data-target],[data-view]');
  if(!el)return;
  if(el.dataset.view){setView(el.dataset.view);return;}
  if(el.dataset.close!==undefined){selected='';render();return;}
  if(el.dataset.mark!==undefined){const m=el.dataset.mark;if(m)state.marks[selected]=m;else delete state.marks[selected];queueSave();render();return;}
  if(el.dataset.target!==undefined){state.target=state.target===el.dataset.target?'':el.dataset.target;$('#target').value=state.target;queueSave();render();return;}
  const id=el.dataset.id||el.dataset.open;if(id&&byId[id]){if(el.dataset.open&&view!=='tree'&&!el.closest('.panel')){openTech(id,false);}else openTech(id);}
});
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'&&selected){selected='';render();}
  if((e.key==='Enter'||e.key===' ')&&e.target.classList?.contains('order-row')){e.preventDefault();openTech(e.target.dataset.open,false);}
});
$('#target').addEventListener('change',e=>{state.target=e.target.value;queueSave();render();if(state.target&&view==='tree')openTech(state.target);});
$('#money').addEventListener('change',e=>{state.money=e.target.value;queueSave();render();});
$('#theme').addEventListener('click',()=>{const root=document.documentElement;const dark=root.dataset.theme==='dark'||(!root.dataset.theme&&matchMedia('(prefers-color-scheme:dark)').matches);root.dataset.theme=dark?'light':'dark';try{localStorage.setItem(THEME_KEY,root.dataset.theme);}catch{}});
window.addEventListener('beforeunload',e=>{if(dirty&&mode==='server'){e.preventDefault();e.returnValue='';}});
renderTargets();render();load();
