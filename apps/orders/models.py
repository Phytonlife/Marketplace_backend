from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Order(models.Model):
    """
    Заказ развлекательной услуги.

    Новые поля для ивентов:
    - duration_hours:  сколько часов/дней нужен исполнитель
    - event_details:   свободный JSON для доп. данных мероприятия:
        {
          "guests_count": 30,
          "child_age": 7,
          "format": "outdoor",
          "theme": "Тачки",
          "wishes": "Хотим шарики и торт",
          "venue_type": "квартира"
        }
    """

    class Status(models.TextChoices):
        PENDING     = "pending",     _("Ожидает подтверждения")
        ACCEPTED    = "accepted",    _("Принят")
        REJECTED    = "rejected",    _("Отклонён")
        IN_PROGRESS = "in_progress", _("В работе")
        COMPLETED   = "completed",   _("Завершён")
        CANCELLED   = "cancelled",   _("Отменён клиентом")

    ALLOWED_TRANSITIONS: dict[str, list[str]] = {
        Status.PENDING:     [Status.ACCEPTED, Status.REJECTED, Status.CANCELLED],
        Status.ACCEPTED:    [Status.IN_PROGRESS, Status.CANCELLED],
        Status.IN_PROGRESS: [Status.COMPLETED],
        Status.COMPLETED:   [],
        Status.REJECTED:    [],
        Status.CANCELLED:   [],
    }

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="client_orders",
        verbose_name=_("клиент"),
        limit_choices_to={"role": "client"},
    )
    master = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="master_orders",
        verbose_name=_("исполнитель"),
        limit_choices_to={"role": "master"},
    )
    service = models.ForeignKey(
        "services.Service",
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name=_("услуга"),
    )
    status = models.CharField(
        _("статус"),
        max_length=15,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    price_at_booking = models.DecimalField(
        _("цена при бронировании"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Зафиксированная цена на момент создания заказа"),
    )
    scheduled_time = models.DateTimeField(_("дата и время мероприятия"))
    address = models.CharField(_("адрес проведения"), max_length=300)
    client_comment = models.TextField(_("комментарий клиента"), blank=True)

    # ── Поля для ивентов ──────────────────────────────────────────────────────

    duration_hours = models.PositiveIntegerField(
        _("продолжительность (часов)"),
        null=True,
        blank=True,
        help_text=_(
            "Сколько часов/дней нужен исполнитель. "
            "Для per_day указывается в сутках."
        ),
    )
    event_details = models.JSONField(
        _("детали мероприятия"),
        default=dict,
        blank=True,
        help_text=_(
            "Свободная структура доп. данных. "
            "Пример: {guests_count, child_age, theme, format, wishes}"
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("заказ")
        verbose_name_plural = _("заказы")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client", "status"]),
            models.Index(fields=["master", "status"]),
            models.Index(fields=["scheduled_time"]),
        ]

    def __str__(self):
        return f"Заказ #{self.pk} [{self.get_status_display()}] — {self.service.title}"

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, [])

    def transition_to(self, new_status: str) -> None:
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Переход из «{self.get_status_display()}» "
                f"в «{Order.Status(new_status).label}» недопустим."
            )
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])

    @property
    def total_price(self):
        """
        Итоговая цена с учётом продолжительности (для почасовых/посуточных).
        Для per_event и fixed — просто price_at_booking.
        """
        from apps.services.models import Service
        if self.duration_hours and self.service.price_type in (
            Service.PriceType.PER_HOUR,
            Service.PriceType.PER_DAY,
        ):
            return self.price_at_booking * self.duration_hours
        return self.price_at_booking


class Review(models.Model):
    """Отзыв клиента после завершения заказа. Один заказ — один отзыв."""

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="review",
        verbose_name=_("заказ"),
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_given",
        verbose_name=_("клиент"),
    )
    master = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_received",
        verbose_name=_("исполнитель"),
    )
    rating = models.PositiveSmallIntegerField(
        _("оценка"),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    text = models.TextField(_("текст отзыва"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("отзыв")
        verbose_name_plural = _("отзывы")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Отзыв на заказ #{self.order_id} — {self.rating}★"
