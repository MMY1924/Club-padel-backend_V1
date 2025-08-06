from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q, Count, Avg
from django.db import transaction
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from .models import Jugador
from .serializers_v2 import (
    JugadorSerializer, JugadorListSerializer, JugadorCreateSerializer,
    JugadorUpdateSerializer, JugadorInvitadoSerializer, PasswordChangeSerializer,
    JugadorEstadisticasSerializer
)
from .permissions import (
    IsJugadorOwner, IsOwnerOrReadOnly, CanManageReservations,
    get_user_permissions_summary
)


class JugadorViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión completa de jugadores"""
    
    queryset = Jugador.objects.select_related('user').all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['sexo', 'activo', 'es_invitado']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'user__username']
    ordering_fields = ['user__first_name', 'user__last_name', 'edad', 'fecha_creacion']
    ordering = ['user__last_name', 'user__first_name']
    
    def get_serializer_class(self):
        """Seleccionar serializer según la acción"""
        if self.action == 'create':
            return JugadorCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return JugadorUpdateSerializer
        elif self.action == 'list':
            return JugadorListSerializer
        elif self.action == 'estadisticas_detalladas':
            return JugadorEstadisticasSerializer
        return JugadorSerializer
    
    def get_permissions(self):
        """Permisos por acción"""
        if self.action in ['create', 'login']:
            permission_classes = [permissions.AllowAny]
        elif self.action in ['me', 'change_password', 'logout']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def create(self, request, *args, **kwargs):
        """Crear jugador registrado con token automático"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                jugador = serializer.save()
                
                # Crear token automáticamente
                token, created = Token.objects.get_or_create(user=jugador.user)
                
                return Response({
                    'jugador': JugadorSerializer(jugador).data,
                    'token': token.key,
                    'message': f'Jugador registrado exitosamente: {jugador.nombre_completo}',
                    'auto_login': True
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({
                'error': f'Error al crear jugador: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login(self, request):
        """Login con email o username"""
        email_or_username = request.data.get('email') or request.data.get('username')
        password = request.data.get('password')
        
        if not email_or_username or not password:
            return Response({
                'error': 'Email/username y contraseña son obligatorios'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Buscar usuario
        user = User.objects.filter(
            Q(email__iexact=email_or_username) | Q(username=email_or_username)
        ).first()
        
        if not user:
            return Response({
                'error': 'Usuario no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Autenticar
        user = authenticate(username=user.username, password=password)
        if not user:
            return Response({
                'error': 'Credenciales inválidas'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Obtener jugador
        try:
            jugador = user.jugador
        except Jugador.DoesNotExist:
            return Response({
                'error': 'No hay jugador asociado a este usuario'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Crear token
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'token': token.key,
            'jugador': JugadorSerializer(jugador).data,
            'message': 'Login exitoso'
        })
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def logout(self, request):
        """Logout eliminando token"""
        try:
            token = Token.objects.get(user=request.user)
            token.delete()
            return Response({'message': 'Logout exitoso'})
        except Token.DoesNotExist:
            return Response({'message': 'Token no encontrado'})
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """Obtener perfil del usuario actual"""
        try:
            jugador = request.user.jugador
            serializer = JugadorSerializer(jugador)
            return Response(serializer.data)
        except Jugador.DoesNotExist:
            return Response({
                'error': 'Jugador no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['put'], permission_classes=[permissions.IsAuthenticated])
    def update_profile(self, request):
        """Actualizar perfil del usuario actual"""
        try:
            jugador = request.user.jugador
            serializer = JugadorUpdateSerializer(jugador, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            
            return Response({
                'jugador': JugadorSerializer(jugador).data,
                'message': 'Perfil actualizado exitosamente'
            })
            
        except Jugador.DoesNotExist:
            return Response({
                'error': 'Jugador no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def change_password(self, request):
        """Cambiar contraseña del usuario actual"""
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'message': 'Contraseña cambiada exitosamente'
        })
    
    @action(detail=True, methods=['get'])
    def estadisticas_detalladas(self, request, pk=None):
        """Estadísticas detalladas del jugador"""
        jugador = self.get_object()
        serializer = JugadorEstadisticasSerializer(jugador)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def historial_partidos(self, request, pk=None):
        """Historial de partidos del jugador"""
        jugador = self.get_object()
        
        # Filtros opcionales
        modalidad = request.query_params.get('modalidad')
        resultado = request.query_params.get('resultado')
        
        # Obtener historial
        historial_query = jugador.historial.select_related(
            'partido', 'partido__cancha', 'Pareja__user'
        ).all()
        
        if modalidad:
            historial_query = historial_query.filter(partido__modalidad=modalidad)
        
        if resultado == 'ganado':
            historial_query = historial_query.filter(es_ganador=True)
        elif resultado == 'perdido':
            historial_query = historial_query.filter(es_ganador=False)
        
        historial_query = historial_query.order_by('-fecha_partido')
        
        # Paginación
        page = self.paginate_queryset(historial_query)
        if page is not None:
            historial_data = self._build_historial_data(page)
            return self.get_paginated_response(historial_data)
        
        historial_data = self._build_historial_data(historial_query)
        return Response(historial_data)
    
    def _build_historial_data(self, historial_queryset):
        """Construir datos del historial"""
        historial_data = []
        
        for historial in historial_queryset:
            partido = historial.partido
            historial_data.append({
                'id': historial.id,
                'partido_id': str(partido.id),
                'fecha': historial.fecha_partido,
                'modalidad': partido.modalidad,
                'tipo': partido.tipo,
                'cancha': partido.cancha.nombre if partido.cancha else None,
                'equipo_jugador': historial.equipo_jugador,
                'resultado': 'Ganado' if historial.es_ganador else 'Perdido',
                'equipo1': partido.equipo1_nombre,
                'equipo2': partido.equipo2_nombre,
                'compañero': historial.Pareja.nombre_completo if historial.Pareja else None,
                'estado_partido': partido.estado,
                'sets_ganados': historial.sets_ganados,
                'sets_perdidos': historial.sets_perdidos,
                'juegos_ganados': historial.juegos_ganados,
                'juegos_perdidos': historial.juegos_perdidos,
                'puntos_ganados': historial.puntos_ganados,
                'puntos_perdidos': historial.puntos_perdidos,
                'duracion': historial.duracion_partido
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
    
    @action(detail=False, methods=['get'])
    def activos(self, request):
        """Obtener solo jugadores activos"""
        jugadores = self.queryset.filter(activo=True)
        serializer = JugadorListSerializer(jugadores, many=True)
        return Response({
            'jugadores': serializer.data,
            'total': jugadores.count()
        })
    
    @action(detail=False, methods=['get'])
    def registrados(self, request):
        """Obtener solo jugadores registrados"""
        jugadores = self.queryset.filter(es_registrado=True)
        serializer = JugadorListSerializer(jugadores, many=True)
        return Response({
            'jugadores': serializer.data,
            'total': jugadores.count()
        })
    
    @action(detail=False, methods=['get'])
    def invitados(self, request):
        """Obtener solo jugadores invitados"""
        jugadores = self.queryset.filter(es_invitado=True)
        serializer = JugadorListSerializer(jugadores, many=True)
        return Response({
            'jugadores': serializer.data,
            'total': jugadores.count()
        })
    
    @action(detail=False, methods=['post'])
    def crear_invitado(self, request):
        """Crear jugador invitado rápido"""
        serializer = JugadorInvitadoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        jugador = serializer.save()
        
        return Response({
            'jugador': JugadorSerializer(jugador).data,
            'message': f'Jugador invitado creado: {jugador.nombre_completo}'
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def disponibles_para_partido(self, request):
        """Jugadores disponibles para crear partido"""
        # Filtros
        excluir_ids = request.query_params.getlist('excluir[]')
        modalidad = request.query_params.get('modalidad', 'Dobles')
        solo_registrados = request.query_params.get('solo_registrados', 'false').lower() == 'true'
        
        jugadores = self.queryset.filter(activo=True)
        
        if excluir_ids:
            jugadores = jugadores.exclude(id__in=excluir_ids)
        
        if solo_registrados:
            jugadores = jugadores.filter(es_registrado=True)
        
        # Agregar estadísticas básicas
        jugadores_data = []
        for jugador in jugadores:
            try:
                stats = jugador.estadisticas
                partidos_jugados = stats.partidos_jugados
                porcentaje_victorias = stats.porcentaje_victorias
            except:
                partidos_jugados = 0
                porcentaje_victorias = 0
            
            jugadores_data.append({
                'id': str(jugador.id),
                'nombre_completo': jugador.nombre_completo,
                'email': jugador.email_efectivo,
                'edad': jugador.edad,
                'sexo': jugador.get_sexo_display() if jugador.sexo else None,
                'partidos_jugados': partidos_jugados,
                'porcentaje_victorias': porcentaje_victorias,
                'tipo': 'Registrado' if jugador.es_registrado else 'Invitado',
                'puede_reservar': jugador.puede_hacer_reservas()
            })
        
        # Ordenar por experiencia
        jugadores_data.sort(key=lambda x: x['partidos_jugados'], reverse=True)
        
        return Response({
            'modalidad': modalidad,
            'jugadores_disponibles': jugadores_data,
            'total': len(jugadores_data),
            'jugadores_requeridos': 2 if modalidad == 'Individual' else 4
        })
    
    @action(detail=False, methods=['get'])
    def estadisticas_generales(self, request):
        """Estadísticas generales de todos los jugadores"""
        total_jugadores = self.queryset.count()
        jugadores_activos = self.queryset.filter(activo=True).count()
        jugadores_registrados = self.queryset.filter(es_registrado=True).count()
        jugadores_invitados = self.queryset.filter(es_invitado=True).count()
        
        # Distribución por sexo
        por_sexo = self.queryset.values('sexo').annotate(
            total=Count('id')
        ).order_by('sexo')
        
        # Edad promedio
        edad_promedio = self.queryset.aggregate(
            promedio=Avg('edad')
        )['promedio'] or 0
        
        # Jugadores más activos
        from .models import EstadisticasJugador
        jugadores_activos_stats = EstadisticasJugador.objects.select_related(
            'jugador__user'
        ).filter(
            partidos_jugados__gt=0
        ).order_by('-partidos_jugados')[:10]
        
        return Response({
            'resumen': {
                'total_jugadores': total_jugadores,
                'activos': jugadores_activos,
                'inactivos': total_jugadores - jugadores_activos,
                'registrados': jugadores_registrados,
                'invitados': jugadores_invitados,
                'edad_promedio': round(edad_promedio, 1)
            },
            'distribucion_sexo': [
                {
                    'sexo': item['sexo'] or 'No especificado',
                    'total': item['total'],
                    'porcentaje': round((item['total'] / total_jugadores * 100), 2) if total_jugadores > 0 else 0
                }
                for item in por_sexo
            ],
            'jugadores_mas_activos': [
                {
                    'nombre_completo': stats.jugador.nombre_completo,
                    'partidos_jugados': stats.partidos_jugados,
                    'partidos_ganados': stats.partidos_ganados,
                    'porcentaje_victorias': stats.porcentaje_victorias,
                    'tipo': 'Registrado' if stats.jugador.es_registrado else 'Invitado'
                }
                for stats in jugadores_activos_stats
            ]
        })
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_permissions(self, request):
        """Obtener permisos del usuario actual"""
        permissions_summary = get_user_permissions_summary(request.user)
        return Response({
            'user_permissions': permissions_summary,
            'available_actions': {
                'can_create_jugadores': True,
                'can_update_own_profile': permissions_summary['authenticated'],
                'can_create_partidos': permissions_summary['can_create_partido'],
                'can_make_reservations': permissions_summary['can_make_reservations'],
                'can_join_tournaments': permissions_summary['can_join_tournaments'],
                'can_access_admin': permissions_summary['is_staff']
            }
        })