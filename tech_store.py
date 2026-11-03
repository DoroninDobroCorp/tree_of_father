"""Revision-checked storage for technology-tree marks. No writes to save.json or workshop.json."""
import copy
import re
from datetime import datetime, timezone

from workshop_store import Conflict, Store

MARKS = {'done', 'active', 'todo'}
MONEY = {'cheap', 'balance', 'time'}


def validate(state, tech_ids):
    def require(ok, message):
        if not ok: raise ValueError(message)
    require(isinstance(state, dict) and state.get('schema') == 1, 'Нужны отметки редакции 1')
    marks = state.get('marks')
    require(isinstance(marks, dict) and len(marks) <= 1000, 'Некорректные отметки')
    for tid, mark in marks.items():
        require(tid in tech_ids and mark in MARKS, 'Неизвестная технология или отметка')
    target = state.get('target', '')
    require(target == '' or target in tech_ids, 'Неизвестная цель')
    require(state.get('money', 'balance') in MONEY, 'Некорректный режим')
    require(set(state) <= {'schema', 'marks', 'target', 'money'}, 'Лишние поля')
    return state


class TechStore(Store):
    """Same write protocol as the hour plan: base revision, request id, backups of the previous version."""

    def __init__(self, directory, tech_ids, lock, keep=50):
        super().__init__(directory, None, lock, keep)
        self.path = self.directory / 'tech.json'
        self.backups = self.directory / 'tech-backups'
        self.tech_ids = set(tech_ids)

    def write(self, request):
        if not isinstance(request, dict): raise ValueError('Некорректный запрос')
        state = validate(request.get('state'), self.tech_ids)
        rid = request.get('requestId'); base = request.get('baseRevision')
        if not isinstance(rid, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}', rid): raise ValueError('Нужен id запроса')
        if type(base) is not int or base < 0: raise ValueError('Нужна исходная ревизия')
        with self.lock:
            old = self.read()
            if old.get('requestId') == rid and old.get('state') == state: return old
            if base != old['revision']: raise Conflict('Отметки уже изменены в другой вкладке или на другом устройстве')
            result = {'revision': base + 1, 'requestId': rid, 'savedAt': datetime.now(timezone.utc).isoformat(), 'state': copy.deepcopy(state)}
            self.directory.mkdir(parents=True, exist_ok=True); self.backups.mkdir(parents=True, exist_ok=True)
            if old.get('state') is not None: self.atomic(self.backups / ('revision-%09d.json' % old['revision']), old)
            self.atomic(self.path, result)
            for path in sorted(self.backups.glob('revision-*.json'))[:-self.keep]: path.unlink()
            return result
