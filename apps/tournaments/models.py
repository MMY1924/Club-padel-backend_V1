
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from apps.players.models import Jugador
from apps.scoring.models import Partido, Cancha
import math
import random


class Torneo(models.Model):
    TIPO_CHOICES = [
        ('Eliminacion', 'Eliminación Directa'),
        ('Ranking', 'Ranking/Liga'),
        ('Grupos', 'Grupos + Eliminación'),
    ]

    MODALIDAD_CHOICES = [
        ('Individual', 'Individual (1 vs 1)'),
        ('Dobles', 'Dobles (2 vs 2)'),
    ]

    ESTADO_CHOICES = [
        ('Inscripcion', 'Inscripción Abierta'),
        ('Preparacion', 'En Preparación'),
        ('En_Curso', 'En Curso'),
        ('Finalizado', 'Finalizado'),
        ('Cancelado', 'Cancelado'),
    ]

    # Identificación
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo_torneo = models.CharField(max_length=20, unique=True, help_text="Código único del torneo")
    nombre = models.CharField(max_length=100, help_text="Nombre del torneo")
    descripcion = models.TextField(blank=True)

    # Configuración del torneo
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    modalidad = models.CharField(max_length=20, choices=MODALIDAD_CHOICES, default='Dobles')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Inscripcion')

    # Participantes
    min_participantes = models.PositiveIntegerField(
        default=4,
        validators=[MinValueValidator(2)],
        help_text="Mínimo de participantes/equipos"
    )
    max_participantes = models.PositiveIntegerField(
        default=32,
        validators=[MaxValueValidator(128)],
        help_text="Máximo de participantes/equipos"
    )

    # Configuración de partidos
    sets_para_ganar = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    juegos_para_ganar_set = models.PositiveIntegerField(default=6)

    # Configuración específica para tipo Grupos
    numero_grupos = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(2), MaxValueValidator(16)],
        help_text="Solo para torneos con grupos"
    )
    clasifican_por_grupo = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        help_text="Cuántos clasifican de cada grupo"
    )

    # Canchas disponibles
    canchas = models.ManyToManyField(
        Cancha,
        blank=True,
        related_name='torneos',
        help_text="Canchas disponibles para el torneo"
    )

    # Fechas
    fecha_inicio = models.DateTimeField(help_text="Fecha de inicio del torneo")
    fecha_fin = models.DateTimeField(help_text="Fecha estimada de finalización")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    # Premios y costos
    costo_inscripcion = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Costo de inscripción por participante/equipo"
    )
    premio_descripcion = models.TextField(blank=True, help_text="Descripción de premios")

    # Configuración adicional
    permite_inscripcion_individual = models.BooleanField(
        default=False,
        help_text="Para dobles: permitir inscripción sin pareja"
    )
    sorteo_publico = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'torneos'
        verbose_name = 'Torneo'
        verbose_name_plural = 'Torneos'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"

    def clean(self):
        super().clean()

        # Validaciones para torneos de grupos
        if self.tipo == 'Grupos':
            if not self.numero_grupos:
                raise ValidationError("Los torneos con grupos deben especificar número de grupos")
            if not self.clasifican_por_grupo:
                raise ValidationError("Debe especificar cuántos clasifican por grupo")

        # Validar fechas
        if self.fecha_inicio and self.fecha_fin:
            if self.fecha_fin <= self.fecha_inicio:
                raise ValidationError("La fecha de fin debe ser posterior a la de inicio")

    @property
    def participantes_registrados(self):
        return self.inscripciones.filter(estado='Confirmada').count()

    @property
    def esta_lleno(self):
        return self.participantes_registrados >= self.max_participantes

    @property
    def puede_iniciar(self):
        return (self.participantes_registrados >= self.min_participantes and
                self.estado == 'Preparacion')


class InscripcionTorneo(models.Model):
    ESTADO_CHOICES = [
        ('Pendiente', 'Pendiente de Pago'),
        ('Confirmada', 'Confirmada'),
        ('Cancelada', 'Cancelada'),
        ('Eliminado', 'Eliminado del Torneo'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='inscripciones')

    # Jugadores (flexibles para individual/dobles)
    jugador1 = models.ForeignKey(
        Jugador, on_delete=models.CASCADE, related_name='inscripciones_j1'
    )
    jugador2 = models.ForeignKey(
        Jugador, on_delete=models.CASCADE, related_name='inscripciones_j2',
        null=True, blank=True,
        help_text="Solo para torneos de dobles"
    )

    # Estado y pagos
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente')
    pagado = models.BooleanField(default=False)
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Ranking/Sembrado
    ranking_inicial = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Posición de siembra (1=mejor)"
    )

    # Metadatos
    fecha_inscripcion = models.DateTimeField(auto_now_add=True)
    notas = models.TextField(blank=True)

    class Meta:
        db_table = 'inscripciones_torneo'
        verbose_name = 'Inscripción'
        verbose_name_plural = 'Inscripciones'
        unique_together = [
            ['torneo', 'jugador1', 'jugador2']  # Evita inscripciones duplicadas
        ]
        ordering = ['fecha_inscripcion']

    def __str__(self):
        if self.torneo.modalidad == 'Individual':
            return f"{self.jugador1.nombre} en {self.torneo.nombre}"
        else:
            j2_nombre = self.jugador2.nombre if self.jugador2 else "Sin pareja"
            return f"{self.jugador1.nombre} & {j2_nombre} en {self.torneo.nombre}"

    def clean(self):
        super().clean()

        # Validar modalidad
        if self.torneo.modalidad == 'Individual' and self.jugador2:
            raise ValidationError("Los torneos individuales no deben tener segundo jugador")

        if self.torneo.modalidad == 'Dobles' and not self.jugador2:
            if not self.torneo.permite_inscripcion_individual:
                raise ValidationError("Este torneo requiere inscripción con pareja")

        # No repetir jugadores
        if self.jugador2 and self.jugador1 == self.jugador2:
            raise ValidationError("Los jugadores no pueden ser iguales")

    @property
    def nombre_equipo(self):
        if self.torneo.modalidad == 'Individual':
            return self.jugador1.nombre_completo
        else:
            j2 = self.jugador2.nombre_completo if self.jugador2 else "Por definir"
            return f"{self.jugador1.nombre_completo} & {j2}"


class FaseTorneo(models.Model):
    TIPO_FASE_CHOICES = [
        ('Grupos', 'Fase de Grupos'),
        ('Eliminacion', 'Eliminación Directa'),
        ('Final', 'Final'),
        ('Clasificacion', 'Partido por Clasificación'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='fases')

    tipo = models.CharField(max_length=20, choices=TIPO_FASE_CHOICES)
    nombre = models.CharField(max_length=50, help_text="Ej: Cuartos de Final, Grupo A")
    orden = models.PositiveIntegerField(help_text="Orden de la fase en el torneo")

    # Estado
    activa = models.BooleanField(default=False)
    completada = models.BooleanField(default=False)

    # Configuración específica
    numero_ronda = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Para eliminación: 1=Final, 2=Semis, 3=Cuartos..."
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fases_torneo'
        verbose_name = 'Fase de Torneo'
        verbose_name_plural = 'Fases de Torneo'
        ordering = ['torneo', 'orden']
        unique_together = [['torneo', 'orden']]

    def __str__(self):
        return f"{self.torneo.nombre} - {self.nombre}"


class GrupoTorneo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fase = models.ForeignKey(
        FaseTorneo,
        on_delete=models.CASCADE,
        related_name='grupos',
        limit_choices_to={'tipo': 'Grupos'}
    )

    nombre = models.CharField(max_length=20, help_text="Ej: Grupo A, Grupo B")
    inscripciones = models.ManyToManyField(InscripcionTorneo, related_name='grupos')

    class Meta:
        db_table = 'grupos_torneo'
        verbose_name = 'Grupo'
        verbose_name_plural = 'Grupos'
        unique_together = [['fase', 'nombre']]
        ordering = ['nombre']

    def __str__(self):
        return f"{self.fase.torneo.nombre} - {self.nombre}"

    def get_tabla_posiciones(self):
        """Calcula la tabla de posiciones del grupo"""
        posiciones = []

        for inscripcion in self.inscripciones.all():
            stats = {
                'inscripcion': inscripcion,
                'partidos_jugados': 0,
                'partidos_ganados': 0,
                'partidos_perdidos': 0,
                'sets_favor': 0,
                'sets_contra': 0,
                'juegos_favor': 0,
                'juegos_contra': 0,
                'puntos': 0
            }

            # Obtener partidos de esta inscripción en el grupo
            partidos = PartidoTorneo.objects.filter(
                fase=self.fase,
                grupo=self
            ).filter(
                models.Q(inscripcion_equipo1=inscripcion) |
                models.Q(inscripcion_equipo2=inscripcion)
            ).filter(
                partido__estado='Finalizado'
            )

            for partido_torneo in partidos:
                partido = partido_torneo.partido
                es_equipo1 = partido_torneo.inscripcion_equipo1 == inscripcion

                stats['partidos_jugados'] += 1

                # Determinar si ganó
                if (es_equipo1 and partido.equipo_ganador == 1) or \
                        (not es_equipo1 and partido.equipo_ganador == 2):
                    stats['partidos_ganados'] += 1
                    stats['puntos'] += 3
                else:
                    stats['partidos_perdidos'] += 1

                # Contar sets y juegos
                for set_obj in partido.sets.all():
                    if es_equipo1:
                        stats['sets_favor'] += 1 if set_obj.equipo_ganador == 1 else 0
                        stats['sets_contra'] += 1 if set_obj.equipo_ganador == 2 else 0
                        stats['juegos_favor'] += set_obj.juegos_equipo1
                        stats['juegos_contra'] += set_obj.juegos_equipo2
                    else:
                        stats['sets_favor'] += 1 if set_obj.equipo_ganador == 2 else 0
                        stats['sets_contra'] += 1 if set_obj.equipo_ganador == 1 else 0
                        stats['juegos_favor'] += set_obj.juegos_equipo2
                        stats['juegos_contra'] += set_obj.juegos_equipo1

            stats['diferencia_sets'] = stats['sets_favor'] - stats['sets_contra']
            stats['diferencia_juegos'] = stats['juegos_favor'] - stats['juegos_contra']

            posiciones.append(stats)

        # Ordenar por puntos, luego diferencia de sets, luego diferencia de juegos
        posiciones.sort(
            key=lambda x: (x['puntos'], x['diferencia_sets'], x['diferencia_juegos']),
            reverse=True
        )

        return posiciones


class PartidoTorneo(models.Model):
    TIPO_PARTIDO_CHOICES = [
        ('Regular', 'Partido Regular'),
        ('Desempate', 'Partido de Desempate'),
        ('Clasificacion', 'Partido por Posición'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relaciones con torneo
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='partidos_torneo')
    fase = models.ForeignKey(FaseTorneo, on_delete=models.CASCADE, related_name='partidos')
    grupo = models.ForeignKey(
        GrupoTorneo,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='partidos'
    )

    # Participantes
    inscripcion_equipo1 = models.ForeignKey(
        InscripcionTorneo,
        on_delete=models.CASCADE,
        related_name='partidos_como_equipo1',
        null=True, blank=True  # Puede ser null para bye o pendiente
    )
    inscripcion_equipo2 = models.ForeignKey(
        InscripcionTorneo,
        on_delete=models.CASCADE,
        related_name='partidos_como_equipo2',
        null=True, blank=True
    )

    # Partido real (se crea cuando se juega)
    partido = models.OneToOneField(
        Partido,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='partido_torneo'
    )

    # Programación
    fecha_programada = models.DateTimeField(null=True, blank=True)
    cancha_asignada = models.ForeignKey(
        Cancha,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    # Tipo y orden
    tipo = models.CharField(max_length=20, choices=TIPO_PARTIDO_CHOICES, default='Regular')
    orden_en_fase = models.PositiveIntegerField(help_text="Orden dentro de la fase")

    # Para brackets de eliminación
    siguiente_partido = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='partidos_previos',
        help_text="Partido al que avanza el ganador"
    )
    es_lado_equipo1 = models.BooleanField(
        null=True, blank=True,
        help_text="True si el ganador va como equipo1 en siguiente partido"
    )

    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    notas = models.TextField(blank=True)

    class Meta:
        db_table = 'partidos_torneo'
        verbose_name = 'Partido de Torneo'
        verbose_name_plural = 'Partidos de Torneo'
        ordering = ['fase', 'orden_en_fase']

    def __str__(self):
        eq1 = self.inscripcion_equipo1.nombre_equipo if self.inscripcion_equipo1 else "Por definir"
        eq2 = self.inscripcion_equipo2.nombre_equipo if self.inscripcion_equipo2 else "Por definir"
        return f"{self.torneo.nombre} - {self.fase.nombre}: {eq1} vs {eq2}"

    def crear_partido_real(self):
        """Crea el partido real cuando se va a jugar"""
        if self.partido:
            raise ValidationError("Este partido ya tiene un partido real asociado")

        if not self.inscripcion_equipo1 or not self.inscripcion_equipo2:
            raise ValidationError("Ambos equipos deben estar definidos")

        # Crear partido según modalidad
        partido_data = {
            'modalidad': self.torneo.modalidad,
            'tipo': 'Torneo',
            'estado': 'Pendiente',
            'sets_para_ganar': self.torneo.sets_para_ganar,
            'juegos_para_ganar_set': self.torneo.juegos_para_ganar_set,
            'cancha': self.cancha_asignada,
            'jugador1_equipo1': self.inscripcion_equipo1.jugador1,
            'jugador1_equipo2': self.inscripcion_equipo2.jugador1,
        }

        if self.torneo.modalidad == 'Dobles':
            partido_data['jugador2_equipo1'] = self.inscripcion_equipo1.jugador2
            partido_data['jugador2_equipo2'] = self.inscripcion_equipo2.jugador2

        self.partido = Partido.objects.create(**partido_data)
        self.save()

        return self.partido

    def procesar_resultado(self):
        """Procesa el resultado y avanza al ganador si corresponde"""
        if not self.partido or self.partido.estado != 'Finalizado':
            raise ValidationError("El partido no está finalizado")

        # Determinar ganador
        inscripcion_ganadora = (
            self.inscripcion_equipo1 if self.partido.equipo_ganador == 1
            else self.inscripcion_equipo2
        )

        # Si hay siguiente partido, colocar al ganador
        if self.siguiente_partido:
            if self.es_lado_equipo1:
                self.siguiente_partido.inscripcion_equipo1 = inscripcion_ganadora
            else:
                self.siguiente_partido.inscripcion_equipo2 = inscripcion_ganadora

            self.siguiente_partido.save()

        return inscripcion_ganadora


class ClasificacionTorneo(models.Model):
    """Tabla de clasificación final del torneo"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='clasificaciones')
    inscripcion = models.ForeignKey(InscripcionTorneo, on_delete=models.CASCADE)

    posicion_final = models.PositiveIntegerField()

    # Estadísticas finales
    partidos_jugados = models.PositiveIntegerField(default=0)
    partidos_ganados = models.PositiveIntegerField(default=0)
    partidos_perdidos = models.PositiveIntegerField(default=0)
    sets_ganados = models.PositiveIntegerField(default=0)
    sets_perdidos = models.PositiveIntegerField(default=0)
    juegos_ganados = models.PositiveIntegerField(default=0)
    juegos_perdidos = models.PositiveIntegerField(default=0)

    # Premios
    premio_descripcion = models.TextField(blank=True)
    premio_monto = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'clasificaciones_torneo'
        verbose_name = 'Clasificación'
        verbose_name_plural = 'Clasificaciones'
        unique_together = [['torneo', 'inscripcion'], ['torneo', 'posicion_final']]
        ordering = ['torneo', 'posicion_final']

    def __str__(self):
        return f"{self.torneo.nombre} - {self.posicion_final}º: {self.inscripcion.nombre_equipo}"