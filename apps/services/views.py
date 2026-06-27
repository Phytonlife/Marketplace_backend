from rest_framework import viewsets, permissions, filters
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend

from .filters import ServiceFilter
from .models import Category, Service
from .permissions import IsMasterOwnerOrReadOnly, IsAdminOrReadOnly
from .serializers import (
    CategorySerializer,
    ServiceReadSerializer,
    ServiceWriteSerializer,
)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/categories/       — список корневых категорий с подкатегориями
    GET /api/v1/categories/{id}/  — одна категория
    """

    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "slug"]

    def get_queryset(self):
        """
        По умолчанию — только корневые категории (parent=None).
        Подкатегории встроены в subcategories через сериализатор.
        Если передан ?all=true — вернуть весь список плоско.
        """
        qs = Category.objects.prefetch_related("subcategories")
        if self.request.query_params.get("all"):
            return qs
        return qs.filter(parent__isnull=True)


class ServiceViewSet(viewsets.ModelViewSet):
    """
    GET    /api/v1/services/          — каталог услуг
    POST   /api/v1/services/          — создать услугу (только мастер)
    GET    /api/v1/services/{id}/     — детали услуги
    PATCH  /api/v1/services/{id}/     — обновить свою услугу
    DELETE /api/v1/services/{id}/     — удалить свою услугу

    Фильтры: ?category=&price_min=&price_max=&search=&price_type=
    Сортировка: ?ordering=price | -price | created_at | -created_at
    """

    permission_classes = [IsMasterOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ServiceFilter
    search_fields = ["title", "description"]
    ordering_fields = ["price", "created_at", "updated_at"]
    ordering = ["-created_at"]

    # Поддержка загрузки файлов (cover_image) через multipart/form-data
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        """
        Разделение Read / Write логики:
        - list / retrieve          → ServiceReadSerializer  (вложенные объекты)
        - create / update / partial → ServiceWriteSerializer (принимает ID-поля)
        """
        if self.action in ("list", "retrieve"):
            return ServiceReadSerializer
        return ServiceWriteSerializer

    def get_queryset(self):
        """
        - Аноним / клиент           → только активные услуги всех мастеров
        - Авторизованный мастер     → свои услуги (любой статус) + чужие активные
        - is_staff / admin          → всё
        """
        user = self.request.user

        base_qs = (
            Service.objects
            .select_related("master", "master__master_profile", "category")
            .prefetch_related("event_types", "images")
        )

        if not user.is_authenticated:
            return base_qs.filter(is_active=True)

        if user.is_staff:
            return base_qs

        if user.role == "master":
            # Свои — все, чужие — только активные
            from django.db.models import Q
            return base_qs.filter(Q(master=user) | Q(is_active=True))

        # Клиент видит только активные
        return base_qs.filter(is_active=True)

    def perform_create(self, serializer):
        """Мастер берётся из текущего запроса, не из тела."""
        serializer.save(master=self.request.user)
