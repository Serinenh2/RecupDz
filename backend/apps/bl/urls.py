from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BLViewSet, generate_bl, generate_bl_word

router = DefaultRouter()
router.register('', BLViewSet)

urlpatterns = [
    path('generate-bl/', generate_bl),
    path('generate-bl-word/', generate_bl_word),
    path('', include(router.urls)),
]
