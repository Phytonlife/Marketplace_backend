from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Category, EventType, Service, ServiceImage


# ─── Category ─────────────────────────────────────────────────────────────────

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


# ─── EventType ────────────────────────────────────────────────────────────────

@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ["icon", "name", "slug", "sort_order", "services_count"]
    list_editable = ["sort_order"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["sort_order", "name"]

    @admin.display(description=_("Услуг"))
    def services_count(self, obj):
        return obj.services.count()


# ─── ServiceImage Inline ──────────────────────────────────────────────────────

class ServiceImageInline(admin.TabularInline):
    """
    Инлайн для загрузки галереи прямо на странице услуги.
    Показывает превью каждого фото, позволяет менять порядок и главное фото.
    """
    model = ServiceImage
    extra = 3                        # 3 пустых слота для загрузки сразу
    fields = ["image", "image_preview", "is_main", "sort_order"]
    readonly_fields = ["image_preview"]
    ordering = ["-is_main", "sort_order"]

    @admin.display(description=_("Превью"))
    def image_preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" height="60" style="border-radius:4px;object-fit:cover;" />',
                obj.image.url,
            )
        return "—"


# ─── Service ──────────────────────────────────────────────────────────────────

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "master_email",
        "category",
        "price",
        "price_type",
        "event_types_list",
        "images_count",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "price_type", "category", "event_types"]
    search_fields = ["title", "description", "master__email"]
    list_editable = ["is_active"]
    readonly_fields = ["created_at", "updated_at", "cover_preview"]
    ordering = ["-created_at"]
    filter_horizontal = ["event_types"]   # удобный виджет для M2M
    inlines = [ServiceImageInline]

    fieldsets = (
        (_("Основное"), {
            "fields": ("master", "category", "title", "description"),
        }),
        (_("Мероприятия"), {
            "fields": ("event_types",),
            "description": _("Для каких типов праздников подходит услуга"),
        }),
        (_("Цена"), {
            "fields": ("price", "price_type", "min_duration"),
        }),
        (_("Обложка"), {
            "fields": ("cover_image", "cover_preview"),
            "description": _(
                "Обложка — быстрая загрузка одного фото. "
                "Полная галерея — через блок «Галерея» ниже."
            ),
        }),
        (_("Статус"), {
            "fields": ("is_active", "created_at", "updated_at"),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        """Показываем в поле «Мастер» только пользователей с role='master'."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["master"].queryset = (
            User.objects.filter(role="master").order_by("email")
        )
        form.base_fields["master"].label_from_instance = (
            lambda u: f"{u.email}  ({u.get_full_name() or u.username})"
        )
        return form

    @admin.display(description=_("Email исполнителя"), ordering="master__email")
    def master_email(self, obj):
        return obj.master.email

    @admin.display(description=_("Мероприятия"))
    def event_types_list(self, obj):
        types = obj.event_types.all()[:3]
        badges = "".join(
            f'<span style="background:#e0e7ff;color:#3730a3;padding:1px 6px;'
            f'border-radius:8px;font-size:11px;margin:1px;display:inline-block">'
            f'{t}</span>'
            for t in types
        )
        more = obj.event_types.count() - 3
        if more > 0:
            badges += (
                f'<span style="color:#6b7280;font-size:11px"> +{more}</span>'
            )
        return format_html(badges) if badges else "—"

    @admin.display(description=_("Фото"))
    def images_count(self, obj):
        count = obj.images.count()
        if count == 0:
            return format_html('<span style="color:#9ca3af">0</span>')
        return format_html(
            '<span style="color:#059669;font-weight:600">📷 {}</span>', count
        )

    @admin.display(description=_("Обложка"))
    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" height="80" style="border-radius:4px;" />',
                obj.cover_image.url,
            )
        return "—"


# ─── ServiceImage (отдельная страница для массовой загрузки) ─────────────────

@admin.register(ServiceImage)
class ServiceImageAdmin(admin.ModelAdmin):
    list_display = ["pk", "image_preview", "service", "is_main", "sort_order", "created_at"]
    list_filter = ["is_main", "service__category"]
    list_editable = ["is_main", "sort_order"]
    search_fields = ["service__title"]
    ordering = ["service", "-is_main", "sort_order"]
    readonly_fields = ["image_preview", "created_at"]

    @admin.display(description=_("Превью"))
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" height="60" style="border-radius:4px;object-fit:cover;" />',
                obj.image.url,
            )
        return "—"
