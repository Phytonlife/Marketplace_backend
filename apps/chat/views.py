import logging
from datetime import datetime, timezone

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.orders.permissions import IsOrderParticipant
from .models import Message
from .serializers import MasterDashboardSerializer, MessageSerializer

logger = logging.getLogger(__name__)


class MessageViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Чат по заказам.

    ── Эндпоинты ───────────────────────────────────────────────────────────────
    GET  /api/v1/messages/?order_id=X
         История чата. Возвращает сообщения с полем is_read.

    GET  /api/v1/messages/?order_id=X&after_timestamp=ISO8601
         Long polling — только новые сообщения после указанного времени.

    POST /api/v1/messages/
         Отправить сообщение. is_read=False по умолчанию.

    POST /api/v1/messages/mark_as_read/
         Пометить все входящие сообщения заказа как прочитанные.
         Body: {"order_id": 42}
         Помечает сообщения, где sender != request.user и is_read=False.

    ── Доступ ──────────────────────────────────────────────────────────────────
    Только участники заказа (IsOrderParticipant).
    """

    serializer_class   = MessageSerializer
    permission_classes = [IsOrderParticipant]

    def get_queryset(self):
        user = self.request.user

        qs = (
            Message.objects
            .select_related("sender", "order")
            .filter(Q(order__client=user) | Q(order__master=user))
        )

        # ── Обязательный фильтр по заказу ─────────────────────────────────────
        order_id = self.request.query_params.get("order_id")
        if order_id:
            try:
                qs = qs.filter(order_id=int(order_id))
            except (ValueError, TypeError):
                raise ValidationError({"order_id": "Укажите корректный числовой ID заказа."})
        else:
            qs = qs.none()

        # ── Long Polling ──────────────────────────────────────────────────────
        after_ts = self.request.query_params.get("after_timestamp")
        if after_ts:
            try:
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
        serializer.save(
            sender=self.request.user,
            is_system=False,
            # is_read=False — дефолт в модели, не нужно передавать явно
        )

    # ── Unread Badges ─────────────────────────────────────────────────────────

    @action(detail=False, methods=["post"], url_path="mark_as_read")
    def mark_as_read(self, request):
        """
        POST /api/v1/messages/mark_as_read/
        Body: {"order_id": 42}

        Помечает is_read=True для всех входящих непрочитанных сообщений заказа.
        «Входящие» = написаны не нами (exclude sender=request.user).
        Системные сообщения уже is_read=True при создании, не затрагиваются.

        Один UPDATE-запрос через .update() — без загрузки объектов в Python.

        Ответ:
          {"status": "success", "updated_count": N}
          {"error": "order_id обязателен"}          — 400 если нет order_id
          {"error": "Заказ не найден или недоступен"} — 404 если не участник
        """
        order_id = request.data.get("order_id")

        if not order_id:
            return Response(
                {"error": "order_id обязателен"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверяем, что пользователь — участник этого заказа
        user = request.user
        is_participant = Order.objects.filter(
            id=order_id,
        ).filter(
            Q(client=user) | Q(master=user)
        ).exists()

        if not is_participant:
            return Response(
                {"error": "Заказ не найден или у вас нет доступа к нему."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Один UPDATE: все чужие непрочитанные сообщения этого заказа
        updated = (
            Message.objects
            .filter(order_id=order_id, is_read=False)
            .exclude(sender=user)          # не трогаем собственные сообщения
            .update(is_read=True)
        )

        logger.debug(
            "mark_as_read: user=%s, order_id=%s, updated=%d",
            user.email, order_id, updated,
        )

        return Response(
            {"status": "success", "updated_count": updated},
            status=status.HTTP_200_OK,
        )


# ─── Master Dashboard ─────────────────────────────────────────────────────────

class MasterDashboardView(APIView):
    """
    GET /api/v1/dashboard/master/

    Аналитика мастера. Поле unread_messages_count теперь использует
    is_read=False вместо временного окна — точный счётчик.
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

        stats = orders_qs.aggregate(
            total_earned=Coalesce(
                Sum("price_at_booking", filter=Q(status=Order.Status.COMPLETED)),
                Value(0, output_field=DecimalField()),
            ),
            active_orders_count=Sum(
                Value(1),
                filter=Q(status__in=[Order.Status.ACCEPTED, Order.Status.IN_PROGRESS]),
            ),
            completed_orders_count=Sum(
                Value(1),
                filter=Q(status=Order.Status.COMPLETED),
            ),
            pending_orders_count=Sum(
                Value(1),
                filter=Q(status=Order.Status.PENDING),
            ),
        )

        stats["active_orders_count"]    = stats["active_orders_count"]    or 0
        stats["completed_orders_count"] = stats["completed_orders_count"] or 0
        stats["pending_orders_count"]   = stats["pending_orders_count"]   or 0

        profile = getattr(user, "master_profile", None)
        stats["rating"]       = float(profile.rating) if profile else 0.0
        stats["review_count"] = profile.review_count  if profile else 0

        # Точный счётчик непрочитанных через is_read=False (не временное окно)
        stats["unread_messages_count"] = (
            Message.objects
            .filter(
                order__master=user,
                order__status__in=[Order.Status.ACCEPTED, Order.Status.IN_PROGRESS],
                is_read=False,
                is_system=False,
            )
            .exclude(sender=user)
            .count()
        )

        return Response(MasterDashboardSerializer(stats).data)
