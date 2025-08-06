# apps/players/authentication.py

from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Jugador
from .serializers_v2 import JugadorSerializer


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Serializer personalizado para JWT que incluye información del jugador"""
    
    username_field = 'email'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'] = self.fields.pop('username')
        self.fields['email'].help_text = 'Email o username del jugador'
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Agregar información personalizada al token
        try:
            jugador = user.jugador
            token['jugador_id'] = str(jugador.id)
            token['nombre'] = jugador.nombre
            token['apellido'] = jugador.apellido
            token['es_registrado'] = jugador.es_registrado
        except Jugador.DoesNotExist:
            token['jugador_id'] = None
            token['nombre'] = user.first_name
            token['apellido'] = user.last_name
            token['es_registrado'] = False
        
        return token
    
    def validate(self, attrs):
        email_or_username = attrs.get('email')
        password = attrs.get('password')
        
        if not email_or_username or not password:
            raise serializers.ValidationError('Email y contraseña son obligatorios')
        
        # Buscar usuario por email o username
        user = User.objects.filter(
            Q(email__iexact=email_or_username) | Q(username=email_or_username)
        ).first()
        
        if not user:
            raise serializers.ValidationError('Usuario no encontrado')
        
        # Autenticar
        user = authenticate(username=user.username, password=password)
        if not user:
            raise serializers.ValidationError('Credenciales inválidas')
        
        # Verificar que tenga jugador asociado
        try:
            jugador = user.jugador
            if not jugador.activo:
                raise serializers.ValidationError('Cuenta de jugador desactivada')
        except Jugador.DoesNotExist:
            raise serializers.ValidationError('No hay jugador asociado a este usuario')
        
        # Usar el username real para la validación padre
        attrs['username'] = user.username
        del attrs['email']
        
        data = super().validate(attrs)
        
        # Agregar información del jugador a la respuesta
        data['jugador'] = JugadorSerializer(jugador).data
        
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    """Vista personalizada para obtener tokens JWT"""
    serializer_class = CustomTokenObtainPairSerializer


class CustomTokenRefreshView(TokenRefreshView):
    """Vista personalizada para refrescar tokens JWT"""
    pass


@api_view(['POST'])
@permission_classes([AllowAny])
def jwt_login(request):
    """
    Login con JWT - alternativa a la vista basada en clase
    Acepta email o username
    """
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
    
    # Verificar jugador
    try:
        jugador = user.jugador
        if not jugador.activo:
            return Response({
                'error': 'Cuenta de jugador desactivada'
            }, status=status.HTTP_403_FORBIDDEN)
    except Jugador.DoesNotExist:
        return Response({
            'error': 'No hay jugador asociado a este usuario'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Generar tokens
    refresh = RefreshToken.for_user(user)
    access = refresh.access_token
    
    # Agregar información personalizada
    access['jugador_id'] = str(jugador.id)
    access['nombre'] = jugador.nombre
    access['apellido'] = jugador.apellido
    access['es_registrado'] = jugador.es_registrado
    
    return Response({
        'access': str(access),
        'refresh': str(refresh),
        'token_type': 'Bearer',
        'expires_in': 86400,  # 24 horas en segundos
        'jugador': JugadorSerializer(jugador).data,
        'message': 'Login exitoso con JWT'
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def jwt_refresh(request):
    """Refrescar token JWT"""
    refresh_token = request.data.get('refresh')
    
    if not refresh_token:
        return Response({
            'error': 'Refresh token es obligatorio'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        refresh = RefreshToken(refresh_token)
        access = refresh.access_token
        
        # Obtener usuario y jugador para agregar info personalizada
        user_id = refresh.payload.get('user_id')
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                jugador = user.jugador
                
                access['jugador_id'] = str(jugador.id)
                access['nombre'] = jugador.nombre
                access['apellido'] = jugador.apellido
                access['es_registrado'] = jugador.es_registrado
            except (User.DoesNotExist, Jugador.DoesNotExist):
                pass
        
        return Response({
            'access': str(access),
            'refresh': str(refresh) if refresh.get('rotate_refresh_tokens') else refresh_token,
            'token_type': 'Bearer',
            'expires_in': 86400
        })
        
    except Exception as e:
        return Response({
            'error': f'Token inválido: {str(e)}'
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
def jwt_logout(request):
    """Logout con JWT - blacklist del refresh token"""
    refresh_token = request.data.get('refresh')
    
    if not refresh_token:
        return Response({
            'error': 'Refresh token es obligatorio para logout'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
        
        return Response({
            'message': 'Logout exitoso - token invalidado'
        })
        
    except Exception as e:
        return Response({
            'error': f'Error al invalidar token: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def jwt_verify(request):
    """Verificar token JWT y obtener información del usuario"""
    if not request.user.is_authenticated:
        return Response({
            'error': 'Token no válido o expirado'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        jugador = request.user.jugador
        return Response({
            'valid': True,
            'user_id': request.user.id,
            'username': request.user.username,
            'jugador': JugadorSerializer(jugador).data,
            'message': 'Token válido'
        })
    except Jugador.DoesNotExist:
        return Response({
            'valid': True,
            'user_id': request.user.id,
            'username': request.user.username,
            'jugador': None,
            'message': 'Token válido pero sin jugador asociado'
        })


# Funciones de utilidad para permisos personalizados

class IsOwnerOrReadOnly(BasePermission):
    """Permiso personalizado para que solo el propietario pueda editar"""
    
    def has_object_permission(self, request, view, obj):
        # Permisos de lectura para cualquier request
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        # Permisos de escritura solo para el propietario
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'jugador'):
            return obj.jugador.user == request.user
        
        return False


class IsJugadorOwner(BasePermission):
    """Permiso para verificar que el usuario es el dueño del jugador"""
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False


def get_user_jugador(user):
    """Función de utilidad para obtener el jugador asociado a un usuario"""
    try:
        return user.jugador
    except Jugador.DoesNotExist:
        return None