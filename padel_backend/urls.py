# padel_backend/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .views import api_root

urlpatterns = [
    # Vista raíz de la API
    path('', api_root, name='api-root'),

    # Panel administrativo
    path('admin/', admin.site.urls),
    
    # API v2 (REST completa)
    path('api/v2/', include('api_v2_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

