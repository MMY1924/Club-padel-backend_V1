# apps/scoring/routing.py
from django.urls import re_path
from . import consumers
# Definición de rutas para WebSocket específicas del sistema de puntuación
websocket_urlpatterns = [
    # Ruta para conexión WebSocket a un partido en vivo
    # partido_id: UUID del partido que se está transmitiendo
    re_path(r'ws/partido/(?P<partido_id>[0-9a-f-]+)/$', consumers.PartidoConsumer.as_asgi()),
]
