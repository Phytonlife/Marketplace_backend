from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


def service_cover_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return f"services/{instance.master_id}/{instance.pk or 'new'}/cover.{ext}"


class Category(models.Model):
    """
    Категория услуг с поддержкой вложенности (одноуровневая для MVP).
    Пример: Красота → Маникюр, Стрижка
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


class Service(models.Model):
    """
    Услуга мастера в каталоге.
    """

    class PriceType(models.TextChoices):
        FIXED = "fixed", _("Фиксированная цена")
        HOURLY = "hourly", _("За час")

    master = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name=_("мастер"),
        limit_choices_to={"role": "master"},
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="services",
        verbose_name=_("категория"),
    )
    title = models.CharField(_("название"), max_length=200)
    description = models.TextField(_("описание"), blank=True)
    price = models.DecimalField(
        _("цена"),
        max_digits=10,
        decimal_places=2,
    )
    price_type = models.CharField(
        _("тип цены"),
        max_length=10,
        choices=PriceType.choices,
        default=PriceType.FIXED,
    )
    cover_image = models.ImageField(
        _("обложка"),
        upload_to=service_cover_upload_path,
        blank=True,
        null=True,
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
        ]

    def __str__(self):
        return f"{self.title} — {self.master.email}"
