from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Message(models.Model):
    """
    Сообщение в чате заказа.

    sender=None + is_system=True → системное уведомление о смене статуса.
    sender=User + is_system=False → обычное сообщение участника.
    """

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name=_("заказ"),
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_messages",
        verbose_name=_("отправитель"),
        help_text=_("null = системное сообщение"),
    )
    text = models.TextField(_("текст"))
    is_system = models.BooleanField(
        _("системное"),
        default=False,
        db_index=True,
    )
    created_at = models.DateTimeField(
        _("время отправки"),
        auto_now_add=True,
        db_index=True,   # ← быстрая сортировка + фильтр after_timestamp
    )

    class Meta:
        verbose_name = _("сообщение")
        verbose_name_plural = _("сообщения")
        ordering = ["created_at"]
        indexes = [
            # Основной паттерн запроса: все сообщения конкретного заказа по времени
            models.Index(fields=["order", "created_at"], name="msg_order_time_idx"),
            # Long polling: сообщения заказа новее заданного timestamp
            models.Index(
                fields=["order", "created_at", "is_system"],
                name="msg_order_time_system_idx",
            ),
        ]

    def __str__(self):
        prefix = "⚙ " if self.is_system else ""
        sender = self.sender.email if self.sender else "system"
        return f"{prefix}[Заказ #{self.order_id}] {sender}: {self.text[:60]}"


# ─── Тексты системных сообщений ───────────────────────────────────────────────
# Вынесены в константу, чтобы легко менять без правки сигналов/логики

SYSTEM_MESSAGES: dict[str, str] = {
    "accepted":    "✅ Заказ принят мастером. Можете обсудить детали в чате.",
    "rejected":    "❌ Мастер отклонил заказ.",
    "in_progress": "🔧 Мастер приступил к работе.",
    "completed":   "🎉 Заказ завершён. Пожалуйста, оставьте отзыв!",
    "cancelled":   "🚫 Заказ отменён клиентом.",
}
