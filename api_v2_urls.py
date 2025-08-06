# api_v2_urls.py - Configuración principal de URLs para API v2

from django.urls import path, include
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


@api_view(['GET'])
def api_v2_root(request):
    """Vista raíz de la API v2 con información de endpoints disponibles"""
    return Response({
        'message': 'API REST v2 para Sistema de Padel',
        'version': '2.0.0',
        'endpoints': {
            'jugadores': {
                'url': '/api/v2/jugadores/',
                'descripcion': 'Gestión completa de jugadores registrados e invitados',
                'acciones_especiales': [
                    'POST /jugadores/login/ - Autenticación',
                    'POST /jugadores/logout/ - Cerrar sesión',
                    'GET /jugadores/me/ - Perfil actual',
                    'PUT /jugadores/update_profile/ - Actualizar perfil',
                    'POST /jugadores/change_password/ - Cambiar contraseña',
                    'GET /jugadores/activos/ - Solo jugadores activos',
                    'POST /jugadores/crear_invitado/ - Crear jugador invitado',
                    'GET /jugadores/disponibles_para_partido/ - Para crear partidos',
                    'GET /jugadores/{id}/estadisticas_detalladas/ - Estadísticas completas',
                    'GET /jugadores/{id}/historial_partidos/ - Historial de partidos'
                ]
            },
            'canchas': {
                'url': '/api/v2/canchas/',
                'descripcion': 'Gestión de canchas y disponibilidad',
                'acciones_especiales': [
                    'GET /canchas/activas/ - Solo canchas activas',
                    'GET /canchas/disponibles/ - Canchas disponibles ahora',
                    'GET /canchas/{id}/disponibilidad/ - Horarios disponibles',
                    'GET /canchas/disponibilidad_multiple/ - Disponibilidad de todas',
                    'POST /canchas/{id}/cambiar_estado/ - Cambiar estado cancha'
                ]
            },
            'partidos': {
                'url': '/api/v2/partidos/',
                'descripcion': 'Gestión de partidos y scoring en vivo',
                'acciones_especiales': [
                    'POST /partidos/{id}/iniciar/ - Iniciar partido',
                    'POST /partidos/{id}/agregar_punto/ - Agregar punto',
                    'POST /partidos/{id}/deshacer_punto/ - Deshacer último punto',
                    'GET /partidos/{id}/marcador/ - Marcador en vivo',
                    'GET /partidos/activos/ - Partidos en juego',
                    'GET /partidos/pendientes/ - Partidos pendientes',
                    'GET /partidos/finalizados/ - Partidos finalizados con filtros'
                ]
            },
            'reservas': {
                'url': '/api/v2/reservas/',
                'descripcion': 'Sistema de reservas de canchas',
                'acciones_especiales': [
                    'POST /reservas/{id}/cambiar_estado/ - Cambiar estado',
                    'POST /reservas/{id}/marcar_pagado/ - Marcar como pagada',
                    'GET /reservas/hoy/ - Reservas de hoy',
                    'GET /reservas/proximas/ - Próximas 7 días',
                    'GET /reservas/calendario/ - Vista calendario'
                ]
            },
            'torneos': {
                'url': '/api/v2/torneos/',
                'descripcion': 'Sistema completo de torneos',
                'acciones_especiales': [
                    'GET /torneos/{id}/status/ - Estado del torneo',
                    'GET /torneos/{id}/inscripciones/ - Lista de inscripciones',
                    'POST /torneos/{id}/inscribir/ - Inscribir jugadores',
                    'GET /torneos/{id}/fases/ - Fases del torneo',
                    'GET /torneos/{id}/grupos/ - Grupos (si aplica)',
                    'GET /torneos/{id}/partidos/ - Partidos del torneo',
                    'GET /torneos/{id}/ranking/ - Clasificación/ranking',
                    'POST /torneos/{id}/generar_sorteo/ - Generar sorteo',
                    'POST /torneos/{id}/programar_partidos/ - Programar automático',
                    'POST /torneos/{id}/iniciar_torneo/ - Iniciar torneo',
                    'POST /torneos/{id}/finalizar_torneo/ - Finalizar torneo'
                ]
            },
            'estadisticas': {
                'url': '/api/v2/estadisticas/',
                'descripcion': 'Estadísticas generales del sistema',
                'acciones_especiales': [
                    'GET /estadisticas/resumen_general/ - Resumen completo del sistema'
                ]
            }
        },
        'autenticacion': {
            'tipos_soportados': ['JWT (recomendado)', 'Token (compatibilidad)'],
            'jwt': {
                'header': 'Authorization: Bearer <access_token>',
                'login': 'POST /api/v2/auth/jwt/login/',
                'refresh': 'POST /api/v2/auth/jwt/refresh-token/',
                'logout': 'POST /api/v2/auth/jwt/logout/',
                'verify': 'GET /api/v2/auth/jwt/verify/'
            },
            'token': {
                'header': 'Authorization: Token <token>',  
                'login': 'POST /api/v2/jugadores/login/',
                'logout': 'POST /api/v2/jugadores/logout/'
            }
        },
        'formatos': {
            'request': 'application/json',
            'response': 'application/json',
            'fechas': 'ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)',
            'ids': 'UUID format'
        },
        'notas': [
            'Todos los endpoints soportan filtrado, búsqueda y ordenamiento',
            'Los endpoints de listado incluyen paginación automática',
            'Las fechas se manejan en UTC',
            'Los errores siguen el formato estándar de DRF'
        ]
    })


urlpatterns = [
    # Vista raíz de la API
    path('', api_v2_root, name='api-v2-root'),
    
    # Autenticación JWT
    path('', include('apps.players.urls_jwt')),
    
    # Endpoints de jugadores
    path('jugadores/', include('apps.players.urls_v2')),
    
    # Endpoints de scoring (canchas, partidos, reservas, estadísticas)
    path('', include('apps.scoring.urls_v2')),
    
    # Endpoints de torneos
    path('', include('apps.tournaments.urls_v2')),
]