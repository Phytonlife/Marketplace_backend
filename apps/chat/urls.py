from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MasterDashboardView, MessageViewSet

router = DefaultRouter()
router.register(r"messages", MessageViewSet, basename="message")

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/master/", MasterDashboardView.as_view(), name="master-dashboard"),
]
