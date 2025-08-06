from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import transaction
from .models import Jugador, crear_jugador_registrado, generar_username_unico


class UserSerializer(serializers.ModelSerializer):
    """Serializer para modelo User de Django"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'is_active']
        read_only_fields = ['id', 'date_joined']


class JugadorSerializer(serializers.ModelSerializer):
    """Serializer principal para Jugador con datos del usuario"""
    
    # Campos del usuario relacionado
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    
    # Propiedades calculadas
    nombre_completo = serializers.CharField(read_only=True)
    es_invitado = serializers.BooleanField(read_only=True)
    es_registrado = serializers.BooleanField(read_only=True)
    email_efectivo = serializers.CharField(read_only=True)
    
    # Estadísticas básicas
    estadisticas = serializers.SerializerMethodField()
    
    class Meta:
        model = Jugador
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'edad', 'sexo', 'telefono', 'activo',
            'fecha_creacion', 'fecha_actualizacion',
            'nombre_completo', 'es_invitado', 'es_registrado', 'email_efectivo',
            'estadisticas'
        ]
        read_only_fields = ['id', 'fecha_creacion', 'fecha_actualizacion']
    
    def get_estadisticas(self, obj):
        """Obtener estadísticas básicas del jugador"""
        try:
            stats = obj.estadisticas
            return {
                'partidos_jugados': stats.partidos_jugados,
                'partidos_ganados': stats.partidos_ganados,
                'porcentaje_victorias': stats.porcentaje_victorias
            }
        except:
            return {
                'partidos_jugados': 0,
                'partidos_ganados': 0,
                'porcentaje_victorias': 0
            }


class JugadorCreateSerializer(serializers.Serializer):
    """Serializer para crear jugador registrado completo con usuario"""
    
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    
    # Campos opcionales del jugador
    edad = serializers.IntegerField(required=False, min_value=8, max_value=120)
    sexo = serializers.ChoiceField(choices=[('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')], required=False)
    telefono = serializers.CharField(max_length=20, required=False)
    
    def validate_username(self, value):
        """Validar que el username sea único"""
        username_unico = generar_username_unico(value)
        if username_unico != value:
            raise serializers.ValidationError(f"Username no disponible. Sugerencia: {username_unico}")
        return value
    
    def validate_email(self, value):
        """Validar que el email sea único"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este email ya está registrado.")
        return value
    
    def create(self, validated_data):
        """Crear jugador registrado usando la función del modelo"""
        password = validated_data.pop('password')
        username = validated_data.pop('username')
        email = validated_data.pop('email')
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        
        jugador = crear_jugador_registrado(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            **validated_data
        )
        return jugador


class JugadorUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar perfil de jugador"""
    
    # Campos del usuario que se pueden actualizar
    first_name = serializers.CharField(source='user.first_name', max_length=150, required=False)
    last_name = serializers.CharField(source='user.last_name', max_length=150, required=False)
    email = serializers.EmailField(source='user.email', required=False)
    
    class Meta:
        model = Jugador
        fields = ['first_name', 'last_name', 'email', 'edad', 'sexo', 'telefono']
    
    def validate_email(self, value):
        """Validar email único excluyendo el usuario actual"""
        if self.instance and self.instance.user.email != value:
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError("Este email ya está registrado.")
        return value
    
    def update(self, instance, validated_data):
        """Actualizar tanto el usuario como el jugador"""
        user_data = {}
        if 'user' in validated_data:
            user_data = validated_data.pop('user')
        
        # Actualizar campos del usuario
        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        instance.user.save()
        
        # Actualizar campos del jugador
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance


class JugadorListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados de jugadores"""
    
    nombre_completo = serializers.CharField(read_only=True)
    es_invitado = serializers.BooleanField(read_only=True)
    tipo_jugador = serializers.SerializerMethodField()
    
    class Meta:
        model = Jugador
        fields = ['id', 'nombre_completo', 'es_invitado', 'activo', 'edad', 'sexo', 'tipo_jugador']
    
    def get_tipo_jugador(self, obj):
        return 'Invitado' if obj.es_invitado else 'Registrado'


class JugadorInvitadoSerializer(serializers.Serializer):
    """Serializer para obtener o crear jugador invitado"""
    
    nombre = serializers.CharField(max_length=150, required=False)
    apellido = serializers.CharField(max_length=150, required=False)
    
    def create(self, validated_data):
        """Crear jugador invitado temporal"""
        from .models import obtener_jugador_invitado_disponible
        
        # Intentar obtener jugador invitado disponible
        jugador_invitado = obtener_jugador_invitado_disponible()
        
        if jugador_invitado:
            # Actualizar nombre si se proporcionó
            if validated_data.get('nombre'):
                jugador_invitado.user.first_name = validated_data['nombre']
            if validated_data.get('apellido'):
                jugador_invitado.user.last_name = validated_data['apellido']
            jugador_invitado.user.save()
            return jugador_invitado
        
        # Si no hay jugadores invitados disponibles, crear uno nuevo
        import random
        username = f"jugador_invitado_{random.randint(1000, 9999)}"
        user = User.objects.create_user(
            username=username,
            first_name=validated_data.get('nombre', 'Invitado'),
            last_name=validated_data.get('apellido', 'Temporal')
        )
        return user.jugador


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer para cambiar contraseña de jugador"""
    
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    
    def validate_old_password(self, value):
        """Validar contraseña actual"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Contraseña actual incorrecta.")
        return value
    
    def save(self):
        """Cambiar contraseña"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class JugadorEstadisticasSerializer(serializers.Serializer):
    """Serializer para estadísticas detalladas del jugador"""
    
    def to_representation(self, instance):
        """Retornar estadísticas detalladas"""
        try:
            stats = instance.estadisticas
            return {
                'jugador': {
                    'id': instance.id,
                    'nombre_completo': instance.nombre_completo,
                    'es_invitado': instance.es_invitado
                },
                'partidos': {
                    'jugados': stats.partidos_jugados,
                    'ganados': stats.partidos_ganados,
                    'perdidos': stats.partidos_perdidos,
                    'porcentaje_victorias': stats.porcentaje_victorias
                },
                'sets': {
                    'jugados': stats.sets_jugados,
                    'ganados': stats.sets_ganados,
                    'perdidos': stats.sets_perdidos,
                    'porcentaje_sets': stats.porcentaje_sets
                },
                'juegos': {
                    'jugados': stats.juegos_jugados,
                    'ganados': stats.juegos_ganados,
                    'perdidos': stats.juegos_perdidos,
                    'porcentaje_juegos': stats.porcentaje_juegos
                },
                'puntos': {
                    'jugados': stats.puntos_jugados,
                    'ganados': stats.puntos_ganados,
                    'perdidos': stats.puntos_perdidos,
                    'porcentaje_puntos': stats.porcentaje_puntos
                },
                'rachas': {
                    'actual_victorias': stats.racha_actual_victorias,
                    'mejor_racha_victorias': stats.mejor_racha_victorias,
                    'actual_derrotas': stats.racha_actual_derrotas
                },
                'fechas': {
                    'primer_partido': stats.primer_partido,
                    'ultimo_partido': stats.ultimo_partido,
                    'ultima_actualizacion': stats.ultima_actualizacion
                }
            }
        except:
            return {
                'jugador': {
                    'id': instance.id,
                    'nombre_completo': instance.nombre_completo,
                    'es_invitado': instance.es_invitado
                },
                'mensaje': 'Sin estadísticas disponibles'
            }