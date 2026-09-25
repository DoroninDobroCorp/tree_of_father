#!/usr/bin/env bash
# macOS Launcher for Своя мастерская · Skill RPG
set -e

# Change to script directory
cd "$(dirname "$0")"

echo "=================================================="
echo "    Своя мастерская · Skill RPG"
echo "=================================================="
echo ""

# Create .env from template if missing
if [ ! -f .env ] && [ -f .env.example ]; then
    echo "Создание файла .env из .env.example..."
    cp .env.example .env
    echo "Файл .env создан. При необходимости укажите в нём OPENAI_API_KEY."
    echo ""
fi

# Detect python executable
PYTHON_BIN=""
for cmd in python3.14 python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON_BIN="$cmd"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "Ошибка: Python 3 не обнаружен в системе."
    echo "Установите Python 3 с официального сайта https://www.python.org/"
    read -p "Нажмите Enter для выхода..."
    exit 1
fi

echo "Используется интерпретатор: $($PYTHON_BIN --version 2>&1)"
echo "Запуск локального сервера..."
echo ""

exec "$PYTHON_BIN" server.py
