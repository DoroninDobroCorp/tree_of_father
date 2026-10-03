/* Pure, testable game rules. No model can execute code or write state directly. */
const Core=(()=>{
'use strict';
const CAPS={practice:80,theory:20,attempt:15,historical:40};
const VERSION=4;
const clone=x=>JSON.parse(JSON.stringify(x));
const assert=(x,m)=>{if(!x)throw Error(m)};
const norm=s=>String(s||'').toLocaleLowerCase('ru').replace(/\s+/g,' ').trim();
const unique=a=>new Set(a).size===a.length;
const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
const isObj=o=>o!==null&&typeof o==='object'&&!Array.isArray(o);
function safeTree(o,depth=0){assert(depth<35,'Слишком глубокая структура данных');if(o&&typeof o==='object'){for(const k of Object.keys(o)){assert(!['__proto__','constructor','prototype'].includes(k),'Недопустимый ключ данных');safeTree(o[k],depth+1)}}}
function validateSchema(value,schema,root=schema,path='данные'){
 if(schema.$ref){const key=schema.$ref.split('/').pop();return validateSchema(value,root.$defs[key],root,path)}
 if(schema.anyOf){let ok=false;for(const variant of schema.anyOf){try{validateSchema(value,variant,root,path);ok=true;break}catch{}}assert(ok,`${path}: неверный тип или формат`);return}
 if(schema.enum)assert(schema.enum.includes(value),`${path}: недопустимое значение`);
 const t=schema.type;
 if(t==='object'){
  assert(isObj(value),`${path}: нужен объект`);
  for(const k of schema.required||[])assert(own(value,k),`${path}: нет поля ${k}`);
  if(schema.additionalProperties===false)for(const k of Object.keys(value))assert(own(schema.properties,k),`${path}: неизвестное поле ${k}`);
  for(const [k,v]of Object.entries(value))if(schema.properties[k])validateSchema(v,schema.properties[k],root,`${path}.${k}`);
 }else if(t==='array'){
  assert(Array.isArray(value),`${path}: нужен массив`);assert(value.length<=(schema.maxItems||10000),`${path}: слишком много элементов`);
  for(let i=0;i<value.length;i++)validateSchema(value[i],schema.items,root,`${path}[${i}]`);
 }else if(t==='string'){
  assert(typeof value==='string',`${path}: нужна строка`);assert(value.length<=(schema.maxLength||100000),`${path}: слишком длинный текст`);
  if(schema.pattern)assert(new RegExp(schema.pattern).test(value),`${path}: неверный формат`);
 }else if(t==='integer'){
  assert(Number.isInteger(value),`${path}: нужно целое число`);
  if(schema.minimum!==undefined)assert(value>=schema.minimum,`${path}: значение слишком мало`);
  if(schema.maximum!==undefined)assert(value<=schema.maximum,`${path}: значение слишком велико`);
 }else if(t==='boolean')assert(typeof value==='boolean',`${path}: нужно true/false`);
 else if(t==='null')assert(value===null,`${path}: нужно null`);
}
function validateState(s,schema){
 safeTree(s);assert(s.schemaVersion===VERSION,`Это не сохранение Skill RPG v${VERSION}`);assert(Number.isInteger(s.revision)&&s.revision>=0,'Неверная ревизия');assert(Number.isInteger(s.catalogVersion)&&s.catalogVersion>=0,'Неверная версия каталога');
 for(const k of ['branches','skills','projects','tools','events','focus','audit','appliedProposalIds','sources'])assert(Array.isArray(s[k]),`Нет массива ${k}`);
 for(const k of ['work','inventory','notes','goals','settings','mastery'])assert(isObj(s[k]),`Нет объекта ${k}`);
 for(const [k,cap]of [['branches',100],['skills',4000],['projects',2000],['tools',500],['events',6000]]){
  assert(s[k].length<=cap,`Слишком много элементов: ${k}`);assert(unique(s[k].map(x=>x.id)),`Повторяются ID: ${k}`);
 }
 const ids=k=>new Set(s[k].map(x=>x.id));const bs=ids('branches'),ss=ids('skills'),ps=ids('projects'),ts=ids('tools');
 const defs=schema.$defs;
 for(const b of s.branches){validateSchema(b,defs.branch,schema,`ветка ${b.id}`);assert(b.title.trim()&&b.goal.trim(),'У направления нужны название и цель')}
 for(const sk of s.skills){
  validateSchema(sk,defs.skill,schema,`навык ${sk.id}`);assert([sk.title,sk.module,sk.goal,sk.exercise,sk.proof].every(x=>x.trim()),'У навыка нужны название, модуль, цель, упражнение и проверка');assert(bs.has(sk.branchId),`Навык ${sk.id}: нет ветки ${sk.branchId}`);
  assert(unique(sk.prerequisites)&&!sk.prerequisites.includes(sk.id),`Некорректные предпосылки ${sk.id}`);
  for(const x of sk.prerequisites)assert(ss.has(x),`Навык ${sk.id}: нет предпосылки ${x}`);
  for(const x of sk.toolIds)assert(ts.has(x),`Навык ${sk.id}: неизвестный инструмент ${x}`);
 }
 const lookup=new Map(s.skills.map(x=>[x.id,x]));const done=new Set(),stack=new Set();
 function walk(id){if(done.has(id))return;assert(!stack.has(id),'Циклические зависимости навыков');stack.add(id);for(const p of lookup.get(id).prerequisites)walk(p);stack.delete(id);done.add(id)}
 for(const id of ss)walk(id);
 for(const p of s.projects){validateSchema(p,defs.project,schema,`проект ${p.id}`);assert(p.title.trim()&&p.description.trim(),'У проекта нужны название и описание');assert(p.steps.length&&p.checks.length&&p.skillIds.length&&p.branchIds.length,'У проекта нужны этапы, критерии и связи');for(const x of p.skillIds)assert(ss.has(x),`Проект ${p.id}: нет навыка ${x}`);for(const x of p.branchIds)assert(bs.has(x),`Нет направления ${x}`);for(const x of p.toolIds)assert(ts.has(x),`Нет инструмента ${x}`)}
 for(const e of s.events){validateEvent(e,s,schema)}
 for(const [id,w]of Object.entries(s.work)){assert(ps.has(id),`Неизвестный проект в работе: ${id}`);assert(isObj(w)&&['planned','active','paused'].includes(w.status),'Неверный статус проекта');assert(Array.isArray(w.steps)&&typeof w.note==='string','Неверный черновик проекта');assert(w.steps.every(x=>Number.isInteger(x)&&x>=0&&x<100),'Неверные отметки этапов')}
 for(const [id,v]of Object.entries(s.inventory))assert(ts.has(id)&&['unknown','used','borrow','have','want','skip'].includes(v),'Неверный инвентарь');
 assert(s.focus.every(x=>bs.has(x)),'Неизвестное направление в фокусе');
 for(const [k,v]of Object.entries(s.notes))assert(ss.has(k)&&typeof v==='string'&&v.length<=10000,'Неверная заметка');
 for(const [k,v]of Object.entries(s.goals))assert(ss.has(k)&&['explore','repeat','deepen','later'].includes(v),'Неверная цель');
 for(const [k,m]of Object.entries(s.mastery)){const sk=lookup.get(k);assert(sk,`Отметка освоения для неизвестного навыка ${k}`);assert(isObj(m)&&typeof m.mastered==='boolean'&&Array.isArray(m.checks)&&(m.date===null||typeof m.date==='string'),`Неверная отметка освоения ${k}`);assert(unique(m.checks)&&m.checks.every(i=>Number.isInteger(i)&&i>=0&&i<sk.criteria.length),`Неверные критерии освоения ${k}`)}
 assert(['light','dark'].includes(s.settings.theme),'Неизвестная тема');
 return true;
}
function validateEvent(e,s,schema){
 const allowed=Object.keys(schema.$defs.event.properties);const core={};for(const k of allowed)core[k]=e[k];validateSchema(core,schema.$defs.event,schema,`запись ${e.id}`);
 assert(e.title.trim()&&e.description.trim().length>=8&&e.evidence.trim().length>=3,'Запись опыта требует описания результата и основания');
 assert(e.allocations.length>0,'У опыта нет связанных навыков');assert(unique(e.allocations.map(x=>x.skillId)),'Один навык дважды в одной записи');
 const ss=new Set(s.skills.map(x=>x.id));for(const a of e.allocations)assert(ss.has(a.skillId),`Неизвестный навык ${a.skillId}`);
 const sum=e.allocations.reduce((n,a)=>n+a.points,0);assert(sum<=CAPS[e.kind],`Предел одной записи: ${CAPS[e.kind]} XP (${e.kind}); сейчас ${sum}`);
 assert(e.projectId===null||s.projects.some(x=>x.id===e.projectId),'У записи неизвестный проект');
 if(e.projectId){const p=s.projects.find(x=>x.id===e.projectId);if(e.kind==='practice')assert(p.kind==='practice','Теоретический проект не даёт практический опыт');}
 if(e.date){const parsed=new Date(e.date+'T12:00:00Z');assert(!Number.isNaN(parsed.valueOf())&&parsed.toISOString().slice(0,10)===e.date,'Некорректная дата')}
 for(const t of e.toolIds)assert(s.tools.some(x=>x.id===t),'Неизвестный инструмент в записи');
}
function skillStats(s,id){const out={practice:0,theory:0,attempt:0,historical:0,count:0,stale:false};for(const e of s.events){const a=e.allocations.find(x=>x.skillId===id);if(a){out[e.kind]+=a.points;out.count++;if(e.stale)out.stale=true}}if(out.practice>0)out.stale=false;out.total=out.practice+out.theory+out.attempt+out.historical;return out}
function stats(s){const r={practice:0,theory:0,attempt:0,historical:0,total:0,explored:0,completed:0,mastered:0,skills:0};for(const e of s.events)r[e.kind]+=e.allocations.reduce((a,b)=>a+b.points,0);r.total=r.practice+r.theory+r.attempt+r.historical;const active=s.skills.filter(x=>!x.archived);r.skills=active.length;r.explored=active.filter(x=>skillStats(s,x.id).total>0).length;r.mastered=active.filter(x=>s.mastery[x.id]?.mastered).length;r.completed=new Set(s.events.filter(e=>e.kind==='practice'&&e.projectId).map(e=>e.projectId)).size;return r}
// Mastery is the user's own tick and is kept apart from XP: XP records what was done, mastery what feels closed.
function skillProgress(s,id){const sk=s.skills.find(x=>x.id===id),m=s.mastery[id],xp=skillStats(s,id);const checks=m?m.checks.length:0,criteria=sk?sk.criteria.length:0;const status=m?.mastered?'mastered':(checks||xp.total)?'progress':'todo';return{status,mastered:!!m?.mastered,date:m?.date||null,checks,criteria,xp:xp.total,stale:xp.stale}}
function isReady(s,id){const sk=s.skills.find(x=>x.id===id);return!!sk&&sk.prerequisites.every(p=>s.mastery[p]?.mastered||!s.skills.some(x=>x.id===p&&!x.archived))}
function branchStats(s,id){const skills=s.skills.filter(x=>x.branchId===id&&!x.archived);let seen=0,total=0,practice=0,theory=0,mastered=0,progress=0;for(const x of skills){const n=skillStats(s,x.id);if(n.total)seen++;total+=n.total;practice+=n.practice+n.historical;theory+=n.theory;const st=skillProgress(s,x.id).status;if(st==='mastered')mastered++;else if(st==='progress')progress++}return{count:skills.length,seen,total,practice,theory,mastered,progress,todo:skills.length-mastered-progress}}
function projectState(s,id){const p=s.projects.find(x=>x.id===id);if(p&&s.events.some(x=>x.projectId===id&&x.kind===p.kind))return'done';return s.work[id]?.status||'catalog'}
function eventFingerprint(e){return[e.kind,e.date||'',norm(e.title),norm(e.description)].join('|')}
function applyProposal(state,proposal,chosen,schema){
 safeTree(proposal);validateSchema(proposal,schema);assert(proposal.baseRevision===state.revision,`Предложение для ревизии ${proposal.baseRevision}, а карта уже ${state.revision}. Получи новое предложение с актуальным контекстом.`);
 assert(!state.appliedProposalIds.includes(proposal.id),'Это предложение уже применялось. Повторное начисление заблокировано.');
 assert(unique(proposal.operations.map(x=>x.id)),'Повторяются ID операций');const ops=proposal.operations.filter(x=>chosen.includes(x.id));assert(ops.length,'Сначала выбери хотя бы одно изменение');
 const s=clone(state);const touched=new Set();
 for(const op of ops){
  const category=op.type.endsWith('skill')?'skills':op.type.endsWith('project')?'projects':op.type.endsWith('branch')?'branches':'events';
  const key=category+':'+op.targetId;assert(!touched.has(key),'Несколько изменений одного объекта в пакете. Попроси ИИ объединить их.');touched.add(key);
  const arr=s[category];const index=arr.findIndex(x=>x.id===op.targetId);
  if(op.type.startsWith('archive_')){assert(index>=0,'Архивируемый объект не найден');arr[index].archived=true;continue}
  const d=clone(op.data);assert(d.id===op.targetId,'ID данных не соответствует targetId');
  if(category==='skills')assert(d.criteria.length>=2&&d.criteria.every(x=>x.trim()),`У навыка ${d.id} нужны хотя бы два критерия освоения`);
  if(op.type.startsWith('add_')){
   assert(index<0,`ID ${d.id} уже занят`);
   if(category==='events'){
    assert(!s.events.some(e=>eventFingerprint(e)===eventFingerprint(d)),'Похожая запись уже есть: двойной зачёт заблокирован');d.source='ai';d.createdAt=new Date().toISOString();
    if(d.projectId&&s.work[d.projectId])delete s.work[d.projectId];
   }
   arr.push(d);
  }else{
   assert(index>=0,`Объект ${d.id} для обновления не найден`);
   const riskRank={low:0,care:1,pro:2};if(arr[index].risk)assert(riskRank[d.risk]>=riskRank[arr[index].risk],'ИИ не может понижать предупреждение о риске');
   if(category==='skills'&&JSON.stringify(arr[index].criteria)!==JSON.stringify(d.criteria)&&s.mastery[d.id])s.mastery[d.id].checks=[];
   arr[index]=d;
  }
 }
 validateState(s,schema);
 for(const sk of s.skills.filter(x=>!x.archived))assert(s.branches.some(b=>b.id===sk.branchId&&!b.archived),'Активный навык не может находиться в архивной ветке');
 s.appliedProposalIds.push(proposal.id);if(s.appliedProposalIds.length>3000)s.appliedProposalIds.shift();return s;
}
// Catalog items shipped with the app. A saved copy that still hashes to a known shipped version was never edited
// by the user, so it can be replaced by the newer shipped version; edited copies are always kept.
const CATALOG=['branches','tools','skills','projects'];
function hash(str){let h=0x811c9dc5;for(let i=0;i<str.length;i++){h^=str.charCodeAt(i);h=Math.imul(h,0x01000193)}return(h>>>0).toString(36)}
function itemHash(item){const o={};for(const k of Object.keys(item).sort())if(k!=='archived'&&!(k==='criteria'&&!item[k].length))o[k]=item[k];return hash(JSON.stringify(o))}
function catalogHashes(seed){const out={};for(const k of CATALOG)for(const x of seed[k])out[k+':'+x.id]=itemHash(x);return out}
function mergeCatalog(state,seed,history){
 const s=clone(state),report={added:0,updated:0,kept:0};
 for(const k of CATALOG){
  const mine=new Map(s[k].map(x=>[x.id,x])),shipped=new Set(seed[k].map(x=>x.id));const next=[];
  for(const fresh of seed[k]){
   const cur=mine.get(fresh.id);
   if(!cur){next.push(clone(fresh));report.added++;continue}
   const known=(history[k+':'+fresh.id]||[]).includes(itemHash(cur));
   if(known&&itemHash(cur)!==itemHash(fresh)){const upd=clone(fresh);if('archived'in cur)upd.archived=cur.archived;if(k==='skills'&&s.mastery[upd.id]&&JSON.stringify(cur.criteria)!==JSON.stringify(upd.criteria))s.mastery[upd.id].checks=[];next.push(upd);report.updated++}
   else{if(k==='skills'&&!(cur.criteria||[]).length)cur.criteria=clone(fresh.criteria);if(!known&&itemHash(cur)!==itemHash(fresh))report.kept++;next.push(cur)}
  }
  for(const x of s[k])if(!shipped.has(x.id))next.push(x);
  s[k]=next;
 }
 for(const sk of s.skills){sk.criteria||=[];const m=s.mastery[sk.id];if(m)m.checks=m.checks.filter(i=>i<sk.criteria.length)}
 s.sources=clone(seed.sources);s.catalogVersion=seed.catalogVersion;
 return{state:s,report};
}
function migrate(raw,seed,history){
 safeTree(raw);let s=clone(raw),from=s.schemaVersion;
 assert(from===3||from===VERSION,'Неизвестная версия сохранения');
 if(from===3){s.schemaVersion=VERSION;s.catalogVersion=0;s.mastery={};for(const sk of s.skills)sk.criteria||=[]}
 if(s.catalogVersion>=seed.catalogVersion)return{state:s,migrated:from!==VERSION,report:null};
 const r=mergeCatalog(s,seed,history);return{state:r.state,migrated:true,report:r.report};
}
return{CAPS,VERSION,clone,assert,norm,safeTree,validateSchema,validateState,validateEvent,stats,skillStats,skillProgress,isReady,branchStats,projectState,eventFingerprint,applyProposal,itemHash,catalogHashes,mergeCatalog,migrate};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=Core;
