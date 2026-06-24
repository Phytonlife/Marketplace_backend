from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.services.models import Service
from .models import Order, Review

User = get_user_model()


# ─── Inline cards ─────────────────────────────────────────────────────────────

class UserShortSerializer(serializers.ModelSerializer):
    """Краткая карточка пользователя для вложенных данных заказа."""

    full_name = serializers.CharField(read_only=True)
    avatar = serializers.ImageField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "phone_number", "avatar"]


class ServiceShortSerializer(serializers.ModelSerializer):
    """Краткая карточка услуги для вложенных данных заказа."""

    class Meta:
        model = Service
        fields = ["id", "title", "price", "price_type", "cover_image"]


# ─── Order — Read ─────────────────────────────────────────────────────────────

class OrderReadSerializer(serializers.ModelSerializer):
    """
    GET /orders/ и GET /orders/{id}/
    Возвращает полные вложенные объекты клиента, мастера, услуги.
    """

    client = UserShortSerializer(read_only=True)
    master = UserShortSerializer(read_only=True)
    service = ServiceShortSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    has_review = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "client",
            "master",
            "service",
            "status",
            "status_display",
            "price_at_booking",
            "scheduled_time",
            "address",
            "client_comment",
            "has_review",
            "created_at",
            "updated_at",
        ]

    def get_has_review(self, obj) -> bool:
        return hasattr(obj, "review")


# ─── Order — Create ───────────────────────────────────────────────────────────

class OrderCreateSerializer(serializers.ModelSerializer):
    """
    POST /orders/
    Клиент передаёт: service (id), scheduled_time, address, client_comment.
    client / master / status / price_at_booking устанавливаются в perform_create.
    """

    service_id = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.filter(is_active=True),
        source="service",
        write_only=False,
    )

    # Все авто-поля — read_only (заполняются во вьюхе)
    client = serializers.HiddenField(default=serializers.CurrentUserDefault())
    master = UserShortSerializer(read_only=True)
    status = serializers.CharField(read_only=True)
    price_at_booking = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = Order
        fields = [
            "id",
            "service_id",
            "client",
            "master",
            "status",
            "price_at_booking",
            "scheduled_time",
            "address",
            "client_comment",
        ]

    def validate_service_id(self, service):
        """Нельзя заказать услугу у самого себя."""
        request = self.context.get("request")
        if request and service.master == request.user:
            raise serializers.ValidationError("Нельзя заказать свою собственную услугу.")
        return service

    def to_representation(self, instance):
        """После сохранения возвращаем полное Read-представление."""
        return OrderReadSerializer(instance, context=self.context).data


# ─── Review ───────────────────────────────────────────────────────────────────

class ReviewSerializer(serializers.ModelSerializer):
    """
    POST /reviews/  — создать отзыв
    GET  /reviews/  — список отзывов

    Принимает: order_id, rating, text.
    client, master — устанавливаются в perform_create.
    """

    order_id = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.filter(status=Order.Status.COMPLETED),
        source="order",
    )
    client = UserShortSerializer(read_only=True)
    master = UserShortSerializer(read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "order_id",
            "client",
            "master",
            "rating",
            "text",
            "created_at",
        ]
        read_only_fields = ["id", "client", "master", "created_at"]

    def validate_rating(self, value: int) -> int:
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Оценка должна быть от 1 до 5.")
        return value

    def validate_order_id(self, order: Order) -> Order:
        request = self.context.get("request")

        # Только клиент этого заказа может оставить отзыв
        if request and order.client != request.user:
            raise serializers.ValidationError(
                "Оставить отзыв может только клиент, создавший этот заказ."
            )

        # Нельзя оставить второй отзыв
        if hasattr(order, "review"):
            raise serializers.ValidationError(
                "На этот заказ уже есть отзыв."
            )

        return order
