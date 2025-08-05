# apps/scoring/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta
from .permissions import IsPlayerInMatch
from apps.scoring.services import crear_historial_y_actualizar_estadisticas

from .models import (
    Partido, Set, Juego, Punto, HistorialJugador, EstadisticasJugador,
    Cancha, Reserva
)
from .serializers import (
    # Serializers de Cancha
    CanchaSerializer, CanchaListSerializer, CanchaConReservasSerializer,
    # Serializers de Partido
    PartidoSerializer, PartidoCreateSerializer, PartidoListSerializer,
    # Serializers básicos
    SetSerializer, JuegoSerializer, PuntoSerializer,
    HistorialJugadorSerializer, EstadisticasJugadorSerializer,
    # Serializers de Reserva
    ReservaSerializer, ReservaListSerializer, ReservaCreateSerializer,
    # Serializers de acciones
    AddPointSerializer, IniciarPartidoSerializer, DisponibilidadSerializer,
    CalendarioReservasSerializer, CambiarEstadoReservaSerializer,
    CrearPartidoDesdeReservaSerializer
)
from .services import PadelScoringService
from apps.players.models import Jugador


# ==========================================
# API ROOT VIEW
# ==========================================

@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request, format=None):
    """Vista raíz de la API de Scoring"""
    return Response({
        'canchas': request.build_absolute_uri('/scoring/canchas/'),
        'partidos': request.build_absolute_uri('/scoring/partidos/'),
        'sets': request.build_absolute_uri('/scoring/sets/'),
        'juegos': request.build_absolute_uri('/scoring/juegos/'),
        'puntos': request.build_absolute_uri('/scoring/puntos/'),
        'historial': request.build_absolute_uri('/scoring/historial/'),
        'estadisticas': request.build_absolute_uri('/scoring/estadisticas/'),
        'reservas': request.build_absolute_uri('/scoring/reservas/'),
    })


# ==========================================
# VIEWSET DE CANCHA
# ==========================================

class CanchaViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de canchas.

    Endpoints:
    - GET /canchas/ - Lista de canchas
    - POST /canchas/ - Crear cancha
    - GET /canchas/{id}/ - Detalle de cancha
    - PUT/PATCH /canchas/{id}/ - Actualizar cancha
    - DELETE /canchas/{id}/ - Eliminar cancha

    Acciones personalizadas:
    - GET /canchas/disponibles/ - Canchas disponibles ahora
    - POST /canchas/{id}/cambiar_estado/ - Cambiar estado de cancha
    - GET /canchas/{id}/disponibilidad/ - Ver disponibilidad
    """

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tipo', 'estado', 'activa', 'tiene_iluminacion']
    search_fields = ['nombre', 'descripcion']
    ordering_fields = ['numero', 'nombre', 'fecha_creacion']
    ordering = ['numero']

    def get_queryset(self):
        queryset = Cancha.objects.all()

        # Filtro por activas
        if self.request.query_params.get('solo_activas'):
            queryset = queryset.filter(activa=True)

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return CanchaListSerializer
        elif self.action == 'retrieve' and self.request.query_params.get('incluir_reservas'):
            return CanchaConReservasSerializer
        return CanchaSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'disponibles', 'disponibilidad']:
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def disponibles(self, request):
        """Obtiene canchas disponibles en este momento"""
        canchas = self.get_queryset().filter(
            estado='Disponible',
            activa=True
        )

        # Excluir canchas con reservas activas
        ahora = timezone.now()
        canchas_ocupadas = Reserva.objects.filter(
            fecha_inicio__lte=ahora,
            fecha_fin__gte=ahora,
            estado__in=['Confirmada', 'En_Uso']
        ).values_list('cancha_id', flat=True)

        canchas = canchas.exclude(id__in=canchas_ocupadas)

        serializer = self.get_serializer(canchas, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """Cambia el estado de una cancha"""
        cancha = self.get_object()
        nuevo_estado = request.data.get('estado')

        if nuevo_estado not in dict(Cancha.ESTADO_CHOICES):
            return Response(
                {"detail": "Estado inválido"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validaciones especiales
        if nuevo_estado == 'Ocupada' and cancha.partidos.filter(estado='En Juego').exists():
            return Response(
                {"detail": "La cancha ya tiene un partido en juego"},
                status=status.HTTP_400_BAD_REQUEST
            )

        cancha.estado = nuevo_estado
        cancha.save()

        return Response({
            "detail": f"Estado cambiado a {cancha.get_estado_display()}",
            "estado": cancha.estado
        })

    @action(detail=True, methods=['get'])
    def disponibilidad(self, request, pk=None):
        """Verifica disponibilidad de la cancha en una fecha"""
        cancha = self.get_object()
        serializer = DisponibilidadSerializer(data=request.query_params)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        fecha = serializer.validated_data['fecha']
        hora_inicio = serializer.validated_data.get('hora_inicio')
        hora_fin = serializer.validated_data.get('hora_fin')

        # Obtener reservas del día
        reservas = cancha.reservas.filter(
            fecha_inicio__date=fecha,
            estado__in=['Confirmada', 'En_Uso', 'Pendiente']
        ).order_by('fecha_inicio')

        # Si se especifica horario, verificar disponibilidad
        if hora_inicio and hora_fin:
            fecha_inicio = datetime.combine(fecha, hora_inicio)
            fecha_fin = datetime.combine(fecha, hora_fin)

            conflictos = reservas.filter(
                fecha_inicio__lt=fecha_fin,
                fecha_fin__gt=fecha_inicio
            )

            disponible = not conflictos.exists() and cancha.estado != 'Fuera_Servicio'

            return Response({
                'disponible': disponible,
                'conflictos': ReservaListSerializer(conflictos, many=True).data if conflictos else []
            })

        # Si no, mostrar horarios ocupados
        horarios_ocupados = []
        for reserva in reservas:
            horarios_ocupados.append({
                'inicio': reserva.fecha_inicio.strftime('%H:%M'),
                'fin': reserva.fecha_fin.strftime('%H:%M'),
                'codigo': reserva.codigo_reserva,
                'tipo': reserva.tipo_reserva
            })

        return Response({
            'fecha': fecha,
            'cancha': cancha.nombre,
            'horarios_ocupados': horarios_ocupados,
            'estado_cancha': cancha.estado
        })


# ==========================================
# VIEWSET DE PARTIDO
# ==========================================

class PartidoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de partidos.

    Endpoints principales y acciones:
    - POST /partidos/{id}/iniciar/ - Iniciar partido
    - POST /partidos/{id}/agregar_punto/ - Agregar punto
    - POST /partidos/{id}/deshacer_punto/ - Deshacer último punto
    - GET /partidos/{id}/marcador_vivo/ - Obtener marcador en vivo
    - GET /partidos/{id}/historial_detallado/ - Ver historial completo
    """

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['modalidad', 'estado', 'tipo', 'cancha']
    search_fields = ['jugador1_equipo1__nombre', 'jugador1_equipo2__nombre']
    ordering_fields = ['fecha_creacion', 'fecha_inicio', 'fecha_fin']
    ordering = ['-fecha_creacion']

    def get_queryset(self):
        queryset = Partido.objects.all()

        # Filtro por partidos activos
        if self.request.query_params.get('activos'):
            queryset = queryset.filter(estado='En Juego')

        if self.request.query_params.get('jugador_id'):
            jugador_id = self.request.query_params.get('jugador_id')
            queryset = queryset.filter(
                Q(jugador1_equipo1_id=jugador_id) |
                Q(jugador2_equipo1_id=jugador_id) |
                Q(jugador1_equipo2_id=jugador_id) |
                Q(jugador2_equipo2_id=jugador_id)
            )

        return queryset.select_related(
            'cancha',
            'jugador1_equipo1', 'jugador2_equipo1',
            'jugador1_equipo2', 'jugador2_equipo2'

        )

    def get_serializer_class(self):
        if self.action == 'list':
            return PartidoListSerializer
        elif self.action == 'create':
            return PartidoCreateSerializer
        elif self.action == 'iniciar':
            return IniciarPartidoSerializer
        elif self.action == 'agregar_punto':
            return AddPointSerializer
        return PartidoSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'marcador_vivo', 'historial_detallado']:
            return [AllowAny()]
        elif self.action in ['agregar_punto', 'deshacer_punto']:
            return [IsAuthenticated(), IsPlayerInMatch()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def iniciar(self, request, pk=None):
        """Inicia un partido"""
        partido = self.get_object()
        serializer = IniciarPartidoSerializer(
            data=request.data,
            context={'partido': partido}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            service = PadelScoringService(partido.id)
            service.start_match()

            # Actualizar estado de cancha si es necesario
            if partido.cancha and partido.cancha.estado == 'Disponible':
                partido.cancha.estado = 'Ocupada'
                partido.cancha.save()

            return Response({
                "detail": "Partido iniciado exitosamente",
                "estado": partido.estado,
                "marcador": service.get_live_score()
            })

        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def agregar_punto(self, request, pk=None):
        """Agrega un punto al partido - solo jugadores del partido"""
        partido = self.get_object()

        # 1. VALIDACIONES DE ESTADO
        if partido.estado != 'En Juego':
            return Response(
                {"detail": f"No se pueden agregar puntos. El partido está '{partido.estado}'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. LOGGING PARA DEBUG (temporal)
        print(f"=== AGREGANDO PUNTO ===")
        print(f"Usuario: {request.user.username}")
        print(f"Partido: {partido.id}")
        print(f"Data: {request.data}")

        serializer = AddPointSerializer(data=request.data)

        if not serializer.is_valid():
            print(f"Errores de serializer: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # 3. VALIDACIÓN DEL EQUIPO
        equipo_ganador = serializer.validated_data['equipo_ganador']
        if equipo_ganador not in [1, 2]:
            return Response(
                {"detail": "equipo_ganador debe ser 1 o 2"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            service = PadelScoringService(partido.id)
            punto, resultado = service.add_point(
                equipo_ganador=equipo_ganador,
                descripcion=serializer.validated_data.get('descripcion', '')
            )

            # Obtener marcador actualizado
            marcador = service.get_live_score()

            print(f"Punto agregado exitosamente. Nuevo marcador: {marcador}")

            response_data = {
                "detail": "Punto agregado correctamente",
                "resultado": resultado,
                "marcador_actual": marcador,
                "punto_id": str(punto.id) if hasattr(punto, 'id') else None
            }

            # Si el partido terminó, actualizar cancha
            if resultado.get('partido_finalizado') and partido.cancha:
                partido.cancha.estado = 'Disponible'
                partido.cancha.save()
                print(f"Cancha {partido.cancha.id} liberada - partido finalizado")

                # Actualizar reserva si existe
                if hasattr(partido, 'reserva') and partido.reserva:
                    partido.reserva.estado = 'Completada'
                    partido.reserva.save()
                    print(f"Reserva {partido.reserva.id} marcada como completada")

            return Response(response_data)

        except Exception as e:
            print(f"ERROR agregando punto: {str(e)}")
            import traceback
            traceback.print_exc()

            return Response(
                {"detail": f"Error interno: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def deshacer_punto(self, request, pk=None):
        """Deshace el último punto"""
        partido = self.get_object()

        try:
            service = PadelScoringService(partido.id)
            service.undo_last_point()

            return Response({
                "detail": "Punto deshecho correctamente",
                "marcador_actual": service.get_live_score()
            })

        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def marcador_vivo(self, request, pk=None):
        """Obtiene el marcador en vivo"""
        partido = self.get_object()
        service = PadelScoringService(partido.id)
        marcador = service.get_live_score()

        return Response(marcador)

    @action(detail=True, methods=['get'])
    def historial_detallado(self, request, pk=None):
        """Obtiene el historial detallado del partido"""
        partido = self.get_object()
        service = PadelScoringService(partido.id)
        historial = service.get_detailed_score_history()

        return Response({
            'partido': PartidoSerializer(partido).data,
            'historial': historial
        })

    @action(detail=True, methods=['get'])
    def estadisticas(self, request, pk=None):
        """Obtiene estadísticas del partido"""
        partido = self.get_object()
        estadisticas = PadelScoringService.get_match_statistics(str(partido.id))

        return Response(estadisticas)

    @action(detail=True, methods=['post'])
    def finalizar(self, request, pk=None):
        partido = self.get_object()
        if partido.estado == "Finalizado":
            return Response({"detail": "El partido ya está finalizado"}, status=status.HTTP_400_BAD_REQUEST)
        partido.estado = "Finalizado"
        partido.save()
        crear_historial_y_actualizar_estadisticas(partido)
        return Response({"detail": "Partido finalizado y estadísticas actualizadas"})


# ==========================================
# VIEWSET DE SET
# ==========================================

class SetViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet de solo lectura para sets"""
    queryset = Set.objects.all()
    serializer_class = SetSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['partido', 'finalizado', 'equipo_ganador']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrar por partido si se especifica
        partido_id = self.request.query_params.get('partido')
        if partido_id:
            queryset = queryset.filter(partido_id=partido_id)

        return queryset.order_by('numero_set')


# ==========================================
# VIEWSET DE JUEGO
# ==========================================

class JuegoViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet de solo lectura para juegos"""
    queryset = Juego.objects.all()
    serializer_class = JuegoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['set', 'finalizado', 'equipo_ganador', 'equipo_que_saca']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrar por set si se especifica
        set_id = self.request.query_params.get('set')
        if set_id:
            queryset = queryset.filter(set_id=set_id)

        return queryset.order_by('numero_juego')


# ==========================================
# VIEWSET DE PUNTO
# ==========================================

class PuntoViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet de solo lectura para puntos"""
    queryset = Punto.objects.all()
    serializer_class = PuntoSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['juego', 'equipo_ganador', 'tipo_punto']
    ordering_fields = ['numero_punto', 'timestamp']
    ordering = ['numero_punto']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrar por juego si se especifica
        juego_id = self.request.query_params.get('juego')
        if juego_id:
            queryset = queryset.filter(juego_id=juego_id)

        # Filtrar por partido
        partido_id = self.request.query_params.get('partido')
        if partido_id:
            queryset = queryset.filter(juego__set__partido_id=partido_id)

        return queryset


# ==========================================
# VIEWSET DE HISTORIAL JUGADOR
# ==========================================

class HistorialJugadorViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet de solo lectura para historial de jugadores"""
    queryset = HistorialJugador.objects.all()
    serializer_class = HistorialJugadorSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['jugador', 'partido', 'es_ganador', 'equipo_jugador']
    ordering_fields = ['fecha_partido']
    ordering = ['-fecha_partido']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrar por jugador
        jugador_id = self.request.query_params.get('jugador')
        if jugador_id:
            queryset = queryset.filter(jugador_id=jugador_id)

        # Solo victorias
        if self.request.query_params.get('solo_victorias'):
            queryset = queryset.filter(es_ganador=True)

        # Solo partidos finalizados
        queryset = queryset.filter(partido__estado='Finalizado')

        return queryset.select_related('jugador', 'partido')


# ==========================================
# VIEWSET DE ESTADÍSTICAS JUGADOR
# ==========================================

class EstadisticasJugadorViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet de solo lectura para estadísticas de jugadores"""
    queryset = EstadisticasJugador.objects.all()
    serializer_class = EstadisticasJugadorSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['partidos_ganados', 'racha_actual_victorias']
    ordering = ['-partidos_ganados']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Top ganadores
        if self.request.query_params.get('top'):
            limite = int(self.request.query_params.get('top', 10))
            queryset = queryset[:limite]

        return queryset.select_related('jugador')

    @action(detail=False, methods=['get'])
    def ranking(self, request):
        """Obtiene el ranking de jugadores (mínimo 5 partidos)"""
        estadisticas = self.get_queryset().filter(
            partidos_jugados__gte=5
        ).order_by('-porcentaje_victorias')[:20]

        ranking_data = []
        for idx, stat in enumerate(estadisticas, 1):
            ranking_data.append({
                'posicion': idx,
                'jugador': stat.jugador.nombre_completo,
                'partidos_jugados': stat.partidos_jugados,
                'partidos_ganados': stat.partidos_ganados,
                'porcentaje_victorias': stat.porcentaje_victorias,
                'racha_actual': stat.racha_actual_victorias
            })

        return Response(ranking_data)

    @action(detail=True, methods=['get'])
    def detalle(self, request, pk=None):
        """Detalle completo de un jugador (estadísticas + últimos partidos)"""
        estadistica = self.get_object()
        serializer = self.get_serializer(estadistica)
        return Response(serializer.data)


# ==========================================
# VIEWSET DE RESERVA
# ==========================================

class ReservaViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de reservas.

    Acciones especiales:
    - POST /reservas/{id}/confirmar/ - Confirmar reserva
    - POST /reservas/{id}/cancelar/ - Cancelar reserva
    - POST /reservas/{id}/cambiar_estado/ - Cambiar estado
    - POST /reservas/{id}/crear_partido/ - Crear partido desde reserva
    - GET /reservas/calendario/ - Vista calendario
    - GET /reservas/disponibilidad/ - Verificar disponibilidad
    - GET /reservas/calcular_precio/ - Calcular precio dinámico
    - GET /reservas/mejor_horario/ - Mejor horario según criterio
    """

    queryset = Reserva.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['cancha', 'estado', 'tipo_reserva', 'jugador', 'fecha_inicio__date']
    search_fields = ['codigo_reserva', 'jugador__nombre', 'jugador__apellido']
    ordering_fields = ['fecha_inicio', 'fecha_creacion', 'precio_total']
    ordering = ['fecha_inicio']

    def get_queryset(self):
        queryset = Reserva.objects.all()

        # Filtros adicionales
        if self.request.query_params.get('proximas'):
            queryset = queryset.filter(
                fecha_inicio__gt=timezone.now(),
                estado__in=['Confirmada', 'Pendiente']
            )

        if self.request.query_params.get('hoy'):
            hoy = timezone.now().date()
            queryset = queryset.filter(fecha_inicio__date=hoy)

        if self.request.query_params.get('jugador_id'):
            jugador_id = self.request.query_params.get('jugador_id')
            queryset = queryset.filter(jugador_id=jugador_id)

        return queryset.select_related('cancha', 'jugador', 'partido')

    def get_serializer_class(self):
        """Usar diferentes serializers según la acción"""
        if self.action == 'create':
            return ReservaCreateSerializer
        elif self.action == 'list':
            return ReservaListSerializer
        return ReservaSerializer

    def get_permissions(self):
        """Permisos según la acción"""
        if self.action in ['disponibilidad', 'calcular_precio', 'mejor_horario', 'list', 'retrieve', 'calendario']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        """Al crear, calcular precio total"""
        with transaction.atomic():
            # Obtener datos antes de guardar
            precio_hora = serializer.validated_data.get('precio_hora', 0)
            duracion_minutos = serializer.validated_data.get('duracion_minutos', 60)

            # Calcular precio total
            horas = duracion_minutos / 60
            precio_total = precio_hora * horas

            # Generar código de reserva único
            import random
            import string
            codigo_reserva = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            while Reserva.objects.filter(codigo_reserva=codigo_reserva).exists():
                codigo_reserva = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

            print(f"DEBUG - Precio hora: {precio_hora}, Duración: {duracion_minutos} min, Precio total: {precio_total}")

            # Guardar con el precio total calculado y código generado
            reserva = serializer.save(precio_total=precio_total, codigo_reserva=codigo_reserva)

    @action(detail=True, methods=['post'])
    def confirmar(self, request, pk=None):
        """Confirma una reserva pendiente"""
        reserva = self.get_object()

        if reserva.estado != 'Pendiente':
            return Response(
                {"detail": "Solo se pueden confirmar reservas pendientes"},
                status=status.HTTP_400_BAD_REQUEST
            )

        reserva.estado = 'Confirmada'
        reserva.pagado = True
        reserva.save()

        return Response({
            "detail": "Reserva confirmada exitosamente",
            "codigo": reserva.codigo_reserva
        })

    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        """Cancela una reserva"""
        reserva = self.get_object()

        if reserva.estado in ['Cancelada', 'Completada']:
            return Response(
                {"detail": f"No se puede cancelar una reserva {reserva.get_estado_display()}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar tiempo mínimo para cancelación (2 horas antes)
        tiempo_limite = reserva.fecha_inicio - timedelta(hours=2)
        if timezone.now() > tiempo_limite:
            return Response(
                {"detail": "No se puede cancelar con menos de 2 horas de anticipación"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            reserva.estado = 'Cancelada'
            reserva.save()

            # Liberar cancha si estaba ocupada
            if reserva.cancha.estado == 'Ocupada':
                # Verificar que no haya otros partidos activos
                otros_activos = reserva.cancha.partidos.filter(
                    estado='En Juego'
                ).exists()

                if not otros_activos:
                    reserva.cancha.estado = 'Disponible'
                    reserva.cancha.save()

        return Response({
            "detail": "Reserva cancelada exitosamente"
        })

    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """Cambia el estado de una reserva"""
        reserva = self.get_object()
        serializer = CambiarEstadoReservaSerializer(
            data=request.data,
            context={'reserva': reserva}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        nuevo_estado = serializer.validated_data['estado']
        motivo = serializer.validated_data.get('motivo', '')

        with transaction.atomic():
            estado_anterior = reserva.estado
            reserva.estado = nuevo_estado

            if motivo:
                reserva.observaciones = f"{reserva.observaciones}\n[{timezone.now():%d/%m/%Y %H:%M}] " \
                                        f"Cambio de estado: {estado_anterior} → {nuevo_estado}. " \
                                        f"Motivo: {motivo}".strip()

            reserva.save()

            # Lógica adicional según el nuevo estado
            if nuevo_estado == 'En_Uso' and reserva.cancha.estado == 'Disponible':
                reserva.cancha.estado = 'Ocupada'
                reserva.cancha.save()
            elif nuevo_estado in ['Completada', 'Cancelada', 'No_Show']:
                if reserva.cancha.estado == 'Ocupada':
                    # Verificar si hay otros usos activos
                    otros_activos = Reserva.objects.filter(
                        cancha=reserva.cancha,
                        estado='En_Uso'
                    ).exclude(id=reserva.id).exists()

                    if not otros_activos:
                        reserva.cancha.estado = 'Disponible'
                        reserva.cancha.save()

        return Response({
            "detail": f"Estado cambiado a {reserva.get_estado_display()}",
            "estado_anterior": estado_anterior,
            "estado_nuevo": nuevo_estado
        })

    @action(detail=True, methods=['post'])
    def crear_partido(self, request, pk=None):
        """Crear partido desde reserva"""
        reserva = self.get_object()

        if reserva.partido:
            return Response(
                {"detail": "Esta reserva ya tiene un partido asociado"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if reserva.estado not in ['Confirmada', 'En_Uso']:
            return Response(
                {"detail": "Solo se pueden crear partidos de reservas confirmadas o en uso"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CrearPartidoDesdeReservaSerializer(
            data=request.data,
            context={'reserva': reserva}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Obtener jugadores
                jugadores = [reserva.jugador]
                if serializer.validated_data.get('jugadores_adicionales'):
                    jugadores_adicionales = Jugador.objects.filter(
                        id__in=serializer.validated_data['jugadores_adicionales']
                    )
                    jugadores.extend(list(jugadores_adicionales))

                # Determinar modalidad
                modalidad = serializer.validated_data.get('modalidad')
                if not modalidad:
                    modalidad = 'Individual' if len(jugadores) == 2 else 'Dobles'

                # Crear partido
                partido_data = {
                    'modalidad': modalidad,
                    'tipo': 'Amistoso',
                    'cancha': reserva.cancha,
                    'estado': 'Pendiente',
                    'jugador1_equipo1': jugadores[0],
                    'jugador1_equipo2': jugadores[1] if len(jugadores) > 1 else None,
                }

                if modalidad == 'Dobles' and len(jugadores) >= 4:
                    partido_data.update({
                        'jugador2_equipo1': jugadores[2],
                        'jugador2_equipo2': jugadores[3]
                    })

                partido = Partido.objects.create(**partido_data)

                # Asociar con reserva
                reserva.partido = partido
                reserva.save()

                # Cambiar estado si es necesario
                if reserva.estado == 'En_Uso':
                    partido.estado = 'En Juego'
                    partido.fecha_inicio = timezone.now()
                    partido.save()

                    # Crear estructura inicial
                    service = PadelScoringService(partido.id)
                    service.start_match()

                return Response({
                    "detail": "Partido creado exitosamente",
                    "partido_id": str(partido.id),
                    "partido": PartidoSerializer(partido).data
                })

        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def calendario(self, request):
        """Vista de calendario de reservas"""
        serializer = CalendarioReservasSerializer(data=request.query_params)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        fecha_inicio = serializer.validated_data['fecha_inicio']
        fecha_fin = serializer.validated_data['fecha_fin']
        cancha_id = serializer.validated_data.get('cancha')

        # Obtener reservas en el rango
        reservas = self.get_queryset().filter(
            fecha_inicio__date__gte=fecha_inicio,
            fecha_inicio__date__lte=fecha_fin
        ).exclude(
            estado='Cancelada'
        )

        if cancha_id:
            reservas = reservas.filter(cancha_id=cancha_id)

        # Agrupar por día
        calendario = {}
        for reserva in reservas:
            fecha_str = reserva.fecha_inicio.date().isoformat()
            if fecha_str not in calendario:
                calendario[fecha_str] = []

            calendario[fecha_str].append({
                'id': str(reserva.id),
                'codigo': reserva.codigo_reserva,
                'hora_inicio': reserva.fecha_inicio.strftime('%H:%M'),
                'hora_fin': reserva.fecha_fin.strftime('%H:%M'),
                'cancha': reserva.cancha.nombre,
                'tipo': reserva.tipo_reserva,
                'estado': reserva.estado,
                'jugador': reserva.jugador.nombre_completo if reserva.jugador else None
            })

        # Ordenar por hora en cada día
        for fecha in calendario:
            calendario[fecha].sort(key=lambda x: x['hora_inicio'])

        return Response({
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'total_reservas': reservas.count(),
            'calendario': calendario
        })

    @action(detail=False, methods=['get'])
    def disponibilidad(self, request):
        """Obtener disponibilidad de canchas para una fecha"""
        from .services import obtener_disponibilidad_multiple_canchas, obtener_horarios_disponibles
        from datetime import datetime

        fecha_str = request.query_params.get('fecha')
        cancha_id = request.query_params.get('cancha')
        duracion = int(request.query_params.get('duracion', 60))

        if not fecha_str:
            return Response({'error': 'Parámetro fecha requerido'}, status=400)

        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Formato de fecha inválido'}, status=400)

        if cancha_id:
            try:
                cancha = Cancha.objects.get(id=cancha_id)
                horarios = obtener_horarios_disponibles(cancha, fecha, duracion)

                return Response({
                    'fecha': fecha_str,
                    'cancha': {'id': str(cancha.id), 'nombre': cancha.nombre},
                    'horarios_disponibles': horarios,
                    'total_slots': len(horarios)
                })
            except Cancha.DoesNotExist:
                return Response({'error': 'Cancha no encontrada'}, status=404)
        else:
            disponibilidad = obtener_disponibilidad_multiple_canchas(fecha, duracion)
            return Response({'fecha': fecha_str, 'canchas': disponibilidad})

    @action(detail=False, methods=['get'])
    def calcular_precio(self, request):
        """Calcular precio dinámico"""
        from .services import calcular_precio_dinamico
        from datetime import datetime

        cancha_id = request.query_params.get('cancha')
        fecha_str = request.query_params.get('fecha')
        hora_str = request.query_params.get('hora', '12:00')
        duracion = int(request.query_params.get('duracion', 60))

        if not cancha_id or not fecha_str:
            return Response({'error': 'Cancha y fecha requeridos'}, status=400)

        try:
            cancha = Cancha.objects.get(id=cancha_id)
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            hora = datetime.strptime(hora_str, '%H:%M').time()
            fecha_hora = datetime.combine(fecha, hora)

            precio = calcular_precio_dinamico(cancha, fecha_hora, duracion)

            return Response({
                'cancha': cancha.nombre,
                'fecha_hora': f'{fecha_str} {hora_str}',
                'precio_por_hora': precio,
                'precio_total': (precio * duracion) / 60
            })

        except Cancha.DoesNotExist:
            return Response({'error': 'Cancha no encontrada'}, status=404)
        except ValueError:
            return Response({'error': 'Formato inválido'}, status=400)

    @action(detail=False, methods=['get'])
    def mejor_horario(self, request):
        """Mejor horario según criterio"""
        from .services import calcular_mejor_horario
        from datetime import datetime

        cancha_id = request.query_params.get('cancha')
        fecha_str = request.query_params.get('fecha')
        prioridad = request.query_params.get('prioridad', 'precio')

        if not cancha_id or not fecha_str:
            return Response({'error': 'Cancha y fecha requeridos'}, status=400)

        try:
            cancha = Cancha.objects.get(id=cancha_id)
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()

            mejor = calcular_mejor_horario(cancha, fecha, 60, prioridad)

            if not mejor:
                return Response({'mensaje': 'No hay horarios disponibles'})

            return Response({
                'cancha': cancha.nombre,
                'fecha': fecha_str,
                'criterio': prioridad,
                'recomendacion': mejor
            })

        except Cancha.DoesNotExist:
            return Response({'error': 'Cancha no encontrada'}, status=404)
        except ValueError:
            return Response({'error': 'Formato inválido'}, status=400)