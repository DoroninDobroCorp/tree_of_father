"""Append future-project skills and route links; existing catalog entries are preserved except explicit building corrections."""
from pathlib import Path
import json
R=Path(__file__).parent;S=R/'tree-integration/src'
seed=json.loads((S/'seed.json').read_text());D=json.loads((R/'expanded-data.json').read_text());F=json.loads((R/'future-projects.json').read_text());links=json.loads((S/'workshop-links.json').read_text());skills={s['id']:s for s in seed['skills']}
def add(id,title,parents,goal,exercise,criteria):
 if id in skills:return
 s=dict(id=id,branchId=id.split('.')[0],module='Большие проекты мастерской',title=title,goal=goal,exercise=exercise,proof='; '.join(criteria),criteria=criteria,prerequisites=parents.split(),toolIds=skills[parents.split()[0]]['toolIds'][:],risk='pro',stage=4,archived=False);seed['skills'].append(s);skills[id]=s
add('building.workshop_survey','Обследование постройки под мастерскую','building.loads building.maintenance','Перевести состояние здания в решение о восстановлении.','Собрать обмер и заключение специалиста по фундаменту, стенам и крыше.',['Записал размеры и признаки дефектов','Получил вывод о сохраняемых конструкциях','Сравнил варианты восстановления по ведомостям'])
add('building.workshop_layout','Размещение процессов в небольшой мастерской','base.workshop mechanics.vent','Распределить хранение, проходы и несовместимые процессы.','Сделать макет комнаты, гаража и сарая под реальные изделия.',['Проверил проход и обслуживание на макете','Разделил чистые, пыльные и горячие операции','Определил вентиляцию с профильным специалистом'])
add('transport.prototype_drive','Совместимость привода самодельного перевозчика','mechanics.drive transport.smallengine','Выбирать полный согласованный привод вместо случайных компонентов.','Составить таблицу валов, колёс, сцепления и передачи для проекта V1.',['Записал размеры и режим каждого узла','Подтвердил комплектность у продавца','Согласовал подбор и ограничения с механиком'])
add('transport.prototype_accept','Приёмка малого транспортного прототипа','transport.prototype_drive metal.welded_frame','Проверять машину по проекту и измерениям.','Пройти программу V0/V1 на закрытой площадке с механиком.',['Отделил цели нагрузки от подтверждённых пределов','Проверил рулевое и тормоза по программе','Сохранил протокол и повторный осмотр'])
add('mechanics.powerpack','Приёмка модульной гидростанции','mechanics.hydraulic mechanics.drive','Согласовывать мощность, интерфейсы и тепловой режим.','С гидравликом принять станцию для одного рабочего модуля.',['Составил паспорт давления, расхода и масла','Проверил останов и удержание нагрузки по проекту','Записал нагрев цикла и обслуживание'])
add('mechanics.load_module','Приёмка рабочего модуля на своём основании','mechanics.powerpack building.loads','Отделять устойчивость основания от мощности инструмента.','С конструктором принять кран, стойку бура или руку по отдельному проекту.',['Получил расчёт опор и рабочих границ','Проверил силовые детали и удержание','Сохранил протокол и паспорт конкретного модуля'])
add('electronics.machine_cycle','Измерение и ограниченный автоматический цикл','electronics.failsafe electronics.sensors','Управлять по измеряемым состояниям и проверенным отказам.','Сначала на малом стенде отладить наблюдаемый цикл с ручной отменой.',['Откалибровал измеряемые состояния и записал логи','Отделил защиту от обычного компьютера','Проверил потерю связи и неизвестное состояние'])
add('transport.replica_plan','Проект реплики и документированная база','transport.auto transport.body','Согласовать кузов, базу и путь оформления до закупок.','С техническим представителем составить паспорт проекта 356.',['Выбрал кузов и проверил комплектность','Проверил документы и состояние базы','Уточнил применимый путь регистрации'])
add('transport.replica_accept','Приёмка собранной реплики автомобиля','transport.replica_plan transport.prototype_accept','Довести сборку до проверенного результата и оформленного применения.','Пройти техническую приёмку, закрытые испытания и согласованное оформление реплики.',['Получил проверку ответственных систем','Сохранил протокол и исправления после испытаний','Подтвердил документы до публичной дороги'])
selected={
 'small-room':'base.workshop building.workshop_layout',
 'workshop-survey':'building.workshop_survey building.workshop_layout',
 'garage-workshop':'building.workshop_survey building.workshop_layout building.maintenance',
 'shed-workshop':'building.workshop_survey building.workshop_layout building.frame',
 'mule-v1':'transport.prototype_drive transport.prototype_accept metal.welded_frame',
 'mule-v2':'transport.prototype_accept mechanics.drive',
 'mule-hydraulics':'mechanics.powerpack mechanics.hydraulic',
 'mule-crane':'mechanics.load_module mechanics.powerpack',
 'mule-auger':'mechanics.load_module mechanics.powerpack',
 'mule-backhoe':'mechanics.load_module mechanics.powerpack metal.welded_frame',
 'mule-control':'electronics.machine_cycle electronics.failsafe electronics.sensors',
 'porsche-356':'transport.replica_plan transport.replica_accept transport.body composite.mould_accept'}
for r in F['routes']:
 pid='route-'+r['id'];ss=selected[r['id']].split();assert all(s in skills for s in ss);ts=[t for t in D['tasks'] if t['module']==r['id']]
 p=dict(id=pid,title=r['title'],description=r['intro']+' '+r['assumptions']+' Подробные шаги, часы и деньги — в плане мастерской; завершение шагов само по себе не начисляет XP.',branchIds=list(dict.fromkeys(skills[s]['branchId'] for s in ss)),skillIds=ss,steps=[t['title'] for t in ts],checks=[t['result'] for t in ts if t['level']=='project'][-4:],toolIds=list(dict.fromkeys(t for s in ss for t in skills[s]['toolIds']))[:30],stage=4,risk='care' if r['id']=='small-room' else 'pro',kind='practice',size=str(sum(t['plannedHours'] for t in ts))+' ч · изменяемая оценка',archived=False)
 if r['id'] in ['garage-workshop','shed-workshop'] and D.get('planRevisions'):
  p['checks']=[ts[3]['result'],ts[-1]['result']]
 if not any(x['id']==pid for x in seed['projects']):seed['projects'].append(p)
 elif r['id'] in ['garage-workshop','shed-workshop'] and D.get('planRevisions'):
  seed['projects'][next(n for n,x in enumerate(seed['projects']) if x['id']==pid)]=p
 links[pid]=r['id']
if any(r['id']=='workshop-room-base-consistency-v1' for r in D.get('planRevisions',[])):
 base=next(m for m in D['modules'] if m['id']=='base')
 ts=[t for t in D['tasks'] if t['module']=='base']
 p=next(p for p in seed['projects'] if p['id']=='route-base')
 p.update(description=base['description']+' Результаты и учёт работы раскрыты в отдельном плане в часах. Оценки можно менять; отмеченные этапы сами по себе не начисляют опыт.',steps=[t['title'] for t in ts],checks=[t['result'] for t in ts[-4:]])
 seed['catalogVersion']=10
else:
 seed['catalogVersion']=9 if D.get('planRevisions') else 8
(S/'seed.json').write_text(json.dumps(seed,ensure_ascii=False,indent=2)+'\n');(S/'workshop-links.json').write_text(json.dumps(links,ensure_ascii=False,indent=2)+'\n')
print(len(seed['skills']),'skills;',len(seed['projects']),'projects;',len(links),'route links')
