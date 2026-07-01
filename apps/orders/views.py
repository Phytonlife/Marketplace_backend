from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Order, Review
from .permissions import IsOrderParticipant, IsReviewAuthorOrReadOnly
from .serializers import (
    OrderCreateSerializer,
    OrderReadSerializer,
    ReviewSerializer,
)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _transition_response(order: Order, new_status: str):
    """
    Выполняет переход статуса и возвращает Response.
    ValueError → 409 Conflict.
    """
    try:
        order.transition_to(new_status)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    return Response(
        {"detail": f"Статус изменён на «{order.get_status_display()}».", "status": order.status},
        status=status.HTTP_200_OK,
    )


# ─── Order ViewSet ────────────────────────────────────────────────────────────

class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/v1/orders/       — список заказов текущего пользователя
    POST /api/v1/orders/       — создать заказ (только клиент)
    GET  /api/v1/orders/{id}/  — детали заказа (участники)

    Кастомные действия (state machine):
    POST /api/v1/orders/{id}/accept/    — мастер принимает заказ
    POST /api/v1/orders/{id}/reject/    — мастер отклоняет заказ
    POST /api/v1/orders/{id}/start/     — мастер начинает работу
    POST /api/v1/orders/{id}/complete/  — мастер завершает заказ
    POST /api/v1/orders/{id}/cancel/    — клиент отменяет заказ
    """

    permission_classes = [IsOrderParticipant]

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        return OrderReadSerializer

    def get_queryset(self):
        """
        Клиент видит свои заказы, мастер — заказы на его услуги.
        Staff/admin видят всё.
        """
        user = self.request.user

        base_qs = (
            Order.objects
            .select_related(
                "client",
                "master",
                "master__master_profile",
                "service",
            )
            .prefetch_related("messages")  # для unread_messages_count без N+1
        )

        if user.is_staff:
            return base_qs

        if user.role == "master":
            return base_qs.filter(master=user)

        # Клиент
        return base_qs.filter(client=user)

    def perform_create(self, serializer):
        """
        Извлекаем service из валидированных данных и автоматически:
        - ставим client = request.user
        - ставим master = service.master
        - фиксируем price_at_booking = service.price
        """
        user = self.request.user

        if user.role != "client":
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Создавать заказы могут только клиенты.")

        service = serializer.validated_data["service"]
        serializer.save(
            client=user,
            master=service.master,
            price_at_booking=service.price,
        )

    # ─── State Machine Actions ─────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, pk=None):
        """pending → accepted. Только мастер."""
        order = self.get_object()
        if order.master != request.user:
            return Response(
                {"detail": "Только мастер может принять заказ."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return _transition_response(order, Order.Status.ACCEPTED)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        """pending → rejected. Только мастер."""
        order = self.get_object()
        if order.master != request.user:
            return Response(
                {"detail": "Только мастер может отклонить заказ."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return _transition_response(order, Order.Status.REJECTED)

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        """accepted → in_progress. Только мастер."""
        order = self.get_object()
        if order.master != request.user:
            return Response(
                {"detail": "Только мастер может начать работу."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return _transition_response(order, Order.Status.IN_PROGRESS)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        """in_progress → completed. Только мастер."""
        order = self.get_object()
        if order.master != request.user:
            return Response(
                {"detail": "Только мастер может завершить заказ."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return _transition_response(order, Order.Status.COMPLETED)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """pending | accepted → cancelled. Только клиент."""
        order = self.get_object()
        if order.client != request.user:
            return Response(
                {"detail": "Только клиент может отменить заказ."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return _transition_response(order, Order.Status.CANCELLED)


# ─── Review ViewSet ───────────────────────────────────────────────────────────

class ReviewViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/v1/reviews/       — список отзывов (с фильтрацией по мастеру)
    POST /api/v1/reviews/       — оставить отзыв (только клиент, статус completed)
    GET  /api/v1/reviews/{id}/  — один отзыв
    """

    serializer_class = ReviewSerializer
    permission_classes = [IsReviewAuthorOrReadOnly]

    def get_queryset(self):
        qs = (
            Review.objects
            .select_related("client", "master", "order")
        )
        # ?master_id=X — отзывы конкретного мастера (для публичного профиля)
        master_id = self.request.query_params.get("master_id")
        if master_id:
            qs = qs.filter(master_id=master_id)
        return qs

    def perform_create(self, serializer):
        """
        Дополнительные проверки перед сохранением:
        1. Заказ завершён (валидируется в сериализаторе через queryset)
        2. request.user — клиент этого заказа (тоже в сериализаторе)
        3. Устанавливаем client и master из заказа
        """
        order = serializer.validated_data["order"]
        serializer.save(
            client=self.request.user,
            master=order.master,
        )
