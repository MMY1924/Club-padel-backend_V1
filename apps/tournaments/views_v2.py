# apps/tournaments/views_v2.py

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q, Count, Avg, Max
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta

from .models import (
    Torneo, InscripcionTorneo, FaseTorneo,
    GrupoTorneo, PartidoTorneo, ClasificacionTorneo
)
from .serializers import (
    TorneoListSerializer, TorneoDetailSerializer, TorneoCreateSerializer,
    InscripcionListSerializer, InscripcionDetailSerializer, InscripcionCreateSerializer,
    FaseTorneoSerializer, GrupoTorneoSerializer,
    PartidoTorneoListSerializer, PartidoTorneoDetailSerializer, PartidoTorneoUpdateSerializer,
    ClasificacionSerializer, TorneoStatusSerializer,
    GenerarSorteoSerializer, ProgramarPartidosSerializer
)
from apps.players.models import Jugador


class TorneoViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de torneos"""
    
    queryset = Torneo.objects.prefetch_related('inscripciones', 'canchas').all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['estado', 'tipo', 'modalidad', 'activo']
    search_fields = ['nombre', 'codigo_torneo', 'descripcion']
    ordering_fields = ['fecha_creacion', 'fecha_inicio', 'fecha_fin', 'nombre']
    ordering = ['-fecha_creacion']
    
    def get_serializer_class(self):
        """Seleccionar serializer según acción"""
        if self.action == 'create':
            return TorneoCreateSerializer
        elif self.action == 'list':
            return TorneoListSerializer
        return TorneoDetailSerializer
    
    def get_permissions(self):
        """Permisos por acción"""
        if self.action in ['list', 'retrieve', 'status', 'ranking', 'partidos']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def create(self, request, *args, **kwargs):
        """Crear torneo"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                torneo = serializer.save()
                
                return Response({
                    'torneo': TorneoDetailSerializer(torneo).data,
                    'message': f'Torneo creado exitosamente: {torneo.nombre}'
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({
                'error': f'Error al crear torneo: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Estado actual del torneo"""
        torneo = self.get_object()
        
        inscripciones = torneo.inscripciones.filter(estado='Confirmada')
        partidos_totales = PartidoTorneo.objects.filter(fase__torneo=torneo).count()
        partidos_jugados = PartidoTorneo.objects.filter(
            fase__torneo=torneo,
            partido__estado='Finalizado'
        ).count()
        partidos_en_curso = PartidoTorneo.objects.filter(
            fase__torneo=torneo,
            partido__estado='En Juego'
        ).count()
        partidos_pendientes = partidos_totales - partidos_jugados - partidos_en_curso
        
        fases = FaseTorneo.objects.filter(torneo=torneo)
        fase_actual = fases.filter(activa=True).first()
        
        # Líderes actuales
        lideres = []
        if torneo.estado in ['En_Juego', 'Finalizado']:
            clasificacion = ClasificacionTorneo.objects.filter(
                torneo=torneo
            ).select_related('inscripcion').order_by('posicion_final')[:3]
            
            for pos in clasificacion:
                lideres.append({
                    'posicion': pos.posicion_final,
                    'equipo': pos.inscripcion.nombre_equipo,
                    'partidos_ganados': pos.partidos_ganados,
                    'partidos_jugados': pos.partidos_jugados,
                    'porcentaje_victorias': round(
                        (pos.partidos_ganados / pos.partidos_jugados * 100) if pos.partidos_jugados > 0 else 0,
                        1
                    )
                })
        
        status_data = {
            'estado': torneo.estado,
            'participantes': inscripciones.count(),
            'fase_actual': fase_actual.nombre if fase_actual else None,
            'partidos_totales': partidos_totales,
            'partidos_jugados': partidos_jugados,
            'partidos_en_curso': partidos_en_curso,
            'partidos_pendientes': partidos_pendientes,
            'total_fases': fases.count(),
            'fases_completadas': fases.filter(completada=True).count(),
            'lideres': lideres
        }
        
        serializer = TorneoStatusSerializer(status_data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def inscripciones(self, request, pk=None):
        """Obtener inscripciones del torneo"""
        torneo = self.get_object()
        inscripciones = torneo.inscripciones.select_related(
            'jugador1__user', 'jugador2__user'
        ).all()
        
        # Filtros opcionales
        estado = request.query_params.get('estado')
        if estado:
            inscripciones = inscripciones.filter(estado=estado)
        
        serializer = InscripcionListSerializer(inscripciones, many=True)
        return Response({
            'torneo': {
                'id': str(torneo.id),
                'nombre': torneo.nombre,
                'estado': torneo.estado,
                'modalidad': torneo.modalidad
            },
            'inscripciones': serializer.data,
            'total': inscripciones.count(),
            'max_participantes': torneo.max_participantes,
            'espacios_disponibles': max(0, torneo.max_participantes - inscripciones.filter(estado='Confirmada').count())
        })
    
    @action(detail=True, methods=['post'])
    def inscribir(self, request, pk=None):
        """Inscribir jugadores al torneo"""
        torneo = self.get_object()
        
        # Agregar torneo al contexto
        data = request.data.copy()
        data['torneo'] = torneo.id
        
        serializer = InscripcionCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                inscripcion = serializer.save()
                
                return Response({
                    'inscripcion': InscripcionDetailSerializer(inscripcion).data,
                    'message': f'Inscripción exitosa: {inscripcion.nombre_equipo}',
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({
                'error': f'Error al inscribir: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def fases(self, request, pk=None):
        """Obtener fases del torneo"""
        torneo = self.get_object()
        fases = torneo.fases.prefetch_related('partidos__partido').order_by('orden')
        
        serializer = FaseTorneoSerializer(fases, many=True)
        return Response({
            'torneo': torneo.nombre,
            'fases': serializer.data,
            'total_fases': fases.count()
        })
    
    @action(detail=True, methods=['get'])
    def grupos(self, request, pk=None):
        """Obtener grupos del torneo"""
        torneo = self.get_object()
        
        if torneo.tipo != 'Grupos':
            return Response({
                'error': 'Este torneo no maneja grupos'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        grupos = torneo.grupos.prefetch_related('inscripciones').all()
        
        serializer = GrupoTorneoSerializer(grupos, many=True)
        return Response({
            'torneo': torneo.nombre,
            'grupos': serializer.data,
            'total_grupos': grupos.count()
        })
    
    @action(detail=True, methods=['get'])
    def partidos(self, request, pk=None):
        """Obtener partidos del torneo"""
        torneo = self.get_object()
        partidos = PartidoTorneo.objects.filter(
            fase__torneo=torneo
        ).select_related(
            'fase', 'grupo', 'inscripcion_equipo1', 'inscripcion_equipo2',
            'cancha_asignada', 'partido'
        ).order_by('fase__orden', 'orden_en_fase')
        
        # Filtros opcionales
        fase_id = request.query_params.get('fase')
        grupo_id = request.query_params.get('grupo')
        estado = request.query_params.get('estado')
        
        if fase_id:
            partidos = partidos.filter(fase__id=fase_id)
        if grupo_id:
            partidos = partidos.filter(grupo__id=grupo_id)
        if estado:
            if estado == 'programado':
                partidos = partidos.filter(partido__isnull=True)
            else:
                partidos = partidos.filter(partido__estado=estado)
        
        serializer = PartidoTorneoListSerializer(partidos, many=True)
        return Response({
            'torneo': torneo.nombre,
            'partidos': serializer.data,
            'total': partidos.count()
        })
    
    @action(detail=True, methods=['get'])
    def ranking(self, request, pk=None):
        """Obtener ranking/clasificación del torneo"""
        torneo = self.get_object()
        
        clasificacion = ClasificacionTorneo.objects.filter(
            torneo=torneo
        ).select_related('inscripcion').order_by('posicion_final')
        
        if not clasificacion.exists():
            # Si no hay clasificación formal, calcular temporal
            inscripciones = torneo.inscripciones.filter(estado='Confirmada')
            ranking_temporal = []
            
            for inscripcion in inscripciones:
                # Calcular estadísticas básicas
                partidos_torneo = PartidoTorneo.objects.filter(
                    Q(inscripcion_equipo1=inscripcion) | Q(inscripcion_equipo2=inscripcion),
                    fase__torneo=torneo,
                    partido__estado='Finalizado'
                )
                
                ganados = sum(1 for p in partidos_torneo if p.get_ganador() == inscripcion)
                jugados = partidos_torneo.count()
                
                ranking_temporal.append({
                    'inscripcion': inscripcion,
                    'partidos_jugados': jugados,
                    'partidos_ganados': ganados,
                    'partidos_perdidos': jugados - ganados,
                    'porcentaje_victorias': round((ganados / jugados * 100) if jugados > 0 else 0, 1)
                })
            
            # Ordenar por porcentaje de victorias
            ranking_temporal.sort(key=lambda x: x['porcentaje_victorias'], reverse=True)
            
            return Response({
                'torneo': torneo.nombre,
                'tipo_ranking': 'temporal',
                'ranking': [
                    {
                        'posicion': idx + 1,
                        'equipo': item['inscripcion'].nombre_equipo,
                        'jugador1': item['inscripcion'].jugador1.nombre_completo,
                        'jugador2': item['inscripcion'].jugador2.nombre_completo if item['inscripcion'].jugador2 else None,
                        'partidos_jugados': item['partidos_jugados'],
                        'partidos_ganados': item['partidos_ganados'],
                        'partidos_perdidos': item['partidos_perdidos'],
                        'porcentaje_victorias': item['porcentaje_victorias']
                    }
                    for idx, item in enumerate(ranking_temporal)
                ]
            })
        
        # Ranking oficial
        serializer = ClasificacionSerializer(clasificacion, many=True)
        return Response({
            'torneo': torneo.nombre,
            'tipo_ranking': 'oficial',
            'ranking': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def generar_sorteo(self, request, pk=None):
        """Generar sorteo del torneo"""
        torneo = self.get_object()
        
        serializer = GenerarSorteoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        if torneo.estado != 'Inscripcion':
            return Response({
                'error': 'Solo se puede generar sorteo en estado de inscripción'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not torneo.puede_iniciar:
            return Response({
                'error': f'No se puede iniciar. Mínimo {torneo.min_participantes} participantes requeridos'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                # Lógica de sorteo según tipo de torneo
                if torneo.tipo == 'Eliminacion':
                    self._generar_sorteo_eliminacion(torneo)
                elif torneo.tipo == 'Ranking':
                    self._generar_sorteo_ranking(torneo)
                elif torneo.tipo == 'Grupos':
                    self._generar_sorteo_grupos(torneo)
                
                torneo.estado = 'Sorteo_Realizado'
                torneo.save()
                
                return Response({
                    'message': 'Sorteo generado exitosamente',
                    'torneo': TorneoDetailSerializer(torneo).data
                })
                
        except Exception as e:
            return Response({
                'error': f'Error al generar sorteo: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def _generar_sorteo_eliminacion(self, torneo):
        """Generar sorteo para eliminación directa"""
        import random
        
        inscripciones = list(torneo.inscripciones.filter(estado='Confirmada'))
        random.shuffle(inscripciones)
        
        # Crear fase inicial
        fase_inicial = FaseTorneo.objects.create(
            torneo=torneo,
            tipo='Eliminacion',
            nombre='Primera Ronda',
            orden=1,
            activa=True
        )
        
        # Crear partidos
        for i in range(0, len(inscripciones), 2):
            if i + 1 < len(inscripciones):
                PartidoTorneo.objects.create(
                    fase=fase_inicial,
                    inscripcion_equipo1=inscripciones[i],
                    inscripcion_equipo2=inscripciones[i + 1],
                    tipo='Eliminacion',
                    orden_en_fase=i // 2 + 1
                )
    
    def _generar_sorteo_ranking(self, torneo):
        """Generar sorteo para ranking/liga"""
        inscripciones = list(torneo.inscripciones.filter(estado='Confirmada'))
        
        # Crear fase única
        fase_liga = FaseTorneo.objects.create(
            torneo=torneo,
            tipo='Liga',
            nombre='Liga General',
            orden=1,
            activa=True
        )
        
        # Crear todos los partidos posibles
        orden = 1
        for i, inscripcion1 in enumerate(inscripciones):
            for inscripcion2 in inscripciones[i + 1:]:
                PartidoTorneo.objects.create(
                    fase=fase_liga,
                    inscripcion_equipo1=inscripcion1,
                    inscripcion_equipo2=inscripcion2,
                    tipo='Liga',
                    orden_en_fase=orden
                )
                orden += 1
    
    def _generar_sorteo_grupos(self, torneo):
        """Generar sorteo para grupos"""
        import random
        
        inscripciones = list(torneo.inscripciones.filter(estado='Confirmada'))
        random.shuffle(inscripciones)
        
        num_grupos = torneo.numero_grupos
        equipos_por_grupo = len(inscripciones) // num_grupos
        
        # Crear grupos
        grupos = []
        for i in range(num_grupos):
            grupo = GrupoTorneo.objects.create(
                torneo=torneo,
                nombre=f'Grupo {chr(65 + i)}'  # A, B, C, etc.
            )
            grupos.append(grupo)
        
        # Distribuir equipos en grupos
        for i, inscripcion in enumerate(inscripciones):
            grupo_idx = i % num_grupos
            grupos[grupo_idx].inscripciones.add(inscripcion)
        
        # Crear fase de grupos
        fase_grupos = FaseTorneo.objects.create(
            torneo=torneo,
            tipo='Grupos',
            nombre='Fase de Grupos',
            orden=1,
            activa=True
        )
        
        # Crear partidos dentro de cada grupo
        for grupo in grupos:
            inscripciones_grupo = list(grupo.inscripciones.all())
            orden = 1
            
            for i, inscripcion1 in enumerate(inscripciones_grupo):
                for inscripcion2 in inscripciones_grupo[i + 1:]:
                    PartidoTorneo.objects.create(
                        fase=fase_grupos,
                        grupo=grupo,
                        inscripcion_equipo1=inscripcion1,
                        inscripcion_equipo2=inscripcion2,
                        tipo='Grupos',
                        orden_en_fase=orden
                    )
                    orden += 1
    
    @action(detail=True, methods=['post'])
    def programar_partidos(self, request, pk=None):
        """Programar partidos automáticamente"""
        torneo = self.get_object()
        
        serializer = ProgramarPartidosSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        if torneo.estado not in ['Sorteo_Realizado', 'En_Juego']:
            return Response({
                'error': 'Solo se pueden programar partidos después del sorteo'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                fecha_inicio = serializer.validated_data['fecha_inicio']
                canchas = serializer.validated_data['canchas_ids']
                partidos_por_dia = serializer.validated_data['partidos_por_dia']
                
                # Obtener partidos sin programar
                partidos_sin_programar = PartidoTorneo.objects.filter(
                    fase__torneo=torneo,
                    fecha_programada__isnull=True
                ).order_by('fase__orden', 'orden_en_fase')
                
                fecha_actual = fecha_inicio
                partidos_programados = 0
                cancha_idx = 0
                
                for partido in partidos_sin_programar:
                    # Asignar cancha
                    partido.cancha_asignada = canchas[cancha_idx % len(canchas)]
                    partido.fecha_programada = fecha_actual
                    partido.save()
                    
                    partidos_programados += 1
                    cancha_idx += 1
                    
                    # Avanzar al siguiente día si se alcanzó el límite
                    if partidos_programados % partidos_por_dia == 0:
                        fecha_actual += timedelta(days=1)
                
                return Response({
                    'message': f'{partidos_programados} partidos programados exitosamente',
                    'fecha_inicio': fecha_inicio,
                    'fecha_estimada_fin': fecha_actual,
                    'canchas_utilizadas': len(canchas)
                })
                
        except Exception as e:
            return Response({
                'error': f'Error al programar partidos: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def iniciar_torneo(self, request, pk=None):
        """Iniciar torneo"""
        torneo = self.get_object()
        
        if torneo.estado != 'Sorteo_Realizado':
            return Response({
                'error': 'El torneo debe tener el sorteo realizado para iniciarse'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            torneo.estado = 'En_Juego'
            torneo.save()
            
            return Response({
                'message': f'Torneo {torneo.nombre} iniciado exitosamente',
                'torneo': TorneoDetailSerializer(torneo).data
            })
            
        except Exception as e:
            return Response({
                'error': f'Error al iniciar torneo: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def finalizar_torneo(self, request, pk=None):
        """Finalizar torneo y generar clasificación"""
        torneo = self.get_object()
        
        if torneo.estado != 'En_Juego':
            return Response({
                'error': 'Solo se pueden finalizar torneos en juego'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                # Generar clasificación final
                self._generar_clasificacion_final(torneo)
                
                torneo.estado = 'Finalizado'
                torneo.save()
                
                return Response({
                    'message': f'Torneo {torneo.nombre} finalizado exitosamente',
                    'torneo': TorneoDetailSerializer(torneo).data
                })
                
        except Exception as e:
            return Response({
                'error': f'Error al finalizar torneo: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def _generar_clasificacion_final(self, torneo):
        """Generar clasificación final del torneo"""
        inscripciones = torneo.inscripciones.filter(estado='Confirmada')
        
        for inscripcion in inscripciones:
            # Calcular estadísticas
            partidos_torneo = PartidoTorneo.objects.filter(
                Q(inscripcion_equipo1=inscripcion) | Q(inscripcion_equipo2=inscripcion),
                fase__torneo=torneo,
                partido__estado='Finalizado'
            )
            
            partidos_jugados = partidos_torneo.count()
            partidos_ganados = sum(1 for p in partidos_torneo if p.get_ganador() == inscripcion)
            partidos_perdidos = partidos_jugados - partidos_ganados
            
            # Crear o actualizar clasificación
            ClasificacionTorneo.objects.update_or_create(
                torneo=torneo,
                inscripcion=inscripcion,
                defaults={
                    'partidos_jugados': partidos_jugados,
                    'partidos_ganados': partidos_ganados,
                    'partidos_perdidos': partidos_perdidos,
                    'posicion_final': 0  # Se calculará después
                }
            )
        
        # Ordenar y asignar posiciones
        clasificaciones = ClasificacionTorneo.objects.filter(
            torneo=torneo
        ).order_by('-partidos_ganados', '-partidos_jugados')
        
        for idx, clasificacion in enumerate(clasificaciones):
            clasificacion.posicion_final = idx + 1
            clasificacion.save()
    
    @action(detail=False, methods=['get'])
    def disponibles(self, request):
        """Torneos disponibles para inscripción"""
        torneos = self.queryset.filter(
            estado='Inscripcion',
            activo=True,
            fecha_inicio__gte=timezone.now()
        )
        
        serializer = TorneoListSerializer(torneos, many=True)
        return Response({
            'torneos_disponibles': serializer.data,
            'total': torneos.count()
        })
    
    @action(detail=False, methods=['get'])
    def activos(self, request):
        """Torneos activos (en juego)"""
        torneos = self.queryset.filter(estado='En_Juego')
        
        serializer = TorneoListSerializer(torneos, many=True)
        return Response({
            'torneos_activos': serializer.data,
            'total': torneos.count()
        })
    
    @action(detail=False, methods=['get'])
    def finalizados(self, request):
        """Torneos finalizados"""
        torneos = self.queryset.filter(estado='Finalizado').order_by('-fecha_fin')
        
        # Paginación
        page = self.paginate_queryset(torneos)
        if page is not None:
            serializer = TorneoListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = TorneoListSerializer(torneos, many=True)
        return Response({
            'torneos_finalizados': serializer.data,
            'total': torneos.count()
        })


class InscripcionViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de inscripciones"""
    
    queryset = InscripcionTorneo.objects.select_related(
        'torneo', 'jugador1__user', 'jugador2__user'
    ).all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['estado', 'pagado', 'torneo']
    search_fields = ['jugador1__user__first_name', 'jugador2__user__first_name']
    ordering_fields = ['fecha_inscripcion', 'ranking_inicial']
    ordering = ['-fecha_inscripcion']
    
    def get_serializer_class(self):
        """Seleccionar serializer según acción"""
        if self.action == 'create':
            return InscripcionCreateSerializer
        elif self.action == 'list':
            return InscripcionListSerializer
        return InscripcionDetailSerializer
    
    @action(detail=True, methods=['post'])
    def confirmar_pago(self, request, pk=None):
        """Confirmar pago de inscripción"""
        inscripcion = self.get_object()
        
        monto = request.data.get('monto_pagado')
        if not monto:
            return Response({
                'error': 'Debe especificar el monto pagado'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        inscripcion.pagado = True
        inscripcion.monto_pagado = monto
        inscripcion.estado = 'Confirmada'
        inscripcion.save()
        
        return Response({
            'message': 'Pago confirmado exitosamente',
            'inscripcion': InscripcionDetailSerializer(inscripcion).data
        })
    
    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        """Cancelar inscripción"""
        inscripcion = self.get_object()
        motivo = request.data.get('motivo', '')
        
        if inscripcion.torneo.estado not in ['Inscripcion', 'Sorteo_Realizado']:
            return Response({
                'error': 'No se puede cancelar inscripción en torneo iniciado'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        inscripcion.estado = 'Cancelada'
        if motivo:
            inscripcion.notas += f"\nCancelado: {motivo}"
        inscripcion.save()
        
        return Response({
            'message': 'Inscripción cancelada exitosamente',
            'inscripcion': InscripcionDetailSerializer(inscripcion).data
        })


class PartidoTorneoViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de partidos de torneo"""
    
    queryset = PartidoTorneo.objects.select_related(
        'fase__torneo', 'grupo', 'inscripcion_equipo1', 'inscripcion_equipo2',
        'cancha_asignada', 'partido'
    ).all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['fase__torneo', 'fase', 'grupo', 'tipo']
    ordering_fields = ['fecha_programada', 'orden_en_fase']
    ordering = ['fecha_programada', 'orden_en_fase']
    
    def get_serializer_class(self):
        """Seleccionar serializer según acción"""
        if self.action in ['update', 'partial_update']:
            return PartidoTorneoUpdateSerializer
        elif self.action == 'list':
            return PartidoTorneoListSerializer
        return PartidoTorneoDetailSerializer
    
    @action(detail=True, methods=['post'])
    def crear_partido(self, request, pk=None):
        """Crear partido real desde partido de torneo"""
        partido_torneo = self.get_object()
        
        if partido_torneo.partido:
            return Response({
                'error': 'El partido ya fue creado'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                from apps.scoring.models import Partido
                
                # Crear partido real
                partido = Partido.objects.create(
                    modalidad=partido_torneo.fase.torneo.modalidad,
                    cancha=partido_torneo.cancha_asignada,
                    jugador1_equipo1=partido_torneo.inscripcion_equipo1.jugador1,
                    jugador2_equipo1=partido_torneo.inscripcion_equipo1.jugador2,
                    jugador1_equipo2=partido_torneo.inscripcion_equipo2.jugador1,
                    jugador2_equipo2=partido_torneo.inscripcion_equipo2.jugador2,
                    tipo='Torneo',
                    sets_para_ganar=partido_torneo.fase.torneo.sets_para_ganar,
                    juegos_para_ganar_set=partido_torneo.fase.torneo.juegos_para_ganar_set
                )
                
                partido_torneo.partido = partido
                partido_torneo.save()
                
                return Response({
                    'message': 'Partido creado exitosamente',
                    'partido_torneo': PartidoTorneoDetailSerializer(partido_torneo).data
                })
                
        except Exception as e:
            return Response({
                'error': f'Error al crear partido: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)