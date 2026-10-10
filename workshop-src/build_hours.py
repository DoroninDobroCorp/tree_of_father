from pathlib import Path
import json,re,runpy
ROOT=Path(__file__).parent
runpy.run_path(str(ROOT/'make_hours_template.py'))
data=json.loads((ROOT/'data.json').read_text())
data['version']=4
data['journey']=json.loads((ROOT/'journey-content.json').read_text())
groups=json.loads((ROOT/'step-levels.json').read_text())
data['stepLevels']=groups['levels']
classification={}
for level,ids in groups['tasks'].items():
 for id in ids.split():
  if id in classification:raise ValueError('Repeated step category: '+id)
  classification[id]=level
if set(classification)!=set(t['id'] for t in data['tasks']):raise ValueError('Incomplete step classification')
for task in data['tasks']:task['level']=classification[task['id']]
from expand_data import expand
data=expand(data)
data["budgetPlanning"]=json.loads((ROOT/"budget-planning.json").read_text())
(ROOT/'expanded-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
guide=(ROOT/'app.js').read_text().split('function renderGuide(){',1)[1].split('function renderSettings(){',1)[0]
guide='function renderGuide(){'+guide
guide=re.sub(r" \['Как читать календарь','[^\n]*\],", " ['Как читать план в часах','Общий объём — сумма оценок шагов. Темп задаётся в часах за месяц. У каждого шага есть результат и полезные предшественники, но календарной даты выполнения нет. Записывай реальную работу и отдельно отмечай готовность результата.'],",guide)
guide=re.sub(r" \['Честное сравнение плана и факта','[^\n]*\],", " ['Три независимых показателя времени','Темп результата: готовый плановый объём минус ожидаемый к выбранному числу месяцев. Трудоёмкость: плановый объём готовой работы минус реально затраченные часы. Вложенное время: реальные часы минус месячный ориентир. Можно делать задачи медленнее оценки, работать больше и в итоге двигаться быстрее общего плана.'],",guide)
guide=guide.replace('Здесь учтены замечания к редакции 2.','Здесь учтены замечания к первоначальному плану.')
app=(ROOT/'hours-app.js').read_text().replace('__GUIDE__',guide).replace('__JOURNEY__',(ROOT/'journey-view.js').read_text()).replace('__STEPS__',(ROOT/'steps-view.js').read_text()).replace('__SYNC__',(ROOT/'hours-sync.js').read_text())
source=(ROOT/'hours-template.html').read_text().replace('__JOURNEY_CSS__',(ROOT/'journey.css').read_text()).replace('__STEPS_CSS__',(ROOT/'steps.css').read_text())
for key,value in [('DATA',json.dumps(data,ensure_ascii=False).replace('<','\\u003c')),('CORE',(ROOT/'hours-core.js').read_text()),('APP',app)]:source=source.replace('__'+key+'__',value)
(ROOT/'hours.html').write_text(source)
print('Built hours.html:',len(source.encode()),'bytes')
