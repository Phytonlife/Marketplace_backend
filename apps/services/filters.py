import django_filters
from django.db.models import Q

from apps.users.models import KazakhstanCity
from .models import Category, EventType, Service


class ServiceFilter(django_filters.FilterSet):
    """
    Фильтры для GET /api/v1/services/

    ?city=atyrau                   — по городу исполнителя (value из KazakhstanCity)
    ?category=3                    — по ID категории
    ?category_slug=animators       — по slug категории
    ?event_types=1&event_types=2   — по типам мероприятий (OR-логика)
    ?event_type_slug=birthday      — по slug типа мероприятия
    ?price_min=5000&price_max=50000
    ?price_type=per_event
    ?search=аниматор               — полнотекстовый по title+description
    ?verified_only=true            — только верифицированные исполнители

    Фильтр ?city= дублируется в FilterSet для совместимости,
    но основная обработка — в ServiceViewSet.get_queryset().
    """

    city = django_filters.ChoiceFilter(
        choices=KazakhstanCity.choices,
        field_name="master__master_profile__city",
        label="Город",
    )
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.all(),
        label="Категория",
    )
    category_slug = django_filters.CharFilter(
        field_name="category__slug",
        lookup_expr="exact",
        label="Slug категории",
    )
    event_types = django_filters.ModelMultipleChoiceFilter(
        queryset=EventType.objects.all(),
        label="Типы мероприятий",
        conjoined=False,   # OR: услуга подходит хотя бы для одного типа
    )
    event_type_slug = django_filters.CharFilter(
        field_name="event_types__slug",
        lookup_expr="exact",
        label="Slug типа мероприятия",
    )
    price_min = django_filters.NumberFilter(
        field_name="price", lookup_expr="gte", label="Цена от"
    )
    price_max = django_filters.NumberFilter(
        field_name="price", lookup_expr="lte", label="Цена до"
    )
    price_type = django_filters.MultipleChoiceFilter(
        choices=Service.PriceType.choices,
        label="Тип цены",
    )
    verified_only = django_filters.BooleanFilter(
        field_name="master__master_profile__is_verified",
        label="Только верифицированные",
    )
    search = django_filters.CharFilter(
        method="filter_search",
        label="Поиск",
    )

    class Meta:
        model  = Service
        fields = [
            "city", "category", "category_slug",
            "event_types", "event_type_slug",
            "price_min", "price_max", "price_type",
            "verified_only", "search",
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value) | Q(description__icontains=value)
        )
