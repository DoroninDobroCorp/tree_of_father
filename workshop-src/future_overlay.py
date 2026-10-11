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
  picks=[tid for tid,s in zip(ts,r['steps']) if s['level']=='project']
  if len(picks)<len(r['projects']):picks=ts[-len(r['projects']):]
  data['journey'][r['id']]=dict(intro=r['intro'],opens=r['opens'],icon=r['icon'],kit='',projects=[dict(id=id,label=label) for id,label in zip(picks,r['projects'])])
 for iid,i in f['items'].items():
  q=None
  if i['quote']:
   ref=f['references'][i['quote']['ref']];q={**ref,'model':ref['title'],'vendor':ref['title'].split(' · ')[0],'terms':ref['note'],'quantity':1,'tax':0,'partial':i['quote']['partial']};q.pop('note')
  data['catalog'].append(dict(id=iid,title=i['title'],note=i['basis'],oldStage='',kind='buy',optional=False,quote=q,module=i['module']))
 data['expansions']=[data['expansion'],dict(id=f['id'],stepIds=ids,label=f['label'])]
 data['facilities']=dict(room='Комната ≈ 2×3 м · 6 м²',garage='Гараж ≈ 3×6 м · 18 м²',shed='Сарай ≈ 4×6 м · 24 м²',note='Размеры со слов владельца, уточняются обмером. В комнате — CAD, электроника, текстиль и чистая сборка. Гараж — первый кандидат под механику и сборку техники; сарай — дерево и ЧПУ после восстановления. Состояние и несущая способность обоих фундаментов ещё не подтверждены.')
 return data
