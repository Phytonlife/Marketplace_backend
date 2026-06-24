from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "type_badge",
        "order_link",
        "sender_email",
        "short_text",
        "created_at",
    ]
    list_filter = ["is_system", "created_at"]
    search_fields = ["text", "sender__email", "order__id"]
    readonly_fields = ["sender", "order", "is_system", "created_at"]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("sender", "order")

    @admin.display(description=_("Тип"))
    def type_badge(self, obj):
        if obj.is_system:
            return format_html(
                '<span style="background:#6b7280;color:#fff;padding:2px 8px;'
                'border-radius:12px;font-size:11px">⚙ Система</span>'
            )
        return format_html(
            '<span style="background:#3b82f6;color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:11px">💬 Чат</span>'
        )

    @admin.display(description=_("Заказ"))
    def order_link(self, obj):
        url = f"/admin/orders/order/{obj.order_id}/change/"
        return format_html('<a href="{}">#{}</a>', url, obj.order_id)

    @admin.display(description=_("Отправитель"))
    def sender_email(self, obj):
        return obj.sender.email if obj.sender else "— система —"

    @admin.display(description=_("Сообщение"))
    def short_text(self, obj):
        return obj.text[:80] + ("…" if len(obj.text) > 80 else "")
