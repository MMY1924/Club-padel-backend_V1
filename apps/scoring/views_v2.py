from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q, Count, Avg
from django.utils import timezone
from datetime import datetime, timedelta

from .models import (
    Cancha, Partido, Set, Juego, Punto, Reserva, 
    HistorialJugador, EstadisticasJugador
)
from .serializers import (
    CanchaSerializer, CanchaListSerializer, CanchaConReservasSerializer,
    PartidoSerializer, PartidoCreateSerializer, PartidoListSerializer,
    ReservaSerializer, ReservaCreateSerializer, ReservaListSerializer,
    EstadisticasJugadorSerializer, HistorialJugadorSerializer,
    SetSerializer, JuegoSerializer, PuntoSerializer,
    AddPointSerializer, IniciarPartidoSerializer
)
from .services import (
    PadelScoringService, obtener_horarios_disponibles, 
    calcular_precio_dinamico, obtener_disponibilidad_multiple_canchas
)


class CanchaViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de canchas"""
    
    queryset = Cancha.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['tipo', 'estado', 'activa', 'tiene_iluminacion']
    search_fields = ['nombre', 'descripcion']
    ordering_fields = ['numero', 'nombre', 'fecha_creacion']
    ordering = ['numero']
    
    def get_serializer_class(self):
        """Seleccionar serializer según acción"""
        if self.action == 'list':
            return CanchaListSerializer
        elif self.action == 'con_reservas':
            return CanchaConReservasSerializer
        return CanchaSerializer
    
    @action(detail=False, methods=['get'])
    def activas(self, request):
        """Obtener solo canchas activas"""
        canchas = self.queryset.filter(activa=True)
        serializer = CanchaListSerializer(canchas, many=True)
        return Response({
            'canchas': serializer.data,
            'total': canchas.count()
        })
    
    @action(detail=False, methods=['get'])
    def disponibles(self, request):
        """Obtener canchas disponibles ahora"""
        canchas = self.queryset.filter(activa=True, estado='Disponible')
        serializer = CanchaListSerializer(canchas, many=True)
        return Response({
            'canchas': serializer.data,
            'total': canchas.count()
        })
    
    @action(detail=True, methods=['get'])
    def disponibilidad(self, request, pk=None):
        """Obtener disponibilidad de una cancha específica"""
        cancha = self.get_object()
        fecha_str = request.query_params.get('fecha')
        duracion = int(request.query_params.get('duracion', 60))
        
        if not fecha_str:
            fecha = timezone.now().date()
        else:
            try:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'error': 'Formato de fecha inválido. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        horarios = obtener_horarios_disponibles(cancha, fecha, duracion)
        
        return Response({
            'cancha': {
                'id': str(cancha.id),
                'nombre': cancha.nombre,
                'numero': cancha.numero,
                'tipo': cancha.tipo
            },
            'fecha': fecha,
            'duracion_solicitada': duracion,
            'horarios_disponibles': horarios,
            'total_horarios': len(horarios),
            'horas_totales_disponibles': sum(h['duracion_minutos'] for h in horarios) / 60
        })
    
    @action(detail=False, methods=['get'])
    def disponibilidad_multiple(self, request):
        """Disponibilidad de todas las canchas para una fecha"""
        fecha_str = request.query_params.get('fecha')
        duracion = int(request.query_params.get('duracion', 60))
        
        if not fecha_str:
            fecha = timezone.now().date()
        else:
            try:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'error': 'Formato de fecha inválido. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        disponibilidad = obtener_disponibilidad_multiple_canchas(fecha, duracion)
        
        return Response({
            'fecha': fecha,
            'duracion_solicitada': duracion,
            'disponibilidad': disponibilidad,
            'total_canchas': len(disponibilidad)
        })
    
    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """Cambiar estado de la cancha"""
        cancha = self.get_object()
        nuevo_estado = request.data.get('estado')
        
        if nuevo_estado not in dict(Cancha.ESTADO_CHOICES):
            return Response({
                'error': 'Estado inválido'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        cancha.estado = nuevo_estado
        cancha.save()
        
        return Response({
            'message': f'Estado de cancha cambiado a {nuevo_estado}',
            'cancha': CanchaSerializer(cancha).data
        })


class PartidoViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de partidos"""
    
    queryset = Partido.objects.select_related(
        'cancha', 'jugador1_equipo1__user', 'jugador2_equipo1__user',
        'jugador1_equipo2__user', 'jugador2_equipo2__user'
    ).all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['modalidad', 'estado', 'tipo', 'cancha']
    search_fields = ['jugador1_equipo1__user__first_name', 'jugador1_equipo2__user__first_name']
    ordering_fields = ['fecha_creacion', 'fecha_inicio', 'fecha_fin']
    ordering = ['-fecha_creacion']
    
    def get_serializer_class(self):
        """Seleccionar serializer según acción"""
        if self.action == 'create':
            return PartidoCreateSerializer
        elif self.action == 'list':
            return PartidoListSerializer
        return PartidoSerializer
    
    def create(self, request, *args, **kwargs):
        """Crear partido usando el servicio"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            partido = serializer.save()
            
            return Response({
                'partido': PartidoSerializer(partido).data,
                'message': f'Partido creado exitosamente: {partido.equipo1_nombre} vs {partido.equipo2_nombre}'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': f'Error al crear partido: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def iniciar(self, request, pk=None):
        """Iniciar partido"""
        partido = self.get_object()
        
        if partido.estado != 'Pendiente':
            return Response({
                'error': 'Solo se pueden iniciar partidos pendientes'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            service = PadelScoringService(partido.id)
            service.start_match()
            
            return Response({
                'message': 'Partido iniciado exitosamente',
                'partido': PartidoSerializer(partido).data,
                'marcador': service.get_live_score()
            })
            
        except Exception as e:
            return Response({
                'error': f'Error al iniciar partido: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def agregar_punto(self, request, pk=None):
        """Agregar punto al partido"""
        partido = self.get_object()
        
        if partido.estado != 'En Juego':
            return Response({
                'error': 'Solo se pueden agregar puntos a partidos en juego'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = AddPointSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            service = PadelScoringService(partido.id)
            punto, resultado = service.add_point(
                equipo_ganador=serializer.validated_data['equipo_ganador'],
                descripcion=serializer.validated_data.get('descripcion', '')
            )
            
            return Response({
                'punto': PuntoSerializer(punto).data,
                'resultado': resultado,
                'marcador_actual': service.get_live_score()
            })
            
        except Exception as e:
            return Response({
                'error': f'Error al agregar punto: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def deshacer_punto(self, request, pk=None):
        """Deshacer último punto"""
        partido = self.get_object()
        
        if partido.estado != 'En Juego':
            return Response({
                'error': 'Solo se pueden deshacer puntos de partidos en juego'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            service = PadelScoringService(partido.id)
            resultado = service.undo_last_point()
            
            if resultado:
                return Response({
                    'message': 'Punto deshecho exitosamente',
                    'marcador_actual': service.get_live_score()
                })
            else:
                return Response({
                    'error': 'No hay puntos para deshacer'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'error': f'Error al deshacer punto: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def marcador(self, request, pk=None):
        """Obtener marcador en vivo"""
        partido = self.get_object()
        
        try:
            service = PadelScoringService(partido.id)
            marcador = service.get_live_score()
            
            return Response(marcador)
            
        except Exception as e:
            return Response({
                'error': f'Error al obtener marcador: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def estadisticas(self, request, pk=None):
        """Obtener estadísticas del partido"""
        partido = self.get_object()
        
        try:
            stats = PadelScoringService.get_match_statistics(partido.id)
            return Response(stats)
            
        except Exception as e:
            return Response({
                'error': f'Error al obtener estadísticas: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def historial_detallado(self, request, pk=None):
        """Obtener historial detallado de puntuación"""
        partido = self.get_object()
        
        try:
            service = PadelScoringService(partido.id)
            historial = service.get_detailed_score_history()
            
            return Response({
                'partido': PartidoListSerializer(partido).data,
                'historial': historial
            })
            
        except Exception as e:
            return Response({
                'error': f'Error al obtener historial: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def activos(self, request):
        """Obtener partidos activos (en juego)"""
        partidos_activos = self.queryset.filter(estado='En Juego')
        serializer = PartidoListSerializer(partidos_activos, many=True)
        
        # Agregar marcador actual de cada partido
        partidos_con_marcador = []
        for partido_data in serializer.data:
            try:
                service = PadelScoringService(partido_data['id'])
                marcador = service.get_live_score()
                partido_data['marcador_actual'] = marcador
            except:
                partido_data['marcador_actual'] = None
            
            partidos_con_marcador.append(partido_data)
        
        return Response({
            'partidos_activos': partidos_con_marcador,
            'total': partidos_activos.count()
        })
    
    @action(detail=False, methods=['get'])
    def pendientes(self, request):
        """Obtener partidos pendientes"""
        partidos = self.queryset.filter(estado='Pendiente')
        serializer = PartidoListSerializer(partidos, many=True)
        return Response({
            'partidos_pendientes': serializer.data,
            'total': partidos.count()
        })
    
    @action(detail=False, methods=['get'])
    def finalizados(self, request):
        """Obtener partidos finalizados con paginación"""
        partidos = self.queryset.filter(estado='Finalizado')
        
        # Filtros opcionales
        modalidad = request.query_params.get('modalidad')
        tipo = request.query_params.get('tipo')
        fecha_desde = request.query_params.get('fecha_desde')
        fecha_hasta = request.query_params.get('fecha_hasta')
        
        if modalidad:
            partidos = partidos.filter(modalidad=modalidad)
        if tipo:
            partidos = partidos.filter(tipo=tipo)
        if fecha_desde:
            try:
                fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                partidos = partidos.filter(fecha_fin__date__gte=fecha_desde)
            except ValueError:
                pass
        if fecha_hasta:
            try:
                fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                partidos = partidos.filter(fecha_fin__date__lte=fecha_hasta)
            except ValueError:
                pass
        
        page = self.paginate_queryset(partidos)
        if page is not None:
            serializer = PartidoListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = PartidoListSerializer(partidos, many=True)
        return Response({
            'partidos_finalizados': serializer.data,
            'total': partidos.count()
        })


class ReservaViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de reservas"""
    
    queryset = Reserva.objects.select_related('cancha', 'jugador__user').all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['estado', 'tipo_reserva', 'cancha', 'pagado']
    search_fields = ['codigo_reserva', 'jugador__user__first_name', 'cancha__nombre']
    ordering_fields = ['fecha_inicio', 'fecha_creacion', 'precio_total']
    ordering = ['-fecha_creacion']
    
    def get_serializer_class(self):
        """Seleccionar serializer según acción"""
        if self.action == 'create':
            return ReservaCreateSerializer
        elif self.action == 'list':
            return ReservaListSerializer
        return ReservaSerializer
    
    def create(self, request, *args, **kwargs):
        """Crear reserva con precio automático"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            reserva = serializer.save()
            
            return Response({
                'reserva': ReservaSerializer(reserva).data,
                'message': f'Reserva creada exitosamente: {reserva.codigo_reserva}'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': f'Error al crear reserva: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """Cambiar estado de la reserva"""
        reserva = self.get_object()
        nuevo_estado = request.data.get('estado')
        motivo = request.data.get('motivo', '')
        
        if nuevo_estado not in dict(Reserva.ESTADO_CHOICES):
            return Response({
                'error': 'Estado inválido'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validaciones de cambio de estado
        if reserva.estado == 'Cancelada' and nuevo_estado != 'Cancelada':
            return Response({
                'error': 'No se puede cambiar el estado de una reserva cancelada'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        reserva.estado = nuevo_estado
        if motivo:
            reserva.observaciones += f"\n[{timezone.now().strftime('%d/%m/%Y %H:%M')}] Estado cambiado a {nuevo_estado}: {motivo}"
        reserva.save()
        
        return Response({
            'message': f'Estado de reserva cambiado a {nuevo_estado}',
            'reserva': ReservaSerializer(reserva).data
        })
    
    @action(detail=True, methods=['post'])
    def marcar_pagado(self, request, pk=None):
        """Marcar reserva como pagada"""
        reserva = self.get_object()
        
        if reserva.pagado:
            return Response({
                'message': 'La reserva ya está marcada como pagada'
            })
        
        reserva.pagado = True
        if reserva.estado == 'Pendiente':
            reserva.estado = 'Confirmada'
        reserva.save()
        
        return Response({
            'message': 'Reserva marcada como pagada',
            'reserva': ReservaSerializer(reserva).data
        })
    
    @action(detail=False, methods=['get'])
    def hoy(self, request):
        """Reservas de hoy"""
        hoy = timezone.now().date()
        reservas = self.queryset.filter(fecha_inicio__date=hoy)
        serializer = ReservaListSerializer(reservas, many=True)
        
        return Response({
            'fecha': hoy,
            'reservas': serializer.data,
            'total': reservas.count()
        })
    
    @action(detail=False, methods=['get'])
    def proximas(self, request):
        """Próximas reservas (próximos 7 días)"""
        ahora = timezone.now()
        en_una_semana = ahora + timedelta(days=7)
        
        reservas = self.queryset.filter(
            fecha_inicio__gte=ahora,
            fecha_inicio__lte=en_una_semana,
            estado__in=['Confirmada', 'Pendiente']
        ).order_by('fecha_inicio')
        
        serializer = ReservaListSerializer(reservas, many=True)
        
        return Response({
            'periodo': f'{ahora.date()} - {en_una_semana.date()}',
            'reservas': serializer.data,
            'total': reservas.count()
        })
    
    @action(detail=False, methods=['get'])
    def calendario(self, request):
        """Vista de calendario de reservas"""
        fecha_inicio_str = request.query_params.get('fecha_inicio')
        fecha_fin_str = request.query_params.get('fecha_fin')
        cancha_id = request.query_params.get('cancha')
        
        # Fechas por defecto (próximos 7 días)
        if not fecha_inicio_str:
            fecha_inicio = timezone.now().date()
        else:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        
        if not fecha_fin_str:
            fecha_fin = fecha_inicio + timedelta(days=7)
        else:
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
        
        reservas_query = self.queryset.filter(
            fecha_inicio__date__gte=fecha_inicio,
            fecha_inicio__date__lte=fecha_fin
        )
        
        if cancha_id:
            reservas_query = reservas_query.filter(cancha_id=cancha_id)
        
        reservas = reservas_query.order_by('fecha_inicio')
        
        # Agrupar por fecha
        calendario = {}
        for reserva in reservas:
            fecha_str = reserva.fecha_inicio.date().strftime('%Y-%m-%d')
            if fecha_str not in calendario:
                calendario[fecha_str] = []
            
            calendario[fecha_str].append({
                'id': str(reserva.id),
                'codigo_reserva': reserva.codigo_reserva,
                'cancha': reserva.cancha.nombre,
                'hora_inicio': reserva.fecha_inicio.strftime('%H:%M'),
                'hora_fin': reserva.fecha_fin.strftime('%H:%M'),
                'duracion': reserva.duracion_display,
                'estado': reserva.estado,
                'tipo': reserva.tipo_reserva,
                'precio': float(reserva.precio_total),
                'pagado': reserva.pagado,
                'jugador': reserva.jugador.nombre_completo if reserva.jugador else None
            })
        
        return Response({
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'calendario': calendario,
            'total_reservas': reservas.count()
        })


class EstadisticasViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para estadísticas generales"""
    
    queryset = EstadisticasJugador.objects.select_related('jugador__user').all()
    serializer_class = EstadisticasJugadorSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['jugador']
    ordering_fields = ['partidos_jugados', 'partidos_ganados', 'porcentaje_victorias']
    ordering = ['-partidos_jugados']
    
    @action(detail=False, methods=['get'])
    def resumen_general(self, request):
        """Resumen estadístico general del sistema"""
        # Estadísticas de partidos
        total_partidos = Partido.objects.count()
        partidos_finalizados = Partido.objects.filter(estado='Finalizado').count()
        partidos_activos = Partido.objects.filter(estado='En Juego').count()
        partidos_pendientes = Partido.objects.filter(estado='Pendiente').count()
        
        # Estadísticas de reservas
        total_reservas = Reserva.objects.count()
        reservas_confirmadas = Reserva.objects.filter(estado='Confirmada').count()
        reservas_hoy = Reserva.objects.filter(fecha_inicio__date=timezone.now().date()).count()
        
        # Estadísticas de canchas
        total_canchas = Cancha.objects.count()
        canchas_activas = Cancha.objects.filter(activa=True).count()
        canchas_disponibles = Cancha.objects.filter(activa=True, estado='Disponible').count()
        
        # Top jugadores
        top_jugadores = self.queryset.filter(partidos_jugados__gt=0).order_by('-partidos_jugados')[:10]
        
        return Response({
            'partidos': {
                'total': total_partidos,
                'finalizados': partidos_finalizados,
                'activos': partidos_activos,
                'pendientes': partidos_pendientes
            },
            'reservas': {
                'total': total_reservas,
                'confirmadas': reservas_confirmadas,
                'hoy': reservas_hoy
            },
            'canchas': {
                'total': total_canchas,
                'activas': canchas_activas,
                'disponibles': canchas_disponibles
            },
            'top_jugadores': EstadisticasJugadorSerializer(top_jugadores, many=True).data
        })