// Server storage is enabled only on the hosted /workshop page. Portable copies stay local.
const hosted=/^\/workshop\/?$/.test(location.pathname)&&/^https?:$/.test(location.protocol)&&!suffix;
let serverReady=!hosted,serverRevision=null,serverBusy=false,serverConflict=false,serverPending=null;
const pendingKey=KEY+'-pending',revisionKey=KEY+'-revision';
function accessHeaders(){try{const key=localStorage.getItem('svoya-masterskaya-access-key');return key?{'X-Workshop-Key':key}:{};}catch{return {};}}
function syncBadge(message,bad=false){if(!hosted)return;$('#save-status').textContent=message;$('#save-status').className=bad?'save-warn':'';const box=$('#server-sync');if(box){box.querySelector('span').textContent=message;box.querySelector('[data-server-reload]').hidden=!serverConflict;}}
function localSnapshot(value){const raw=JSON.stringify(value);if(lastSaved&&lastSaved!==raw)localStorage.setItem(KEY+'-previous',lastSaved);localStorage.setItem(KEY,raw);lastSaved=raw;state=value;}
function queueServer(){if(!hosted)return;serverPending={baseRevision:serverRevision,requestId:crypto.randomUUID(),state:C.clone(state)};try{localStorage.setItem(pendingKey,JSON.stringify(serverPending));}catch{syncBadge('Копия в памяти — скачай JSON перед закрытием',true);return;}flushServer();}
async function flushServer(){if(!hosted||!serverReady||serverBusy||serverConflict||!serverPending)return;serverBusy=true;const request=serverPending;syncBadge('Сохраняю на сервере…');try{
 const response=await fetch('/api/workshop',{method:'POST',headers:{'Content-Type':'application/json',...accessHeaders()},body:JSON.stringify(request),signal:AbortSignal.timeout(12000)});const body=await response.json();
 if(response.status===409){serverConflict=true;throw Error('На сервере есть другая версия. Скачай свою копию и загрузи серверную.');}if(!response.ok)throw Error(body.error||'Сервер не сохранил изменения');
 serverRevision=body.revision;localStorage.setItem(revisionKey,String(serverRevision));
 if(serverPending===request){serverPending=null;localStorage.removeItem(pendingKey);syncBadge('Сохранено на сервере · копия в этом браузере');}
 else{serverPending.baseRevision=serverRevision;localStorage.setItem(pendingKey,JSON.stringify(serverPending));}
 }catch(e){syncBadge(e.message+' · локальная копия сохранена',true);}finally{serverBusy=false;}
 if(serverPending&&serverPending!==request&&!serverConflict)flushServer();
}
async function initHoursServer(){if(!hosted)return;syncBadge('Загружаю серверное сохранение…');try{
 const response=await fetch('/api/workshop',{headers:accessHeaders(),cache:'no-store',signal:AbortSignal.timeout(12000)});if(!response.ok)throw Error(response.status===403?'Нужен ключ доступа: открой настройки ИИ в дереве':'Не удалось загрузить план с сервера');const body=await response.json();
 const pendingRaw=localStorage.getItem(pendingKey);serverPending=pendingRaw?JSON.parse(pendingRaw):null;
 if(serverPending){const pending=serverPending;C.validate(pending.state,D);const expanded=C.expand(pending.state,D);localSnapshot(expanded);serverRevision=pending.baseRevision;serverReady=true;await flushServer();if(!serverPending&&!serverConflict&&JSON.stringify(expanded)!==JSON.stringify(pending.state))queueServer();}
 else{serverRevision=body.revision;const remote=body.state?C.migrate(body.state,D):state;localSnapshot(remote);localStorage.setItem(revisionKey,String(serverRevision));serverReady=true;syncBadge('Сохранено на сервере · копия в этом браузере');if(!body.state||JSON.stringify(remote)!==JSON.stringify(body.state))queueServer();}
 renderHeader();renderCurrent();applyStageHash();
 }catch(e){syncBadge(e.message+' · повтори подключение',true);}
}
function setupHoursServer(){if(!hosted)return;const el=document.createElement('div');el.id='server-sync';el.className='notice row';el.innerHTML='<span role="status">Подключаю сохранение…</span><button class="small" data-server-retry>Повторить подключение</button><button class="small" data-server-export>Скачать мою копию</button><button class="small" data-server-reload hidden>Загрузить серверную версию</button>';document.querySelector('main').before(el);
 el.querySelector('[data-server-export]').onclick=exportJSON;el.querySelector('[data-server-retry]').onclick=()=>serverReady?flushServer():initHoursServer();
 el.querySelector('[data-server-reload]').onclick=()=>{exportJSON();localStorage.removeItem(pendingKey);serverPending=null;serverConflict=false;serverReady=false;initHoursServer();};
 window.addEventListener('online',()=>serverReady?flushServer():initHoursServer());window.addEventListener('beforeunload',e=>{if(serverPending){e.preventDefault();e.returnValue='';}});initHoursServer();
}
