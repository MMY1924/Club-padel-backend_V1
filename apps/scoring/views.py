# apps/scoring/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q, Count, Avg, Max, Sum
from django.db.models.functions import Extract
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, datetime, time
from django.http import JsonResponse
from django.shortcuts import redirect
from collections import defaultdict

from .models import (
    Partido, Set, Juego, Punto, HistorialJugador, EstadisticasJugador,
    Cancha, Reserva
)
from .serializers import (
    PartidoSerializer, PartidoCreateSerializer, PartidoListSerializer,
    SetSerializer, JuegoSerializer, PuntoSerializer,
    HistorialJugadorSerializer, EstadisticasJugadorSerializer,
    CanchaSerializer, CanchaListSerializer,
    AddPointSerializer, IniciarPartidoSerializer,
    ReservaSerializer, ReservaListSerializer, ReservaCreateSerializer,
    DisponibilidadSerializer, CalendarioReservasSerializer, CambiarEstadoReservaSerializer,
    CanchaConReservasSerializer, CrearJugadorSerializer, CrearPartidoDesdeReservaSerializer
)


# ==========================================
# VIEWSET PARA CANCHAS
# ==========================================
class CanchaViewSet(viewsets.ModelViewSet):
    queryset = Cancha.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['tipo', 'estado', 'activa', 'tiene_iluminacion']
    search_fields = ['nombre', 'descripcion']
    ordering_fields = ['numero', 'nombre', 'fecha_creacion']
    ordering = ['numero']

    def get_serializer_class(self):
        if self.action == 'list':
            return CanchaListSerializer
        return CanchaSerializer

    @action(detail=False, methods=['get'])
    def disponibles(self, request):
        """Obtener canchas disponibles"""
        canchas = Cancha.objects.filter(
            estado='Disponible',
            activa=True
        ).order_by('numero')

        serializer = CanchaListSerializer(canchas, many=True)
        return Response({
            'canchas_disponibles': serializer.data,
            'total': canchas.count()
        })

    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Estadísticas generales de canchas"""
        total_canchas = Cancha.objects.filter(activa=True).count()
        disponibles = Cancha.objects.filter(estado='Disponible', activa=True).count()
        ocupadas = Cancha.objects.filter(estado='Ocupada', activa=True).count()
        mantenimiento = Cancha.objects.filter(estado='Mantenimiento', activa=True).count()

        # Cancha más utilizada
        cancha_mas_usada = Cancha.objects.filter(activa=True).annotate(
            total_partidos=Count('partidos')
        ).order_by('-total_partidos').first()

        return Response({
            'resumen': {
                'total_canchas': total_canchas,
                'disponibles': disponibles,
                'ocupadas': ocupadas,
                'en_mantenimiento': mantenimiento,
                'fuera_servicio': total_canchas - disponibles - ocupadas - mantenimiento
            },
            'cancha_mas_utilizada': {
                'nombre': cancha_mas_usada.nombre if cancha_mas_usada else None,
                'total_partidos': cancha_mas_usada.total_partidos if cancha_mas_usada else 0
            } if cancha_mas_usada else None
        })

    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """Cambiar estado de una cancha"""
        cancha = self.get_object()
        nuevo_estado = request.data.get('estado')

        if nuevo_estado not in dict(Cancha.ESTADO_CHOICES):
            return Response(
                {'error': 'Estado no válido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verificar si hay partidos activos
        if nuevo_estado in ['Mantenimiento', 'Fuera_Servicio']:
            partidos_activos = cancha.partidos.filter(estado__in=['Pendiente', 'En Juego'])
            if partidos_activos.exists():
                return Response(
                    {'error': f'No se puede cambiar estado. Hay {partidos_activos.count()} partidos activos'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        cancha.estado = nuevo_estado
        cancha.save()

        return Response({
            'message': f'Estado de cancha cambiado a {nuevo_estado}',
            'cancha': CanchaSerializer(cancha).data
        })

    @action(detail=True, methods=['get'])
    def reservas(self, request, pk=None):
        """Obtener reservas de una cancha específica"""
        cancha = self.get_object()

        # Filtros opcionales
        fecha = request.query_params.get('fecha')
        estado = request.query_params.get('estado')

        reservas = cancha.reservas.all()

        if fecha:
            try:
                fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
                reservas = reservas.filter(fecha_inicio__date=fecha_obj)
            except ValueError:
                return Response(
                    {'error': 'Formato de fecha inválido. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if estado:
            reservas = reservas.filter(estado=estado)

        reservas = reservas.order_by('fecha_inicio')

        page = self.paginate_queryset(reservas)
        if page is not None:
            serializer = ReservaListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ReservaListSerializer(reservas, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def calendario_cancha(self, request, pk=None):
        """Calendario específico de una cancha"""
        cancha = self.get_object()

        # Obtener parámetros
        fecha_inicio = request.query_params.get('fecha_inicio', timezone.now().date().strftime('%Y-%m-%d'))
        fecha_fin = request.query_params.get('fecha_fin',
                                             (timezone.now().date() + timedelta(days=7)).strftime('%Y-%m-%d'))

        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Formato de fecha inválido. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Obtener reservas
        reservas = cancha.reservas.filter(
            fecha_inicio__date__gte=fecha_inicio_obj,
            fecha_inicio__date__lte=fecha_fin_obj,
            estado__in=['Confirmada', 'En_Uso', 'Pendiente']
        ).order_by('fecha_inicio')

        # Organizar por días
        calendario = defaultdict(list)
        for reserva in reservas:
            fecha_str = reserva.fecha_inicio.date().strftime('%Y-%m-%d')
            calendario[fecha_str].append({
                'id': reserva.id,
                'codigo': reserva.codigo_reserva,
                'hora_inicio': reserva.fecha_inicio.strftime('%H:%M'),
                'hora_fin': reserva.fecha_fin.strftime('%H:%M'),
                # 'cliente': reserva.cliente.nombre_completo,  # COMENTADO - requiere Cliente
                'tipo_reserva': reserva.tipo_reserva,
                'estado': reserva.estado,
                'numero_jugadores': reserva.numero_jugadores
            })

        return Response({
            'cancha': {
                'id': cancha.id,
                'nombre': cancha.nombre,
                'numero': cancha.numero
            },
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'calendario': dict(calendario)
        })


# ==========================================
# VIEWSET PARA PARTIDOS
# ==========================================
class PartidoViewSet(viewsets.ModelViewSet):
    queryset = Partido.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['modalidad', 'estado', 'tipo', 'equipo_ganador', 'cancha']
    search_fields = [
        'jugador1_equipo1__nombre', 'jugador1_equipo1__apellido',
        'jugador2_equipo1__nombre', 'jugador2_equipo1__apellido',
        'jugador1_equipo2__nombre', 'jugador1_equipo2__apellido',
        'jugador2_equipo2__nombre', 'jugador2_equipo2__apellido',
        'cancha__nombre'
    ]
    ordering_fields = ['fecha_creacion', 'fecha_inicio', 'fecha_fin']
    ordering = ['-fecha_creacion']

    def get_serializer_class(self):
        if self.action == 'create':
            return PartidoCreateSerializer
        elif self.action == 'list':
            return PartidoListSerializer
        return PartidoSerializer

    def create(self, request, *args, **kwargs):
        """Crear partido con validaciones"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                partido = serializer.save()

                response_serializer = PartidoSerializer(partido)
                return Response(
                    {
                        'message': f'Partido {partido.modalidad.lower()} creado exitosamente',
                        'partido': response_serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )
        except Exception as e:
            return Response(
                {'error': f'Error al crear partido: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def iniciar_partido(self, request, pk=None):
        """Iniciar partido - funciona para Individual y Dobles"""
        partido = self.get_object()

        serializer = IniciarPartidoSerializer(
            data={},
            context={'partido': partido}
        )
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                # Actualizar estado del partido
                partido.estado = 'En Juego'
                partido.fecha_inicio = timezone.now()
                partido.save()

                # Actualizar estado de cancha
                if partido.cancha:
                    partido.cancha.estado = 'Ocupada'
                    partido.cancha.save()

                # Crear primer set
                primer_set = Set.objects.create(
                    partido=partido,
                    numero_set=1,
                    juegos_equipo1=0,
                    juegos_equipo2=0,
                    finalizado=False
                )

                # Crear primer juego
                primer_juego = Juego.objects.create(
                    set=primer_set,
                    numero_juego=1,
                    puntos_equipo1=0,
                    puntos_equipo2=0,
                    equipo_que_saca=1,  # Empieza sacando equipo 1
                    finalizado=False
                )

                return Response({
                    'message': f'Partido {partido.modalidad.lower()} iniciado correctamente',
                    'partido_id': partido.id,
                    'modalidad': partido.modalidad,
                    'equipo1': partido.equipo1_nombre,
                    'equipo2': partido.equipo2_nombre,
                    'cancha': partido.cancha.nombre if partido.cancha else None,
                    'set_actual': primer_set.numero_set,
                    'juego_actual': primer_juego.numero_juego,
                    'quien_saca': primer_juego.equipo_que_saca
                })

        except Exception as e:
            return Response(
                {'error': f'Error al iniciar partido: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def add_point(self, request, pk=None):
        """Agregar punto al partido"""
        partido = self.get_object()

        if partido.estado != 'En Juego':
            return Response(
                {'error': 'Solo se pueden agregar puntos a partidos en juego'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = AddPointSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        equipo_ganador = serializer.validated_data['equipo_ganador']
        tipo_punto = serializer.validated_data.get('tipo_punto', 'Punto')
        descripcion = serializer.validated_data.get('descripcion', '')

        try:
            with transaction.atomic():
                # Obtener set y juego actual
                set_actual = partido.sets.filter(finalizado=False).last()
                if not set_actual:
                    return Response(
                        {'error': 'No hay sets activos'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                juego_actual = set_actual.juegos.filter(finalizado=False).last()
                if not juego_actual:
                    return Response(
                        {'error': 'No hay juegos activos'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Crear el punto
                numero_punto = juego_actual.puntos.count() + 1
                punto = Punto.objects.create(
                    juego=juego_actual,
                    equipo_ganador=equipo_ganador,
                    tipo_punto=tipo_punto,
                    descripcion=descripcion,
                    numero_punto=numero_punto
                )

                # Actualizar puntuación del juego
                if equipo_ganador == 1:
                    juego_actual.puntos_equipo1 += 1
                else:
                    juego_actual.puntos_equipo2 += 1

                # Verificar si el juego terminó
                juego_terminado = self._verificar_juego_terminado(juego_actual)
                if juego_terminado:
                    juego_actual.finalizado = True
                    juego_actual.equipo_ganador = juego_terminado
                    juego_actual.fecha_fin = timezone.now()

                    # Actualizar puntuación del set
                    if juego_terminado == 1:
                        set_actual.juegos_equipo1 += 1
                    else:
                        set_actual.juegos_equipo2 += 1

                    # Verificar si el set terminó
                    set_terminado = self._verificar_set_terminado(set_actual, partido)
                    if set_terminado:
                        set_actual.finalizado = True
                        set_actual.equipo_ganador = set_terminado
                        set_actual.fecha_fin = timezone.now()

                        # Verificar si el partido terminó
                        partido_terminado = self._verificar_partido_terminado(partido)
                        if partido_terminado:
                            partido.estado = 'Finalizado'
                            partido.equipo_ganador = partido_terminado
                            partido.fecha_fin = timezone.now()

                            # Liberar cancha
                            if partido.cancha:
                                partido.cancha.estado = 'Disponible'
                                partido.cancha.save()

                            partido.save()
                        else:
                            # Crear nuevo set
                            nuevo_numero_set = set_actual.numero_set + 1
                            nuevo_set = Set.objects.create(
                                partido=partido,
                                numero_set=nuevo_numero_set,
                                juegos_equipo1=0,
                                juegos_equipo2=0,
                                finalizado=False
                            )

                            # Crear primer juego del nuevo set
                            Juego.objects.create(
                                set=nuevo_set,
                                numero_juego=1,
                                puntos_equipo1=0,
                                puntos_equipo2=0,
                                equipo_que_saca=1 if juego_actual.equipo_que_saca == 2 else 2,
                                finalizado=False
                            )
                    else:
                        # Crear nuevo juego
                        nuevo_numero_juego = juego_actual.numero_juego + 1
                        Juego.objects.create(
                            set=set_actual,
                            numero_juego=nuevo_numero_juego,
                            puntos_equipo1=0,
                            puntos_equipo2=0,
                            equipo_que_saca=1 if juego_actual.equipo_que_saca == 2 else 2,
                            finalizado=False
                        )

                    set_actual.save()

                juego_actual.save()

                return Response({
                    'message': 'Punto agregado correctamente',
                    'punto_id': punto.id,
                    'juego_terminado': juego_actual.finalizado,
                    'set_terminado': set_actual.finalizado if juego_actual.finalizado else False,
                    'partido_terminado': partido.estado == 'Finalizado'
                })

        except Exception as e:
            return Response(
                {'error': f'Error al agregar punto: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def live_score(self, request, pk=None):
        """Score en tiempo real"""
        partido = self.get_object()

        if partido.estado not in ['En Juego', 'Finalizado']:
            return Response({
                'partido_id': partido.id,
                'modalidad': partido.modalidad,
                'estado': partido.estado,
                'mensaje': 'Partido no iniciado'
            })

        try:
            sets = partido.sets.all().order_by('numero_set')
            set_actual = sets.filter(finalizado=False).first()

            score_data = {
                'partido_id': partido.id,
                'modalidad': partido.modalidad,
                'estado': partido.estado,
                'equipo1_info': {
                    'jugadores': partido.equipo1_nombre,
                    'sets_ganados': sets.filter(equipo_ganador=1).count()
                },
                'equipo2_info': {
                    'jugadores': partido.equipo2_nombre,
                    'sets_ganados': sets.filter(equipo_ganador=2).count()
                },
                'cancha_info': {
                    'nombre': partido.cancha.nombre if partido.cancha else None,
                    'numero': partido.cancha.numero if partido.cancha else None
                },
                'sets_detalle': [],
                'set_actual': None,
                'juego_actual': None
            }

            # Detalle de sets
            for set_obj in sets:
                score_data['sets_detalle'].append({
                    'numero': set_obj.numero_set,
                    'juegos_equipo1': set_obj.juegos_equipo1,
                    'juegos_equipo2': set_obj.juegos_equipo2,
                    'finalizado': set_obj.finalizado,
                    'equipo_ganador': set_obj.equipo_ganador
                })

            # Set actual
            if set_actual:
                juego_actual = set_actual.juegos.filter(finalizado=False).first()

                score_data['set_actual'] = {
                    'numero': set_actual.numero_set,
                    'juegos_equipo1': set_actual.juegos_equipo1,
                    'juegos_equipo2': set_actual.juegos_equipo2
                }

                # Juego actual con conversión de puntos
                if juego_actual:
                    score_data['juego_actual'] = {
                        'numero': juego_actual.numero_juego,
                        'puntos_equipo1': juego_actual.puntos_display_equipo1,
                        'puntos_equipo2': juego_actual.puntos_display_equipo2,
                        'quien_saca': juego_actual.equipo_que_saca
                    }

            return Response(score_data)

        except Exception as e:
            return Response(
                {'error': f'Error al obtener score: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def estadisticas_modalidades(self, request):
        """Estadísticas por modalidad de partido"""
        stats = Partido.objects.values('modalidad', 'estado').annotate(
            cantidad=Count('id')
        ).order_by('modalidad', 'estado')

        estadisticas = {
            'Individual': {'Pendiente': 0, 'En Juego': 0, 'Finalizado': 0, 'Cancelado': 0},
            'Dobles': {'Pendiente': 0, 'En Juego': 0, 'Finalizado': 0, 'Cancelado': 0}
        }

        for stat in stats:
            modalidad = stat['modalidad']
            estado = stat['estado']
            cantidad = stat['cantidad']
            estadisticas[modalidad][estado] = cantidad

        total_individual = sum(estadisticas['Individual'].values())
        total_dobles = sum(estadisticas['Dobles'].values())
        total_general = total_individual + total_dobles

        return Response({
            'estadisticas_detalladas': estadisticas,
            'totales': {
                'Individual': total_individual,
                'Dobles': total_dobles,
                'Total': total_general
            },
            'porcentajes': {
                'Individual': round((total_individual / total_general * 100), 2) if total_general > 0 else 0,
                'Dobles': round((total_dobles / total_general * 100), 2) if total_general > 0 else 0
            }
        })

    # ==========================================
    # MÉTODOS AUXILIARES PRIVADOS
    # ==========================================
    def _verificar_juego_terminado(self, juego):
        """Verificar si un juego ha terminado según reglas de tenis"""
        puntos1 = juego.puntos_equipo1
        puntos2 = juego.puntos_equipo2

        # Mínimo 4 puntos para ganar y diferencia de 2
        if puntos1 >= 4 and puntos1 - puntos2 >= 2:
            return 1
        elif puntos2 >= 4 and puntos2 - puntos1 >= 2:
            return 2

        return None

    def _verificar_set_terminado(self, set_obj, partido):
        """Verificar si un set ha terminado"""
        juegos1 = set_obj.juegos_equipo1
        juegos2 = set_obj.juegos_equipo2
        min_juegos = partido.juegos_para_ganar_set

        # Ganar por diferencia de 2 juegos
        if juegos1 >= min_juegos and juegos1 - juegos2 >= 2:
            return 1
        elif juegos2 >= min_juegos and juegos2 - juegos1 >= 2:
            return 2

        # Caso especial: 7-5
        if (juegos1 == min_juegos + 1 and juegos2 == min_juegos - 1):
            return 1
        elif (juegos2 == min_juegos + 1 and juegos1 == min_juegos - 1):
            return 2

        return None

    def _verificar_partido_terminado(self, partido):
        """Verificar si un partido ha terminado"""
        sets_ganados_1 = partido.sets.filter(equipo_ganador=1).count()
        sets_ganados_2 = partido.sets.filter(equipo_ganador=2).count()
        sets_para_ganar = partido.sets_para_ganar

        if sets_ganados_1 >= sets_para_ganar:
            return 1
        elif sets_ganados_2 >= sets_para_ganar:
            return 2

        return None


# ==========================================
# VIEWSET PARA RESERVAS (SIMPLIFICADO)
# ==========================================
class ReservaViewSet(viewsets.ModelViewSet):
    queryset = Reserva.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['cancha', 'estado', 'tipo_reserva', 'pagado']
    search_fields = ['codigo_reserva', 'cancha__nombre']
    ordering_fields = ['fecha_inicio', 'fecha_creacion', 'precio_total']
    ordering = ['-fecha_inicio']

    def get_serializer_class(self):
        if self.action == 'create':
            return ReservaCreateSerializer
        elif self.action == 'list':
            return ReservaListSerializer
        return ReservaSerializer

    def create(self, request, *args, **kwargs):
        """Crear nueva reserva con validaciones"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                reserva = serializer.save()

                response_serializer = ReservaSerializer(reserva)
                return Response(
                    {
                        'message': f'Reserva {reserva.codigo_reserva} creada exitosamente',
                        'reserva': response_serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )
        except Exception as e:
            return Response(
                {'error': f'Error al crear reserva: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def disponibilidad(self, request):
        """Verificar disponibilidad de canchas"""
        serializer = DisponibilidadSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        cancha = serializer.validated_data['cancha_obj']
        fecha = serializer.validated_data['fecha']
        hora_inicio = serializer.validated_data.get('hora_inicio')
        hora_fin = serializer.validated_data.get('hora_fin')

        # Obtener reservas del día
        reservas_dia = Reserva.objects.filter(
            cancha=cancha,
            fecha_inicio__date=fecha,
            estado__in=['Confirmada', 'En_Uso', 'Pendiente']
        ).order_by('fecha_inicio')

        # Generar horarios disponibles
        horarios_disponibles = self._generar_horarios_disponibles(
            fecha, reservas_dia, hora_inicio, hora_fin
        )

        return Response({
            'cancha': {
                'id': cancha.id,
                'nombre': cancha.nombre,
                'numero': cancha.numero
            },
            'fecha': fecha.strftime('%Y-%m-%d'),
            'reservas_existentes': [
                {
                    'codigo': r.codigo_reserva,
                    'hora_inicio': r.fecha_inicio.strftime('%H:%M'),
                    'hora_fin': r.fecha_fin.strftime('%H:%M'),
                    'estado': r.estado
                } for r in reservas_dia
            ],
            'horarios_disponibles': horarios_disponibles
        })

    @action(detail=False, methods=['get'])
    def calendario(self, request):
        """Obtener calendario de reservas"""
        serializer = CalendarioReservasSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        fecha_inicio = serializer.validated_data['fecha_inicio']
        fecha_fin = serializer.validated_data['fecha_fin']
        cancha_id = serializer.validated_data.get('cancha')

        # Filtros
        reservas_query = Reserva.objects.filter(
            fecha_inicio__date__gte=fecha_inicio,
            fecha_inicio__date__lte=fecha_fin,
            estado__in=['Confirmada', 'En_Uso', 'Pendiente']
        )

        if cancha_id:
            reservas_query = reservas_query.filter(cancha_id=cancha_id)

        reservas = reservas_query.select_related('cancha').order_by('fecha_inicio')

        # Organizar por días
        calendario = defaultdict(list)
        for reserva in reservas:
            fecha_str = reserva.fecha_inicio.date().strftime('%Y-%m-%d')
            calendario[fecha_str].append({
                'id': reserva.id,
                'codigo': reserva.codigo_reserva,
                'hora_inicio': reserva.fecha_inicio.strftime('%H:%M'),
                'hora_fin': reserva.fecha_fin.strftime('%H:%M'),
                'cancha': {
                    'id': reserva.cancha.id,
                    'nombre': reserva.cancha.nombre,
                    'numero': reserva.cancha.numero
                },
                # 'cliente': reserva.cliente.nombre_completo,  # COMENTADO - requiere Cliente
                'tipo_reserva': reserva.tipo_reserva,
                'estado': reserva.estado,
                'precio_total': float(reserva.precio_total),
                'numero_jugadores': reserva.numero_jugadores
            })

        return Response({
            'fecha_inicio': fecha_inicio.strftime('%Y-%m-%d'),
            'fecha_fin': fecha_fin.strftime('%Y-%m-%d'),
            'total_reservas': reservas.count(),
            'calendario': dict(calendario)
        })

    @action(detail=True, methods=['post'])
    def confirmar(self, request, pk=None):
        """Confirmar una reserva pendiente"""
        reserva = self.get_object()

        if reserva.estado != 'Pendiente':
            return Response(
                {'error': 'Solo se pueden confirmar reservas pendientes'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reserva.confirmar()
        return Response({
            'message': f'Reserva {reserva.codigo_reserva} confirmada exitosamente',
            'reserva': ReservaSerializer(reserva).data
        })

    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        """Cancelar una reserva"""
        reserva = self.get_object()
        motivo = request.data.get('motivo', '')

        if reserva.cancelar(motivo):
            return Response({
                'message': f'Reserva {reserva.codigo_reserva} cancelada exitosamente',
                'reserva': ReservaSerializer(reserva).data
            })
        else:
            return Response(
                {'error': 'No se puede cancelar esta reserva (tiempo límite excedido o estado no válido)'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Estadísticas generales de reservas"""
        # Filtros de fecha
        fecha_desde = request.query_params.get('fecha_desde')
        fecha_hasta = request.query_params.get('fecha_hasta')

        reservas_query = Reserva.objects.all()

        if fecha_desde:
            fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            reservas_query = reservas_query.filter(fecha_inicio__date__gte=fecha_desde)

        if fecha_hasta:
            fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            reservas_query = reservas_query.filter(fecha_inicio__date__lte=fecha_hasta)

        # Estadísticas básicas
        total_reservas = reservas_query.count()
        reservas_confirmadas = reservas_query.filter(estado='Confirmada').count()
        reservas_completadas = reservas_query.filter(estado='Completada').count()
        reservas_canceladas = reservas_query.filter(estado='Cancelada').count()

        # Ingresos
        ingresos_totales = reservas_query.filter(pagado=True).aggregate(
            total=Sum('precio_total'))['total'] or 0

        # Estadísticas por cancha
        stats_canchas = reservas_query.values('cancha__nombre').annotate(
            total_reservas=Count('id'),
            ingresos=Sum('precio_total', filter=Q(pagado=True))
        ).order_by('-total_reservas')

        # Estadísticas por tipo de reserva
        stats_tipos = reservas_query.values('tipo_reserva').annotate(
            total=Count('id')
        ).order_by('-total')

        return Response({
            'resumen': {
                'total_reservas': total_reservas,
                'confirmadas': reservas_confirmadas,
                'completadas': reservas_completadas,
                'canceladas': reservas_canceladas,
                'tasa_confirmacion': round((reservas_confirmadas / total_reservas * 100),
                                           2) if total_reservas > 0 else 0,
                'ingresos_totales': float(ingresos_totales)
            },
            'por_cancha': list(stats_canchas),
            'por_tipo': list(stats_tipos)
        })

    def _generar_horarios_disponibles(self, fecha, reservas_existentes, hora_inicio=None, hora_fin=None):
        """Generar lista de horarios disponibles"""
        # Horarios de funcionamiento (6:00 AM a 11:00 PM)
        hora_apertura = time(6, 0)
        hora_cierre = time(23, 0)

        if hora_inicio:
            hora_apertura = max(hora_apertura, hora_inicio)
        if hora_fin:
            hora_cierre = min(hora_cierre, hora_fin)

        # Generar slots de 1 hora
        horarios_disponibles = []
        hora_actual = datetime.combine(fecha, hora_apertura)
        hora_limite = datetime.combine(fecha, hora_cierre)

        while hora_actual < hora_limite:
            hora_siguiente = hora_actual + timedelta(hours=1)

            # Verificar si está ocupado
            ocupado = any(
                reserva.fecha_inicio < hora_siguiente and reserva.fecha_fin > hora_actual
                for reserva in reservas_existentes
            )

            if not ocupado:
                horarios_disponibles.append({
                    'hora_inicio': hora_actual.strftime('%H:%M'),
                    'hora_fin': hora_siguiente.strftime('%H:%M'),
                    'disponible': True
                })

            hora_actual = hora_siguiente

        return horarios_disponibles


# ==========================================
# VIEWSETS EXISTENTES (MANTENER IGUAL)
# ==========================================
class SetViewSet(viewsets.ModelViewSet):
    queryset = Set.objects.all()
    serializer_class = SetSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['partido', 'finalizado', 'equipo_ganador']


class JuegoViewSet(viewsets.ModelViewSet):
    queryset = Juego.objects.all()
    serializer_class = JuegoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['set', 'finalizado', 'equipo_ganador', 'equipo_que_saca']


class PuntoViewSet(viewsets.ModelViewSet):
    queryset = Punto.objects.all()
    serializer_class = PuntoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['juego', 'equipo_ganador', 'tipo_punto']


class HistorialJugadorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HistorialJugador.objects.all()
    serializer_class = HistorialJugadorSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['jugador', 'partido', 'es_ganador', 'equipo_jugador']


class EstadisticasJugadorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EstadisticasJugador.objects.all()
    serializer_class = EstadisticasJugadorSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['jugador']


# ==========================================
# VIEWS DE API
# ==========================================
@api_view(['GET'])
def api_root(request):
    """Vista raíz de la API - Información para desarrolladores frontend"""
    if request.accepts('text/html'):
        # Si se accede desde navegador, mostrar información básica
        return JsonResponse({
            'message': '🏓 Pádel Score API',
            'version': 'v1.0',
            'description': 'Backend API para sistema de puntuación de pádel',
            'endpoints': {
                'admin': '/admin/',
                'api_players': '/api/v1/players/',
                'api_scoring': '/api/v1/scoring/',
                'docs': 'Documentación pendiente'
            },
            'status': 'operational',
            'frontend': 'To be developed separately'
        }, json_dumps_params={'indent': 2})

    # Para requests de API, devolver estructura JSON limpia
    return JsonResponse({
        'api_name': 'Pádel Score API',
        'version': 'v1.0',
        'endpoints': [
            '/api/v1/players/',
            '/api/v1/scoring/'
        ]
    })
