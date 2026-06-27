from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.services.models import Service
from .models import Order, Review

User = get_user_model()


# ─── Inline cards ─────────────────────────────────────────────────────────────

class UserShortSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    avatar = serializers.ImageField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "phone_number", "avatar"]


class ServiceShortSerializer(serializers.ModelSerializer):
    price_type_display = serializers.CharField(
        source="get_price_type_display", read_only=True
    )

    class Meta:
        model = Service
        fields = ["id", "title", "price", "price_type", "price_type_display", "cover_image"]


# ─── Order — Read ─────────────────────────────────────────────────────────────

class OrderReadSerializer(serializers.ModelSerializer):
    client = UserShortSerializer(read_only=True)
    master = UserShortSerializer(read_only=True)
    service = ServiceShortSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    has_review = serializers.SerializerMethodField()

    # ИСПРАВЛЕНО: удален source="total_price"
    total_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

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
            "duration_hours",
            "total_price",
            "event_details",
            "scheduled_time",
            "address",
            "client_comment",
            "has_review",
            "created_at",
            "updated_at",
        ]

    def get_has_review(self, obj) -> bool:
        return hasattr(obj, "review")


# ─── Event Details validator ──────────────────────────────────────────────────

EVENT_DETAILS_KNOWN_FIELDS: dict[str, type] = {
    "guests_count": int,
    "child_age": int,
    "theme": str,
    "format": str,
    "venue_type": str,
    "wishes": str,
    "equipment": bool,
    "decor_style": str,
}


def validate_event_details(value: dict) -> dict:
    if not isinstance(value, dict):
        raise serializers.ValidationError("event_details должен быть объектом JSON.")

    errors = {}
    for field, expected_type in EVENT_DETAILS_KNOWN_FIELDS.items():
        if field in value and value[field] is not None:
            if not isinstance(value[field], expected_type):
                errors[field] = f"Ожидается {expected_type.__name__}."

    if "guests_count" in value and isinstance(value["guests_count"], int):
        if value["guests_count"] < 1:
            errors["guests_count"] = "Количество гостей должно быть не менее 1."
        if value["guests_count"] > 10000:
            errors["guests_count"] = "Укажите реальное количество гостей."

    if "child_age" in value and isinstance(value["child_age"], int):
        if not (1 <= value["child_age"] <= 18):
            errors["child_age"] = "Возраст ребёнка должен быть от 1 до 18 лет."

    if errors:
        raise serializers.ValidationError(errors)

    return value


# ─── Order — Create ───────────────────────────────────────────────────────────

class OrderCreateSerializer(serializers.ModelSerializer):
    service_id = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.filter(is_active=True),
        source="service",
    )
    client = serializers.HiddenField(default=serializers.CurrentUserDefault())
    master = UserShortSerializer(read_only=True)
    status = serializers.CharField(read_only=True)
    price_at_booking = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    # ИСПРАВЛЕНО: удален source="total_price"
    total_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    event_details = serializers.JSONField(required=False, default=dict)

    class Meta:
        model = Order
        fields = [
            "id",
            "service_id",
            "client",
            "master",
            "status",
            "price_at_booking",
            "duration_hours",
            "total_price",
            "event_details",
            "scheduled_time",
            "address",
            "client_comment",
        ]

    def validate_service_id(self, service: Service) -> Service:
        request = self.context.get("request")
        if request and service.master == request.user:
            raise serializers.ValidationError("Нельзя заказать свою собственную услугу.")
        return service

    def validate_event_details(self, value: dict) -> dict:
        return validate_event_details(value)

    def validate(self, attrs):
        service: Service = attrs.get("service")
        duration = attrs.get("duration_hours")

        if service and service.price_type in (
                Service.PriceType.PER_HOUR,
                Service.PriceType.PER_DAY,
        ) and not duration:
            raise serializers.ValidationError({
                "duration_hours": (
                    f"Для услуги с типом цены «{service.get_price_type_display()}» "
                    f"необходимо указать продолжительность."
                )
            })

        if service and duration and getattr(service, 'min_duration', None):
            if duration < service.min_duration:
                raise serializers.ValidationError({
                    "duration_hours": (
                        f"Минимальная продолжительность для этой услуги: "
                        f"{service.min_duration} ч."
                    )
                })

        return attrs

    def to_representation(self, instance):
        return OrderReadSerializer(instance, context=self.context).data


# ─── Review ───────────────────────────────────────────────────────────────────

class ReviewSerializer(serializers.ModelSerializer):
    order_id = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.filter(status=Order.Status.COMPLETED),
        source="order",
    )
    client = UserShortSerializer(read_only=True)
    master = UserShortSerializer(read_only=True)

    class Meta:
        model = Review
        fields = ["id", "order_id", "client", "master", "rating", "text", "created_at"]
        read_only_fields = ["id", "client", "master", "created_at"]

    def validate_rating(self, value: int) -> int:
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Оценка должна быть от 1 до 5.")
        return value

    def validate_order_id(self, order: Order) -> Order:
        request = self.context.get("request")
        if request and order.client != request.user:
            raise serializers.ValidationError(
                "Оставить отзыв может только клиент, создавший этот заказ."
            )
        if hasattr(order, "review"):
            raise serializers.ValidationError("На этот заказ уже есть отзыв.")
        return order