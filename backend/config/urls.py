from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/token/', TokenObtainPairView.as_view()),
    path('api/auth/token/refresh/', TokenRefreshView.as_view()),
    path('api/accounts/', include('apps.accounts.urls')),
    path('api/recuperateurs/', include('apps.recuperateurs.urls')),
    path('api/nomenclature/', include('apps.nomenclature.urls')),
    path('api/traceability/', include('apps.traceability.urls')),
    path('api/bsd/', include('apps.bsd.urls')),
    path('api/declarations/', include('apps.declarations.urls')),
    path('api/inspections/', include('apps.inspections.urls')),
    path('api/operateurs/',  include('apps.operateurs.urls')),
    path('api/administration/', include('apps.administration.urls')),
    path('api/archive/', include('apps.archive.urls')),
    path('api/ai/', include('apps.ai_assistant.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
