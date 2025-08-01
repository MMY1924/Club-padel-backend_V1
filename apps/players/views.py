# apps/players/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q, Count, Avg
from django.db import transaction

from .models import Jugador
from .serializers import (
    JugadorSerializer, JugadorListSerializer, JugadorCreateSerializer,
    JugadorUpdateSerializer, ConvertirJugadorSerializer
)


class JugadorViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar Jugadores - Registrados e Invitados"""
    queryset = Jugador.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['sexo', 'activo', 'es_invitado', 'nivel_habilidad']
    search_fields = ['nombre', 'apellido', 'email', 'user__username']
    ordering_fields = ['nombre', 'apellido', 'edad', 'fecha_creacion', 'nivel_habilidad']
    ordering = ['apellido', 'nombre']

    def get_serializer_class(self):
        """Seleccionar el serializer según la acción"""
        if self.action == 'create':
            return JugadorCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return JugadorUpdateSerializer
        elif self.action == 'list':
            return JugadorListSerializer
        return JugadorSerializer

    def create(self, request, *args, **kwargs):
        """Crear jugador con validaciones"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                jugador = serializer.save()

                tipo = 'registrado' if not jugador.es_invitado else 'invitado'
                mensaje = f'Jugador {tipo} {jugador.nombre_completo} creado exitosamente'

                if not jugador.es_invitado:
                    mensaje += f' (Username: {jugador.user.username})'

                return Response(
                    {
                        'message': mensaje,
                        'jugador': JugadorSerializer(jugador).data
                    },
                    status=status.HTTP_201_CREATED
                )
        except Exception as e:
            return Response(
                {'error': f'Error al crear jugador: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def estadisticas(self, request, pk=None):
        """Obtener estadísticas detalladas del jugador"""
        jugador = self.get_object()

        # Estadísticas básicas
        if hasattr(jugador, 'historial_partidos'):
            partidos_jugados = jugador.historial_partidos.count()
            partidos_ganados = jugador.historial_partidos.filter(es_ganador=True).count()
            partidos_perdidos = partidos_jugados - partidos_ganados

            # Porcentaje de victorias
            porcentaje_victorias = round((partidos_ganados / partidos_jugados * 100), 2) if partidos_jugados > 0 else 0

            # Estadísticas por modalidad
            individual_jugados = jugador.historial_partidos.filter(partido__modalidad='Individual').count()
            individual_ganados = jugador.historial_partidos.filter(partido__modalidad='Individual',
                                                                   es_ganador=True).count()

            dobles_jugados = jugador.historial_partidos.filter(partido__modalidad='Dobles').count()
            dobles_ganados = jugador.historial_partidos.filter(partido__modalidad='Dobles', es_ganador=True).count()

            # Compañeros más frecuentes (en dobles)
            compañeros_stats = jugador.historial_partidos.filter(
                partido__modalidad='Dobles',
                Pareja__isnull=False
            ).values('Pareja__nombre', 'Pareja__apellido').annotate(
                partidos_juntos=Count('id'),
                victorias_juntos=Count('id', filter=Q(es_ganador=True))
            ).order_by('-partidos_juntos')[:5]
        else:
            partidos_jugados = partidos_ganados = partidos_perdidos = 0
            porcentaje_victorias = 0
            individual_jugados = individual_ganados = 0
            dobles_jugados = dobles_ganados = 0
            compañeros_stats = []

        return Response({
            'jugador': {
                'id': jugador.id,
                'nombre_completo': jugador.nombre_completo,
                'email': jugador.email_efectivo,
                'edad': jugador.edad,
                'sexo': jugador.get_sexo_display(),
                'nivel_habilidad': jugador.nivel_habilidad,
                'tipo': 'Registrado' if not jugador.es_invitado else 'Invitado',
                'username': jugador.user.username if jugador.user else None
            },
            'estadisticas_generales': {
                'partidos_jugados': partidos_jugados,
                'partidos_ganados': partidos_ganados,
                'partidos_perdidos': partidos_perdidos,
                'porcentaje_victorias': porcentaje_victorias
            },
            'por_modalidad': {
                'individual': {
                    'jugados': individual_jugados,
                    'ganados': individual_ganados,
                    'porcentaje': round((individual_ganados / individual_jugados * 100),
                                        2) if individual_jugados > 0 else 0
                },
                'dobles': {
                    'jugados': dobles_jugados,
                    'ganados': dobles_ganados,
                    'porcentaje': round((dobles_ganados / dobles_jugados * 100), 2) if dobles_jugados > 0 else 0
                }
            },
            'compañeros_frecuentes': [
                {
                    'nombre': f"{comp['Pareja__nombre']} {comp['Pareja__apellido']}",
                    'partidos_juntos': comp['partidos_juntos'],
                    'victorias_juntos': comp['victorias_juntos'],
                    'porcentaje_victorias': round((comp['victorias_juntos'] / comp['partidos_juntos'] * 100), 2)
                }
                for comp in compañeros_stats
            ]
        })

    @action(detail=True, methods=['get'])
    def historial_partidos(self, request, pk=None):
        """Obtener historial de partidos del jugador"""
        jugador = self.get_object()

        if not hasattr(jugador, 'historial_partidos'):
            return Response({'message': 'Este jugador no tiene historial de partidos'})

        # Filtros opcionales
        modalidad = request.query_params.get('modalidad')
        resultado = request.query_params.get('resultado')  # 'ganado' o 'perdido'

        partidos_query = jugador.historial_partidos.select_related('partido', 'partido__cancha').all()

        if modalidad:
            partidos_query = partidos_query.filter(partido__modalidad=modalidad)

        if resultado == 'ganado':
            partidos_query = partidos_query.filter(es_ganador=True)
        elif resultado == 'perdido':
            partidos_query = partidos_query.filter(es_ganador=False)

        partidos_query = partidos_query.order_by('-partido__fecha_creacion')

        # Paginación
        page = self.paginate_queryset(partidos_query)
        if page is not None:
            historial_data = self._build_historial_data(page)
            return self.get_paginated_response(historial_data)

        historial_data = self._build_historial_data(partidos_query)
        return Response(historial_data)

    def _build_historial_data(self, historial_queryset):
        """Construir datos del historial de partidos"""
        historial_data = []
        for historial in historial_queryset:
            partido = historial.partido
            historial_data.append({
                'partido_id': partido.id,
                'fecha': partido.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                'modalidad': partido.modalidad,
                'tipo': partido.tipo,
                'cancha': partido.cancha.nombre if partido.cancha else None,
                'equipo_jugador': historial.equipo_jugador,
                'resultado': 'Ganado' if historial.es_ganador else 'Perdido',
                'equipo1': partido.equipo1_nombre,
                'equipo2': partido.equipo2_nombre,
                'compañero': historial.Pareja.nombre_completo if historial.Pareja else None,
                'estado_partido': partido.estado
            })
        return historial_data

    @action(detail=True, methods=['post'])
    def toggle_activo(self, request, pk=None):
        """Activar/desactivar jugador"""
        jugador = self.get_object()
        jugador.activo = not jugador.activo
        jugador.save()

        estado = "activado" if jugador.activo else "desactivado"
        return Response({
            'message': f'Jugador {jugador.nombre_completo} {estado} exitosamente',
            'jugador': JugadorSerializer(jugador).data
        })

    @action(detail=True, methods=['post'])
    def convertir_a_registrado(self, request, pk=None):
        """Convertir jugador invitado a registrado"""
        jugador = self.get_object()

        if not jugador.es_invitado:
            return Response(
                {'error': 'Este jugador ya está registrado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ConvertirJugadorSerializer(
            data=request.data,
            context={'jugador': jugador}
        )
        serializer.is_valid(raise_exception=True)

        try:
            jugador_convertido = serializer.save()
            return Response({
                'message': f'Jugador {jugador_convertido.nombre_completo} convertido a registrado exitosamente',
                'username': jugador_convertido.user.username,
                'jugador': JugadorSerializer(jugador_convertido).data
            })
        except Exception as e:
            return Response(
                {'error': f'Error al convertir jugador: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def estadisticas_generales(self, request):
        """Estadísticas generales de todos los jugadores"""
        total_jugadores = Jugador.objects.count()
        jugadores_activos = Jugador.objects.filter(activo=True).count()
        jugadores_inactivos = total_jugadores - jugadores_activos

        # Estadísticas por tipo
        registrados = Jugador.objects.filter(es_invitado=False).count()
        invitados = Jugador.objects.filter(es_invitado=True).count()

        # Estadísticas por género
        por_sexo = Jugador.objects.values('sexo').annotate(
            total=Count('id')
        ).order_by('sexo')

        # Estadísticas por nivel
        por_nivel = Jugador.objects.values('nivel_habilidad').annotate(
            total=Count('id')
        ).order_by('nivel_habilidad')

        # Estadísticas por edad
        edad_promedio = Jugador.objects.aggregate(
            promedio=Avg('edad')
        )['promedio'] or 0

        # Jugadores más activos (con historial)
        jugadores_activos_stats = Jugador.objects.annotate(
            partidos_jugados=Count('historial_partidos')
        ).filter(partidos_jugados__gt=0).order_by('-partidos_jugados')[:10]

        return Response({
            'resumen': {
                'total_jugadores': total_jugadores,
                'activos': jugadores_activos,
                'inactivos': jugadores_inactivos,
                'registrados': registrados,
                'invitados': invitados,
                'edad_promedio': round(edad_promedio, 1)
            },
            'distribucion_sexo': [
                {
                    'sexo': item['sexo'],
                    'sexo_display': dict(Jugador.SEXO_CHOICES).get(item['sexo'], item['sexo']),
                    'total': item['total'],
                    'porcentaje': round((item['total'] / total_jugadores * 100), 2)
                }
                for item in por_sexo
            ],
            'distribucion_nivel': [
                {
                    'nivel': item['nivel_habilidad'],
                    'total': item['total'],
                    'porcentaje': round((item['total'] / total_jugadores * 100), 2)
                }
                for item in por_nivel
            ],
            'jugadores_mas_activos': [
                {
                    'nombre_completo': j.nombre_completo,
                    'partidos_jugados': j.partidos_jugados,
                    'email': j.email_efectivo,
                    'tipo': 'Registrado' if not j.es_invitado else 'Invitado'
                }
                for j in jugadores_activos_stats
            ]
        })

    @action(detail=False, methods=['get'])
    def disponibles_para_partido(self, request):
        """Obtener jugadores disponibles para crear un partido"""
        # Filtros opcionales
        excluir_ids = request.query_params.getlist('excluir[]')
        modalidad = request.query_params.get('modalidad', 'Dobles')
        solo_registrados = request.query_params.get('solo_registrados', 'false').lower() == 'true'

        jugadores = Jugador.objects.filter(activo=True)

        if excluir_ids:
            jugadores = jugadores.exclude(id__in=excluir_ids)

        if solo_registrados:
            jugadores = jugadores.filter(es_invitado=False)

        jugadores_data = []
        for jugador in jugadores:
            # Calcular estadísticas básicas
            if hasattr(jugador, 'historial_partidos'):
                partidos_jugados = jugador.historial_partidos.count()
                partidos_ganados = jugador.historial_partidos.filter(es_ganador=True).count()
                porcentaje_victorias = round((partidos_ganados / partidos_jugados * 100),
                                             1) if partidos_jugados > 0 else 0
            else:
                partidos_jugados = partidos_ganados = 0
                porcentaje_victorias = 0

            jugadores_data.append({
                'id': jugador.id,
                'nombre_completo': jugador.nombre_completo,
                'email': jugador.email_efectivo,
                'edad': jugador.edad,
                'sexo': jugador.get_sexo_display(),
                'nivel_habilidad': jugador.nivel_habilidad,
                'partidos_jugados': partidos_jugados,
                'porcentaje_victorias': porcentaje_victorias,
                'tipo': 'Registrado' if not jugador.es_invitado else 'Invitado',
                'puede_reservar': jugador.puede_hacer_reservas()
            })

        # Ordenar por nivel y experiencia
        jugadores_data.sort(key=lambda x: (x['nivel_habilidad'], x['partidos_jugados']), reverse=True)

        return Response({
            'modalidad': modalidad,
            'jugadores_disponibles': jugadores_data,
            'total': len(jugadores_data),
            'requeridos': 1 if modalidad == 'Individual' else 3
        })

    @action(detail=False, methods=['get'])
    def tipos_jugador(self, request):
        """Información sobre los tipos de jugador disponibles"""
        return Response({
            'tipos': [
                {
                    'valor': 'registrado',
                    'nombre': 'Jugador Registrado',
                    'descripcion': 'Jugador con cuenta de usuario, puede hacer reservas y acceder al sistema',
                    'campos_requeridos': ['nombre', 'apellido', 'email'],
                    'campos_opcionales': ['edad', 'sexo', 'telefono', 'nivel_habilidad', 'password']
                },
                {
                    'valor': 'invitado',
                    'nombre': 'Jugador Invitado',
                    'descripcion': 'Jugador casual sin cuenta, solo para participar en partidos',
                    'campos_requeridos': ['nombre', 'apellido'],
                    'campos_opcionales': ['email', 'edad', 'sexo', 'telefono', 'nivel_habilidad']
                }
            ],
            'notas': [
                'Los jugadores registrados obtienen automáticamente un username único',
                'Los jugadores invitados pueden convertirse a registrados posteriormente',
                'Solo los jugadores registrados pueden hacer reservas de canchas'
            ]
        })
