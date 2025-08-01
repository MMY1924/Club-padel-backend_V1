# apps/scoring/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PartidoViewSet, SetViewSet, JuegoViewSet, PuntoViewSet,
    HistorialJugadorViewSet, EstadisticasJugadorViewSet,
    CanchaViewSet, ReservaViewSet,
    api_root
)

router = DefaultRouter()

# Endpoints de scoring únicamente
router.register(r'canchas', CanchaViewSet, basename='cancha')
router.register(r'partidos', PartidoViewSet, basename='partido')
router.register(r'sets', SetViewSet, basename='set')
router.register(r'juegos', JuegoViewSet, basename='juego')
router.register(r'puntos', PuntoViewSet, basename='punto')
router.register(r'historial', HistorialJugadorViewSet, basename='historial')
router.register(r'estadisticas', EstadisticasJugadorViewSet, basename='estadisticas')
router.register(r'reservas', ReservaViewSet, basename='reserva')

urlpatterns = [
    # Vista raíz de la API
    path('', api_root, name='scoring-api-root'),

    # Incluir todas las rutas del router
    path('', include(router.urls)),
]
