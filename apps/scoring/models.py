
import uuid
from django.db import models
from django.core.validators import EmailValidator, MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from apps.players.models import Jugador
import logging
logger = logging.getLogger(__name__)



class Cancha(models.Model):
    ESTADO_CHOICES = [
        ('Disponible', 'Disponible'),
        ('Ocupada', 'Ocupada'),
        ('Mantenimiento', 'Mantenimiento'),
        ('Fuera_Servicio', 'Fuera de Servicio'),
    ]

    TIPO_CHOICES = [
        ('Interior', 'Interior'),
        ('Exterior', 'Exterior'),
        ('Cubierta', 'Cubierta'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=50, unique=True, help_text="Nombre o número de la cancha")
    numero = models.PositiveIntegerField(unique=True, help_text="Número de identificación")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='Exterior')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Disponible')


    descripcion = models.TextField(blank=True, help_text="Descripción o características especiales")
    capacidad_espectadores = models.PositiveIntegerField(default=0, help_text="Capacidad de espectadores")
    tiene_iluminacion = models.BooleanField(default=True)

    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = 'canchas'
        verbose_name = 'Cancha'
        verbose_name_plural = 'Canchas'
        ordering = ['numero']

    def __str__(self):
        return f"Cancha {self.numero} - {self.nombre}"


# Modelo Partido
class Partido(models.Model):
    ESTADO_CHOICES = [
        ('Pendiente', 'Pendiente'),
        ('En Juego', 'En Juego'),
        ('Finalizado', 'Finalizado'),
        ('Cancelado', 'Cancelado'),
    ]

    TIPO_CHOICES = [
        ('Amistoso', 'Amistoso'),
        ('Torneo', 'Torneo'),
        ('RANK', 'RAKING'),
    ]

    # NUEVO: Modalidad de partido
    MODALIDAD_CHOICES = [
        ('Individual', 'Individual (1 vs 1)'),
        ('Dobles', 'Dobles (2 vs 2)'),
    ]

    # Identificación
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # NUEVO: Modalidad y Cancha
    modalidad = models.CharField(
        max_length=20,
        choices=MODALIDAD_CHOICES,
        default='Dobles',
        help_text="Individual (1vs1) o Dobles (2vs2)"
    )

    cancha = models.ForeignKey(
        Cancha,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='partidos',
        help_text="Cancha donde se juega el partido"
    )

    # JUGADORES MODIFICADOS (ahora flexibles)
    jugador1_equipo1 = models.ForeignKey(
        Jugador, on_delete=models.CASCADE, related_name='partidos_j1_e1'
    )

    # MODIFICADO: Ahora opcional para partidos individuales
    jugador2_equipo1 = models.ForeignKey(
        Jugador, on_delete=models.CASCADE, related_name='partidos_j2_e1',
        null=True, blank=True,
        help_text="Solo requerido para partidos de dobles"
    )

    jugador1_equipo2 = models.ForeignKey(
        Jugador, on_delete=models.CASCADE, related_name='partidos_j1_e2'
    )

    # MODIFICADO: Ahora opcional para partidos individuales
    jugador2_equipo2 = models.ForeignKey(
        Jugador, on_delete=models.CASCADE, related_name='partidos_j2_e2',
        null=True, blank=True,
        help_text="Solo requerido para partidos de dobles"
    )

    # Estado del partido
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='Amistoso')

    # Configuración del partido
    sets_para_ganar = models.IntegerField(default=2)

    # CONFIGURAR REGLAS
    puntos_para_ganar_juego = models.IntegerField(default=4)  # Ej: 4 (juego normal)
    diferencia_minima_puntos = models.IntegerField(default=2)  # Ej: 2 (ventaja)
    juegos_para_ganar_set = models.IntegerField(default=6)  # Ej: 6 (set normal)
    diferencia_minima_juegos = models.IntegerField(default=2)  # Ej: 2 (ventaja en juegos)

    def __str__(self):
        return f"{self.equipo1_nombre} vs {self.equipo2_nombre} ({self.estado})"

    # Metadatos
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    # Resultados
    equipo_ganador = models.PositiveIntegerField(null=True, blank=True,
                                                 validators=[MinValueValidator(1), MaxValueValidator(2)])

    class Meta:
        db_table = 'partidos'
        verbose_name = 'Partido'
        verbose_name_plural = 'Partidos'
        ordering = ['-fecha_creacion']

    # NUEVO: Validaciones personalizadas
    def clean(self):
        super().clean()

        # Validar jugadores según modalidad
        if self.modalidad == 'Individual':
            if self.jugador2_equipo1 or self.jugador2_equipo2:
                raise ValidationError("Los partidos individuales no deben tener segundos jugadores")
        elif self.modalidad == 'Dobles':
            if not self.jugador2_equipo1 or not self.jugador2_equipo2:
                raise ValidationError("Los partidos de dobles requieren 2 jugadores por equipo")

        # Validar que no se repitan jugadores
        jugadores = self.get_jugadores_list()
        if len(jugadores) != len(set(jugadores)):
            raise ValidationError("No se pueden repetir jugadores en el mismo partido")

    # NUEVOS MÉTODOS AUXILIARES
    def get_jugadores_list(self):
        """Retorna lista de objetos Jugador sin duplicados ni None"""
        jugadores = []
        if self.jugador1_equipo1:
            jugadores.append(self.jugador1_equipo1)
        if self.jugador1_equipo2:
            jugadores.append(self.jugador1_equipo2)
        if self.jugador2_equipo1:
            jugadores.append(self.jugador2_equipo1)
        if self.jugador2_equipo2:
            jugadores.append(self.jugador2_equipo2)
        return jugadores

    def get_equipo_jugadores(self, equipo):
        """Retorna los jugadores de un equipo específico"""
        if equipo == 1:
            jugadores = [self.jugador1_equipo1]
            if self.jugador2_equipo1:
                jugadores.append(self.jugador2_equipo1)
            return jugadores
        elif equipo == 2:
            jugadores = [self.jugador1_equipo2]
            if self.jugador2_equipo2:
                jugadores.append(self.jugador2_equipo2)
            return jugadores
        return []

    def save(self, *args, **kwargs):
        estado_anterior = None
        if self.pk:
            estado_anterior = Partido.objects.filter(pk=self.pk).values_list('estado', flat=True).first()

        super().save(*args, **kwargs)  # Guardar primero

        # Si el estado cambia a "En Juego", aseguramos set y juego
        if self.estado == "En Juego" and estado_anterior != "En Juego":
            from .services import PadelScoringService
            try:
                servicio = PadelScoringService(self.id)
                servicio._ensure_active_set_and_game()
                logger.info(f"Partido {self.id}: Estructura inicial asegurada automáticamente.")
            except Exception as e:
                logger.error(f"Error asegurando estructura para el partido {self.id}: {e}")


    def __str__(self):
        if self.modalidad == 'Individual':
            return f"{self.jugador1_equipo1.nombre} vs {self.jugador1_equipo2.nombre}"
        else:
            return f"{self.jugador1_equipo1.nombre} & {self.jugador2_equipo1.nombre} vs {self.jugador1_equipo2.nombre} & {self.jugador2_equipo2.nombre}"

    @property
    def equipo1_nombre(self):
        if self.modalidad == 'Individual':
            return f"{self.jugador1_equipo1.nombre}"
        else:
            return f"{self.jugador1_equipo1.nombre} & {self.jugador2_equipo1.nombre}"

    @property
    def equipo2_nombre(self):
        if self.modalidad == 'Individual':
            return f"{self.jugador1_equipo2.nombre}"
        else:
            return f"{self.jugador1_equipo2.nombre} & {self.jugador2_equipo2.nombre}"


class Set(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partido = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name='sets')
    numero_set = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    # Puntuación del set
    juegos_equipo1 = models.PositiveIntegerField(default=0)
    juegos_equipo2 = models.PositiveIntegerField(default=0)

    # Estado
    finalizado = models.BooleanField(default=False)
    equipo_ganador = models.PositiveIntegerField(null=True, blank=True,
                                                 validators=[MinValueValidator(1), MaxValueValidator(2)])

    # Tiebreak
    tiene_tiebreak = models.BooleanField(default=False)
    puntos_tiebreak_equipo1 = models.PositiveIntegerField(default=0)
    puntos_tiebreak_equipo2 = models.PositiveIntegerField(default=0)

    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sets'
        unique_together = ['partido', 'numero_set']
        ordering = ['numero_set']

    def __str__(self):
        if self.tiene_tiebreak:
            return f"Set {self.numero_set}: {self.juegos_equipo1}-{self.juegos_equipo2} ({self.puntos_tiebreak_equipo1}-{self.puntos_tiebreak_equipo2})"
        return f"Set {self.numero_set}: {self.juegos_equipo1}-{self.juegos_equipo2}"


class Juego(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    set = models.ForeignKey(Set, on_delete=models.CASCADE, related_name='juegos')
    numero_juego = models.PositiveIntegerField()

    # Puntuación del juego (0, 15, 30, 40, A)
    puntos_equipo1 = models.PositiveIntegerField(default=0)
    puntos_equipo2 = models.PositiveIntegerField(default=0)

    # Estado
    finalizado = models.BooleanField(default=False)
    equipo_ganador = models.PositiveIntegerField(null=True, blank=True,
                                                 validators=[MinValueValidator(1), MaxValueValidator(2)])

    # Quien saca
    equipo_que_saca = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(2)])

    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'juegos'
        unique_together = ['set', 'numero_juego']
        ordering = ['numero_juego']

    def __str__(self):
        return f"Juego {self.numero_juego}: {self.puntos_display_equipo1} - {self.puntos_display_equipo2}"

    @property
    def puntos_display_equipo1(self):
        return self._convertir_puntos_display(self.puntos_equipo1, self.puntos_equipo2)

    @property
    def puntos_display_equipo2(self):
        return self._convertir_puntos_display(self.puntos_equipo2, self.puntos_equipo1)

    def _convertir_puntos_display(self, puntos_equipo, puntos_oponente):
        """Convierte puntos numéricos a display de tenis (0, 15, 30, 40, A)"""
        if puntos_equipo >= 3 and puntos_oponente >= 3:
            if puntos_equipo == puntos_oponente:
                return "40"
            elif puntos_equipo > puntos_oponente:
                return "A"  # Ventaja
            else:
                return "40"
        else:
            conversion = {0: "0", 1: "15", 2: "30", 3: "40"}
            return conversion.get(puntos_equipo, "40")


class Punto(models.Model):
    TIPO_PUNTO_CHOICES = [
        ('Punto', 'Punto'),
        ('Deshacer', 'Deshacer Punto'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    juego = models.ForeignKey(Juego, on_delete=models.CASCADE, related_name='puntos')

    # Quien gana el punto
    equipo_ganador = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(2)])

    # Detalles del punto
    tipo_punto = models.CharField(max_length=10, choices=TIPO_PUNTO_CHOICES, default='Punto')
    descripcion = models.TextField(blank=True)

    # Metadatos
    timestamp = models.DateTimeField(auto_now_add=True)
    numero_punto = models.PositiveIntegerField()

    class Meta:
        db_table = 'puntos'
        ordering = ['numero_punto']

    def __str__(self):
        return f"Punto {self.numero_punto}: Equipo {self.equipo_ganador} ({self.get_tipo_punto_display()})"


class HistorialJugador(models.Model):
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE,
        null=True,
        blank=True, related_name='historial')
    partido = models.ForeignKey(Partido, on_delete=models.CASCADE,
        null=True,
        blank=True, related_name='historiales')

    # Información del partido
    es_ganador = models.BooleanField()
    equipo_jugador = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(2)])

    # MODIFICADO: Compañero puede ser null para partidos individuales
    Pareja = models.ForeignKey(
        Jugador, on_delete=models.CASCADE, related_name='compañeros_historial',
        null=True, blank=True,
        help_text="Compañero de equipo (solo en partidos de dobles)"
    )

    # Estadísticas del partido
    sets_ganados = models.PositiveIntegerField(default=0)
    sets_perdidos = models.PositiveIntegerField(default=0)
    juegos_ganados = models.PositiveIntegerField(default=0)
    juegos_perdidos = models.PositiveIntegerField(default=0)
    puntos_ganados = models.PositiveIntegerField(default=0)
    puntos_perdidos = models.PositiveIntegerField(default=0)

    # Metadatos
    fecha_partido = models.DateTimeField()
    duracion_partido = models.DurationField(null=True, blank=True)

    class Meta:
        db_table = 'historial_jugadores'
        verbose_name = 'Historial de Jugador'
        verbose_name_plural = 'Historiales de Jugadores'
        ordering = ['-fecha_partido']
        unique_together = ['jugador', 'partido']

    def __str__(self):
        resultado = "Ganó" if self.es_ganador else "Perdió"
        return f"{self.jugador.nombre_completo} - {resultado} vs {self.get_oponentes_display()}"

    def get_oponentes_display(self):
        """Obtener nombres de los oponentes (funciona para Individual y Dobles)"""
        if self.partido.modalidad == 'Individual':
            if self.equipo_jugador == 1:
                return f"{self.partido.jugador1_equipo2.nombre}"
            else:
                return f"{self.partido.jugador1_equipo1.nombre}"
        else:
            if self.equipo_jugador == 1:
                return f"{self.partido.jugador1_equipo2.nombre} & {self.partido.jugador2_equipo2.nombre}"
            else:
                return f"{self.partido.jugador1_equipo1.nombre} & {self.partido.jugador2_equipo1.nombre}"

    @property
    def porcentaje_sets(self):
        total_sets = self.sets_ganados + self.sets_perdidos
        if total_sets == 0:
            return 0
        return round((self.sets_ganados / total_sets) * 100, 1)

    @property
    def porcentaje_juegos(self):
        total_juegos = self.juegos_ganados + self.juegos_perdidos
        if total_juegos == 0:
            return 0
        return round((self.juegos_ganados / total_juegos) * 100, 1)

    @property
    def porcentaje_puntos(self):
        total_puntos = self.puntos_ganados + self.puntos_perdidos
        if total_puntos == 0:
            return 0
        return round((self.puntos_ganados / total_puntos) * 100, 1)


class EstadisticasJugador(models.Model):
    """Modelo para estadísticas acumuladas del jugador"""
    jugador = models.OneToOneField(Jugador, on_delete=models.CASCADE, related_name='estadisticas')

    # Estadísticas generales
    partidos_jugados = models.PositiveIntegerField(default=0)
    partidos_ganados = models.PositiveIntegerField(default=0)
    partidos_perdidos = models.PositiveIntegerField(default=0)

    # Estadísticas por sets
    sets_jugados = models.PositiveIntegerField(default=0)
    sets_ganados = models.PositiveIntegerField(default=0)
    sets_perdidos = models.PositiveIntegerField(default=0)

    # Estadísticas por juegos
    juegos_jugados = models.PositiveIntegerField(default=0)
    juegos_ganados = models.PositiveIntegerField(default=0)
    juegos_perdidos = models.PositiveIntegerField(default=0)

    # Estadísticas por puntos
    puntos_jugados = models.PositiveIntegerField(default=0)
    puntos_ganados = models.PositiveIntegerField(default=0)
    puntos_perdidos = models.PositiveIntegerField(default=0)

    # Rachas
    racha_actual_victorias = models.PositiveIntegerField(default=0)
    mejor_racha_victorias = models.PositiveIntegerField(default=0)
    racha_actual_derrotas = models.PositiveIntegerField(default=0)

    # Fechas importantes
    primer_partido = models.DateTimeField(null=True, blank=True)
    ultimo_partido = models.DateTimeField(null=True, blank=True)
    ultima_actualizacion = models.DateTimeField(auto_now=True)

    @property
    def porcentaje_victorias(self):
        """Calcula el porcentaje de victorias"""
        if self.partidos_jugados == 0:
            return 0
        return round((self.partidos_ganados / self.partidos_jugados) * 100, 1)

    @property
    def porcentaje_sets(self):
        """Calcula el porcentaje de sets ganados"""
        if self.sets_jugados == 0:
            return 0
        return round((self.sets_ganados / self.sets_jugados) * 100, 1)

    @property
    def porcentaje_juegos(self):
        """Calcula el porcentaje de juegos ganados"""
        if self.juegos_jugados == 0:
            return 0
        return round((self.juegos_ganados / self.juegos_jugados) * 100, 1)

    @property
    def porcentaje_puntos(self):
        """Calcula el porcentaje de puntos ganados"""
        if self.puntos_jugados == 0:
            return 0
        return round((self.puntos_ganados / self.puntos_jugados) * 100, 1)

    class Meta:
        db_table = 'estadisticas_jugadores'
        verbose_name = 'Estadísticas de Jugador'
        verbose_name_plural = 'Estadísticas de Jugadores'


class Reserva(models.Model):
    """Modelo para reservas de canchas"""

    ESTADO_CHOICES = [
        ('Pendiente', 'Pendiente'),
        ('Confirmada', 'Confirmada'),
        ('En_Uso', 'En Uso'),
        ('Completada', 'Completada'),
        ('Cancelada', 'Cancelada'),
        ('No_Show', 'No Show'),
    ]

    TIPO_RESERVA_CHOICES = [
        ('Individual', 'Práctica Individual'),
        ('Dobles', 'Práctica Dobles'),
        ('Clase', 'Clase/Entrenamiento'),
        ('Torneo', 'Torneo'),
        ('Evento', 'Evento Especial'),
    ]

    # Identificación
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo_reserva = models.CharField(max_length=10, unique=True, editable=False)

    # Relaciones
    cancha = models.ForeignKey(
        Cancha,
        on_delete=models.CASCADE,
        related_name='reservas',
        help_text="Cancha reservada"
    )

    jugador = models.ForeignKey(
        'players.Jugador',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reservas',
        help_text="Jugador que hace la reserva"
    )

    # Información temporal
    fecha_inicio = models.DateTimeField(help_text="Fecha y hora de inicio")
    fecha_fin = models.DateTimeField(help_text="Fecha y hora de fin")
    duracion_minutos = models.PositiveIntegerField(
        default=60,
        validators=[MinValueValidator(30), MaxValueValidator(180)],
        help_text="Duración en minutos"
    )

    # Estado y tipo
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente')
    tipo_reserva = models.CharField(max_length=20, choices=TIPO_RESERVA_CHOICES, default='Dobles')

    # Información económica
    precio_hora = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text="Precio por hora en COP"
    )
    precio_total = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text="Precio total de la reserva"
    )
    pagado = models.BooleanField(default=False)

    # Información adicional
    numero_jugadores = models.PositiveIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(6)],
        help_text="Número de jugadores esperados"
    )

    observaciones = models.TextField(blank=True, help_text="Observaciones de la reserva")
    equipamiento_incluido = models.BooleanField(default=False, help_text="¿Incluye raquetas/pelotas?")

    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    creado_por = models.CharField(max_length=100, blank=True, help_text="Usuario que creó la reserva")

    # Relación opcional con partido
    partido = models.OneToOneField(
        Partido,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reserva',
        help_text="Partido asociado (si aplica)"
    )

    class Meta:
        db_table = 'reservas'
        verbose_name = 'Reserva'
        verbose_name_plural = 'Reservas'
        ordering = ['fecha_inicio']

    def generar_codigo_reserva(self):
        """Generar código único de reserva"""
        import random
        import string
        while True:
            codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not Reserva.objects.filter(codigo_reserva=codigo).exists():
                return codigo

    def clean(self):
        """Validaciones personalizadas"""
        from decimal import Decimal
        from django.core.exceptions import ValidationError
        super().clean()

        # 1. Calcular fecha_fin automáticamente si no está establecida
        if self.fecha_inicio and self.duracion_minutos and not self.fecha_fin:
            from datetime import timedelta
            self.fecha_fin = self.fecha_inicio + timedelta(minutes=self.duracion_minutos)

        # 2. Validar que no haya conflictos de horario
        if self.fecha_inicio and self.fecha_fin and self.cancha:
            self._validar_disponibilidad_cancha()

    def _validar_disponibilidad_cancha(self):
        """Validar que la cancha esté disponible en el horario solicitado"""
        from django.core.exceptions import ValidationError

        # Buscar reservas que se solapen en la misma cancha
        reservas_conflicto = Reserva.objects.filter(
            cancha=self.cancha,
            estado__in=['Confirmada', 'En_Uso', 'Pendiente'],
            fecha_inicio__lt=self.fecha_fin,
            fecha_fin__gt=self.fecha_inicio
        )

        # Excluir la reserva actual si estamos editando
        if self.pk:
            reservas_conflicto = reservas_conflicto.exclude(pk=self.pk)

        if reservas_conflicto.exists():
            conflicto = reservas_conflicto.first()

            # Determinar si es el mismo día o cruza a otro día
            if conflicto.fecha_inicio.date() == conflicto.fecha_fin.date():
                # Mismo día: mostrar solo las horas
                horario_conflicto = f"{conflicto.fecha_inicio.strftime('%H:%M')} a {conflicto.fecha_fin.strftime('%H:%M')}"
            else:
                # Cruza días: mostrar fecha y hora completas
                fecha_inicio_conflicto = conflicto.fecha_inicio.strftime("%d/%m %H:%M")
                fecha_fin_conflicto = conflicto.fecha_fin.strftime("%d/%m %H:%M")
                horario_conflicto = f"{fecha_inicio_conflicto} a {fecha_fin_conflicto}"

            raise ValidationError({
                'fecha_inicio': f' CANCHA OCUPADA - Ya existe la reserva {conflicto.codigo_reserva} Selecciona otro horario disponible.'
            })

    def save(self, *args, **kwargs):
        """Override save para aplicar cálculos automáticos y validaciones"""
        from decimal import Decimal
        from datetime import timedelta

        print(f"DEBUG - Guardando reserva. Código actual: '{self.codigo_reserva}'")

        # 1. Generar código si no existe
        if not self.codigo_reserva:
            import random
            import string
            print("DEBUG - Generando nuevo código...")
            while True:
                codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                if not Reserva.objects.filter(codigo_reserva=codigo).exists():
                    self.codigo_reserva = codigo
                    print(f"DEBUG - Código generado: {codigo}")
                    break

        # 2. Calcular fecha_fin automáticamente
        if self.fecha_inicio and self.duracion_minutos and not self.fecha_fin:
            self.fecha_fin = self.fecha_inicio + timedelta(minutes=self.duracion_minutos)

        # 3. Calcular precio_total automáticamente (SIEMPRE)
        if self.duracion_minutos and self.precio_hora:
            horas = Decimal(str(self.duracion_minutos)) / Decimal('60')
            self.precio_total = self.precio_hora * horas
            print(f"DEBUG - Precio calculado: {self.precio_hora} * {horas} = {self.precio_total}")

        print(f"DEBUG - Código final antes de guardar: '{self.codigo_reserva}'")

        # 4. Ejecutar validaciones (HABILITADAS)
        self.full_clean()

        super().save(*args, **kwargs)
        print(f"DEBUG - Reserva guardada con ID: {self.id}")

    def __str__(self):
        return f"Reserva {self.codigo_reserva} - {self.cancha.nombre}"

    # Propiedades calculadas para el admin y API
    @property
    def duracion_display(self):
        """Duración formateada para mostrar"""
        horas = self.duracion_minutos // 60
        minutos = self.duracion_minutos % 60
        if horas > 0:
            return f"{horas}h {minutos}m" if minutos > 0 else f"{horas}h"
        return f"{minutos}m"

    @property
    def es_hoy(self):
        """Verifica si la reserva es para hoy"""
        from django.utils import timezone
        return self.fecha_inicio.date() == timezone.now().date()

    @property
    def tiempo_restante(self):
        """Tiempo restante hasta la reserva"""
        from django.utils import timezone
        if self.fecha_inicio > timezone.now():
            delta = self.fecha_inicio - timezone.now()
            horas = delta.seconds // 3600
            minutos = (delta.seconds % 3600) // 60
            if delta.days > 0:
                return f"{delta.days} días"
            elif horas > 0:
                return f"{horas}h {minutos}m"
            else:
                return f"{minutos}m"
        return "Ya comenzó"

    @property
    def puede_cancelar(self):
        """Verifica si la reserva se puede cancelar"""
        from django.utils import timezone
        from datetime import timedelta

        if self.estado in ['Cancelada', 'Completada', 'No_Show']:
            return False

        # Permitir cancelación hasta 2 horas antes
        tiempo_limite = self.fecha_inicio - timedelta(hours=2)
        return timezone.now() < tiempo_limite

    @property
    def puede_crear_partido(self):
        """Verifica si se puede crear un partido desde esta reserva"""
        return (
                self.estado in ['Confirmada', 'En_Uso'] and
                not self.partido and
                self.jugador is not None
        )






