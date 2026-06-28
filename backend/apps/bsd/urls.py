from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BSDViewSet, generate_bsd, generate_bsd_word

router = DefaultRouter()
router.register('', BSDViewSet)

urlpatterns = [
    path('generate-bsd/', generate_bsd),
    path('generate-bsd-word/', generate_bsd_word),
    path('', include(router.urls)),
]
