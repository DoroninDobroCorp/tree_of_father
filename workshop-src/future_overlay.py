"""Apply future projects without replacing any previously shipped task or quote."""
from pathlib import Path
import json
R=Path(__file__).parent
CAPABILITIES={
 'small-room':'Первые проекты в комнате',
 'workshop-survey':'Понятный проект двух построек',
 'garage-workshop':'Место для механики и сборки',
 'shed-workshop':'Место для дерева и ЧПУ',
 'mule-v1':'Свой лёгкий перевозчик',
 'mule-v2':'Грузовая оснастка под свои задачи',
 'mule-hydraulics':'Общая энергия для рабочих модулей',
 'mule-crane':'Подъём на отдельном основании',
 'mule-auger':'Бурение под задачу участка',
 'mule-backhoe':'Своя экскаваторная рука',
 'mule-control':'Измерения и повторяемый цикл',
 'porsche-356':'Большой личный автомобильный проект',
}
def add(data):
 f=json.loads((R/'future-projects.json').read_text()); ids=[]
 for r in f['routes']:
  data['modules'].append(dict(id=r['id'],number='',title=r['title'],description=r['intro'],capability=CAPABILITIES[r['id']],requires=r['requires'],family=r['branch'],mode=r['mode'],assumptions=r['assumptions'],sources=r['sources']))
  previous=None;ts=[]
  for pos,s in enumerate(r['steps'],1):
   tid=f"f-{r['id']}-{pos:02d}";ids.append(tid);ts.append(tid)
   data['tasks'].append(dict(id=tid,module=r['id'],title=s['title'],hours=s['hours']/1.25,plannedHours=s['hours'],level=s['level'],deps=[previous] if previous else [],result=s['result'],items=s['items'],lag=0,gate='',project='',expanded=True));previous=tid
  picks=[ts[n-1] for n in r['projectSteps']]
  assert len(picks)==len(r['projects']) and len(set(picks))==len(picks)
  data['journey'][r['id']]=dict(intro=r['intro'],opens=r['opens'],icon=r['icon'],kit='',projects=[dict(id=id,label=label) for id,label in zip(picks,r['projects'])])
 for iid,i in f['items'].items():
  q=None
  if i['quote']:
   ref=f['references'][i['quote']['ref']];q={**ref,'model':ref['title'],'vendor':ref['title'].split(' · ')[0],'terms':ref['note'],'quantity':1,'tax':0,'partial':i['quote']['partial']};q.pop('note')
  data['catalog'].append(dict(id=iid,title=i['title'],note=i['basis'],oldStage='',kind='buy',optional=False,quote=q,module=i['module']))
 data['expansions']=[data['expansion'],dict(id=f['id'],stepIds=ids,label=f['label'])]
 data['planRevisions']=[json.loads((R/name).read_text()) for name in ['building-revision.json','room-base-revision.json']]
 data['facilities']=dict(room='Комната ≈ 2×3 м · 6 м²',garage='Гараж ≈ 3×6 м · 18 м²',shed='Сарай ≈ 4×6 м · 24 м²',note='Сейчас доступна только комната в доме. Гараж и сарай непригодны для работы: сначала обследование, восстановление и приёмка каждого здания, затем размещение оборудования. Размеры со слов владельца, уточняются обмером. Состояние и несущая способность обоих фундаментов ещё не подтверждены.')
 data['facilities']['layout']=[
  dict(title='6 м² · чистое начало',text='Складное место для чертежей, низковольтной электроники, текстиля и ручной сборки. Перед новой операцией проверяем шум, выделения и уборку; хранение оставляет дверь и проход свободными.'),
  dict(title='18 м² · один большой проект',text='В гараже сначала механика и MULE, затем автомобиль. До заказа 356 делаем макет кузова с открытыми дверями, местами снятых деталей и доступом для обслуживания. MULE и оснастку на время автомобильной сборки нужно разместить вне этого рабочего места.'),
  dict(title='24 м² · станки по мере готовности',text='В сарае сначала столярное место, затем LowRider и PrintNC. На плане отмечаем корпус станка, подачу заготовки, обслуживание, пылеудаление и уже стоящее оборудование. Рабочее поле ЧПУ меньше занимаемого им места; до заказа используем размеры выбранной версии.'),
  dict(title='Особые процессы · своё место',text='Для плазмы, печи, мокрой обработки камня и композитов отдельно решаем размещение, вытяжку и коммуникации. Горячую работу отделяем от древесной пыли и горючего хранения. Нужные условия проверяются до установки оборудования; все направления остаются в плане.'),
 ]
 data['facilities']['spaceGate']='Перед покупкой каждого крупного станка проверяем полный макет вместе с уже установленными станками. Если места не хватает, выбираем хранение и перестановку, отдельную площадку или расширение и добавляем соответствующий шаг с часами и сметой. Расширение зданий сверх нынешних 18 и 24 м² в текущую сумму не включено: необходимость и объём ещё не определены.'
 data['facilities']['layoutSources']=[dict(title='LowRider · расчёт габаритов стола',url='https://docs.v1e.com/lowrider/calculator/'),dict(title='PrintNC · планирование размеров',url='https://wiki.printnc.info/en/planning')]
 return data
