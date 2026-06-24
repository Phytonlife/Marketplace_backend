from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Category, Service

User = get_user_model()


# ─── Category ─────────────────────────────────────────────────────────────────

class SubcategorySerializer(serializers.ModelSerializer):
    """Плоское представление дочерней категории (без рекурсии)."""

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "icon"]


class CategorySerializer(serializers.ModelSerializer):
    """
    Категория с вложенными подкатегориями.
    Возвращает subcategories только для корневых узлов (parent=None).
    """

    subcategories = SubcategorySerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "icon", "parent", "subcategories"]
        read_only_fields = ["slug"]


# ─── Master short card (используется внутри ServiceReadSerializer) ────────────

class MasterShortSerializer(serializers.ModelSerializer):
    """Краткая карточка мастера для отображения в услуге."""

    full_name = serializers.CharField(read_only=True)
    rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    avatar = serializers.ImageField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "avatar", "rating", "review_count"]

    def _get_profile(self, obj):
        """Безопасный доступ к MasterProfile через related_name."""
        return getattr(obj, "master_profile", None)

    def get_rating(self, obj):
        profile = self._get_profile(obj)
        return float(profile.rating) if profile else 0.0

    def get_review_count(self, obj):
        profile = self._get_profile(obj)
        return profile.review_count if profile else 0


# ─── Service — Read ───────────────────────────────────────────────────────────

class ServiceReadSerializer(serializers.ModelSerializer):
    """
    Сериализатор для GET /services/ и GET /services/{id}/.
    Возвращает вложенные объекты: категорию и краткий профиль мастера.
    """

    category = SubcategorySerializer(read_only=True)
    master = MasterShortSerializer(read_only=True)
    price_type_display = serializers.CharField(
        source="get_price_type_display", read_only=True
    )

    class Meta:
        model = Service
        fields = [
            "id",
            "master",
            "category",
            "title",
            "description",
            "price",
            "price_type",
            "price_type_display",
            "cover_image",
            "is_active",
            "created_at",
            "updated_at",
        ]


# ─── Service — Write ──────────────────────────────────────────────────────────

class ServiceWriteSerializer(serializers.ModelSerializer):
    """
    Сериализатор для POST / PUT / PATCH.
    Принимает только category_id (не объект).
    Поле master — read_only, устанавливается во вьюхе через perform_create.
    """

    # Явно объявляем, чтобы DRF принимал числовой ID, а не объект
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
        write_only=False,            # возвращаем id в ответе
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
            "title",
            "description",
            "price",
            "price_type",
            "cover_image",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Цена должна быть больше нуля.")
        return value

    def validate(self, attrs):
        # Мастер может редактировать только свои услуги (дополнительная проверка)
        request = self.context.get("request")
        if self.instance and request and self.instance.master != request.user:
            raise serializers.ValidationError(
                "Вы не можете редактировать чужую услугу."
            )
        return attrs

    def to_representation(self, instance):
        """После сохранения возвращаем полное Read-представление."""
        return ServiceReadSerializer(instance, context=self.context).data
