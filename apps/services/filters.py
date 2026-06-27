import django_filters
from django.db.models import Q

from .models import Category, EventType, Service


class ServiceFilter(django_filters.FilterSet):
    """
    Фильтры для GET /api/v1/services/

    Примеры:
      ?category=3
      ?event_types=1,2          — услуги для дня рождения И корпоратива
      ?price_min=500&price_max=5000
      ?price_type=per_event
      ?search=аниматор
    """

    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.all(),
        label="Категория",
    )
    category_slug = django_filters.CharFilter(
        field_name="category__slug",
        lookup_expr="exact",
        label="Slug категории",
    )

    # Фильтр по типам мероприятий (множественный: ?event_types=1&event_types=2)
    event_types = django_filters.ModelMultipleChoiceFilter(
        queryset=EventType.objects.all(),
        label="Типы мероприятий",
        conjoined=False,  # OR-логика: подходит для хотя бы одного типа
    )
    event_type_slug = django_filters.CharFilter(
        field_name="event_types__slug",
        lookup_expr="exact",
        label="Slug типа мероприятия",
    )

    price_min = django_filters.NumberFilter(field_name="price", lookup_expr="gte", label="Цена от")
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr="lte", label="Цена до")

    price_type = django_filters.MultipleChoiceFilter(
        choices=Service.PriceType.choices,
        label="Тип цены",
    )

    search = django_filters.CharFilter(method="filter_search", label="Поиск")

    class Meta:
        model = Service
        fields = [
            "category", "category_slug",
            "event_types", "event_type_slug",
            "price_min", "price_max", "price_type",
            "search",
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value) | Q(description__icontains=value)
        )
