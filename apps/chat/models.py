from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Message(models.Model):
    """
    Сообщение в чате заказа.

    sender=None + is_system=True  → системное уведомление о смене статуса.
    sender=User + is_system=False → обычное сообщение участника.

    is_read — флаг прочтения для системы Unread Badges:
      - При создании = False (новое сообщение непрочитано получателем)
      - Системные сообщения: is_read=True сразу (некому «читать»)
      - Переключается в True через POST /messages/mark_as_read/
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
    text      = models.TextField(_("текст"))
    is_system = models.BooleanField(_("системное"), default=False, db_index=True)
    is_read   = models.BooleanField(
        _("прочитано"),
        default=False,
        db_index=True,
        help_text=_(
            "False = непрочитано получателем. "
            "Системные сообщения помечаются прочитанными при создании."
        ),
    )
    created_at = models.DateTimeField(
        _("время отправки"),
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        verbose_name        = _("сообщение")
        verbose_name_plural = _("сообщения")
        ordering            = ["created_at"]
        indexes = [
            # GET /messages/?order_id=X  — история чата
            models.Index(fields=["order", "created_at"], name="msg_order_time_idx"),
            # GET /messages/?order_id=X&after_timestamp=...  — long polling
            models.Index(fields=["order", "created_at", "is_system"], name="msg_order_time_system_idx"),
            # POST /messages/mark_as_read/ + unread_messages_count
            # Покрывает: WHERE order_id=X AND is_read=False AND sender_id != Y
            models.Index(fields=["order", "is_read", "sender"], name="msg_order_unread_idx"),
        ]

    def __str__(self):
        prefix = "⚙ " if self.is_system else ""
        sender = self.sender.email if self.sender else "system"
        read   = "✓" if self.is_read else "○"
        return f"{read} {prefix}[Заказ #{self.order_id}] {sender}: {self.text[:60]}"

    def save(self, *args, **kwargs):
        # Системные сообщения никто не «читает» — сразу помечаем прочитанными,
        # чтобы они не портили счётчик непрочитанных
        if self.is_system:
            self.is_read = True
        super().save(*args, **kwargs)


# ─── Тексты системных сообщений ───────────────────────────────────────────────

SYSTEM_MESSAGES: dict[str, str] = {
    "accepted":    "✅ Заказ принят мастером. Можете обсудить детали в чате.",
    "rejected":    "❌ Мастер отклонил заказ.",
    "in_progress": "🔧 Мастер приступил к работе.",
    "completed":   "🎉 Заказ завершён. Пожалуйста, оставьте отзыв!",
    "cancelled":   "🚫 Заказ отменён клиентом.",
}
