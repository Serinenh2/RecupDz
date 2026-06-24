from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NomenclatureViewSet, designations_par_code
router = DefaultRouter()
router.register('', NomenclatureViewSet)
urlpatterns = [
    path('designations/', designations_par_code),
    path('', include(router.urls)),
]
