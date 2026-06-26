from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, MasterProfile


class MasterProfileInline(admin.StackedInline):
    model = MasterProfile
    can_delete = False
    verbose_name_plural = _("Профиль мастера")
    fk_name = "user"


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    inlines = [MasterProfileInline]

    list_display = ("email", "username", "role", "is_active", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "username", "phone_number")
    ordering = ("-date_joined",)

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        (_("Персональные данные"), {"fields": ("first_name", "last_name", "phone_number", "avatar")}),
        (_("Роль"), {"fields": ("role",)}),
        (_("Права доступа"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Даты"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "role", "password1", "password2"),
        }),
    )

    def get_inline_instances(self, request, obj=None):
        """
        Умное управление инлайнами:
        1. Прячем инлайн при СОЗДАНИИ нового юзера (obj=None), чтобы избежать IntegrityError от сигналов.
        2. Прячем инлайн, если юзер — не 'master' (чтобы не показывать профиль мастера клиентам).
        """
        if not obj:
            return []  # Не показываем при добавлении нового пользователя

        if obj.role != CustomUser.Role.MASTER:
            return []  # Не показываем, если роль не "Мастер"

        return super().get_inline_instances(request, obj)


@admin.register(MasterProfile)
class MasterProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "city", "rating", "review_count", "is_verified")
    list_filter = ("is_verified", "city")
    search_fields = ("user__email", "city")
    readonly_fields = ("rating", "review_count", "created_at", "updated_at")