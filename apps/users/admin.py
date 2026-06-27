from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, MasterProfile


class MasterProfileInline(admin.StackedInline):
    model = MasterProfile
    can_delete = False
    verbose_name_plural = _("Профиль исполнителя")
    fk_name = "user"
    fields = ["city", "description", "rating", "review_count", "is_verified"]
    readonly_fields = ["rating", "review_count"]


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    inlines = [MasterProfileInline]
    list_display = ["email", "username", "role", "city_display", "is_active", "date_joined"]
    list_filter = ["role", "is_active", "is_staff", "master_profile__city",
                   "master_profile__is_verified"]
    search_fields = ["email", "username", "phone_number"]
    ordering = ["-date_joined"]

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        (_("Персональные данные"), {"fields": ("first_name", "last_name", "phone_number", "avatar")}),
        (_("Роль"), {"fields": ("role",)}),
        (_("Права доступа"), {"fields": ("is_active", "is_staff", "is_superuser",
                                         "groups", "user_permissions")}),
        (_("Даты"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "role", "password1", "password2"),
        }),
    )

    # ==========================================
    # НАША ЗАЩИТА ОТ ОШИБКИ INTEGRITY ERROR
    # ==========================================
    def get_inline_instances(self, request, obj=None):
        """
        Прячем инлайн при создании нового юзера (obj=None).
        Прячем инлайн, если юзер — не 'master'.
        """
        if not obj:
            return []

        if obj.role != CustomUser.Role.MASTER:
            return []

        return super().get_inline_instances(request, obj)

    @admin.display(description=_("Город"))
    def city_display(self, obj):
        p = getattr(obj, "master_profile", None)
        return p.get_city_display() if p else "—"


@admin.register(MasterProfile)
class MasterProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "city", "get_city_display", "rating", "review_count", "is_verified"]
    list_filter = ["is_verified", "city"]
    search_fields = ["user__email", "city"]
    readonly_fields = ["rating", "review_count", "created_at", "updated_at"]
    list_editable = ["is_verified"]