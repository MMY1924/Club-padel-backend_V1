# apps/players/permissions.py

from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework import permissions


class IsOwnerOrReadOnly(BasePermission):
    """
    Permiso personalizado para permitir lectura a todos,
    pero escritura solo al propietario del objeto.
    """
    
    def has_object_permission(self, request, view, obj):
        # Permisos de lectura para cualquier request
        if request.method in SAFE_METHODS:
            return True
        
        # Permisos de escritura solo para el propietario
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'jugador') and hasattr(obj.jugador, 'user'):
            return obj.jugador.user == request.user
        
        return False


class IsJugadorOwner(BasePermission):
    """
    Permite acceso solo si el usuario es el propietario del jugador.
    """
    
    def has_object_permission(self, request, view, obj):
        # Para modelos Jugador
        if hasattr(obj, 'user'):
            return obj.user == request.user
        # Para modelos relacionados con Jugador
        elif hasattr(obj, 'jugador') and hasattr(obj.jugador, 'user'):
            return obj.jugador.user == request.user
        
        return False


class IsJugadorOrReadOnly(BasePermission):
    """
    Permite lectura a todos, escritura solo al jugador propietario.
    """
    
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        
        try:
            # Verificar si el usuario tiene un jugador asociado
            jugador = request.user.jugador
            
            # Para objetos Jugador
            if hasattr(obj, 'user'):
                return obj.user == request.user
            # Para objetos relacionados con Jugador
            elif hasattr(obj, 'jugador'):
                return obj.jugador == jugador
            
        except AttributeError:
            pass
        
        return False


class CanManageReservations(BasePermission):
    """
    Permite gestionar reservas solo a jugadores registrados.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        try:
            jugador = request.user.jugador
            return jugador.es_registrado and jugador.activo
        except AttributeError:
            return False
    
    def has_object_permission(self, request, view, obj):
        # Para reservas, solo el creador puede modificar
        if hasattr(obj, 'jugador'):
            return obj.jugador.user == request.user
        return False


class CanJoinTournaments(BasePermission):
    """
    Permite inscribirse en torneos solo a jugadores activos.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        try:
            jugador = request.user.jugador
            return jugador.activo
        except AttributeError:
            return False


class IsAdminOrReadOnly(BasePermission):
    """
    Permite acceso completo a admins, solo lectura a otros.
    """
    
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class IsPlayerActive(BasePermission):
    """
    Verifica que el jugador asociado esté activo.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        try:
            jugador = request.user.jugador
            return jugador.activo
        except AttributeError:
            return False


class CanAccessPlayerStats(BasePermission):
    """
    Permite ver estadísticas: propietario siempre, otros solo si son públicas.
    """
    
    def has_object_permission(self, request, view, obj):
        # Si es el propietario, siempre puede ver
        if hasattr(obj, 'user') and obj.user == request.user:
            return True
        
        # Para otros usuarios, depende de la configuración de privacidad
        # (esto podría expandirse con un campo de privacidad en el modelo)
        return True  # Por ahora, todas las estadísticas son públicas


class DynamicPermission(BasePermission):
    """
    Permiso dinámico basado en la acción del ViewSet.
    """
    
    def has_permission(self, request, view):
        # Permisos por acción
        action_permissions = {
            'list': permissions.AllowAny,
            'retrieve': permissions.AllowAny,
            'create': permissions.IsAuthenticated,
            'update': permissions.IsAuthenticated,
            'partial_update': permissions.IsAuthenticated,
            'destroy': permissions.IsAuthenticated,
        }
        
        permission_class = action_permissions.get(view.action, permissions.IsAuthenticated)
        permission = permission_class()
        
        return permission.has_permission(request, view)


# Funciones de utilidad para verificar permisos

def can_user_modify_jugador(user, jugador):
    """Verifica si un usuario puede modificar un jugador específico"""
    if not user.is_authenticated:
        return False
    
    # El usuario puede modificar su propio jugador
    if hasattr(jugador, 'user') and jugador.user == user:
        return True
    
    # Los staff pueden modificar cualquier jugador
    if user.is_staff:
        return True
    
    return False


def can_user_create_partido(user):
    """Verifica si un usuario puede crear partidos"""
    if not user.is_authenticated:
        return False
    
    try:
        jugador = user.jugador
        return jugador.activo
    except AttributeError:
        return False


def can_user_make_reservations(user):
    """Verifica si un usuario puede hacer reservas"""
    if not user.is_authenticated:
        return False
    
    try:
        jugador = user.jugador
        return jugador.es_registrado and jugador.activo
    except AttributeError:
        return False


def get_user_permissions_summary(user):
    """Obtiene un resumen de permisos del usuario"""
    if not user.is_authenticated:
        return {
            'authenticated': False,
            'can_create_partido': False,
            'can_make_reservations': False,
            'can_join_tournaments': False,
            'is_staff': False
        }
    
    try:
        jugador = user.jugador
        return {
            'authenticated': True,
            'jugador_id': str(jugador.id),
            'jugador_activo': jugador.activo,
            'es_registrado': jugador.es_registrado,
            'can_create_partido': jugador.activo,
            'can_make_reservations': jugador.es_registrado and jugador.activo,
            'can_join_tournaments': jugador.activo,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser
        }
    except AttributeError:
        return {
            'authenticated': True,
            'jugador_id': None,
            'jugador_activo': False,
            'es_registrado': False,
            'can_create_partido': False,
            'can_make_reservations': False,
            'can_join_tournaments': False,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser
        }