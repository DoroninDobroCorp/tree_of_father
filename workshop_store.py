"""Independent, revision-checked storage for the hour plan. No writes to tree save.json."""
import copy
import json
import math
import os
import re
import tempfile
from pathlib import Path
from datetime import datetime, timezone, date

class Conflict(ValueError):
    pass

def validate(state, catalog):
    def require(ok, message):
        if not ok: raise ValueError(message)
    def number(value, low, high):
        return type(value) in (int, float) and math.isfinite(value) and low <= value <= high
    def text(value, maximum):
        return isinstance(value, str) and len(value) <= maximum
    require(isinstance(state, dict) and state.get('schema') == 4, 'Нужен план редакции 4')
    config=state.get('config', {})
    for key,lo,hi in [('hoursPerMonth',.25,2000),('elapsedMonths',0,10000),('monthlyBudget',0,1e9),('fx',.01,1e7)]:
        require(number(config.get(key),lo,hi), 'Некорректная настройка '+key)
    require(config.get('timeMode','manual') in ['manual','calendar'], 'Некорректный способ сравнения')
    start=config.get('startDate','')
    require(isinstance(start,str), 'Некорректная дата старта')
    if start:
        try: parsed=date.fromisoformat(start)
        except (ValueError,TypeError): raise ValueError('Некорректная дата старта')
        require(parsed.isoformat()==start and '1900-01-01'<=start<='2100-12-31','Некорректная дата старта')
    require(config.get('timeMode')!='calendar' or bool(start), 'Нужна дата старта')
    if 'reservePercent' in config: require(number(config['reservePercent'],0,100), 'Некорректный резерв')
    steps=state.get('steps'); entries=state.get('entries'); items=state.get('items')
    require(isinstance(steps,list) and len(steps)<=5000, 'Некорректные шаги')
    require(isinstance(entries,list) and len(entries)<=50000, 'Некорректный журнал')
    require(isinstance(items,dict), 'Некорректные покупки')
    modules={m['id'] for m in catalog['modules']}; products={i['id'] for i in catalog['catalog']}
    ids=set();assigned=set()
    for s in steps:
        require(isinstance(s,dict),'Некорректный шаг')
        sid=s.get('id');require(text(sid,100) and re.fullmatch(r'[a-zA-Z0-9_-]+',sid) and sid not in ids,'Повтор или некорректный шаг');ids.add(sid)
        require(text(s.get('title'),300) and s['title'].strip(),'Нужно название')
        require(s.get('module') in modules,'Неизвестное направление')
        require(number(s.get('hours'),.25,1e6) and number(s.get('basePercent'),0,100),'Некорректные часы или готовность')
        require(s.get('budget') is None or number(s['budget'],0,1e9),'Некорректная смета')
        require(type(s.get('archived')) is bool and text(s.get('result'),6000) and text(s.get('note'),6000),'Повреждён шаг')
        require(s.get('level','project') in ['prepare','setup','practice','project'],'Некорректная категория')
        require(isinstance(s.get('deps'),list) and isinstance(s.get('items'),list),'Повреждены связи')
        for i in s['items']:
            require(isinstance(i,str) and i in products and i not in assigned,'Покупка отсутствует или учтена дважды');assigned.add(i)
    graph={s['id']:s['deps'] for s in steps}
    for sid,deps in graph.items():
        require(all(isinstance(d,str) and d in ids and d!=sid for d in deps),'Некорректная зависимость')
    # Iterative DFS avoids recursion limits for long custom plans.
    marks={}
    for sid in graph:
        todo=[(sid,False)]
        while todo:
            node,leaving=todo.pop()
            if leaving:marks[node]=2;continue
            require(marks.get(node)!=1,'Цикл в зависимостях')
            if marks.get(node)==2:continue
            marks[node]=1;todo.append((node,True));todo.extend((d,False) for d in graph[node])
    entryids=set()
    for e in entries:
        require(isinstance(e,dict),'Повреждена запись')
        eid=e.get('id');require(text(eid,100) and re.fullmatch(r'[a-zA-Z0-9_-]+',eid) and eid not in entryids,'Повтор или некорректная запись');entryids.add(eid)
        require(e.get('stepId') in ids,'Запись без шага')
        require(number(e.get('month'),1,10000) and e['month']%1==0 and number(e.get('hours'),0,1e6),'Некорректные часы или месяц')
        require(e.get('amount') is None or number(e['amount'],0,1e12),'Некорректный платёж')
        require(e.get('currency') in ['ARS','USD'] and number(e.get('fx'),.01,1e7),'Некорректная валюта')
        require(e.get('percent') is None or number(e['percent'],0,100),'Некорректная готовность')
        require(text(e.get('note'),6000) and (e.get('itemId') is None or e['itemId'] in products),'Повреждена запись')
    for iid,item in items.items():
        require(iid in products and isinstance(item,dict),'Неизвестная покупка')
        for key in ['estimate','annual','outsource']:
            require(item.get(key) is None or number(item[key],0,1e9),'Некорректная цена')
        for key in ['model','note','url']:
            require(item.get(key) is None or text(item[key],6000),'Некорректное описание')
        require(item.get('status','planned') in ['planned','ordered','bought','built','tested','mastered','owned'],'Некорректный статус')
        for key in ['include','exclude']:
            require(key not in item or type(item[key]) is bool,'Некорректный флаг')
    changes=state.get('changes');original=state.get('original',{})
    require(isinstance(changes,list) and len(changes)<=500 and all(text(x,1000) for x in changes),'Некорректная история')
    require(number(original.get('hours'),0,1e9) and number(original.get('stepCount'),0,5000),'Некорректная исходная оценка')
    require(isinstance(state.get('catalogExpansions',[]),list) and all(text(x,100) for x in state.get('catalogExpansions',[])),'Некорректные дополнения')
    return state

class Store:
    def __init__(self, directory, catalog, lock, keep=50):
        self.directory=Path(directory); self.path=self.directory/'workshop.json'; self.backups=self.directory/'workshop-backups'
        self.catalog=catalog;self.lock=lock;self.keep=max(2,keep)
    def read(self):
        if not self.path.exists():return {'revision':0,'state':None}
        return json.loads(self.path.read_text(encoding='utf-8'))
    def write(self, request):
        if not isinstance(request,dict):raise ValueError('Некорректный запрос')
        state=validate(request.get('state'),self.catalog)
        rid=request.get('requestId');base=request.get('baseRevision')
        if not isinstance(rid,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}',rid):raise ValueError('Нужен id запроса')
        if type(base) is not int or base<0:raise ValueError('Нужна исходная ревизия')
        with self.lock:
            old=self.read()
            if old.get('requestId')==rid and old.get('state')==state:return old
            if base!=old['revision']:raise Conflict('План уже изменён в другой вкладке или на другом устройстве')
            result={'revision':base+1,'requestId':rid,'savedAt':datetime.now(timezone.utc).isoformat(),'state':copy.deepcopy(state)}
            self.directory.mkdir(parents=True,exist_ok=True);self.backups.mkdir(parents=True,exist_ok=True)
            if old.get('state') is not None:self.atomic(self.backups/('revision-%09d.json'%old['revision']),old)
            self.atomic(self.path,result)
            for path in sorted(self.backups.glob('revision-*.json'))[:-self.keep]:path.unlink()
            return result
    @staticmethod
    def atomic(path, value):
        fd,name=tempfile.mkstemp(prefix='.workshop-',dir=str(path.parent))
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                json.dump(value,f,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
            os.replace(name,path)
        finally:
            if os.path.exists(name):os.unlink(name)
