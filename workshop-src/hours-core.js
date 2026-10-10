(function(global){
'use strict';
const round=n=>Math.round((n+Number.EPSILON)*100)/100;
const clone=x=>JSON.parse(JSON.stringify(x));
const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
function finite(n,min,max,label){if(typeof n!=='number'||!Number.isFinite(n)||n<min||n>max)throw new Error(label+': недопустимое значение');return n;}
function object(o,label){if(!o||typeof o!=='object'||Array.isArray(o))throw new Error('Повреждён раздел '+label);}
function string(s,max,label){if(typeof s!=='string'||s.length>max)throw new Error('Некорректно: '+label);}
function quoteUSD(q,fx){if(!q||q.amount==null||q.exampleOnly)return null;return round(q.amount*(1+(q.tax||0)/100)*(q.quantity||1)/(q.currency==='ARS'?fx:1));}
function level(data,step){const original=data.tasks.find(t=>t.id===step.id&&t.module===step.module);return step.level||original?.level||'project';}
function itemEstimate(item,state){const s=state.items[item.id]||{};if(s.exclude||s.status==='owned'||item.kind==='have')return {value:0,complete:true,ignored:true};if(s.estimate!=null)return {value:s.estimate,complete:true};const value=quoteUSD(item.quote,state.config.fx);return {value:value??0,complete:value!==null&&!item.quote?.partial};}
function defaults(data){
 const state={schema:4,config:{hoursPerMonth:25,elapsedMonths:0,monthlyBudget:0,fx:data.fx.rate},steps:[],entries:[],items:{},changes:[]};
 state.steps=data.tasks.map(t=>({id:t.id,title:t.title,module:t.module,level:level(data,t),hours:round(t.plannedHours??t.hours*1.25),budget:null,items:[],deps:[...t.deps],result:[t.result||'',t.gate||''].filter(Boolean).join('\n'),note:'',basePercent:0,archived:false}));
 const assigned=new Set();for(const step of state.steps){const task=data.tasks.find(t=>t.id===step.id);for(const id of task.items){const i=data.catalog.find(x=>x.id===id);if(i&&i.kind!=='have'&&(!i.optional||task.expanded)&&!assigned.has(id)){step.items.push(id);assigned.add(id);}}}
 for(const i of data.catalog)if(i.kind!=='have'&&!i.optional&&!assigned.has(i.id)){const candidates=state.steps.filter(t=>t.module===i.module);const s=candidates.find(t=>/заказать|заказ|выбрать|выбор|подобрать|принять|подготовить/i.test(t.title)&&t.items.length)||candidates.find(t=>t.items.length)||candidates[0];if(s){s.items.push(i.id);assigned.add(i.id);}}
 for(const s of state.steps)if(!s.items.length)s.budget=0;
 state.original={hours:round(state.steps.reduce((a,s)=>a+s.hours,0)),stepCount:state.steps.length};if(data.expansion)state.catalogExpansions=[data.expansion.id];return state;
}
function expand(state,data){
 validate(state,data);const manifest=data.expansion;if(!manifest||state.catalogExpansions?.includes(manifest.id))return state;
 const out=clone(state),ids=new Set(out.steps.map(s=>s.id)),assigned=new Set(out.steps.flatMap(s=>s.items));
 const additions=defaults(data).steps.filter(s=>manifest.stepIds.includes(s.id)&&!ids.has(s.id));
 additions.forEach(s=>ids.add(s.id));for(const s of additions){s.deps=s.deps.filter(id=>ids.has(id));s.items=s.items.filter(id=>{if(assigned.has(id))return false;assigned.add(id);return true});if(!s.items.length)s.budget=0;out.steps.push(s);}
 out.catalogExpansions=[...(out.catalogExpansions||[]),manifest.id];out.changes.push('Добавлены все направления: '+additions.length+' шагов. Прежние оценки, записи и покупки сохранены.');out.changes=out.changes.slice(-500);return validate(out,data);
}
function migrate(old,data){
 if(old?.schema===4)return expand(old,data);
 if(old?.schema!==3)throw new Error('Поддерживаются редакции 3 и 4');
 object(old.progress,'старый прогресс');object(old.items,'старые покупки');object(old.config,'старые настройки');
 const state=defaults(data);if(old.config.fx!=null)state.config.fx=finite(old.config.fx,.01,1e7,'Курс');
 let n=0;
 for(const step of state.steps){const p=old.progress[step.id]||{},o=old.overrides?.[step.id]||{};const originalTask=data.tasks.find(t=>t.id===step.id);step.hours=originalTask.expanded?originalTask.plannedHours:round((o.hours??originalTask.hours)*(1+(old.config.buffer??25)/100));step.basePercent=p.percent??0;step.note=p.note||step.note;
   if(old.config.modules&&!old.config.modules.includes(step.module)&&!data.tasks.find(t=>t.id===step.id).expanded)step.archived=true;
   if(p.actualHours>0)state.entries.push({id:'migrated-work-'+(++n),stepId:step.id,month:1,hours:p.actualHours,amount:null,currency:'USD',fx:state.config.fx,percent:null,note:'Перенесённое время из редакции 3',itemId:null});
 }
 for(const [id,i] of Object.entries(old.items)){const item=data.catalog.find(x=>x.id===id);if(!item)throw new Error('Неизвестная старая позиция '+id);state.items[id]={...i};delete state.items[id].amount;delete state.items[id].date;delete state.items[id].currency;delete state.items[id].fx;
   let step=state.steps.find(s=>s.items.includes(id));if(!step&&i.include){step=state.steps.find(s=>s.module===item.module)||state.steps[0];step.items.push(id);}
   if(i.amount!=null){finite(i.amount,0,1e12,'Старый платёж');if(!['ARS','USD'].includes(i.currency))throw new Error('Некорректная старая валюта');if(i.currency==='ARS')finite(i.fx,.01,1e7,'Курс старой покупки');state.entries.push({id:'migrated-money-'+(++n),stepId:step?.id||state.steps[0].id,month:1,hours:0,amount:i.amount,currency:i.currency,fx:i.fx||state.config.fx,percent:null,note:'Покупка из редакции 3: '+item.title,itemId:id});}
 }
 state.original={hours:round(state.steps.filter(s=>!s.archived).reduce((a,s)=>a+s.hours,0)),stepCount:state.steps.filter(s=>!s.archived).length};state.changes.push('Перенесены часы, готовность и платежи из редакции 3.');return validate(state,data);
}
function active(state){return state.steps.filter(s=>!s.archived);}
function entriesFor(state,id){return state.entries.filter(e=>e.stepId===id);}
function percent(state,step,month=Infinity){let result=step.basePercent;state.entries.map((e,i)=>({...e,index:i})).filter(e=>e.stepId===step.id&&e.percent!==null&&e.month<=month).sort((a,b)=>a.month-b.month||a.index-b.index).forEach(e=>result=e.percent);return result;}
function amountUSD(e){return e.amount===null?null:round(e.amount/(e.currency==='ARS'?e.fx:1));}
function stepBudget(data,state,step){
 if(step.budget!==null)return {value:step.budget,complete:true,unknown:0,manual:true};
 const values=step.items.map(id=>itemEstimate(data.catalog.find(i=>i.id===id),state));return {value:round(values.reduce((a,i)=>a+i.value,0)),complete:values.length>0&&values.every(i=>i.complete),unknown:values.length?values.filter(i=>!i.complete).length:1,manual:false};
}
function rows(data,state){let cursor=0;return active(state).map(s=>{const start=cursor;cursor=round(cursor+s.hours);const p=percent(state,s),entries=entriesFor(state,s.id),cost=stepBudget(data,state,s);return {...s,start,end:cursor,percent:p,earned:round(s.hours*p/100),actual:round(entries.reduce((a,e)=>a+e.hours,0)),spent:round(entries.reduce((a,e)=>a+(amountUSD(e)??0),0)),hasTime:entries.some(e=>e.hours>0),hasPayment:entries.some(e=>e.amount!==null),cost};});}
function metrics(data,state){
 const rs=rows(data,state),hours=round(rs.reduce((a,s)=>a+s.hours,0)),earned=round(rs.reduce((a,s)=>a+s.earned,0)),expected=round(Math.min(hours,state.config.hoursPerMonth*state.config.elapsedMonths));
 const actual=round(state.entries.reduce((a,e)=>a+e.hours,0)),spent=round(state.entries.reduce((a,e)=>a+(amountUSD(e)??0),0));
 const activeActual=round(rs.reduce((a,s)=>a+s.actual,0)),activeSpent=round(rs.reduce((a,s)=>a+s.spent,0)),knownBudget=round(rs.reduce((a,s)=>a+s.cost.value,0)),unknown=rs.filter(s=>!s.cost.complete).length;
 const plannedMoney=round(rs.filter(s=>s.cost.complete).reduce((a,s)=>a+s.cost.value*Math.max(0,Math.min(1,(expected-s.start)/s.hours)),0));
 const comparableSpent=round(rs.filter(s=>s.cost.complete).reduce((a,s)=>a+s.spent,0));
 const comparableEarned=round(rs.filter(s=>s.hasTime).reduce((a,s)=>a+s.earned,0));
 const closed=rs.filter(s=>s.percent===100&&s.cost.complete&&(s.hasPayment||s.cost.value===0)),closedPlan=round(closed.reduce((a,s)=>a+s.cost.value,0)),closedActual=round(closed.reduce((a,s)=>a+s.spent,0));
 const moneyTarget=state.config.monthlyBudget>0?round(state.config.monthlyBudget*state.config.elapsedMonths):plannedMoney;
 const moneyActual=state.config.monthlyBudget>0?spent:comparableSpent;
 return {rs,hours,earned,expected,actual,spent,activeActual,activeSpent,comparableEarned,unloggedEarned:round(earned-comparableEarned),archivedHours:round(actual-activeActual),archivedSpent:round(spent-activeSpent),knownBudget,unknown,pace:round(earned-expected),efficiency:round(comparableEarned-activeActual),investedPace:round(actual-state.config.hoursPerMonth*state.config.elapsedMonths),remaining:round(Math.max(0,hours-earned)),months:round(hours/state.config.hoursPerMonth),remainingMonths:round(Math.max(0,hours-earned)/state.config.hoursPerMonth),percent:hours?round(100*earned/hours):0,moneyTarget,moneyActual,moneyDelta:round(moneyActual-moneyTarget),uncomparedSpent:round(spent-comparableSpent),closedCount:closed.length,closedDelta:round(closedActual-closedPlan),forecastKnown:round(spent+rs.filter(s=>s.percent<100).reduce((a,s)=>a+Math.max(0,s.cost.value-s.spent),0))};
}
function archive(state,id){const step=state.steps.find(s=>s.id===id);if(!step)throw new Error('Шаг не найден');step.archived=true;return state;}
function validate(state,data){
 object(state,'план');if(state.schema!==4)throw new Error('Нужен план редакции 4');object(state.config,'настройки');finite(state.config.hoursPerMonth,.25,2000,'Часов в месяц');finite(state.config.elapsedMonths,0,10000,'Прошло месяцев');finite(state.config.monthlyBudget,0,1e9,'Месячный бюджет');finite(state.config.fx,.01,1e7,'Курс');
 if(!Array.isArray(state.steps)||state.steps.length>5000)throw new Error('Повреждён список шагов');if(!Array.isArray(state.entries)||state.entries.length>50000)throw new Error('Повреждён журнал');object(state.items,'покупки');
 const ids=new Set(),items=new Set(data.catalog.map(i=>i.id)),modules=new Set(data.modules.map(m=>m.id)),assigned=new Set();
 for(const s of state.steps){object(s,'шаг');string(s.id,100,'id');if(!/^[a-zA-Z0-9_-]+$/.test(s.id)||ids.has(s.id))throw new Error('Повтор или некорректный id шага');ids.add(s.id);string(s.title,300,'название');if(!s.title.trim())throw new Error('Нужно название шага');if(!modules.has(s.module))throw new Error('Неизвестное направление');finite(s.hours,.25,1e6,'Оценка часов');finite(s.basePercent,0,100,'Готовность');if(s.budget!==null)finite(s.budget,0,1e9,'Смета шага');if(typeof s.archived!=='boolean')throw new Error('Повреждён флаг удаления');string(s.result,6000,'результат');string(s.note,6000,'заметка');if(!Array.isArray(s.items)||!Array.isArray(s.deps))throw new Error('Повреждены связи шага');for(const id of s.items){if(!items.has(id)||assigned.has(id))throw new Error('Позиция отсутствует или учтена дважды: '+id);assigned.add(id);}}
 for(const s of state.steps){if(s.level!==undefined&&!['prepare','setup','practice','project'].includes(s.level))throw new Error('Неизвестный уровень работы');for(const id of s.deps)if(!ids.has(id)||id===s.id)throw new Error('Некорректная зависимость шага');}
 const graph=new Map(state.steps.map(s=>[s.id,s.deps])),marks=new Map();for(const id of graph.keys()){const stack=[[id,false]];while(stack.length){const [key,leaving]=stack.pop();if(leaving){marks.set(key,2);continue;}if(marks.get(key)===1)throw new Error('Цикл в зависимостях шагов');if(marks.get(key)===2)continue;marks.set(key,1);stack.push([key,true]);graph.get(key).forEach(dep=>stack.push([dep,false]));}}
 if(state.catalogExpansions!==undefined&&(!Array.isArray(state.catalogExpansions)||state.catalogExpansions.some(x=>typeof x!=='string'||x.length>100)))throw new Error('Повреждены дополнения каталога');
 const entryIds=new Set();for(const e of state.entries){object(e,'запись');string(e.id,100,'id записи');if(!/^[a-zA-Z0-9_-]+$/.test(e.id)||entryIds.has(e.id))throw new Error('Повтор или некорректный id записи');entryIds.add(e.id);if(!ids.has(e.stepId))throw new Error('Запись относится к отсутствующему шагу');finite(e.month,1,10000,'Месяц записи');if(!Number.isInteger(e.month))throw new Error('Номер месяца должен быть целым');finite(e.hours,0,1e6,'Фактические часы');if(e.amount!==null)finite(e.amount,0,1e12,'Платёж');if(!['ARS','USD'].includes(e.currency))throw new Error('Неизвестная валюта');finite(e.fx,.01,1e7,'Курс платежа');if(e.percent!==null)finite(e.percent,0,100,'Готовность');string(e.note,6000,'заметка записи');if(e.itemId!==null&&!items.has(e.itemId))throw new Error('Неизвестная покупка');}
 for(const [id,i] of Object.entries(state.items)){if(!items.has(id))throw new Error('Неизвестная позиция '+id);object(i,'позиция');for(const key of ['estimate','annual','outsource'])if(i[key]!=null)finite(i[key],0,1e9,key);for(const key of ['model','note','url'])if(i[key]!=null)string(i[key],6000,key);if(i.status!==undefined&&!['planned','ordered','bought','built','tested','mastered','owned'].includes(i.status))throw new Error('Неизвестное состояние покупки');for(const key of ['include','exclude'])if(i[key]!==undefined&&typeof i[key]!=='boolean')throw new Error('Некорректный флаг покупки');}
 if(!Array.isArray(state.changes)||state.changes.length>500)throw new Error('Повреждена история изменений');for(const c of state.changes)string(c,1000,'изменение');object(state.original,'исходная оценка');finite(state.original.hours,0,1e9,'Исходные часы');finite(state.original.stepCount,0,5000,'Исходное число шагов');return state;
}
const api={round,clone,finite,quoteUSD,level,itemEstimate,defaults,expand,migrate,active,entriesFor,percent,amountUSD,stepBudget,rows,metrics,archive,validate};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else global.WorkshopCore=api;
})(typeof window!=='undefined'?window:globalThis);
