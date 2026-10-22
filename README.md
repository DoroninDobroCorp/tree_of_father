<div align="center">

# 🛠️ Tree of Father · Workshop Skill RPG
### Своя мастерская · Личная карта DIY/Maker-навыков

**A local-first RPG skill tree and journal for makers, DIY enthusiasts, and home craftspeople.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero-success?style=flat-square)](#)
[![Local-First](https://img.shields.io/badge/Storage-Local--First-blueviolet?style=flat-square)](#)
[![AI Assisted](https://img.shields.io/badge/AI-Human--in--the--Loop-orange?style=flat-square)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

<br/>

[🇬🇧 English](#-english) &nbsp;|&nbsp; [🇷🇺 Русский](#-русский) &nbsp;|&nbsp; [📖 Полная документация (RU)](README_RU.md) &nbsp;|&nbsp; [🏗️ Архитектура](ARCHITECTURE.md)

</div>

---

<h2 id="-english">🇬🇧 English</h2>

### Overview

**Tree of Father (Своя мастерская)** turns maker and DIY skills into a tangible RPG-style progression system. Track practical workshop experience, inventory, projects, and learning paths without vanity metrics or gamified fluff.

Built with an uncompromising **local-first, zero-dependency** philosophy: works as a standalone single-file web app directly in any browser, or backed by an ultra-lightweight Python server with Git auto-commit persistence.

### Key Highlights

- 🌳 **14 Disciplines & 391 Skills:** From woodworking, joinery, and plumbing to electronics (Arduino/ESP), composites (fiberglass/molds), 3D modeling (Fusion 360), and metalworking.
- 📋 **120 Project Cards & 134 Tools Catalog:** Detailed prerequisites, required tools (with multilingual EN/ES/RU names), risk tiers, and measurable criteria.
- 🎯 **Verifiable Mastery vs XP:** XP measures verified hands-on hours/repairs; skill mastery requires passing first-person checklist criteria.
- 🤖 **Human-in-the-Loop AI Assistant:** AI proposes skill mappings, project breakdowns, and XP estimations based on natural language project logs. The AI never mutates state directly — you review and approve every atomic diff.
- 🔒 **Zero External Dependencies & Private by Design:** Single self-contained HTML/CSS/JS frontend. Python backend uses 100% standard library (`http.server`, `urllib.request`, `json`, `secrets`). No npm packages, no pip packages, no external CDN requests.
- 💾 **Git-Backed Auto-Save:** Every change is version-controlled with automated local Git commits, rotating file backups, and 3-step undo/redo.

### Quick Start

#### Standalone Mode (No Server Required)
Just double-click or open **`index.html`** in any modern web browser. All state is preserved locally via `localStorage` with JSON export/import support.

#### Full Server Mode (with AI Assistant & Git Persistence)
```bash
# Clone the repository
git clone https://github.com/DoroninDobroCorp/Tree_of_Father.git
cd Tree_of_Father

# (Optional) Configure AI provider for assistance
cp .env.example .env
# Edit .env with your OpenAI-compatible API key (OpenAI, Gemini, VibeProxy, Ollama, etc.)

# Run local backend (Zero pip installs needed — pure Python stdlib!)
python3 server.py
```
Open **`http://127.0.0.1:8765`** in your browser.

---

<h2 id="-русский">🇷🇺 Русский</h2>

### Описание

**Tree of Father (Своя мастерская · Skill RPG)** — персональная интерактивная карта maker/DIY-навыков, каталог реальных домашних проектов и журнал мастерской.

Проект создан для реальной практики и удовольствия от созидания своими руками, а не ради бесконечной прокачки абстрактных чисел.

### Что внутри

- 🌲 **14 крупных направлений и 391 навык:** столярное дело, сантехника, электрика, электроника (Arduino, ESP), композиты (стеклопластик, матрицы), 3D-моделирование (Fusion 360), металлообработка, отделка.
- 📦 **120 проектов и 134 инструмента:** карточки с целями, этапами, техникой безопасности, необходимым оснащением (с названиями на русском и испанском).
- ✅ **Честный учёт освоения:** XP начисляется строго за подтверждённую завершённую практику или изученную теорию; критерии освоения формулируются от первого лица («Отличаю...», «Сделал...», «Могу...»).
- 🧠 **ИИ-наставник под контролем человека:** подбор навыков и декомпозиция задач по текстовому описанию через OpenAI, Gemini или локальные LLM. Никаких бесконтрольных правок: ИИ возвращает структурированный diff (Proposal), который вы подтверждаете вручную.
- 🛡️ **Zero Dependencies & Local-First:** фронтенд — полностью автономный `index.html` без внешних библиотек и CDN; бэкенд на Python использует исключительно стандартную библиотеку (никаких `pip install`).
- 🗄️ **Надёжное версионирование:** автоматические коммиты в локальный Git при каждом сохранении, ротация бэкапов в `data/backups/`, отмена правок.

### Запуск

```bash
# 1. Без сервера — просто откройте index.html в браузере

# 2. С локальным сервером и ИИ:
python3 server.py
# Откройте http://127.0.0.1:8765
```

Подробные инструкции, правила начисления опыта и разбор направлений смотрите в **[README_RU.md](README_RU.md)**.
Архитектура бэкенда и контракт данных описаны в **[ARCHITECTURE.md](ARCHITECTURE.md)**.

---

### 📄 License

MIT © [Vladimir Doronin](https://github.com/DoroninDobroCorp)
