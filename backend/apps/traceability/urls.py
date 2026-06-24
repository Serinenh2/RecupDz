from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TraceabilityViewSet
router = DefaultRouter()
router.register('', TraceabilityViewSet, basename='traceability')
urlpatterns = [path('', include(router.urls))]
