from rest_framework import permissions


class IsOrderParticipant(permissions.BasePermission):
    """
    Доступ к заказу имеют только его участники:
    клиент (obj.client) или мастер (obj.master).
    Анонимам — отказ на уровне has_permission.
    """

    message = "Вы не являетесь участником этого заказа."

    def has_permission(self, request, view) -> bool:
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj) -> bool:
        return obj.client == request.user or obj.master == request.user


class IsReviewAuthorOrReadOnly(permissions.BasePermission):
    """
    Читать отзывы могут все аутентифицированные.
    Создавать — только клиент (проверяется в perform_create).
    Редактировать/удалять — только автор отзыва.
    """

    def has_permission(self, request, view) -> bool:
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.client == request.user
