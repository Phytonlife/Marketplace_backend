import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.orders.models import Order
from .models import Message, SYSTEM_MESSAGES

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def create_system_message_on_status_change(
    sender, instance: Order, created: bool, update_fields=None, **kwargs
) -> None:
    """
    Создаёт системное сообщение в чате заказа при каждом изменении статуса.

    Срабатывает только при update (created=False) и только если
    поле status входит в update_fields (чтобы не спамить при других save()).

    transition_to() вызывает save(update_fields=["status", "updated_at"]),
    поэтому проверка update_fields надёжно отсекает лишние вызовы.
    """
    if created:
        return  # Новый заказ — системное сообщение не нужно

    # Если save() был вызван без update_fields (полное сохранение),
    # проверяем статус напрямую; если update_fields задан — проверяем наличие "status"
    if update_fields is not None and "status" not in update_fields:
        return

    text = SYSTEM_MESSAGES.get(instance.status)
    if not text:
        return

    try:
        Message.objects.create(
            order=instance,
            sender=None,        # системное — отправителя нет
            text=text,
            is_system=True,
        )
        logger.debug(
            "Системное сообщение создано для заказа #%s, статус=%s",
            instance.pk,
            instance.status,
        )
    except Exception as exc:
        # Не роняем транзакцию смены статуса из-за ошибки чата
        logger.error(
            "Ошибка создания системного сообщения для заказа #%s: %s",
            instance.pk,
            exc,
        )
