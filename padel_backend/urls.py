# padel_backend/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.scoring.views import api_root

urlpatterns = [
    # Vista raíz de la API
    path('', api_root, name='api-root'),

    # Endpoints principales
    path('admin/', admin.site.urls),
    path('api/v1/players/', include('apps.players.urls')),
    path('api/v1/scoring/', include('apps.scoring.urls')),
    path('api/v1/tournaments/', include('apps.tournaments.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

