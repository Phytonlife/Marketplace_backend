from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

API_V1 = "api/v1/"

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Auth & Users
    path(f"{API_V1}auth/", include("apps.users.urls")),

    # dj-rest-auth (Google OAuth entry points)
    path(f"{API_V1}auth/registration/", include("dj_rest_auth.registration.urls")),
    path(f"{API_V1}auth/", include("dj_rest_auth.urls")),

    # allauth (handles OAuth redirects — keep even for headless/API mode)
    path("accounts/", include("allauth.urls")),

    # Services & Categories (Module 2)
    path(f"{API_V1}", include("apps.services.urls")),

    # Orders & Reviews (Module 3)
    path(f"{API_V1}", include("apps.orders.urls")),

    # Chat & Dashboard (Module 4)
    path(f"{API_V1}", include("apps.chat.urls")),
]

# Раздача медиа-файлов в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
