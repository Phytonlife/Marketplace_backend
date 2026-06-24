from rest_framework import permissions


class IsMasterOwnerOrReadOnly(permissions.BasePermission):
    """
    Права доступа для услуг:
    - GET (list / retrieve)  — любой пользователь, включая анонимного
    - POST (create)          — только аутентифицированный пользователь с role='master'
    - PUT / PATCH / DELETE   — только мастер, которому принадлежит услуга
    """

    message = "Доступ запрещён."

    def has_permission(self, request, view) -> bool:
        # Безопасные методы открыты всем
        if request.method in permissions.SAFE_METHODS:
            return True

        # Для всех остальных — пользователь должен быть авторизован и быть мастером
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "master"
        )

    def has_object_permission(self, request, view, obj) -> bool:
        # Чтение открыто всем (доп. фильтрация is_active — в get_queryset)
        if request.method in permissions.SAFE_METHODS:
            return True

        # Изменение/удаление — только владелец услуги
        return obj.master == request.user


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Категории: чтение — всем, запись — только admin/staff.
    """

    def has_permission(self, request, view) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff
