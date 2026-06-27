import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


# ─── Upload helpers ────────────────────────────────────────────────────────────

def service_cover_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return f"services/{instance.master_id}/{instance.pk or 'new'}/cover.{ext}"


def service_gallery_upload_path(instance, filename):
    """
    Каждое фото галереи получает UUID-имя, чтобы избежать коллизий
    при параллельной загрузке нескольких файлов.
    Путь: media/gallery/<master_id>/<service_id>/<uuid>.ext
    """
    ext = filename.rsplit(".", 1)[-1]
    return f"gallery/{instance.service.master_id}/{instance.service_id}/{uuid.uuid4().hex}.{ext}"


# ─── Category ─────────────────────────────────────────────────────────────────

class Category(models.Model):
    """
    Двухуровневое дерево категорий.
    Корень: Праздники, Аренда реквизита, Декор...
    Лист:   Аниматоры, Сладкая вата, Оформление залов...
    """

    name   = models.CharField(_("название"), max_length=100, unique=True)
    slug   = models.SlugField(_("slug"), max_length=120, unique=True, blank=True)
    icon   = models.ImageField(_("иконка"), upload_to="categories/icons/", null=True, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subcategories",
        verbose_name=_("родительская категория"),
    )

    class Meta:
        verbose_name        = _("категория")
        verbose_name_plural = _("категории")
        ordering            = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


# ─── EventType ────────────────────────────────────────────────────────────────

class EventType(models.Model):
    """
    Тип мероприятия: для каких праздников подходит услуга.

    ManyToMany → Service, потому что:
    - фильтрация через JOIN быстрее ArrayField на сложных запросах
    - можно добавить sort_order, icon без data-миграции
    - нормализовано: переименование = одна строка в БД
    """

    name       = models.CharField(_("название"), max_length=80, unique=True)
    slug       = models.SlugField(_("slug"), max_length=100, unique=True, blank=True)
    icon       = models.CharField(_("эмодзи"), max_length=10, blank=True,
                                  help_text=_("🎂 🎉 💼 👰"))
    sort_order = models.PositiveSmallIntegerField(_("порядок"), default=0)

    class Meta:
        verbose_name        = _("тип мероприятия")
        verbose_name_plural = _("типы мероприятий")
        ordering            = ["sort_order", "name"]

    def __str__(self):
        return f"{self.icon} {self.name}".strip()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


# ─── Service ──────────────────────────────────────────────────────────────────

class Service(models.Model):
    """
    Услуга исполнителя на платформе Event-маркетплейса.

    PriceType — форматы ценообразования для развлекательной индустрии:
      FIXED     — единая цена (legacy, оставлен для совместимости)
      PER_HOUR  — почасовая аренда (сладкая вата, фотограф, ведущий)
      PER_DAY   — суточная аренда (реквизит, костюмы, декорации)
      PER_EVENT — за мероприятие целиком (аниматор, шоу-программа)
      PER_ITEM  — за штуку (шарики, торт, подарочный бокс)

    video_url — ссылка на YouTube/Vimeo с портфолио исполнителя.
    """

    class PriceType(models.TextChoices):
        FIXED     = "fixed",     _("Фиксированная цена")
        PER_HOUR  = "per_hour",  _("За час")
        PER_DAY   = "per_day",   _("За сутки")
        PER_EVENT = "per_event", _("За мероприятие")
        PER_ITEM  = "per_item",  _("За штуку")

    # ── Relations ──────────────────────────────────────────────────────────────
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
    )

    # ── Core fields ────────────────────────────────────────────────────────────
    title       = models.CharField(_("название"), max_length=200)
    description = models.TextField(_("описание"), blank=True)
    price       = models.DecimalField(_("цена от"), max_digits=10, decimal_places=2)
    price_type  = models.CharField(
        _("тип цены"),
        max_length=10,
        choices=PriceType.choices,
        default=PriceType.PER_EVENT,
    )
    min_duration = models.PositiveSmallIntegerField(
        _("минимальная длительность"),
        null=True,
        blank=True,
        help_text=_("В часах (per_hour) или сутках (per_day)"),
    )

    # ── Media ──────────────────────────────────────────────────────────────────
    cover_image = models.ImageField(
        _("обложка"),
        upload_to=service_cover_upload_path,
        blank=True,
        null=True,
        help_text=_("Главное фото для быстрой загрузки. Галерея — через ServiceImage."),
    )
    video_url = models.URLField(
        _("видео-портфолио"),
        blank=True,
        help_text=_("Ссылка на YouTube, Vimeo или другой видеохостинг"),
    )

    # ── Status ─────────────────────────────────────────────────────────────────
    is_active  = models.BooleanField(_("активна"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("услуга")
        verbose_name_plural = _("услуги")
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["master", "is_active"],     name="svc_master_active_idx"),
            models.Index(fields=["category", "is_active"],   name="svc_cat_active_idx"),
            models.Index(fields=["price"],                   name="svc_price_idx"),
            models.Index(fields=["price_type"],              name="svc_price_type_idx"),
        ]

    def __str__(self):
        return f"{self.title} — {self.master.email}"

    @property
    def main_image_url(self) -> str | None:
        """
        Приоритет: галерея(is_main=True) → cover_image → None.
        Используется в сериализаторе для поля main_image.
        """
        main = self.gallery.filter(is_main=True).first()
        if main:
            return main.image.url
        if self.cover_image:
            return self.cover_image.url
        return None


# ─── ServiceImage ─────────────────────────────────────────────────────────────

class ServiceImage(models.Model):
    """
    Фото портфолио к услуге (галерея). Одна услуга → много фото.

    related_name='gallery' — отличается от 'images' из старого кода,
    чтобы избежать конфликта при миграции. Сериализатор использует 'gallery'.

    is_main=True — только одно фото. Контролируется в save() через UPDATE.
    UUID в имени файла предотвращает коллизии при параллельной загрузке.
    """

    service    = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="gallery",
        verbose_name=_("услуга"),
    )
    image      = models.ImageField(
        _("фотография"),
        upload_to=service_gallery_upload_path,
    )
    is_main    = models.BooleanField(
        _("главное фото"),
        default=False,
        help_text=_("Только одно фото может быть главным"),
    )
    sort_order = models.PositiveSmallIntegerField(_("порядок"), default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _("фото услуги")
        verbose_name_plural = _("галерея услуги")
        ordering            = ["-is_main", "sort_order", "created_at"]

    def __str__(self):
        flag = " ★" if self.is_main else ""
        return f"Фото #{self.pk}{flag} → {self.service.title}"

    def save(self, *args, **kwargs):
        """
        Атомарно снимаем is_main с остальных фото услуги перед сохранением.
        UPDATE + INSERT в одной транзакции — нет race condition.
        """
        if self.is_main:
            ServiceImage.objects.filter(
                service=self.service,
                is_main=True,
            ).exclude(pk=self.pk).update(is_main=False)
        super().save(*args, **kwargs)
