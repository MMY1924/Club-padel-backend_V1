# apps/tournaments/serializers.py

from rest_framework import serializers
from django.db import transaction
from .models import (
    Torneo, InscripcionTorneo, FaseTorneo,
    GrupoTorneo, PartidoTorneo, ClasificacionTorneo
)
from apps.players.models import Jugador
from apps.scoring.models import Partido, Cancha


# SERIALIZERS BÁSICOS


class CanchaSimpleSerializer(serializers.ModelSerializer):
    """Serializer simple para canchas"""

    class Meta:
        model = Cancha
        fields = ['id', 'nombre', 'numero', 'tipo', 'estado']


class JugadorSimpleSerializer(serializers.ModelSerializer):
    """Serializer simple para jugadores"""
    nombre_completo = serializers.CharField(read_only=True)

    class Meta:
        model = Jugador
        fields = ['id', 'nombre', 'apellido', 'nombre_completo', 'email']


class PartidoSimpleSerializer(serializers.ModelSerializer):
    """Serializer simple para partidos"""
    equipo1_nombre = serializers.CharField(read_only=True)
    equipo2_nombre = serializers.CharField(read_only=True)

    class Meta:
        model = Partido
        fields = [
            'id', 'estado', 'modalidad',
            'equipo1_nombre', 'equipo2_nombre',
            'equipo_ganador', 'fecha_inicio', 'fecha_fin'
        ]



# SERIALIZERS DE TORNEO


class TorneoListSerializer(serializers.ModelSerializer):
    """Serializer para listado de torneos"""
    participantes_registrados = serializers.IntegerField(read_only=True)
    esta_lleno = serializers.BooleanField(read_only=True)
    puede_iniciar = serializers.BooleanField(read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    modalidad_display = serializers.CharField(source='get_modalidad_display', read_only=True)

    class Meta:
        model = Torneo
        fields = [
            'id', 'codigo_torneo', 'nombre', 'descripcion',
            'tipo', 'tipo_display', 'modalidad', 'modalidad_display',
            'estado', 'estado_display', 'participantes_registrados',
            'max_participantes', 'min_participantes', 'esta_lleno',
            'puede_iniciar', 'fecha_inicio', 'fecha_fin',
            'costo_inscripcion', 'activo'
        ]


class TorneoDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para torneos"""
    participantes_registrados = serializers.IntegerField(read_only=True)
    esta_lleno = serializers.BooleanField(read_only=True)
    puede_iniciar = serializers.BooleanField(read_only=True)
    canchas = CanchaSimpleSerializer(many=True, read_only=True)
    canchas_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Cancha.objects.all(),
        write_only=True,
        source='canchas'
    )

    class Meta:
        model = Torneo
        fields = '__all__'
        read_only_fields = ['id', 'fecha_creacion', 'fecha_modificacion']

    def validate(self, data):
        """Validaciones personalizadas"""
        if data.get('tipo') == 'Grupos':
            if not data.get('numero_grupos'):
                raise serializers.ValidationError(
                    "Los torneos con grupos deben especificar número de grupos"
                )
            if not data.get('clasifican_por_grupo'):
                raise serializers.ValidationError(
                    "Debe especificar cuántos clasifican por grupo"
                )

        # Validar fechas
        if 'fecha_inicio' in data and 'fecha_fin' in data:
            if data['fecha_fin'] <= data['fecha_inicio']:
                raise serializers.ValidationError(
                    "La fecha de fin debe ser posterior a la de inicio"
                )

        return data


class TorneoCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear torneos"""
    canchas_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Cancha.objects.all(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Torneo
        fields = [
            'codigo_torneo', 'nombre', 'descripcion', 'tipo', 'modalidad',
            'min_participantes', 'max_participantes', 'sets_para_ganar',
            'juegos_para_ganar_set', 'numero_grupos', 'clasifican_por_grupo',
            'canchas_ids', 'fecha_inicio', 'fecha_fin', 'costo_inscripcion',
            'premio_descripcion', 'permite_inscripcion_individual',
            'sorteo_publico'
        ]

    def create(self, validated_data):
        canchas = validated_data.pop('canchas_ids', [])
        torneo = Torneo.objects.create(**validated_data)
        if canchas:
            torneo.canchas.set(canchas)
        return torneo



# SERIALIZERS DE INSCRIPCIÓN


class InscripcionListSerializer(serializers.ModelSerializer):
    """Serializer para listado de inscripciones"""
    jugador1 = JugadorSimpleSerializer(read_only=True)
    jugador2 = JugadorSimpleSerializer(read_only=True)
    nombre_equipo = serializers.CharField(read_only=True)
    torneo_nombre = serializers.CharField(source='torneo.nombre', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = InscripcionTorneo
        fields = [
            'id', 'torneo', 'torneo_nombre', 'jugador1', 'jugador2',
            'nombre_equipo', 'estado', 'estado_display', 'pagado',
            'monto_pagado', 'ranking_inicial', 'fecha_inscripcion'
        ]


class InscripcionDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para inscripciones"""
    jugador1 = JugadorSimpleSerializer(read_only=True)
    jugador2 = JugadorSimpleSerializer(read_only=True)
    nombre_equipo = serializers.CharField(read_only=True)

    class Meta:
        model = InscripcionTorneo
        fields = '__all__'
        read_only_fields = ['id', 'fecha_inscripcion']


class InscripcionCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear inscripciones"""
    jugador1_id = serializers.PrimaryKeyRelatedField(
        queryset=Jugador.objects.all(),
        source='jugador1',
        write_only=True
    )
    jugador2_id = serializers.PrimaryKeyRelatedField(
        queryset=Jugador.objects.all(),
        source='jugador2',
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = InscripcionTorneo
        fields = [
            'torneo', 'jugador1_id', 'jugador2_id',
            'ranking_inicial', 'notas'
        ]

    def validate(self, data):
        torneo = data['torneo']

        # Validar que el torneo esté abierto
        if torneo.estado != 'Inscripcion':
            raise serializers.ValidationError(
                "El torneo no está abierto para inscripciones"
            )

        # Validar que no esté lleno
        if torneo.esta_lleno:
            raise serializers.ValidationError(
                "El torneo está lleno"
            )

        # Validar modalidad
        if torneo.modalidad == 'Individual' and data.get('jugador2'):
            raise serializers.ValidationError(
                "Los torneos individuales no deben tener segundo jugador"
            )

        if torneo.modalidad == 'Dobles' and not data.get('jugador2'):
            if not torneo.permite_inscripcion_individual:
                raise serializers.ValidationError(
                    "Este torneo requiere inscripción con pareja"
                )

        # Validar jugadores diferentes
        if data.get('jugador2') and data['jugador1'] == data['jugador2']:
            raise serializers.ValidationError(
                "Los jugadores no pueden ser iguales"
            )

        return data

    def create(self, validated_data):
        with transaction.atomic():
            inscripcion = InscripcionTorneo.objects.create(**validated_data)
            return inscripcion



# SERIALIZERS DE FASE Y GRUPO


class FaseTorneoSerializer(serializers.ModelSerializer):
    """Serializer para fases del torneo"""
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    partidos_total = serializers.IntegerField(
        source='partidos.count',
        read_only=True
    )
    partidos_jugados = serializers.SerializerMethodField()

    class Meta:
        model = FaseTorneo
        fields = [
            'id', 'tipo', 'tipo_display', 'nombre', 'orden',
            'activa', 'completada', 'numero_ronda',
            'partidos_total', 'partidos_jugados'
        ]

    def get_partidos_jugados(self, obj):
        return obj.partidos.filter(partido__estado='Finalizado').count()


class GrupoTorneoSerializer(serializers.ModelSerializer):
    """Serializer para grupos del torneo"""
    inscripciones = InscripcionListSerializer(many=True, read_only=True)
    tabla_posiciones = serializers.SerializerMethodField()

    class Meta:
        model = GrupoTorneo
        fields = ['id', 'nombre', 'inscripciones', 'tabla_posiciones']

    def get_tabla_posiciones(self, obj):
        """Obtiene la tabla de posiciones del grupo"""
        tabla = obj.get_tabla_posiciones()
        return [
            {
                'posicion': idx + 1,
                'equipo': pos['inscripcion'].nombre_equipo,
                'pj': pos['partidos_jugados'],
                'pg': pos['partidos_ganados'],
                'pp': pos['partidos_perdidos'],
                'sf': pos['sets_favor'],
                'sc': pos['sets_contra'],
                'jf': pos['juegos_favor'],
                'jc': pos['juegos_contra'],
                'pts': pos['puntos']
            }
            for idx, pos in enumerate(tabla)
        ]


# SERIALIZERS DE PARTIDO TORNEO

class PartidoTorneoListSerializer(serializers.ModelSerializer):
    """Serializer para listado de partidos del torneo"""
    inscripcion_equipo1 = InscripcionListSerializer(read_only=True)
    inscripcion_equipo2 = InscripcionListSerializer(read_only=True)
    fase_nombre = serializers.CharField(source='fase.nombre', read_only=True)
    grupo_nombre = serializers.CharField(source='grupo.nombre', read_only=True, allow_null=True)
    cancha_nombre = serializers.CharField(source='cancha_asignada.nombre', read_only=True, allow_null=True)
    partido_estado = serializers.CharField(source='partido.estado', read_only=True, allow_null=True)

    class Meta:
        model = PartidoTorneo
        fields = [
            'id', 'fase_nombre', 'grupo_nombre',
            'inscripcion_equipo1', 'inscripcion_equipo2',
            'fecha_programada', 'cancha_asignada', 'cancha_nombre',
            'partido', 'partido_estado', 'tipo', 'orden_en_fase'
        ]


class PartidoTorneoDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para partidos del torneo"""
    inscripcion_equipo1 = InscripcionDetailSerializer(read_only=True)
    inscripcion_equipo2 = InscripcionDetailSerializer(read_only=True)
    partido = PartidoSimpleSerializer(read_only=True)
    cancha_asignada = CanchaSimpleSerializer(read_only=True)

    class Meta:
        model = PartidoTorneo
        fields = '__all__'
        read_only_fields = ['id', 'fecha_creacion', 'partido']


class PartidoTorneoUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar partidos del torneo"""

    class Meta:
        model = PartidoTorneo
        fields = ['fecha_programada', 'cancha_asignada', 'notas']


# SERIALIZERS DE CLASIFICACIÓN

class ClasificacionSerializer(serializers.ModelSerializer):
    """Serializer para clasificación final"""
    inscripcion = InscripcionListSerializer(read_only=True)
    porcentaje_victorias = serializers.SerializerMethodField()

    class Meta:
        model = ClasificacionTorneo
        fields = [
            'posicion_final', 'inscripcion',
            'partidos_jugados', 'partidos_ganados', 'partidos_perdidos',
            'sets_ganados', 'sets_perdidos',
            'juegos_ganados', 'juegos_perdidos',
            'porcentaje_victorias', 'premio_descripcion', 'premio_monto'
        ]

    def get_porcentaje_victorias(self, obj):
        if obj.partidos_jugados == 0:
            return 0
        return round((obj.partidos_ganados / obj.partidos_jugados) * 100, 1)


# SERIALIZERS DE ESTADO Y ESTADÍSTICAS

class TorneoStatusSerializer(serializers.Serializer):
    """Serializer para estado del torneo"""
    estado = serializers.CharField()
    participantes = serializers.IntegerField()
    fase_actual = serializers.CharField(allow_null=True)
    partidos_totales = serializers.IntegerField()
    partidos_jugados = serializers.IntegerField()
    partidos_en_curso = serializers.IntegerField()
    partidos_pendientes = serializers.IntegerField()
    total_fases = serializers.IntegerField()
    fases_completadas = serializers.IntegerField()
    lideres = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )


class GenerarSorteoSerializer(serializers.Serializer):
    """Serializer para generar sorteo"""
    confirmar = serializers.BooleanField(
        help_text="Confirmar generación de sorteo (borrará sorteo anterior si existe)"
    )


class ProgramarPartidosSerializer(serializers.Serializer):
    """Serializer para programar partidos automáticamente"""
    fecha_inicio = serializers.DateTimeField()
    canchas_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Cancha.objects.all()
    )
    partidos_por_dia = serializers.IntegerField(
        min_value=1,
        max_value=20,
        default=8
    )

    def validate_fecha_inicio(self, value):
        from django.utils import timezone
        if value < timezone.now():
            raise serializers.ValidationError(
                "La fecha de inicio debe ser futura"
            )
        return value

# 7. FUNCIONES DE USUARIO FINAL

def explain_tournament_type(tournament_type):
    """Explica un tipo de torneo de forma simple"""
    explanations = {
        'Eliminacion': """
         ELIMINACIÓN DIRECTA

        ¿Cómo funciona?
        • Pierdes un partido = quedas eliminado
        • Los ganadores avanzan a la siguiente ronda
        • Continúa hasta que quede solo 1 campeón

        Ejemplo con 8 equipos:
        Cuartos → 8 equipos → 4 ganadores
        Semis   → 4 equipos → 2 ganadores  
        Final   → 2 equipos → 1 campeón

        """,

        'Ranking': """
         LIGA/RANKING

        ¿Cómo funciona?
        • Todos juegan contra todos
        • Se suman puntos: Victoria = 3, Derrota = 0
        • El que más puntos tenga al final gana

        Ejemplo con 4 equipos (6 partidos):
        A vs B, A vs C, A vs D
        B vs C, B vs D, C vs D

        """,

        'Grupos': """
         GRUPOS + ELIMINACIÓN

        ¿Cómo funciona?
        • Los equipos se dividen en grupos
        • En cada grupo juegan todos contra todos
        • Los mejores de cada grupo clasifican
        • Los clasificados juegan eliminación directa

        Ejemplo con 8 equipos:
        Grupo A (4 equipos) → 2 mejores clasifican
        Grupo B (4 equipos) → 2 mejores clasifican
        Final entre los 4 clasificados
        """
    }

    return explanations.get(tournament_type, "Tipo de torneo no reconocido")

# EJEMPLO DE USO

"""
# Para usar desde el shell:

from apps.tournaments.flow_services import *

# Ver flujo de un torneo específico
torneo = Torneo.objects.first()
flow_service = TournamentFlowService(torneo)
flow_data = flow_service.get_tournament_flow()

# Crear flujo interactivo
create_interactive_tournament_flow()

# Probar todos los flujos
test_all_tournament_flows()

# Explicar un tipo
print(explain_tournament_type('Eliminacion'))

# Generar reporte
report = generate_flow_report(torneo.id)
"""