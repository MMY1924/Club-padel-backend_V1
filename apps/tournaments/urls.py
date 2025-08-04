# apps/tournaments/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Crear router
router = DefaultRouter()

# Registrar viewsets
router.register(r'torneos', views.TorneoViewSet, basename='torneo')
router.register(r'inscripciones', views.InscripcionTorneoViewSet, basename='inscripcion')
router.register(r'partidos-torneo', views.PartidoTorneoViewSet, basename='partido-torneo')
router.register(r'grupos', views.GrupoTorneoViewSet, basename='grupo-torneo')
router.register(r'clasificaciones', views.ClasificacionTorneoViewSet, basename='clasificacion')

app_name = 'tournaments'

urlpatterns = [
    path('api/', include(router.urls)),
]