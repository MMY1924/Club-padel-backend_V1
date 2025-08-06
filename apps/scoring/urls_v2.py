# apps/scoring/urls_v2.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_v2 import CanchaViewSet, PartidoViewSet, ReservaViewSet, EstadisticasViewSet

router = DefaultRouter()
router.register(r'canchas', CanchaViewSet, basename='cancha')
router.register(r'partidos', PartidoViewSet, basename='partido')
router.register(r'reservas', ReservaViewSet, basename='reserva')
router.register(r'estadisticas', EstadisticasViewSet, basename='estadisticas')

urlpatterns = [
    path('', include(router.urls)),
]