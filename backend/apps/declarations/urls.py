from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DeclarationViewSet, generate_dsd, generate_dsd_word

router = DefaultRouter()
router.register('', DeclarationViewSet, basename='declaration')

urlpatterns = [
    path('generate-dsd/', generate_dsd),
    path('generate-dsd-word/', generate_dsd_word),
    path('', include(router.urls)),
]
