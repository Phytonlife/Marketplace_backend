FROM python:3.12-slim

# Системные зависимости (ДОБАВЛЕН postgresql-client)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходники
COPY . .

# ДЕЛАЕМ СКРИПТ ИСПОЛНЯЕМЫМ (Критически важно!)
RUN chmod +x /app/scripts/entrypoint.sh

# Создаём директории для медиа и статики
RUN mkdir -p /app/media /app/staticfiles

# Непривилегированный пользователь (безопасность)
RUN addgroup --system django && adduser --system --ingroup django django
RUN chown -R django:django /app
USER django

EXPOSE 8000

# Entrypoint обрабатывает миграции и запуск
ENTRYPOINT ["/app/scripts/entrypoint.sh"]