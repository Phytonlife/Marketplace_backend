from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Category, EventType, Service, ServiceImage

User = get_user_model()


# ─── EventType ────────────────────────────────────────────────────────────────

class EventTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventType
        fields = ["id", "name", "slug", "icon"]


# ─── ServiceImage ─────────────────────────────────────────────────────────────

class ServiceImageSerializer(serializers.ModelSerializer):
    """Одна фотография из галереи услуги."""

    class Meta:
        model = ServiceImage
        fields = ["id", "image", "is_main", "sort_order"]
        read_only_fields = ["id"]


# ─── Category ─────────────────────────────────────────────────────────────────

class SubcategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "icon"]


class CategorySerializer(serializers.ModelSerializer):
    subcategories = SubcategorySerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "icon", "parent", "subcategories"]
        read_only_fields = ["slug"]


# ─── Master short card ────────────────────────────────────────────────────────

class MasterShortSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    avatar = serializers.ImageField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "avatar", "rating", "review_count"]

    def _get_profile(self, obj):
        return getattr(obj, "master_profile", None)

    def get_rating(self, obj) -> float:
        p = self._get_profile(obj)
        return float(p.rating) if p else 0.0

    def get_review_count(self, obj) -> int:
        p = self._get_profile(obj)
        return p.review_count if p else 0


# ─── Service — Read ───────────────────────────────────────────────────────────

class ServiceReadSerializer(serializers.ModelSerializer):
    """
    GET /services/ и GET /services/{id}/

    Возвращает:
    - master        — краткая карточка исполнителя с рейтингом
    - category      — объект категории
    - event_types   — массив типов мероприятий [{id, name, slug, icon}]
    - images        — полная галерея портфолио (обложка + загруженные фото)
    - main_image    — URL главного фото (удобно для карточки в каталоге)
    - price_type_display — человекочитаемый тип цены
    """

    category = SubcategorySerializer(read_only=True)
    master = MasterShortSerializer(read_only=True)
    event_types = EventTypeSerializer(many=True, read_only=True)
    images = ServiceImageSerializer(many=True, read_only=True)
    price_type_display = serializers.CharField(
        source="get_price_type_display", read_only=True
    )
    main_image = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = [
            "id",
            "master",
            "category",
            "event_types",
            "title",
            "description",
            "price",
            "price_type",
            "price_type_display",
            "min_duration",
            "cover_image",
            "main_image",
            "images",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_main_image(self, obj) -> str | None:
        """
        URL главного изображения для карточки каталога.
        Приоритет: ServiceImage(is_main=True) → cover_image → None.
        """
        request = self.context.get("request")
        url = obj.main_image_url
        if url and request:
            return request.build_absolute_uri(url)
        return url


# ─── Service — Write ──────────────────────────────────────────────────────────

class ServiceWriteSerializer(serializers.ModelSerializer):
    """
    POST / PATCH /services/

    Принимает:
    - category_id    — ID категории
    - event_type_ids — список ID типов мероприятий (опционально)
    - Все остальные поля модели

    master берётся из request.user (HiddenField).
    После сохранения возвращает полное Read-представление.
    """

    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
    )
    event_type_ids = serializers.PrimaryKeyRelatedField(
        queryset=EventType.objects.all(),
        source="event_types",
        many=True,
        required=False,
    )
    master = serializers.HiddenField(
        default=serializers.CurrentUserDefault()
    )

    class Meta:
        model = Service
        fields = [
            "id",
            "master",
            "category_id",
            "event_type_ids",
            "title",
            "description",
            "price",
            "price_type",
            "min_duration",
            "cover_image",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Цена должна быть больше нуля.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        if self.instance and request and self.instance.master != request.user:
            raise serializers.ValidationError("Вы не можете редактировать чужую услугу.")
        return attrs

    def create(self, validated_data):
        event_types = validated_data.pop("event_types", [])
        instance = super().create(validated_data)
        if event_types:
            instance.event_types.set(event_types)
        return instance

    def update(self, instance, validated_data):
        event_types = validated_data.pop("event_types", None)
        instance = super().update(instance, validated_data)
        if event_types is not None:
            instance.event_types.set(event_types)
        return instance

    def to_representation(self, instance):
        return ServiceReadSerializer(instance, context=self.context).data
