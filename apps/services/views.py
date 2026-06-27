from django.db.models import Case, ExpressionWrapper, F, FloatField, Q, Value, When
from django.db.models.functions import Cast
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from .filters import ServiceFilter
from .models import Category, Service
from .permissions import IsMasterOwnerOrReadOnly
from .serializers import CategorySerializer, ServiceReadSerializer, ServiceWriteSerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/categories/       — список корневых категорий с подкатегориями
    GET /api/v1/categories/{id}/  — одна категория
    GET /api/v1/categories/?all=true — плоский список всех
    GET /api/v1/categories/?search=аниматор
    """

    serializer_class   = CategorySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends    = [filters.SearchFilter]
    search_fields      = ["name", "slug"]

    def get_queryset(self):
        qs = Category.objects.prefetch_related("subcategories")
        if self.request.query_params.get("all"):
            return qs
        return qs.filter(parent__isnull=True)


class ServiceViewSet(viewsets.ModelViewSet):
    """
    Каталог услуг Event-маркетплейса со Smart Ranking.

    ── Эндпоинты ───────────────────────────────────────────────────────────────
    GET    /api/v1/services/          Каталог с фильтрацией и ранжированием
    POST   /api/v1/services/          Создать услугу (только исполнитель)
    GET    /api/v1/services/{id}/     Детальная страница услуги
    PATCH  /api/v1/services/{id}/     Обновить свою услугу
    DELETE /api/v1/services/{id}/     Удалить свою услугу

    ── Фильтры ─────────────────────────────────────────────────────────────────
    ?city=atyrau               Город исполнителя
    ?category=3                ID категории
    ?event_types=1&event_types=2   Типы мероприятий (OR)
    ?event_type_slug=birthday  Slug типа мероприятия
    ?price_min=5000&price_max=50000
    ?price_type=per_event
    ?search=аниматор           Полнотекстовый поиск

    ── Smart Ranking (priority_score) ──────────────────────────────────────────
    Формула рассчитывается на уровне PostgreSQL через аннотацию:

      priority_score =
          (rating × 10)          ← рейтинг (0.0–5.0) × 10 = 0–50 очков
        + (review_count × 2)     ← отзывы: 10 отзывов = +20 очков
        + CASE is_verified        ← верификация: +50 очков единовременно
            WHEN True THEN 50
            ELSE 0

    Диапазон: 0–200. Исполнитель с рейтингом 5.0, 50 отзывами и верификацией
    получает: 50 + 100 + 50 = 200 очков.

    Сортировка по умолчанию: [-priority_score, -created_at]
    Можно переопределить: ?ordering=price | -price | created_at

    ── Загрузка файлов ─────────────────────────────────────────────────────────
    Галерея: multipart/form-data с полем images[] (несколько файлов).
    Обложка: поле cover_image (один файл).
    """

    permission_classes = [IsMasterOwnerOrReadOnly]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class    = ServiceFilter
    search_fields      = ["title", "description"]
    ordering_fields    = ["price", "created_at", "updated_at", "priority_score"]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return ServiceReadSerializer
        return ServiceWriteSerializer

    # ── Smart Ranking annotation ──────────────────────────────────────────────

    @staticmethod
    def _priority_score_annotation():
        """
        Аннотация priority_score на уровне SQL.

        Использует ExpressionWrapper + Cast для правильного типа Float,
        чтобы PostgreSQL не усекал результат до INT.

        SQL-эквивалент (упрощённо):
          (mp.rating::float * 10)
          + (mp.review_count * 2)
          + CASE WHEN mp.is_verified THEN 50 ELSE 0 END
        """
        rating_score = ExpressionWrapper(
            Cast(
                F("master__master_profile__rating"),
                output_field=FloatField(),
            ) * Value(10.0),
            output_field=FloatField(),
        )

        review_score = ExpressionWrapper(
            F("master__master_profile__review_count") * Value(2),
            output_field=FloatField(),
        )

        verified_bonus = Case(
            When(master__master_profile__is_verified=True, then=Value(50.0)),
            default=Value(0.0),
            output_field=FloatField(),
        )

        return ExpressionWrapper(
            rating_score + review_score + verified_bonus,
            output_field=FloatField(),
        )

    def get_queryset(self):
        """
        Матрица доступа:
          Аноним / Клиент  → только is_active=True
          Исполнитель      → свои (любой статус) + чужие активные
          Staff / Admin    → всё без фильтров

        Фильтр по городу из query param ?city= применяется здесь,
        а не в FilterSet, потому что он работает через JOIN на
        master__master_profile и требует аннотации перед фильтрацией.

        select_related / prefetch_related предотвращают N+1:
          - master, master_profile, category → JOIN
          - event_types, gallery            → prefetch (2 доп. запроса)
        """
        user = self.request.user

        qs = (
            Service.objects
            .select_related(
                "master",
                "master__master_profile",
                "category",
                "category__parent",
            )
            .prefetch_related("event_types", "gallery")
            .annotate(priority_score=self._priority_score_annotation())
        )

        # ── Фильтр по городу ─────────────────────────────────────────────────
        city = self.request.query_params.get("city")
        if city:
            qs = qs.filter(master__master_profile__city=city)

        # ── Матрица доступа ───────────────────────────────────────────────────
        if not user.is_authenticated:
            qs = qs.filter(is_active=True)
        elif user.is_staff:
            pass  # admin видит всё
        elif user.role == "master":
            qs = qs.filter(Q(master=user) | Q(is_active=True))
        else:
            qs = qs.filter(is_active=True)

        # ── Сортировка по умолчанию: Smart Ranking ────────────────────────────
        # ?ordering= из OrderingFilter переопишет это, если передан явно
        if not self.request.query_params.get("ordering"):
            qs = qs.order_by("-priority_score", "-created_at")

        return qs

    def perform_create(self, serializer):
        """
        master берётся из request.user (не из тела запроса).
        serializer.create() внутри вызовет _bulk_create_images().
        """
        serializer.save(master=self.request.user)
