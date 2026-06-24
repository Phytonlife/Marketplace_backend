import django_filters
from django.db.models import Q

from .models import Service, Category


class ServiceFilter(django_filters.FilterSet):
    """
    Фильтры для GET /api/v1/services/

    Примеры запросов:
      ?category=3
      ?price_min=500&price_max=5000
      ?search=маникюр
      ?price_type=hourly
      ?category=3&price_min=1000&search=педикюр
    """

    # Фильтр по ID категории (включая подкатегории)
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.all(),
        field_name="category",
        label="Категория",
    )

    # Можно также фильтровать по slug категории
    category_slug = django_filters.CharFilter(
        field_name="category__slug",
        lookup_expr="exact",
        label="Slug категории",
    )

    # Диапазон цен
    price_min = django_filters.NumberFilter(
        field_name="price",
        lookup_expr="gte",
        label="Цена от",
    )
    price_max = django_filters.NumberFilter(
        field_name="price",
        lookup_expr="lte",
        label="Цена до",
    )

    # Тип цены
    price_type = django_filters.ChoiceFilter(
        choices=Service.PriceType.choices,
        label="Тип цены",
    )

    # Полнотекстовый поиск по title + description
    search = django_filters.CharFilter(
        method="filter_search",
        label="Полнотекстовый поиск",
    )

    class Meta:
        model = Service
        fields = ["category", "category_slug", "price_min", "price_max", "price_type", "search"]

    def filter_search(self, queryset, name, value):
        """Поиск по названию и описанию (регистронезависимый)."""
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value) | Q(description__icontains=value)
        )
