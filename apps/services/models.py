from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


# ─── Upload paths ─────────────────────────────────────────────────────────────

def service_cover_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return f"services/{instance.master_id}/{instance.pk or 'new'}/cover.{ext}"


def service_gallery_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    import uuid
    return f"services/{instance.service.master_id}/{instance.service_id}/gallery/{uuid.uuid4().hex}.{ext}"


# ─── Category ─────────────────────────────────────────────────────────────────

class Category(models.Model):
    """
    Категория услуг с поддержкой вложенности.
    Пример: Праздники → Аниматоры, Оформление зала
    """

    name = models.CharField(_("название"), max_length=100, unique=True)
    slug = models.SlugField(_("slug"), max_length=120, unique=True, blank=True)
    icon = models.ImageField(
        _("иконка"),
        upload_to="categories/icons/",
        null=True,
        blank=True,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subcategories",
        verbose_name=_("родительская категория"),
    )

    class Meta:
        verbose_name = _("категория")
        verbose_name_plural = _("категории")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


# ─── EventType ────────────────────────────────────────────────────────────────

class EventType(models.Model):
    """
    Тип мероприятия, для которого подходит услуга.

    Примеры: День рождения, Корпоратив, Свадьба, Выпускной,
             Детский праздник, Новый год, Онлайн-формат.

    Выбран ManyToMany вместо ArrayField потому что:
    - Легко фильтровать через JOIN: ?event_types=1,3
    - Можно добавлять иконки/цвета к типам без миграций данных
    - Работает на любой БД (ArrayField — только PostgreSQL)
    - Нормализованная структура: переименовать тип = одна запись
    """

    name = models.CharField(_("название"), max_length=80, unique=True)
    slug = models.SlugField(_("slug"), max_length=100, unique=True, blank=True)
    icon = models.CharField(
        _("эмодзи-иконка"),
        max_length=10,
        blank=True,
        help_text=_("Например: 🎂 🎉 💼 👰"),
    )
    sort_order = models.PositiveSmallIntegerField(_("порядок сортировки"), default=0)

    class Meta:
        verbose_name = _("тип мероприятия")
        verbose_name_plural = _("типы мероприятий")
        ordering = ["sort_order", "name"]

    def __str__(self):
        prefix = f"{self.icon} " if self.icon else ""
        return f"{prefix}{self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


# ─── Service ──────────────────────────────────────────────────────────────────

class Service(models.Model):
    """
    Услуга исполнителя (аниматор, сладкая вата, оформление праздника и т.д.)

    PriceType — множество форматов ценообразования для развлекательных услуг:
    - FIXED:     единая цена за услугу (архивный, оставлен для совместимости)
    - PER_HOUR:  аренда почасовая (сладкая вата, фотограф)
    - PER_DAY:   аренда посуточная (реквизит, декорации)
    - PER_EVENT: за мероприятие целиком (аниматор на праздник, ведущий)
    - PER_ITEM:  за штуку (шарики, торт, подарочный бокс)
    """

    class PriceType(models.TextChoices):
        FIXED     = "fixed",     _("Фиксированная цена")       # совместимость
        PER_HOUR  = "per_hour",  _("За час")
        PER_DAY   = "per_day",   _("За сутки")
        PER_EVENT = "per_event", _("За мероприятие")
        PER_ITEM  = "per_item",  _("За штуку")

    master = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name=_("исполнитель"),
        limit_choices_to={"role": "master"},
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="services",
        verbose_name=_("категория"),
    )
    event_types = models.ManyToManyField(
        EventType,
        blank=True,
        related_name="services",
        verbose_name=_("типы мероприятий"),
        help_text=_("Для каких мероприятий подходит услуга"),
    )
    title = models.CharField(_("название"), max_length=200)
    description = models.TextField(_("описание"), blank=True)
    price = models.DecimalField(_("цена от"), max_digits=10, decimal_places=2)
    price_type = models.CharField(
        _("тип цены"),
        max_length=10,
        choices=PriceType.choices,
        default=PriceType.PER_EVENT,
    )
    cover_image = models.ImageField(
        _("обложка"),
        upload_to=service_cover_upload_path,
        blank=True,
        null=True,
    )
    # Минимальный и максимальный период (для per_hour / per_day)
    min_duration = models.PositiveSmallIntegerField(
        _("минимальная длительность"),
        null=True,
        blank=True,
        help_text=_("В часах (для per_hour) или сутках (для per_day)"),
    )
    is_active = models.BooleanField(_("активна"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("услуга")
        verbose_name_plural = _("услуги")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["master", "is_active"]),
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["price"]),
            models.Index(fields=["price_type"]),
        ]

    def __str__(self):
        return f"{self.title} — {self.master.email}"

    @property
    def main_image_url(self):
        """Главное фото: сначала помеченное is_main, затем cover_image."""
        main = self.images.filter(is_main=True).first()
        if main:
            return main.image.url
        if self.cover_image:
            return self.cover_image.url
        return None


# ─── ServiceImage (Галерея) ───────────────────────────────────────────────────

class ServiceImage(models.Model):
    """
    Фото портфолио к услуге. Одна услуга → много фото.
    is_main=True — главная карточка (только одна, контролируется через save).
    """

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name=_("услуга"),
    )
    image = models.ImageField(
        _("фотография"),
        upload_to=service_gallery_upload_path,
    )
    is_main = models.BooleanField(
        _("главное фото"),
        default=False,
        help_text=_("Только одно фото может быть главным"),
    )
    sort_order = models.PositiveSmallIntegerField(_("порядок"), default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("фото услуги")
        verbose_name_plural = _("галерея услуги")
        ordering = ["-is_main", "sort_order", "created_at"]

    def __str__(self):
        flag = " [главное]" if self.is_main else ""
        return f"Фото #{self.pk} → {self.service.title}{flag}"

    def save(self, *args, **kwargs):
        """
        Если это фото помечается как главное —
        снимаем is_main со всех остальных фото этой услуги.
        """
        if self.is_main:
            ServiceImage.objects.filter(
                service=self.service, is_main=True
            ).exclude(pk=self.pk).update(is_main=False)
        super().save(*args, **kwargs)
