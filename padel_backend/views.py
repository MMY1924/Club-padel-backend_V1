# padel_backend/views.py

from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(['GET'])
def api_root(request):
    """Vista raíz del API - Redirecciona a la documentación v2"""
    return Response({
        'message': 'Padel Backend API',
        'version': '2.0.0',
        'documentation': {
            'api_v2': request.build_absolute_uri('/api/v2/'),
            'admin': request.build_absolute_uri('/admin/'),
        },
        'endpoints': {
            'authentication': '/api/v2/auth/jwt/login/',
            'players': '/api/v2/jugadores/',
            'courts': '/api/v2/canchas/',
            'matches': '/api/v2/partidos/',
            'reservations': '/api/v2/reservas/',
            'tournaments': '/api/v2/torneos/',
            'statistics': '/api/v2/estadisticas/',
        }
    })