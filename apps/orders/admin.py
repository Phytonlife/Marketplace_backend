from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Order, Review


class ReviewInline(admin.StackedInline):
    model = Review
    extra = 0
    readonly_fields = ["client", "master", "rating", "text", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "status_badge",
        "client_email",
        "master_email",
        "service_title",
        "price_at_booking",
        "scheduled_time",
        "created_at",
    ]
    list_filter = ["status", "created_at", "scheduled_time"]
    search_fields = [
        "client__email",
        "master__email",
        "service__title",
    ]
    readonly_fields = [
        "client",
        "master",
        "service",
        "price_at_booking",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"
    inlines = [ReviewInline]

    fieldsets = (
        (_("Участники"), {
            "fields": ("client", "master", "service"),
        }),
        (_("Детали заказа"), {
            "fields": ("status", "price_at_booking", "scheduled_time", "address", "client_comment"),
        }),
        (_("Системные поля"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description=_("Статус"), ordering="status")
    def status_badge(self, obj):
        colors = {
            "pending":     "#f59e0b",
            "accepted":    "#3b82f6",
            "rejected":    "#ef4444",
            "in_progress": "#8b5cf6",
            "completed":   "#10b981",
            "cancelled":   "#6b7280",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:12px;'
            'font-size:12px;font-weight:600">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description=_("Клиент"), ordering="client__email")
    def client_email(self, obj):
        return obj.client.email

    @admin.display(description=_("Мастер"), ordering="master__email")
    def master_email(self, obj):
        return obj.master.email

    @admin.display(description=_("Услуга"), ordering="service__title")
    def service_title(self, obj):
        return obj.service.title


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "star_rating",
        "client_email",
        "master_email",
        "order_link",
        "created_at",
    ]
    list_filter = ["rating", "created_at"]
    search_fields = ["client__email", "master__email", "text"]
    readonly_fields = ["client", "master", "order", "created_at"]
    ordering = ["-created_at"]

    @admin.display(description=_("Оценка"), ordering="rating")
    def star_rating(self, obj):
        stars = "★" * obj.rating + "☆" * (5 - obj.rating)
        return format_html(
            '<span style="color:#f59e0b;font-size:16px" title="{}/5">{}</span>',
            obj.rating,
            stars,
        )

    @admin.display(description=_("Клиент"))
    def client_email(self, obj):
        return obj.client.email

    @admin.display(description=_("Мастер"))
    def master_email(self, obj):
        return obj.master.email

    @admin.display(description=_("Заказ"))
    def order_link(self, obj):
        url = f"/admin/orders/order/{obj.order_id}/change/"
        return format_html('<a href="{}">Заказ #{}</a>', url, obj.order_id)
