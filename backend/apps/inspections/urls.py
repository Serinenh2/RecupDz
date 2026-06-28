from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InspectionViewSet, generate_pv, generate_pv_word

router = DefaultRouter()
router.register('', InspectionViewSet)

urlpatterns = [
    path('generate-pv/', generate_pv),
    path('generate-pv-word/', generate_pv_word),
    path('', include(router.urls)),
]
