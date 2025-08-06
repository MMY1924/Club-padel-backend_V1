# apps/tournaments/urls_v2.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_v2 import TorneoViewSet, InscripcionViewSet, PartidoTorneoViewSet

router = DefaultRouter()
router.register(r'torneos', TorneoViewSet, basename='torneo')
router.register(r'inscripciones', InscripcionViewSet, basename='inscripcion')
router.register(r'partidos-torneo', PartidoTorneoViewSet, basename='partido-torneo')

urlpatterns = [
    path('', include(router.urls)),
]