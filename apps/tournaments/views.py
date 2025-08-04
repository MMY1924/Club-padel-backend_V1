# apps/tournaments/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    Torneo, InscripcionTorneo, FaseTorneo,
    GrupoTorneo, PartidoTorneo, ClasificacionTorneo
)
from .serializers import (
    # Torneo serializers
    TorneoListSerializer, TorneoDetailSerializer, TorneoCreateSerializer,
    TorneoStatusSerializer, GenerarSorteoSerializer, ProgramarPartidosSerializer,
    # Inscripcion serializers
    InscripcionListSerializer, InscripcionDetailSerializer,
    InscripcionCreateSerializer,
    # Fase y Grupo serializers
    FaseTorneoSerializer, GrupoTorneoSerializer,
    # Partido serializers
    PartidoTorneoListSerializer, PartidoTorneoDetailSerializer,
    PartidoTorneoUpdateSerializer,
    # Clasificacion serializers
    ClasificacionSerializer
)
from .services import TournamentService


# ==========================================
# VIEWSET DE TORNEO
# ==========================================

class TorneoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de torneos.

    Endpoints:
    - GET /torneos/ - Lista de torneos
    - POST /torneos/ - Crear torneo
    - GET /torneos/{id}/ - Detalle de torneo
    - PUT/PATCH /torneos/{id}/ - Actualizar torneo
    - DELETE /torneos/{id}/ - Eliminar torneo

    Acciones personalizadas:
    - POST /torneos/{id}/generar_sorteo/ - Generar sorteo
    - POST /torneos/{id}/iniciar/ - Iniciar torneo
    - GET /torneos/{id}/estado/ - Ver estado actual
    - POST /torneos/{id}/programar_partidos/ - Programar partidos
    - GET /torneos/{id}/clasificacion/ - Ver clasificación
    """

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tipo', 'modalidad', 'estado', 'activo']
    search_fields = ['nombre', 'codigo_torneo', 'descripcion']
    ordering_fields = ['fecha_inicio', 'fecha_creacion', 'nombre']
    ordering = ['-fecha_creacion']

    def get_queryset(self):
        queryset = Torneo.objects.all()

        # Filtros adicionales por query params
        if self.request.query_params.get('abiertos'):
            queryset = queryset.filter(estado='Inscripcion')

        if self.request.query_params.get('en_curso'):
            queryset = queryset.filter(estado='En_Curso')

        if self.request.query_params.get('con_cupo'):
            # Excluir torneos llenos
            queryset = [t for t in queryset if not t.esta_lleno]

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return TorneoListSerializer
        elif self.action == 'create':
            return TorneoCreateSerializer
        elif self.action in ['retrieve', 'update', 'partial_update']:
            return TorneoDetailSerializer
        elif self.action == 'estado':
            return TorneoStatusSerializer
        elif self.action == 'generar_sorteo':
            return GenerarSorteoSerializer
        elif self.action == 'programar_partidos':
            return ProgramarPartidosSerializer
        return TorneoListSerializer

    def get_permissions(self):
        """Define permisos por acción"""
        if self.action in ['list', 'retrieve', 'estado', 'clasificacion']:
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def generar_sorteo(self, request, pk=None):
        """Genera el sorteo del torneo"""
        torneo = self.get_object()
        serializer = GenerarSorteoSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if not serializer.validated_data['confirmar']:
            return Response(
                {"detail": "Debe confirmar la generación del sorteo"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            service = TournamentService(torneo)

            # Cambiar a preparación si está en inscripción
            if torneo.estado == 'Inscripcion':
                torneo.estado = 'Preparacion'
                torneo.save()

            service.generate_draw()

            return Response({
                "detail": "Sorteo generado exitosamente",
                "fases_creadas": torneo.fases.count(),
                "partidos_creados": PartidoTorneo.objects.filter(torneo=torneo).count()
            })

        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def iniciar(self, request, pk=None):
        """Inicia el torneo"""
        torneo = self.get_object()

        try:
            service = TournamentService(torneo)
            service.start_tournament()

            return Response({
                "detail": "Torneo iniciado exitosamente",
                "estado": torneo.get_estado_display()
            })

        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def estado(self, request, pk=None):
        """Obtiene el estado actual del torneo"""
        torneo = self.get_object()
        service = TournamentService(torneo)
        estado = service.get_tournament_status()

        serializer = TorneoStatusSerializer(estado)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def programar_partidos(self, request, pk=None):
        """Programa automáticamente los partidos del torneo"""
        torneo = self.get_object()
        serializer = ProgramarPartidosSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            service = TournamentService(torneo)
            programados = service.schedule_matches(
                fecha_inicio=serializer.validated_data['fecha_inicio'],
                canchas_disponibles=list(serializer.validated_data['canchas_ids']),
                partidos_por_dia=serializer.validated_data['partidos_por_dia']
            )

            return Response({
                "detail": f"{programados} partidos programados exitosamente"
            })

        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def clasificacion(self, request, pk=None):
        """Obtiene la clasificación del torneo"""
        torneo = self.get_object()

        if torneo.estado == 'Finalizado':
            # Clasificación final
            clasificaciones = ClasificacionTorneo.objects.filter(
                torneo=torneo
            ).order_by('posicion_final')
            serializer = ClasificacionSerializer(clasificaciones, many=True)
        else:
            # Clasificación actual
            service = TournamentService(torneo)
            standings = service._calculate_current_standings()

            # Convertir a formato similar a ClasificacionSerializer
            data = []
            for idx, standing in enumerate(standings):
                data.append({
                    'posicion_final': idx + 1,
                    'inscripcion': InscripcionListSerializer(standing['inscripcion']).data,
                    'partidos_ganados': standing['partidos_ganados'],
                    'partidos_perdidos': standing['partidos_perdidos'],
                    'partidos_jugados': standing['partidos_ganados'] + standing['partidos_perdidos']
                })

            return Response(data)

        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def fases(self, request, pk=None):
        """Obtiene las fases del torneo"""
        torneo = self.get_object()
        fases = torneo.fases.all().order_by('orden')
        serializer = FaseTorneoSerializer(fases, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def partidos(self, request, pk=None):
        """Obtiene los partidos del torneo"""
        torneo = self.get_object()
        partidos = PartidoTorneo.objects.filter(torneo=torneo)

        # Filtros opcionales
        fase_id = request.query_params.get('fase')
        if fase_id:
            partidos = partidos.filter(fase_id=fase_id)

        grupo_id = request.query_params.get('grupo')
        if grupo_id:
            partidos = partidos.filter(grupo_id=grupo_id)

        estado_partido = request.query_params.get('estado')
        if estado_partido:
            partidos = partidos.filter(partido__estado=estado_partido)

        partidos = partidos.order_by('fase__orden', 'orden_en_fase')

        serializer = PartidoTorneoListSerializer(partidos, many=True)
        return Response(serializer.data)


# ==========================================
# VIEWSET DE INSCRIPCIÓN
# ==========================================

class InscripcionTorneoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de inscripciones.

    Endpoints:
    - GET /inscripciones/ - Lista de inscripciones
    - POST /inscripciones/ - Crear inscripción
    - GET /inscripciones/{id}/ - Detalle de inscripción
    - PATCH /inscripciones/{id}/ - Actualizar inscripción

    Acciones personalizadas:
    - POST /inscripciones/{id}/confirmar/ - Confirmar inscripción
    - POST /inscripciones/{id}/cancelar/ - Cancelar inscripción
    """

    queryset = InscripcionTorneo.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['torneo', 'estado', 'pagado']
    search_fields = ['jugador1__nombre', 'jugador1__apellido',
                     'jugador2__nombre', 'jugador2__apellido']

    def get_serializer_class(self):
        if self.action == 'list':
            return InscripcionListSerializer
        elif self.action == 'create':
            return InscripcionCreateSerializer
        return InscripcionDetailSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrar por torneo si se especifica
        torneo_id = self.request.query_params.get('torneo')
        if torneo_id:
            queryset = queryset.filter(torneo_id=torneo_id)

        # Filtrar por jugador
        jugador_id = self.request.query_params.get('jugador')
        if jugador_id:
            queryset = queryset.filter(
                models.Q(jugador1_id=jugador_id) |
                models.Q(jugador2_id=jugador_id)
            )

        return queryset.order_by('-fecha_inscripcion')

    @action(detail=True, methods=['post'])
    def confirmar(self, request, pk=None):
        """Confirma una inscripción"""
        inscripcion = self.get_object()

        if inscripcion.estado != 'Pendiente':
            return Response(
                {"detail": "Solo se pueden confirmar inscripciones pendientes"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            inscripcion.estado = 'Confirmada'
            inscripcion.pagado = True
            inscripcion.monto_pagado = inscripcion.torneo.costo_inscripcion
            inscripcion.save()

        return Response({
            "detail": "Inscripción confirmada exitosamente",
            "estado": inscripcion.get_estado_display()
        })

    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        """Cancela una inscripción"""
        inscripcion = self.get_object()

        if inscripcion.estado == 'Cancelada':
            return Response(
                {"detail": "La inscripción ya está cancelada"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if inscripcion.torneo.estado != 'Inscripcion':
            return Response(
                {"detail": "No se pueden cancelar inscripciones una vez iniciado el torneo"},
                status=status.HTTP_400_BAD_REQUEST
            )

        inscripcion.estado = 'Cancelada'
        inscripcion.save()

        return Response({
            "detail": "Inscripción cancelada exitosamente"
        })


# ==========================================
# VIEWSET DE PARTIDO TORNEO
# ==========================================

class PartidoTorneoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de partidos del torneo.

    Endpoints:
    - GET /partidos-torneo/ - Lista de partidos
    - GET /partidos-torneo/{id}/ - Detalle de partido
    - PATCH /partidos-torneo/{id}/ - Actualizar partido (fecha, cancha)

    Acciones personalizadas:
    - POST /partidos-torneo/{id}/crear_partido/ - Crear partido real
    - POST /partidos-torneo/{id}/procesar_resultado/ - Procesar resultado
    """

    queryset = PartidoTorneo.objects.all()
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['torneo', 'fase', 'grupo', 'tipo']
    ordering_fields = ['fecha_programada', 'orden_en_fase']
    ordering = ['orden_en_fase']

    def get_serializer_class(self):
        if self.action == 'list':
            return PartidoTorneoListSerializer
        elif self.action in ['update', 'partial_update']:
            return PartidoTorneoUpdateSerializer
        return PartidoTorneoDetailSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtros adicionales
        torneo_id = self.request.query_params.get('torneo')
        if torneo_id:
            queryset = queryset.filter(torneo_id=torneo_id)

        # Partidos pendientes de programar
        if self.request.query_params.get('sin_programar'):
            queryset = queryset.filter(fecha_programada__isnull=True)

        # Partidos de hoy
        if self.request.query_params.get('hoy'):
            hoy = timezone.now().date()
            queryset = queryset.filter(fecha_programada__date=hoy)

        return queryset.select_related(
            'torneo', 'fase', 'grupo',
            'inscripcion_equipo1', 'inscripcion_equipo2',
            'partido', 'cancha_asignada'
        )

    @action(detail=True, methods=['post'])
    def crear_partido(self, request, pk=None):
        """Crea el partido real para jugar"""
        partido_torneo = self.get_object()

        if partido_torneo.partido:
            return Response(
                {"detail": "Este partido ya tiene un partido real asociado"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not partido_torneo.inscripcion_equipo1 or not partido_torneo.inscripcion_equipo2:
            return Response(
                {"detail": "Ambos equipos deben estar definidos"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            partido = partido_torneo.crear_partido_real()

            return Response({
                "detail": "Partido creado exitosamente",
                "partido_id": str(partido.id),
                "estado": partido.estado
            })

        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def procesar_resultado(self, request, pk=None):
        """Procesa el resultado del partido"""
        partido_torneo = self.get_object()

        if not partido_torneo.partido:
            return Response(
                {"detail": "No hay partido real asociado"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if partido_torneo.partido.estado != 'Finalizado':
            return Response(
                {"detail": "El partido no está finalizado"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            ganador = partido_torneo.procesar_resultado()

            # Verificar si la fase está completa
            fase = partido_torneo.fase
            partidos_pendientes = fase.partidos.filter(
                partido__isnull=False
            ).exclude(
                partido__estado='Finalizado'
            ).count()

            response_data = {
                "detail": "Resultado procesado exitosamente",
                "ganador": ganador.nombre_equipo,
                "fase_completa": partidos_pendientes == 0
            }

            if partidos_pendientes == 0:
                # Intentar procesar la fase completa
                try:
                    service = TournamentService(partido_torneo.torneo)
                    service.process_phase_completion(fase)
                    response_data["fase_procesada"] = True
                except Exception as e:
                    response_data["fase_procesada"] = False
                    response_data["error_fase"] = str(e)

            return Response(response_data)

        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ==========================================
# VIEWSET DE GRUPO
# ==========================================

class GrupoTorneoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para grupos del torneo.

    Endpoints:
    - GET /grupos-torneo/ - Lista de grupos
    - GET /grupos-torneo/{id}/ - Detalle de grupo con tabla
    """

    queryset = GrupoTorneo.objects.all()
    serializer_class = GrupoTorneoSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrar por torneo
        torneo_id = self.request.query_params.get('torneo')
        if torneo_id:
            queryset = queryset.filter(fase__torneo_id=torneo_id)

        # Filtrar por fase
        fase_id = self.request.query_params.get('fase')
        if fase_id:
            queryset = queryset.filter(fase_id=fase_id)

        return queryset.prefetch_related('inscripciones')


# ==========================================
# VIEWSET DE CLASIFICACIÓN
# ==========================================

class ClasificacionTorneoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para clasificaciones finales.

    Endpoints:
    - GET /clasificaciones/ - Lista de clasificaciones
    - GET /clasificaciones/{id}/ - Detalle de clasificación
    """

    queryset = ClasificacionTorneo.objects.all()
    serializer_class = ClasificacionSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['torneo']
    ordering_fields = ['posicion_final']
    ordering = ['posicion_final']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrar por torneo
        torneo_id = self.request.query_params.get('torneo')
        if torneo_id:
            queryset = queryset.filter(torneo_id=torneo_id)

        # Top N
        top = self.request.query_params.get('top')
        if top and top.isdigit():
            queryset = queryset[:int(top)]

        return queryset.select_related('inscripcion', 'torneo')