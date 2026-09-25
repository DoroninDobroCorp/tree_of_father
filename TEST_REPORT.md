# Отчёт о тестировании «Своя мастерская · Skill RPG»

Дата проверки: 25 сентября 2026 г.  
Статус: **Все тесты пройдены успешно (100% PASS)**

---

## 1. Состав тестового контура

Тестовый контур покрывает все уровни системы:
1. **Игровая логика и правила (`tests/core.test.js`)** — модульные тесты на Node.js для движка `Core`.
2. **Локальный сервер и API (`tests/test_server.py`)** — интеграционные и модульные тесты на Python 3 для `server.py`.
3. **Целостность DOM и разметки (`tests/browser_smoke.py`)** — дымовое тестирование HTML, JSON-схем и клиентского интерфейса.
4. **Валидация каталога (`src/build_data.py`)** — проверка связности начального профиля.
5. **Валидация схемы OpenAI (`src/build_schema.py`)** — проверка строгости контракта Structured Outputs.

---

## 2. Результаты выполнения тестов

### 2.1. Игровая логика и движок правил (`node tests/core.test.js`)

Команда запуска:
```bash
node tests/core.test.js
```

Результат:
```text
--- Running Core Rules & State Validation Tests ---
  ✓ Initial seed state validates against schema and rules
  ✓ Stats calculation matches initial seed counts
  ✓ Branch and skill stats calculation
  ✓ validateState rejects invalid schemaVersion
  ✓ validateState rejects skill with nonexistent branchId
  ✓ validateState rejects skill with unknown toolId
  ✓ validateState rejects cyclic prerequisites (A -> B -> A)
  ✓ validateEvent enforces caps for each event kind
  ✓ validateEvent rejects single allocation > 30 XP
  ✓ eventFingerprint detects duplicate events
  ✓ applyProposal succeeds with valid add_skill and add_project
  ✓ applyProposal rejects revision mismatch
  ✓ applyProposal rejects risk downgrade (AI cannot lower risk from pro to low)
  ✓ safeTree rejects prototype pollution attempts

Core Tests Result: 14 passed, 0 failed.
```

Проверенные инварианты:
- Начальный каталог v3 полностью соответствует правилам.
- Подсчёт очков совпадает с исходными суммами (70 практика, 8 теория, 49 старый опыт = 127 XP).
- Ограничения XP на одну запись (CAPS: practice=80, theory=20, attempt=15, historical=40).
- Предел XP на один навык в записи (30 XP).
- Обнаружение циклических зависимостей в графе предпосылок.
- Защита от понижения уровня риска при обновлениях ИИ.
- Защита от загрязнения прототипа (`__proto__`).

---

### 2.2. Локальный сервер и API (`python3 -m unittest discover -s tests -p 'test_*.py' -v`)

Команда запуска:
```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Результат:
```text
test_configured_api_key (test_server.TestConfigAndRateLimiter) ... ok
test_default_config (test_server.TestConfigAndRateLimiter) ... ok
test_placeholder_api_key_is_not_configured (test_server.TestConfigAndRateLimiter) ... ok
test_rate_limiter_window (test_server.TestConfigAndRateLimiter) ... ok
test_cors_options (test_server.TestServerEndpoints) ... ok
test_directory_traversal_blocked (test_server.TestServerEndpoints) ... ok
test_health_endpoint (test_server.TestServerEndpoints) ... ok
test_propose_openai_api_error_401 (test_server.TestServerEndpoints) ... ok
test_propose_openai_refusal (test_server.TestServerEndpoints) ... ok
test_propose_rejects_missing_token (test_server.TestServerEndpoints) ... ok
test_propose_rejects_unconfigured_server (test_server.TestServerEndpoints) ... ok
test_propose_rejects_wrong_token (test_server.TestServerEndpoints) ... ok
test_propose_success_with_mocked_openai (test_server.TestServerEndpoints) ... ok
test_serve_index_html (test_server.TestServerEndpoints) ... ok
test_serve_initial_profile_json (test_server.TestServerEndpoints) ... ok
test_serve_nonexistent_file (test_server.TestServerEndpoints) ... ok
test_serve_robots_txt (test_server.TestServerEndpoints) ... ok

----------------------------------------------------------------------
Ran 17 tests in 1.699s

OK
```

Проверенные инварианты:
- Парсинг конфигурации `.env` и переменных окружения.
- Распознавание плейсхолдера ключа (`your_api_key_here` не считается настроенным).
- Почасовой лимитер запросов (скользящее окно, вычисление времени повтора).
- Статическая раздача файлов (`index.html`, `initial-profile.json`, `robots.txt`).
- Защита от Path Traversal (`../../etc/passwd` блокируется).
- Эндпоинт `GET /api/health` возвращает корректную структуру и сессионный токен.
- Эндпоинт `POST /api/propose`:
  - отклоняет запросы без токена или с неверным токеном (401);
  - отклоняет запросы при ненастроенном ключе (400);
  - проксирует запрос в OpenAI со схемой Structured Outputs и возвращает валидное предложение (200);
  - корректно обрабатывает отказ модели `refusal` (400);
  - возвращает понятную ошибку на русском языке при недействительном ключе (401).

---

### 2.3. Дымовое тестирование разметки и интерфейса (`python3 tests/browser_smoke.py`)

Команда запуска:
```bash
python3 tests/browser_smoke.py
```

Результат:
```text
Running static DOM & contract smoke checks...
  ✓ Seed data verified (164 skills, 60 projects)
  ✓ Proposal schema verified
  ✓ App JS startup entry verified
Static smoke check PASSED!
```

---

### 2.4. Сборка и целостность каталога

1. `python3 src/build_data.py`:
   - 14 веток, 164 навыка, 60 проектов, 69 инструментов, 8 событий проверены на отсутствие битых ссылок и дублирующихся ID.
2. `python3 src/build_schema.py`:
   - Схема предложений проверена по строгим правилам OpenAI (`additionalProperties: false`, полнота массива `required`).
3. `python3 src/build.py`:
   - Автономные файлы `index.html` и `maker_rpg.html` успешно собраны из исходных модулей `src/`.
4. `examples/wood-proposal.json`:
   - Пример предложения успешно применён к начальному профилю ревизии 0; ревизия увеличена до 1, каталог пополнился новым навыком и проектом.

---

## 3. Заключение

Проект доведён до полностью рабочего состояния:
- Backend реализован на стандартной библиотеке Python без внешних зависимостей.
- Интеграция с OpenAI API поддерживает актуальный формат Structured Outputs.
- Вся цепочка автоматической сборки, валидации данных и тестов функционирует и проходит 100% проверок.
