from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


def avatar_upload_path(instance, filename):
    """Сохраняем аватар в media/avatars/<user_id>/<filename>"""
    ext = filename.rsplit(".", 1)[-1]
    return f"avatars/{instance.pk}/avatar.{ext}"


class CustomUser(AbstractUser):
    """
    Кастомная модель пользователя.
    Email используется как основной идентификатор вместо username.
    """

    class Role(models.TextChoices):
        CLIENT = "client", _("Клиент")
        MASTER = "master", _("Мастер")
        ADMIN = "admin", _("Администратор")

    # AbstractUser уже содержит: username, first_name, last_name,
    # email, is_staff, is_active, date_joined
    # Переопределяем email → уникальный, обязательный
    email = models.EmailField(
        _("email address"),
        unique=True,
        error_messages={"unique": _("Пользователь с таким email уже существует.")},
    )

    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message=_("Номер телефона должен быть в формате: '+79991234567'. До 15 цифр."),
    )
    phone_number = models.CharField(
        _("номер телефона"),
        validators=[phone_regex],
        max_length=17,
        unique=True,
        blank=True,
        null=True,
    )
    role = models.CharField(
        _("роль"),
        max_length=10,
        choices=Role.choices,
        default=Role.CLIENT,
    )
    avatar = models.ImageField(
        _("аватар"),
        upload_to=avatar_upload_path,
        blank=True,
        null=True,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]   # username нужен для createsuperuser

    class Meta:
        verbose_name = _("пользователь")
        verbose_name_plural = _("пользователи")
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def is_master(self):
        return self.role == self.Role.MASTER

    @property
    def is_client(self):
        return self.role == self.Role.CLIENT


class MasterProfile(models.Model):
    """
    Расширенный профиль для мастеров (исполнителей).
    Создаётся автоматически через сигнал при role='master'.
    """

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="master_profile",
        verbose_name=_("пользователь"),
    )
    description = models.TextField(
        _("описание"),
        blank=True,
        help_text=_("Расскажите о себе и своих услугах"),
    )
    city = models.CharField(_("город"), max_length=100, blank=True)
    rating = models.DecimalField(
        _("рейтинг"),
        max_digits=3,
        decimal_places=2,
        default=0.0,
    )
    review_count = models.PositiveIntegerField(_("количество отзывов"), default=0)
    is_verified = models.BooleanField(
        _("верифицирован"),
        default=False,
        help_text=_("Подтверждено администратором"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("профиль мастера")
        verbose_name_plural = _("профили мастеров")

    def __str__(self):
        return f"MasterProfile({self.user.email})"

    def update_rating(self, new_rating: float):
        """Пересчитывает средний рейтинг при добавлении нового отзыва."""
        total = self.rating * self.review_count + new_rating
        self.review_count += 1
        self.rating = round(total / self.review_count, 2)
        self.save(update_fields=["rating", "review_count"])
