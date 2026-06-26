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
    prepopulated_fields = {"slug": ("name",)}
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

    # Оставляем автокомплит ТОЛЬКО для категории, так как в CategoryAdmin есть search_fields.
    autocomplete_fields = ["category"]

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
        Умный выпадающий список для поля "Мастер".
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Получаем стандартную форму
        form = super().get_form(request, obj, **kwargs)

        # Фильтруем: показываем ТОЛЬКО мастеров.
        form.base_fields["master"].queryset = User.objects.filter(role="master").order_by("email")

        # Делаем красивое отображение в выпадающем списке
        form.base_fields["master"].label_from_instance = lambda u: (
            f"{u.email} (Рейтинг: {u.master_profile.rating if hasattr(u, 'master_profile') else '0'})"
        )
        return form

    @admin.display(description=_("Email мастера"))
    def master_email(self, obj):
        return obj.master.email if obj.master else "—"

    @admin.display(description=_("Обложка"))
    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" height="80" style="border-radius:4px; object-fit:cover;" />',
                obj.cover_image.url,
            )
        return "—"