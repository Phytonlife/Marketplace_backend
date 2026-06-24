from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Category, Service


class SubcategoryInline(admin.TabularInline):
    model = Category
    fk_name = "parent"
    extra = 0
    fields = ["name", "slug", "icon"]
    readonly_fields = ["slug"]
    show_change_link = True


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "parent", "subcategory_count", "icon_preview"]
    list_filter = ["parent"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}   # ← автозаполнение slug из name
    inlines = [SubcategoryInline]
    ordering = ["name"]

    @admin.display(description=_("Подкатегорий"))
    def subcategory_count(self, obj):
        return obj.subcategories.count()

    @admin.display(description=_("Иконка"))
    def icon_preview(self, obj):
        if obj.icon:
            return format_html('<img src="{}" height="32" />', obj.icon.url)
        return "—"


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0
    fields = ["title", "category", "price", "price_type", "is_active"]
    show_change_link = True


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "master_email",
        "category",
        "price",
        "price_type",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "price_type", "category"]
    search_fields = ["title", "description", "master__email"]
    list_editable = ["is_active"]
    readonly_fields = ["created_at", "updated_at", "cover_preview"]
    ordering = ["-created_at"]
    # НЕ используем autocomplete_fields — оно требует search_fields на связанном Admin.
    # Вместо этого переопределяем get_form и показываем только мастеров.

    fieldsets = (
        (_("Основное"), {
            "fields": ("master", "category", "title", "description"),
        }),
        (_("Цена"), {
            "fields": ("price", "price_type"),
        }),
        (_("Медиа"), {
            "fields": ("cover_image", "cover_preview"),
        }),
        (_("Статус"), {
            "fields": ("is_active", "created_at", "updated_at"),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        """
        Фильтруем выпадающий список «Мастер»:
        показываем только пользователей с role='master'.
        Без этого суперадмин видит всех юзеров или пустой список.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["master"].queryset = User.objects.filter(
            role="master"
        ).order_by("email")
        form.base_fields["master"].label_from_instance = lambda u: (
            f"{u.email}  ({u.get_full_name() or u.username})"
        )
        return form

    @admin.display(description=_("Email мастера"))
    def master_email(self, obj):
        return obj.master.email

    @admin.display(description=_("Обложка"))
    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" height="80" style="border-radius:4px;" />',
                obj.cover_image.url,
            )
        return "—"
