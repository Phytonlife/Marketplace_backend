from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


def avatar_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return f"avatars/{instance.pk}/avatar.{ext}"


class CustomUser(AbstractUser):
    """
    Кастомная модель пользователя.
    Авторизация по email. Роли: client / master / admin.
    """

    class Role(models.TextChoices):
        CLIENT = "client", _("Клиент")
        MASTER = "master", _("Исполнитель")
        ADMIN  = "admin",  _("Администратор")

    email = models.EmailField(
        _("email"),
        unique=True,
        error_messages={"unique": _("Пользователь с таким email уже существует.")},
    )
    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message=_("Формат: '+77001234567'. До 15 цифр."),
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
        db_index=True,
    )
    avatar = models.ImageField(
        _("аватар"),
        upload_to=avatar_upload_path,
        blank=True,
        null=True,
    )

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name         = _("пользователь")
        verbose_name_plural  = _("пользователи")
        ordering             = ["-date_joined"]

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


# ─── Kazakhstan Cities ─────────────────────────────────────────────────────────

class KazakhstanCity(models.TextChoices):
    """
    Полный список городов Казахстана для маркетплейса.
    Значение (value) = slug для URL-фильтрации (?city=atyrau).
    Метка (label)    = отображаемое название на русском.

    Список охватывает все областные центры + крупные города,
    что покрывает 95%+ населения страны.
    """
    ASTANA           = "astana",           _("Астана")
    ALMATY           = "almaty",           _("Алматы")
    SHYMKENT         = "shymkent",         _("Шымкент")
    ATYRAU           = "atyrau",           _("Атырау")
    AKTAU            = "aktau",            _("Актау")
    AKTOBE           = "aktobe",           _("Актобе")
    KARAGANDA        = "karaganda",        _("Караганда")
    TARAZ            = "taraz",            _("Тараз")
    PAVLODAR         = "pavlodar",         _("Павлодар")
    UST_KAMENOGORSK  = "ust_kamenogorsk",  _("Усть-Каменогорск")
    SEMEY            = "semey",            _("Семей")
    URALSK           = "uralsk",           _("Уральск")
    KOSTANAY         = "kostanay",         _("Костанай")
    KYZYLORDA        = "kyzylorda",        _("Кызылорда")
    PETROPAVLOVSK    = "petropavlovsk",    _("Петропавловск")
    KOKSHETAU        = "kokshetau",        _("Кокшетау")
    TURKESTAN        = "turkestan",        _("Туркестан")


class MasterProfile(models.Model):
    """
    Расширенный профиль исполнителя.
    Создаётся автоматически через сигнал при role='master'.

    city — TextChoices по городам Казахстана.
    Дефолт: Атырау (место регистрации стартапа).
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
    city = models.CharField(
        _("город"),
        max_length=20,
        choices=KazakhstanCity.choices,
        default=KazakhstanCity.ATYRAU,
        db_index=True,   # ← фильтрация по городу — частый запрос
    )
    rating = models.DecimalField(
        _("рейтинг"),
        max_digits=3,
        decimal_places=2,
        default=0.0,
        db_index=True,   # ← участвует в сортировке priority_score
    )
    review_count = models.PositiveIntegerField(
        _("количество отзывов"),
        default=0,
    )
    is_verified = models.BooleanField(
        _("верифицирован"),
        default=False,
        help_text=_("Подтверждён администратором платформы"),
        db_index=True,   # ← участвует в priority_score (Case/When)
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("профиль исполнителя")
        verbose_name_plural = _("профили исполнителей")

    def __str__(self):
        return f"MasterProfile({self.user.email}, {self.get_city_display()})"

    def update_rating(self, new_rating: float) -> None:
        """
        Пересчитывает скользящее среднее при добавлении нового отзыва.
        Используется из signals.py приложения orders.
        """
        total = self.rating * self.review_count + new_rating
        self.review_count += 1
        self.rating = round(total / self.review_count, 2)
        self.save(update_fields=["rating", "review_count", "updated_at"])
