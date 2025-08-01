# apps/players/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import transaction
from .models import Jugador


class JugadorSerializer(serializers.ModelSerializer):
    """Serializer completo para Jugador"""
    nombre_completo = serializers.ReadOnlyField()
    email_efectivo = serializers.ReadOnlyField()
    partidos_jugados = serializers.SerializerMethodField()
    partidos_ganados = serializers.SerializerMethodField()
    username = serializers.CharField(source='user.username', read_only=True)
    es_registrado = serializers.SerializerMethodField()

    class Meta:
        model = Jugador
        fields = [
            'id', 'nombre', 'apellido', 'nombre_completo', 'email', 'email_efectivo',
            'edad', 'sexo', 'telefono', 'nivel_habilidad', 'es_invitado',
            'activo', 'fecha_creacion', 'username', 'es_registrado',
            'partidos_jugados', 'partidos_ganados'
        ]
        read_only_fields = ['id', 'fecha_creacion']

    def get_partidos_jugados(self, obj):
        return obj.historial_partidos.count() if hasattr(obj, 'historial_partidos') else 0

    def get_partidos_ganados(self, obj):
        return obj.historial_partidos.filter(es_ganador=True).count() if hasattr(obj, 'historial_partidos') else 0

    def get_es_registrado(self, obj):
        return obj.es_registrado()


class JugadorListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados"""
    nombre_completo = serializers.ReadOnlyField()
    email_efectivo = serializers.ReadOnlyField()
    username = serializers.CharField(source='user.username', read_only=True)
    tipo_jugador = serializers.SerializerMethodField()

    class Meta:
        model = Jugador
        fields = [
            'id', 'nombre_completo', 'email_efectivo', 'edad', 'sexo',
            'nivel_habilidad', 'activo', 'username', 'tipo_jugador'
        ]

    def get_tipo_jugador(self, obj):
        return 'Invitado' if obj.es_invitado else 'Registrado'


class JugadorCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear jugadores - maneja ambos tipos"""
    password = serializers.CharField(
        write_only=True,
        required=False,
        help_text="Contraseña para jugadores registrados (opcional, por defecto: padel123)"
    )
    tipo_jugador = serializers.ChoiceField(
        choices=[('registrado', 'Registrado'), ('invitado', 'Invitado')],
        write_only=True,
        default='registrado',
        help_text="Tipo de jugador a crear"
    )

    class Meta:
        model = Jugador
        fields = [
            'nombre', 'apellido', 'email', 'edad', 'sexo', 'telefono',
            'nivel_habilidad', 'password', 'tipo_jugador'
        ]

    def validate_email(self, value):
        """Validar email según el tipo de jugador"""
        tipo_jugador = self.initial_data.get('tipo_jugador', 'registrado')

        if not value and tipo_jugador == 'registrado':
            raise serializers.ValidationError("El email es obligatorio para jugadores registrados")

        if value:
            # Verificar que no exista en jugadores
            if Jugador.objects.filter(email__iexact=value).exists():
                raise serializers.ValidationError("Ya existe un jugador con este email")

            # Verificar que no exista en usuarios (solo para registrados)
            if tipo_jugador == 'registrado' and User.objects.filter(email__iexact=value).exists():
                raise serializers.ValidationError("Ya existe un usuario con este email")

        return value.lower() if value else value

    def validate(self, data):
        """Validaciones generales"""
        tipo_jugador = data.get('tipo_jugador', 'registrado')

        # Validaciones para jugadores registrados
        if tipo_jugador == 'registrado':
            if not data.get('nombre') or not data.get('apellido'):
                raise serializers.ValidationError("Nombre y apellido son obligatorios para jugadores registrados")
            if not data.get('email'):
                raise serializers.ValidationError("Email es obligatorio para jugadores registrados")

        # Validaciones para jugadores invitados
        elif tipo_jugador == 'invitado':
            if not data.get('nombre') or not data.get('apellido'):
                raise serializers.ValidationError("Nombre y apellido son obligatorios para jugadores invitados")

        # Validar edad
        if data.get('edad') and data['edad'] < 8:
            raise serializers.ValidationError("La edad mínima es 8 años")

        return data

    def create(self, validated_data):
        """Crear jugador según el tipo especificado"""
        password = validated_data.pop('password', None)
        tipo_jugador = validated_data.pop('tipo_jugador', 'registrado')

        with transaction.atomic():
            if tipo_jugador == 'registrado':
                # Crear jugador registrado con User automático
                return self._crear_jugador_registrado(validated_data, password)
            else:
                # Crear jugador invitado sin User
                return self._crear_jugador_invitado(validated_data)

    def _crear_jugador_registrado(self, validated_data, password=None):
        """Crear jugador registrado con User automático"""
        # Generar username único
        username = self._generate_username(
            validated_data['nombre'],
            validated_data['apellido']
        )

        # Crear usuario de Django
        user = User.objects.create_user(
            username=username,
            email=validated_data['email'],
            first_name=validated_data['nombre'],
            last_name=validated_data['apellido'],
            password=password if password else 'padel123'
        )

        # Crear jugador asociado al usuario
        jugador = Jugador.objects.create(
            user=user,
            es_invitado=False,  # Jugador registrado
            **validated_data
        )

        return jugador

    def _crear_jugador_invitado(self, validated_data):
        """Crear jugador invitado sin User"""
        jugador = Jugador.objects.create(
            user=None,  # Sin usuario asociado
            es_invitado=True,  # Jugador invitado
            **validated_data
        )

        return jugador

    def _generate_username(self, nombre, apellido):
        """Generar username único basado en nombre y apellido"""
        import unicodedata
        import re

        # Normalizar y limpiar nombre y apellido
        def clean_string(s):
            # Remover acentos
            s = unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('ascii')
            # Solo letras y números
            s = re.sub(r'[^a-zA-Z0-9]', '', s)
            return s.lower()

        nombre_clean = clean_string(nombre)
        apellido_clean = clean_string(apellido)

        base_username = f"{nombre_clean}.{apellido_clean}"
        username = base_username
        counter = 1

        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        return username

    def to_representation(self, instance):
        """Usar JugadorSerializer para la respuesta"""
        return JugadorSerializer(instance).data


class JugadorUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar jugadores (sin cambiar tipo)"""

    class Meta:
        model = Jugador
        fields = [
            'nombre', 'apellido', 'email', 'edad', 'sexo', 'telefono',
            'nivel_habilidad', 'activo'
        ]

    def validate_email(self, value):
        """Validar email en actualización"""
        if value:
            # Verificar que no exista en otros jugadores
            existing = Jugador.objects.filter(email__iexact=value).exclude(id=self.instance.id)
            if existing.exists():
                raise serializers.ValidationError("Ya existe un jugador con este email")

        return value.lower() if value else value

    def update(self, instance, validated_data):
        """Actualizar jugador y su User asociado si existe"""
        with transaction.atomic():
            # Si tiene user asociado, actualizar también
            if instance.user and not instance.es_invitado:
                user = instance.user
                if 'nombre' in validated_data:
                    user.first_name = validated_data['nombre']
                if 'apellido' in validated_data:
                    user.last_name = validated_data['apellido']
                if 'email' in validated_data:
                    user.email = validated_data['email']
                user.save()

            # Actualizar jugador
            return super().update(instance, validated_data)


class ConvertirJugadorSerializer(serializers.Serializer):
    """Serializer para convertir jugador invitado a registrado"""
    password = serializers.CharField(
        required=False,
        help_text="Contraseña para la cuenta (opcional, por defecto: padel123)"
    )

    def validate(self, data):
        jugador = self.context.get('jugador')
        if not jugador:
            raise serializers.ValidationError("Jugador no encontrado")

        if not jugador.es_invitado:
            raise serializers.ValidationError("Este jugador ya está registrado")

        if not jugador.email:
            raise serializers.ValidationError("El jugador debe tener un email para convertirse en registrado")

        # Verificar que no exista usuario con ese email
        if User.objects.filter(email__iexact=jugador.email).exists():
            raise serializers.ValidationError("Ya existe un usuario con este email")

        return data

    def save(self):
        """Convertir jugador invitado a registrado"""
        jugador = self.context['jugador']
        password = self.validated_data.get('password', 'padel123')

        with transaction.atomic():
            # Crear usuario
            username = self._generate_username(jugador.nombre, jugador.apellido)
            user = User.objects.create_user(
                username=username,
                email=jugador.email,
                first_name=jugador.nombre,
                last_name=jugador.apellido,
                password=password
            )

            # Actualizar jugador
            jugador.user = user
            jugador.es_invitado = False
            jugador.save()

            return jugador

    def _generate_username(self, nombre, apellido):
        """Generar username único"""
        import unicodedata
        import re

        def clean_string(s):
            s = unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('ascii')
            s = re.sub(r'[^a-zA-Z0-9]', '', s)
            return s.lower()

        nombre_clean = clean_string(nombre)
        apellido_clean = clean_string(apellido)

        base_username = f"{nombre_clean}.{apellido_clean}"
        username = base_username
        counter = 1

        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        return username
