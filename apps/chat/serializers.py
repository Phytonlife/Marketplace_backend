from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from rest_framework import serializers

from apps.orders.models import Order
from .models import Message

User = get_user_model()


# ─── Sender card ──────────────────────────────────────────────────────────────

class SenderSerializer(serializers.ModelSerializer):
    """Краткая карточка отправителя сообщения."""

    full_name = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "role", "full_name", "avatar_url"]

    def get_avatar_url(self, obj) -> str | None:
        request = self.context.get("request")
        if obj.avatar and request:
            return request.build_absolute_uri(obj.avatar.url)
        return None


# ─── Message ──────────────────────────────────────────────────────────────────

class MessageSerializer(serializers.ModelSerializer):
    """
    Сериализатор сообщений чата.

    GET:  возвращает вложенный объект sender (null для системных).
    POST: принимает order_id + text. sender и is_system устанавливаются во вьюхе.
    """

    sender = SenderSerializer(read_only=True)
    order_id = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(),
        source="order",
        write_only=False,
    )

    class Meta:
        model = Message
        fields = [
            "id",
            "order_id",
            "sender",
            "text",
            "is_system",
            "created_at",
        ]
        read_only_fields = ["id", "sender", "is_system", "created_at"]

    def validate_order_id(self, order: Order) -> Order:
        """Проверяем, что пользователь — участник этого заказа."""
        request = self.context.get("request")
        if request:
            user = request.user
            if order.client != user and order.master != user:
                raise serializers.ValidationError(
                    "Вы не являетесь участником этого заказа."
                )
        return order

    def validate(self, attrs):
        """Проверяем статус заказа: чат открыт только в активных заказах."""
        order: Order = attrs.get("order")
        allowed_statuses = [
            Order.Status.ACCEPTED,
            Order.Status.IN_PROGRESS,
            Order.Status.COMPLETED,
        ]
        if order and order.status not in allowed_statuses:
            raise serializers.ValidationError(
                {"order_id": "В этом статусе нельзя отправлять сообщения. "
                             "Чат доступен для принятых, активных и завершённых заказов."}
            )
        return attrs


# ─── Master Dashboard ─────────────────────────────────────────────────────────

class MasterDashboardSerializer(serializers.Serializer):
    """
    Аналитика мастера. Не ModelSerializer — считается через ORM aggregate.
    Все вычисления производятся в MasterDashboardView.get().
    """

    total_earned = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Сумма всех завершённых заказов",
    )
    active_orders_count = serializers.IntegerField(
        help_text="Принятые + в работе",
    )
    completed_orders_count = serializers.IntegerField(
        help_text="Завершённых заказов всего",
    )
    pending_orders_count = serializers.IntegerField(
        help_text="Ожидают подтверждения",
    )
    rating = serializers.FloatField(
        help_text="Текущий рейтинг из MasterProfile",
    )
    review_count = serializers.IntegerField(
        help_text="Количество отзывов",
    )
    unread_messages_count = serializers.IntegerField(
        help_text="Сообщений в активных заказах за последние 7 дней",
    )
