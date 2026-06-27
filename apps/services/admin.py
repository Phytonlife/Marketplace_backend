from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Category, EventType, Service, ServiceImage


# ─── Category ─────────────────────────────────────────────────────────────────

class SubcategoryInline(admin.TabularInline):
    model             = Category
    fk_name           = "parent"
    extra             = 0
    fields            = ["name", "slug", "icon"]
    readonly_fields   = ["slug"]
    show_change_link  = True


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display       = ["name", "slug", "parent", "subcategory_count", "icon_preview"]
    list_filter        = ["parent"]
    search_fields      = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    inlines            = [SubcategoryInline]
    ordering           = ["name"]

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
    list_display       = ["icon", "name", "slug", "sort_order", "services_count"]
    list_editable      = ["sort_order"]
    search_fields      = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering           = ["sort_order", "name"]

    @admin.display(description=_("Услуг"))
    def services_count(self, obj):
        return obj.services.count()


# ─── ServiceImage Inline ──────────────────────────────────────────────────────

class ServiceImageInline(admin.TabularInline):
    """
    Галерея портфолио прямо на странице услуги.

    ┌──────────┬───────────┬──────────┬─────────┐
    │ Превью   │  Файл     │ Главное? │ Порядок │
    ├──────────┼───────────┼──────────┼─────────┤
    │ [img 40] │ [upload]  │  [ ]     │   0     │
    │ [img 40] │ [upload]  │  [x]     │   1     │
    │ [img 40] │ [upload]  │  [ ]     │   2     │
    └──────────┴───────────┴──────────┴─────────┘

    extra=4 — 4 пустых слота для пакетной загрузки фото за один раз.
    Встроенная логика save() автоматически следит за is_main=True.
    """

    model           = ServiceImage
    extra           = 4
    fields          = ["image_preview", "image", "is_main", "sort_order"]
    readonly_fields = ["image_preview"]
    ordering        = ["-is_main", "sort_order"]

    @admin.display(description=_("Превью"))
    def image_preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" height="50" width="75"'
                ' style="object-fit:cover;border-radius:4px;" />',
                obj.image.url,
            )
        return "—"


# ─── Service ──────────────────────────────────────────────────────────────────

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "master_email",
        "city_display",
        "category",
        "price_formatted",
        "event_types_badges",
        "gallery_count",
        "has_video",
        "is_active",
        "created_at",
    ]
    list_filter        = ["is_active", "price_type", "category", "event_types",
                          "master__master_profile__city",
                          "master__master_profile__is_verified"]
    search_fields      = ["title", "description", "master__email"]
    list_editable      = ["is_active"]
    readonly_fields    = ["created_at", "updated_at", "cover_preview", "priority_score_display"]
    ordering           = ["-created_at"]
    filter_horizontal  = ["event_types"]
    inlines            = [ServiceImageInline]

    fieldsets = (
        (_("Исполнитель"), {
            "fields": ("master",),
        }),
        (_("Описание"), {
            "fields": ("category", "title", "description"),
        }),
        (_("Мероприятия"), {
            "fields": ("event_types",),
        }),
        (_("Ценообразование"), {
            "fields": ("price", "price_type", "min_duration"),
        }),
        (_("Медиа"), {
            "fields": ("cover_image", "cover_preview", "video_url"),
            "description": _(
                "Обложка — одно фото. Галерея — блок «Галерея» ниже. "
                "Video URL — ссылка на YouTube/Vimeo."
            ),
        }),
        (_("Публикация"), {
            "fields": ("is_active", "priority_score_display", "created_at", "updated_at"),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        """Показываем в поле «Исполнитель» только пользователей с role='master'."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["master"].queryset = (
            User.objects.filter(role="master")
            .select_related("master_profile")
            .order_by("email")
        )
        form.base_fields["master"].label_from_instance = (
            lambda u: (
                f"{u.email}  "
                f"({u.get_full_name() or u.username})"
                + (f" — {u.master_profile.get_city_display()}"
                   if hasattr(u, "master_profile") else "")
            )
        )
        return form

    # ── List display helpers ───────────────────────────────────────────────────

    @admin.display(description=_("Исполнитель"), ordering="master__email")
    def master_email(self, obj):
        return obj.master.email

    @admin.display(description=_("Город"), ordering="master__master_profile__city")
    def city_display(self, obj):
        p = getattr(obj.master, "master_profile", None)
        return p.get_city_display() if p else "—"

    @admin.display(description=_("Цена"), ordering="price")
    def price_formatted(self, obj):
        return format_html(
            "<b>{} ₸</b> <span style='color:#6b7280;font-size:11px'>{}</span>",
            f"{obj.price:,.0f}",
            obj.get_price_type_display(),
        )

    @admin.display(description=_("Мероприятия"))
    def event_types_badges(self, obj):
        types = list(obj.event_types.all()[:3])
        if not types:
            return "—"
        badges = "".join(
            f'<span style="background:#ede9fe;color:#5b21b6;padding:1px 6px;'
            f'border-radius:8px;font-size:11px;margin:1px;display:inline-block">'
            f'{t}</span>'
            for t in types
        )
        extra = obj.event_types.count() - 3
        if extra > 0:
            badges += f'<span style="color:#9ca3af;font-size:11px"> +{extra}</span>'
        return format_html(badges)

    @admin.display(description=_("Фото"))
    def gallery_count(self, obj):
        count = obj.gallery.count()
        color = "#059669" if count > 0 else "#9ca3af"
        return format_html(
            '<span style="color:{};font-weight:600">📷 {}</span>', color, count
        )

    @admin.display(description=_("Видео"), boolean=True)
    def has_video(self, obj):
        return bool(obj.video_url)

    @admin.display(description=_("Обложка"))
    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" height="80" style="border-radius:6px;object-fit:cover;" />',
                obj.cover_image.url,
            )
        return "—"

    @admin.display(description=_("Smart Ranking Score"))
    def priority_score_display(self, obj):
        """
        Показывает расчётный рейтинг ранжирования (только для существующих объектов).
        Формула: rating×10 + review_count×2 + (50 если верифицирован).
        """
        p = getattr(obj.master, "master_profile", None)
        if not p:
            return "—"
        score = float(p.rating) * 10 + p.review_count * 2 + (50 if p.is_verified else 0)
        bar_width = min(int(score / 2), 100)   # max 200 очков → 100% ширина
        color = "#10b981" if score >= 100 else "#f59e0b" if score >= 50 else "#ef4444"
        return format_html(
            '<div style="display:flex;align-items:center;gap:8px">'
            '<div style="width:100px;background:#f3f4f6;border-radius:4px;height:8px">'
            '<div style="width:{bar}%;background:{color};height:8px;border-radius:4px"></div>'
            '</div>'
            '<span style="font-weight:600">{score:.1f}</span>'
            '</div>',
            bar=bar_width, color=color, score=score,
        )


# ─── ServiceImage standalone ──────────────────────────────────────────────────

@admin.register(ServiceImage)
class ServiceImageAdmin(admin.ModelAdmin):
    list_display   = ["pk", "thumb", "service", "is_main", "sort_order", "created_at"]
    list_filter    = ["is_main"]
    list_editable  = ["is_main", "sort_order"]
    search_fields  = ["service__title"]
    ordering       = ["service", "-is_main", "sort_order"]
    readonly_fields = ["thumb", "created_at"]

    @admin.display(description=_("Фото"))
    def thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" height="50" width="75"'
                ' style="object-fit:cover;border-radius:4px;" />',
                obj.image.url,
            )
        return "—"
