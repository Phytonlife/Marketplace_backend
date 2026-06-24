import logging
from datetime import datetime, timezone

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.orders.permissions import IsOrderParticipant
from .models import Message
from .serializers import MasterDashboardSerializer, MessageSerializer

logger = logging.getLogger(__name__)


# ─── Message ViewSet ──────────────────────────────────────────────────────────

class MessageViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/v1/messages/?order_id=X           — история чата
    GET  /api/v1/messages/?order_id=X&after_timestamp=ISO8601  — long polling
    POST /api/v1/messages/                        — отправить сообщение

    Доступ: только участники заказа (клиент или мастер).
    """

    serializer_class = MessageSerializer
    permission_classes = [IsOrderParticipant]

    def get_queryset(self):
        user = self.request.user

        # Базовый queryset: только сообщения заказов, где юзер — участник
        qs = (
            Message.objects
            .select_related("sender", "order")
            .filter(
                Q(order__client=user) | Q(order__master=user)
            )
        )

        # ── Фильтр по заказу (обязательный для list) ──────────────────────────
        order_id = self.request.query_params.get("order_id")
        if order_id:
            try:
                qs = qs.filter(order_id=int(order_id))
            except (ValueError, TypeError):
                raise ValidationError({"order_id": "Укажите корректный числовой ID заказа."})
        else:
            # Без order_id возвращаем пустой qs — не хотим сливать все сообщения разом
            qs = qs.none()

        # ── Long Polling: ?after_timestamp=2024-06-01T12:00:00Z ──────────────
        after_ts = self.request.query_params.get("after_timestamp")
        if after_ts:
            try:
                # Принимаем ISO 8601 с Z или +00:00
                after_ts = after_ts.replace("Z", "+00:00")
                dt = datetime.fromisoformat(after_ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                qs = qs.filter(created_at__gt=dt)
            except (ValueError, AttributeError):
                raise ValidationError(
                    {"after_timestamp": "Формат: YYYY-MM-DDTHH:MM:SSZ (ISO 8601 UTC)."}
                )

        return qs.order_by("created_at")

    def perform_create(self, serializer):
        """
        Проверки (часть уже в сериализаторе):
        - Статус заказа допускает отправку (validate в сериализаторе).
        - Устанавливаем sender = request.user, is_system = False.
        """
        serializer.save(
            sender=self.request.user,
            is_system=False,
        )


# ─── Master Dashboard ─────────────────────────────────────────────────────────

class MasterDashboardView(APIView):
    """
    GET /api/v1/dashboard/master/

    Аналитика мастера: выручка, заказы, рейтинг, сообщения.
    Доступ: только пользователи с role='master'.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user

        if user.role != "master":
            return Response(
                {"detail": "Дашборд доступен только для мастеров."},
                status=status.HTTP_403_FORBIDDEN,
            )

        orders_qs = user.master_orders.all()

        # ── Агрегации одним запросом ──────────────────────────────────────────
        stats = orders_qs.aggregate(
            # Суммарный заработок по завершённым заказам
            total_earned=Coalesce(
                Sum(
                    "price_at_booking",
                    filter=Q(status=Order.Status.COMPLETED),
                ),
                Value(0, output_field=DecimalField()),
            ),
            # Активные заказы: принятые + в работе
            active_orders_count=Sum(
                Value(1),
                filter=Q(status__in=[Order.Status.ACCEPTED, Order.Status.IN_PROGRESS]),
            ),
            # Завершённые заказы
            completed_orders_count=Sum(
                Value(1),
                filter=Q(status=Order.Status.COMPLETED),
            ),
            # Ожидают подтверждения
            pending_orders_count=Sum(
                Value(1),
                filter=Q(status=Order.Status.PENDING),
            ),
        )

        # None → 0 для счётчиков (когда заказов нет, Sum возвращает None)
        stats["active_orders_count"]    = stats["active_orders_count"] or 0
        stats["completed_orders_count"] = stats["completed_orders_count"] or 0
        stats["pending_orders_count"]   = stats["pending_orders_count"] or 0

        # ── Рейтинг из MasterProfile ──────────────────────────────────────────
        profile = getattr(user, "master_profile", None)
        stats["rating"]       = float(profile.rating) if profile else 0.0
        stats["review_count"] = profile.review_count  if profile else 0

        # ── Непрочитанные/новые сообщения в активных заказах ─────────────────
        # Считаем сообщения от клиентов (не системные) в активных заказах
        # за последние 7 дней — простая и полезная метрика для MVP
        from datetime import timedelta
        from django.utils import timezone as dj_timezone

        week_ago = dj_timezone.now() - timedelta(days=7)

        unread_count = (
            Message.objects
            .filter(
                order__master=user,
                order__status__in=[Order.Status.ACCEPTED, Order.Status.IN_PROGRESS],
                is_system=False,
                created_at__gte=week_ago,
            )
            .exclude(sender=user)   # не считаем собственные сообщения
            .count()
        )
        stats["unread_messages_count"] = unread_count

        serializer = MasterDashboardSerializer(stats)
        return Response(serializer.data)
