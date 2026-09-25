#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -f .env ] && [ -f .env.example ]; then
    echo "Создание .env из .env.example..."
    cp .env.example .env
    echo "Укажите ваш OPENAI_API_KEY в .env"
fi

python3 server.py "$@"
