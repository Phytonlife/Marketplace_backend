# Marketplace API

Бэкенд маркетплейса услуг (аналог Яндекс Услуг / Profi.ru) на Django + DRF.  
Четыре модуля, 40 файлов, полная Docker-инфраструктура.

---

## Быстрый старт (Docker)

```bash
# 1. Клонируй / распакуй проект
cd marketplace

# 2. Запусти всё одной командой
docker compose up --build

# 3. API доступно на:
#    http://localhost/api/v1/
#    http://localhost/admin/   →  admin@marketplace.local / admin1234
```

Первый запуск занимает ~60 секунд: сборка образа, запуск PostgreSQL, миграции, создание суперпользователя, сборка статики.

---

## Архитектура инфраструктуры

```
                ┌─────────────────────────────────┐
   Browser/     │           Docker Network         │
   Postman  ──▶ │  Nginx :80  ──▶  Gunicorn :8000 │
                │               (Django App)        │
                │                    │              │
                │             PostgreSQL :5432      │
                └─────────────────────────────────-─┘
                         Volumes:
                  postgres_data / media / staticfiles
```

| Сервис | Образ | Роль |
|--------|-------|------|
| `db` | postgres:16-alpine | Хранилище данных |
| `web` | ./Dockerfile (python:3.12) | Django + Gunicorn |
| `nginx` | nginx:1.25-alpine | Reverse proxy, отдача статики/медиа |

---

## Структура проекта

```
marketplace/
├── Dockerfile
├── docker-compose.yml
├── .env                    ← переменные окружения
├── manage.py
├── requirements.txt
├── nginx/
│   └── nginx.conf
├── scripts/
│   └── entrypoint.sh       ← миграции → superuser → collectstatic → gunicorn
└── apps/
    ├── users/              ← Модуль 1: Auth & Пользователи
    ├── services/           ← Модуль 2: Каталог & Услуги
    ├── orders/             ← Модуль 3: Заказы & Отзывы
    └── chat/               ← Модуль 4: Чат & Дашборд
```

---

## Модуль 1 — Auth & Пользователи (`apps/users`)

### Что делает
Управляет пользователями, JWT-авторизацией и профилями мастеров.

### Модели
**`CustomUser`** (наследует AbstractUser)  
Авторизация по email (`USERNAME_FIELD = "email"`).  
Поля: `email` (unique), `phone_number` (unique, nullable), `role` (client/master/admin), `avatar`.

**`MasterProfile`** (OneToOne → CustomUser)  
Создаётся автоматически через сигнал при `role='master'`.  
Поля: `description`, `city`, `rating`, `review_count`, `is_verified`.  
Метод `update_rating(new_rating)` — пересчитывает скользящее среднее.

### API эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/v1/auth/register/` | Регистрация → возвращает JWT |
| POST | `/api/v1/auth/login/` | Вход → возвращает JWT |
| POST | `/api/v1/auth/logout/` | Отзыв refresh-токена (blacklist) |
| POST | `/api/v1/auth/token/refresh/` | Обновление access-токена |
| GET | `/api/v1/auth/me/` | Свой профиль |
| PATCH | `/api/v1/auth/me/` | Обновление профиля |
| POST | `/api/v1/auth/registration/` | Google OAuth (через dj-rest-auth) |

### Ключевые решения
- JWT: access 60 мин, refresh 30 дней с ротацией
- Google Auth через `django-allauth` + `dj-rest-auth` — клиент отправляет `{"code":"..."}`, получает JWT
- Logout инвалидирует токен через SimpleJWT Blacklist
- `RegisterSerializer.to_representation()` после сохранения сразу возвращает JWT-пару

---

## Модуль 2 — Каталог & Услуги (`apps/services`)

### Что делает
Публичный каталог услуг с категориями, фильтрацией и поиском.

### Модели
**`Category`**  
Поддержка вложенности через self-FK `parent → subcategories`.  
`slug` автогенерируется из `name` в `save()`.

**`Service`**  
Привязана к мастеру и категории.  
`cover_image` загружается в `media/services/<master_id>/`.  
`is_active` скрывает услугу от публичного каталога.

### API эндпоинты

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| GET | `/api/v1/categories/` | Все | Список + subcategories |
| GET | `/api/v1/categories/?all=true` | Все | Плоский список всех |
| GET | `/api/v1/services/` | Все | Каталог с фильтрами |
| POST | `/api/v1/services/` | Мастер | Создать услугу |
| GET | `/api/v1/services/{id}/` | Все | Детали услуги |
| PATCH | `/api/v1/services/{id}/` | Владелец | Изменить свою услугу |
| DELETE | `/api/v1/services/{id}/` | Владелец | Удалить свою услугу |

### Параметры фильтрации
```
?category=3          — по ID категории
?category_slug=beauty — по slug
?price_min=500       — цена от
?price_max=5000      — цена до
?price_type=hourly   — тип цены (fixed/hourly)
?search=маникюр      — полнотекстовый поиск по title+description
?ordering=-price     — сортировка (price, -price, created_at, -created_at)
```

### Ключевые решения
- **Read/Write split**: `ServiceReadSerializer` (GET) возвращает вложенные объекты; `ServiceWriteSerializer` (POST/PATCH) принимает `category_id`
- `to_representation()` в WriteSerializer переключает ответ на Read-формат
- `get_queryset` матрица: аноним/клиент → только активные; мастер → свои (все) + чужие активные
- `HiddenField(CurrentUserDefault)` — `master` берётся из `request.user` автоматически

---

## Модуль 3 — Заказы & Отзывы (`apps/orders`)

### Что делает
Управляет полным жизненным циклом заказа и системой отзывов с автопересчётом рейтинга.

### Модели
**`Order`**  
Связывает клиента, мастера и услугу.  
`price_at_booking` — иммутабельный снапшот цены на момент заказа.  
State machine встроена в модель: `ALLOWED_TRANSITIONS` + `transition_to()`.

**`Review`** (OneToOne → Order)  
Только для завершённых заказов. Один заказ — один отзыв.

### State Machine заказа

```
         [Клиент создаёт]
               │
           PENDING ──────────────────────┐
           │    │                        │
      accept   reject               cancel (клиент)
           │    │                        │
       ACCEPTED  REJECTED          CANCELLED
           │
          start
           │
       IN_PROGRESS
           │
         complete
           │
        COMPLETED ──▶ [Клиент оставляет Review]
                              │
                        [Сигнал post_save]
                              │
                    MasterProfile.update_rating()
```

### API эндпоинты

| Метод | URL | Роль | Описание |
|-------|-----|------|----------|
| GET | `/api/v1/orders/` | Auth | Свои заказы |
| POST | `/api/v1/orders/` | Клиент | Создать заказ |
| GET | `/api/v1/orders/{id}/` | Участник | Детали |
| POST | `/api/v1/orders/{id}/accept/` | Мастер | pending → accepted |
| POST | `/api/v1/orders/{id}/reject/` | Мастер | pending → rejected |
| POST | `/api/v1/orders/{id}/start/` | Мастер | accepted → in_progress |
| POST | `/api/v1/orders/{id}/complete/` | Мастер | in_progress → completed |
| POST | `/api/v1/orders/{id}/cancel/` | Клиент | pending/accepted → cancelled |
| GET | `/api/v1/reviews/` | Auth | Список отзывов (`?master_id=X`) |
| POST | `/api/v1/reviews/` | Клиент | Оставить отзыв |

### Ключевые решения
- State machine в **модели**, не во вьюхе — добавить новый переход = одна строка в словаре
- Недопустимый переход → `ValueError` → HTTP 409 Conflict
- Двойная защита Review: queryset-фильтр по `status=completed` + валидация `order.client == request.user`
- Сигнал `post_save(Review)` вызывает `update_rating()` с логированием ошибок (не роняет транзакцию)

---

## Модуль 4 — Чат & Дашборд (`apps/chat`)

### Что делает
Внутрипроектный чат по заказам с системными сообщениями и аналитической панелью мастера.

### Модели
**`Message`**  
`sender=null + is_system=True` → системное уведомление о смене статуса.  
Индексы: `(order, created_at)` для быстрой выборки истории; `(order, created_at, is_system)` для long polling.

### Системные сообщения (автоматически)
При каждом переходе статуса заказа сигнал `post_save(Order)` создаёт сообщение:

| Статус | Текст сообщения |
|--------|----------------|
| accepted | ✅ Заказ принят мастером. Можете обсудить детали в чате. |
| rejected | ❌ Мастер отклонил заказ. |
| in_progress | 🔧 Мастер приступил к работе. |
| completed | 🎉 Заказ завершён. Пожалуйста, оставьте отзыв! |
| cancelled | 🚫 Заказ отменён клиентом. |

### API эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/v1/messages/?order_id=X` | История чата |
| GET | `/api/v1/messages/?order_id=X&after_timestamp=ISO` | Long polling (только новые) |
| POST | `/api/v1/messages/` | Отправить сообщение |
| GET | `/api/v1/dashboard/master/` | Дашборд мастера |

### Дашборд мастера (ответ)
```json
{
  "total_earned": "45000.00",
  "active_orders_count": 3,
  "completed_orders_count": 12,
  "pending_orders_count": 1,
  "rating": 4.83,
  "review_count": 12,
  "unread_messages_count": 5
}
```

### Long Polling
```
GET /api/v1/messages/?order_id=42&after_timestamp=2024-06-01T10:00:00Z
```
Возвращает только сообщения, созданные **после** указанного timestamp.  
Фронтенд делает запрос каждые 3-5 секунд, обновляя `after_timestamp` из `created_at` последнего полученного сообщения.

### Ключевые решения
- Сигнал создания системных сообщений проверяет `update_fields`, чтобы срабатывать **только при смене статуса** (`transition_to` вызывает `save(update_fields=["status", "updated_at"])`)
- Дашборд считает всю аналитику **одним SQL-запросом** через `aggregate()` с условными `Sum(filter=Q(...))`
- Чат заблокирован в статусах `pending` и `rejected/cancelled` — нельзя писать до принятия заказа

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `SECRET_KEY` | `super-secret...` | Django secret key |
| `DEBUG` | `True` | Режим отладки |
| `DB_NAME` | `marketplace` | Имя БД |
| `DB_USER` | `postgres` | Пользователь БД |
| `DB_PASSWORD` | `postgres` | Пароль БД |
| `DJANGO_SUPERUSER_EMAIL` | `admin@marketplace.local` | Email суперпользователя |
| `DJANGO_SUPERUSER_PASSWORD` | `admin1234` | Пароль суперпользователя |
| `GOOGLE_CLIENT_ID` | — | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | — | Google OAuth Secret |
| `NGINX_PORT` | `80` | Порт Nginx на хосте |
| `GUNICORN_WORKERS` | `3` | Количество воркеров Gunicorn |

---

## Полезные команды

```bash
# Запуск
docker compose up --build           # первый запуск
docker compose up -d                # в фоне

# Остановка
docker compose down                 # остановить
docker compose down -v              # остановить + удалить тома (сброс БД)

# Django manage.py
docker compose exec web python manage.py shell
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser

# Логи
docker compose logs web             # логи Django
docker compose logs nginx           # логи Nginx
docker compose logs db              # логи PostgreSQL
docker compose logs -f web          # следить в реальном времени

# Пересборка только Django
docker compose up --build web
```

---

## Примеры запросов (curl)

```bash
# Регистрация
curl -X POST http://localhost/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","username":"user1","password":"pass1234","password_confirm":"pass1234","role":"client"}'

# Логин
curl -X POST http://localhost/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"pass1234"}'

# Каталог услуг с фильтрами
curl "http://localhost/api/v1/services/?search=маникюр&price_max=3000&ordering=-price"

# Создать заказ (с токеном)
curl -X POST http://localhost/api/v1/orders/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"service_id":1,"scheduled_time":"2024-07-15T14:00:00Z","address":"ул. Ленина, 1"}'

# Чат
curl "http://localhost/api/v1/messages/?order_id=1" \
  -H "Authorization: Bearer <access_token>"

# Дашборд мастера
curl http://localhost/api/v1/dashboard/master/ \
  -H "Authorization: Bearer <access_token>"
```

---

## Технологический стек

| Компонент | Технология |
|-----------|-----------|
| Фреймворк | Django 5.0 + DRF 3.15 |
| База данных | PostgreSQL 16 |
| Аутентификация | SimpleJWT + dj-rest-auth + django-allauth |
| Фильтрация | django-filter |
| Изображения | Pillow |
| Сервер | Gunicorn |
| Прокси | Nginx |
| Контейнеризация | Docker + Docker Compose |
