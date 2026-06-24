from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, ServiceViewSet

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"services", ServiceViewSet, basename="service")

urlpatterns = [
    path("", include(router.urls)),
]
