#!/bin/sh
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Marketplace API — startup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Ждём PostgreSQL напрямую через сеть
echo "⏳ Ожидание PostgreSQL на хосте 'db'..."
while ! pg_isready -h db -p 5432 > /dev/null 2>&1; do
  echo "   postgres не готов — ждём 2 сек..."
  sleep 2
done
echo "✅ PostgreSQL готов"

# Создаем и Применяем миграции
echo "📦 Применяем миграции..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# Создаём суперпользователя если не существует
echo "👤 Проверяем суперпользователя..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
import os
User = get_user_model()
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@marketplace.local')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin1234')
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(
        username='admin',
        email=email,
        password=password,
        role='admin',
    )
    print(f'Суперпользователь создан: {email}')
else:
    print(f'Суперпользователь уже существует: {email}')
"

# Собираем статику
echo "📁 Собираем статику..."
python manage.py collectstatic --noinput --clear

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Запускаем Gunicorn..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile - \
    --log-level ${GUNICORN_LOG_LEVEL:-info}