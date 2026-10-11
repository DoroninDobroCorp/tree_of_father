"""Build an additive overlay; data.json remains the original 101-step plan."""
from pathlib import Path
import json

ROOT = Path(__file__).parent

def expand(data):
    routes = json.loads((ROOT / 'expansion-routes.json').read_text())
    quotes = {
        'ceramics': (12000, 'ARS', 'Chilavert Blanca con Chamote · 5 kg', 'Insumos para Ceramica', 'https://insumosceramica.com.ar/product-category/arcillas-y-barbotinas/', 'Только глина 5 кг. Согласовать массу и режим с мастерской до покупки; занятие, глазури, обжиг и доставка отдельно.', 'page'),
        'sewing': (450000, 'ARS', 'Singer Simple 3223', 'Singer Argentina', 'https://singerargentina.com.ar/tienda/', 'Цена машины. Раскрой, ткань, иглы и доставка отдельно; сначала проба на выбранной ткани.', 'page'),
        'energy': (102100, 'ARS', 'Enertik PS-100M · 100 W', 'Enertik Argentina', 'https://enertik.com/ar/tienda/fotovoltaica/paneles-solares/panel-solar-enertik-monocristalino-100w/', 'Только панель с IVA. Регулятор, аккумулятор, защита и кабели отдельно. На странице упаковка одной панели ещё ARS 20 500; доставку уточнить.', 'page'),
        'garden': (94990, 'ARS', 'Rehau · капельный полив, 64 детали', 'Easy Argentina', 'https://www.easy.com.ar/kit-de-riego-para-balcon-rehau/p', 'Цена из поисковой выдачи; карточка не подтвердила стоимость при повторном открытии. Перепроверить наличие и цену. Грядка, грунт, растения и доставка отдельно.', 'search'),
        'pcb': (95.67558, 'USD', 'Hantek 6022BE USB · 20 MHz', 'Elemon Argentina', 'https://www.elemon.com.ar/products/detail/code/IN6357000', 'Цена продавца в USD без IVA и IIBB; пересчёт продавцом по официальному курсу Banco Nación. Платы, компоненты, налоги и доставка отдельно. Только низковольтные учебные схемы.', 'page'),
    }
    overview=json.loads((ROOT/'expansion-overview.json').read_text())
    ids=[]
    later=data['modules'].pop()
    for index, r in enumerate(routes, 15):
        mid=r['id']; kitid='x-'+mid+'-kit'
        data['modules'].append(dict(id=mid,number=str(index).zfill(2),title=r['title'],description=r['intro'],capability=overview[mid][0],requires=r['requires'],family=r['branch'],mode=r['mode']))
        quote=None
        if mid in quotes:
            amount,currency,model,vendor,url,terms,access=quotes[mid]
            quote=dict(amount=amount,currency=currency,model=model,vendor=vendor,url=url,terms=terms,access=access,tax=0,quantity=1,partial=True,checked='2026-10-10')
        note=r['kit']+' Режим: '+r['mode']+'. Сначала проверить общий инструмент и остатки материалов. Оплатить только недостающее; занятия, аренду и доставку уточнить в Эль-Больсоне.'
        if mid=='cleaning':note+=' Kärcher Puzzi 4/16 уже есть: второй аппарат в смету не включён.'
        if mid=='thermoplastics':note+=' Строительный фен берётся из существующего каталога; он учитывается один раз.'
        data['catalog'].append(dict(id=kitid,title=r['title']+' · материалы и доступ к оборудованию',note=note,oldStage=str(index),kind='buy',optional=False,quote=quote,module=mid))
        stageids=[]
        for pos, s in enumerate(r['steps'],1):
            tid=f'x-{mid}-{pos:02d}';ids.append(tid);stageids.append(tid)
            data['tasks'].append(dict(id=tid,module=mid,title=s['title'],hours=s['hours']/1.25,plannedHours=s['hours'],level=s['level'],deps=stageids[-2:-1],result=s['result'],items=([kitid]+(['s0-heat'] if mid=='thermoplastics' else [])) if pos==2 else [],lag=0,gate='',project='',expanded=True))
        projects=[dict(id=tid,label=s['title']) for tid,s in zip(stageids,r['steps']) if s['level']=='project'][:3]
        for project,label in zip(projects,overview[mid][1]):project['label']=label
        data['journey'][mid]=dict(intro=r['intro'],opens=r['opens'],icon=r['icon'],kit=r['kit'],projects=projects)
    data['modules'].append(later)
    data['expansion']=dict(id='all-directions-v1',stepIds=ids)
    data['treeURL']='https://tree.54-38-65-155.sslip.io/'
    from future_overlay import add
    data=add(data)
    route_order=json.loads((ROOT/'journey-order.json').read_text())
    ordered_ids=[mid for group in route_order['groups'] for mid in group['modules']]
    modules={m['id']:m for m in data['modules']}
    assert len(ordered_ids)==len(set(ordered_ids)), 'Repeated route in journey order'
    assert set(ordered_ids)==set(modules)-{'later'}, 'Journey order must include every route'
    positions={mid:i for i,mid in enumerate(ordered_ids)}
    for mid in ordered_ids:
        assert all(positions[dep]<positions[mid] for dep in modules[mid]['requires']), ('Route prerequisite follows route',mid)
        modules[mid]['number']=str(positions[mid]).zfill(2)
    task_modules={t['id']:t['module'] for t in data['tasks']}
    for task in data['tasks']:
        assert all(positions[task_modules[dep]]<=positions[task['module']] for dep in task['deps']), ('Step prerequisite follows route',task['id'])
    data['modules']=[modules[mid] for mid in ordered_ids]+[modules['later']]
    data['routeOrder']=route_order
    return data
