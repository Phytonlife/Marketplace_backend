from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, LogoutView, MeView, RegisterView

# ─── Основные эндпоинты аутентификации ───────────────────────────────────────

auth_urlpatterns = [
    # Регистрация / Логин / Логаут
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),

    # JWT refresh
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    # Профиль текущего пользователя
    path("me/", MeView.as_view(), name="auth-me"),

    # ─── Google OAuth через dj-rest-auth + allauth ───────────────────────────
    # Клиент отправляет: POST {"code": "<auth_code>"} или {"access_token": "..."}
    # Ответ: {access, refresh, user}
    path("google/", include("dj_rest_auth.registration.urls")),
    path(
        "social/",
        include("allauth.socialaccount.urls"),   # обработка callback от Google
    ),
]

urlpatterns = auth_urlpatterns
