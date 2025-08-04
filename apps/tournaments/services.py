# apps/tournaments/services.py

from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, Sum
from .models import (
    Torneo, InscripcionTorneo, FaseTorneo,
    GrupoTorneo, PartidoTorneo, ClasificacionTorneo
)
from apps.scoring.models import Partido
import random
import math
import logging

logger = logging.getLogger(__name__)


class TournamentService:
    """Servicio principal para gestión de torneos"""

    def __init__(self, torneo):
        self.torneo = torneo

    def validate_can_start(self):
        """Valida si el torneo puede iniciar"""
        errors = []

        # Validar estado
        if self.torneo.estado != 'Preparacion':
            errors.append("El torneo debe estar en estado 'Preparación'")

        # Validar participantes
        confirmados = self.torneo.inscripciones.filter(estado='Confirmada').count()
        if confirmados < self.torneo.min_participantes:
            errors.append(f"Mínimo {self.torneo.min_participantes} participantes, hay {confirmados}")

        # Validar canchas
        if not self.torneo.canchas.exists():
            errors.append("Debe asignar al menos una cancha al torneo")

        # Validar fases creadas
        if not self.torneo.fases.exists():
            errors.append("Debe generar el sorteo primero")

        return errors

    def generate_draw(self):
        """Genera el sorteo completo del torneo"""
        with transaction.atomic():
            if self.torneo.estado != 'Preparacion':
                raise ValueError("El torneo debe estar en preparación para generar sorteo")

            # Limpiar sorteo anterior si existe
            self.torneo.fases.all().delete()

            # Obtener inscripciones confirmadas
            inscripciones = list(
                self.torneo.inscripciones.filter(estado='Confirmada')
                .order_by('ranking_inicial', '?')  # Por ranking, luego aleatorio
            )

            if len(inscripciones) < self.torneo.min_participantes:
                raise ValueError(f"Insuficientes participantes: {len(inscripciones)}")

            # Generar según tipo de torneo
            if self.torneo.tipo == 'Eliminacion':
                self._generate_elimination_draw(inscripciones)
            elif self.torneo.tipo == 'Ranking':
                self._generate_ranking_draw(inscripciones)
            elif self.torneo.tipo == 'Grupos':
                self._generate_groups_draw(inscripciones)

            logger.info(f"Sorteo generado para torneo {self.torneo.nombre}")
            return True

    def _generate_elimination_draw(self, inscripciones):
        """Genera llave de eliminación directa"""
        n_participantes = len(inscripciones)

        # Calcular siguiente potencia de 2
        n_rondas = math.ceil(math.log2(n_participantes))
        n_bracket = 2 ** n_rondas

        # Crear fase de eliminación
        fase = FaseTorneo.objects.create(
            torneo=self.torneo,
            tipo='Eliminacion',
            nombre='Eliminación Directa',
            orden=1,
            numero_ronda=n_rondas
        )

        # Mezclar participantes respetando sembrados
        participantes_bracket = self._seed_participants(inscripciones, n_bracket)

        # Crear partidos recursivamente
        self._create_elimination_bracket(
            fase, participantes_bracket, n_rondas, n_rondas
        )

        # Crear partido por 3er lugar si hay suficientes participantes
        if n_participantes >= 4:
            FaseTorneo.objects.create(
                torneo=self.torneo,
                tipo='Clasificacion',
                nombre='3er y 4to Lugar',
                orden=2,
                numero_ronda=1
            )

    def _seed_participants(self, inscripciones, bracket_size):
        """Distribuye participantes en bracket respetando sembrados"""
        # Separar sembrados y no sembrados
        sembrados = [i for i in inscripciones if i.ranking_inicial]
        no_sembrados = [i for i in inscripciones if not i.ranking_inicial]

        # Ordenar sembrados
        sembrados.sort(key=lambda x: x.ranking_inicial)

        # Mezclar no sembrados
        random.shuffle(no_sembrados)

        # Crear bracket con None para byes
        bracket = [None] * bracket_size

        # Colocar sembrados en posiciones específicas
        # (1 vs último, 2 vs penúltimo en cuartos opuestos, etc.)
        if len(sembrados) > 0:
            positions = self._get_seed_positions(bracket_size)
            for i, inscripcion in enumerate(sembrados[:len(positions)]):
                bracket[positions[i]] = inscripcion

        # Llenar resto con no sembrados
        empty_positions = [i for i, x in enumerate(bracket) if x is None]
        for i, inscripcion in enumerate(no_sembrados):
            if i < len(empty_positions):
                bracket[empty_positions[i]] = inscripcion

        # Agregar el resto de inscripciones sembradas si hay
        for inscripcion in sembrados[len(positions):]:
            for i, x in enumerate(bracket):
                if x is None:
                    bracket[i] = inscripcion
                    break

        return bracket

    def _get_seed_positions(self, bracket_size):
        """Obtiene posiciones para sembrados en el bracket"""
        if bracket_size == 2:
            return [0, 1]
        elif bracket_size == 4:
            return [0, 3, 1, 2]
        elif bracket_size == 8:
            return [0, 7, 3, 4, 1, 6, 2, 5]
        elif bracket_size == 16:
            return [0, 15, 7, 8, 3, 12, 4, 11, 1, 14, 6, 9, 2, 13, 5, 10]
        else:
            # Para brackets más grandes, distribuir uniformemente
            positions = [0, bracket_size - 1]
            for i in range(2, min(bracket_size, 16)):
                positions.append(i - 1)
            return positions

    def _create_elimination_bracket(self, fase, participantes, ronda_actual, total_rondas):
        """Crea bracket de eliminación recursivamente"""
        n_partidos = len(participantes) // 2
        partidos_ronda = []

        # Crear partidos de esta ronda
        for i in range(n_partidos):
            idx1 = i * 2
            idx2 = i * 2 + 1

            partido = PartidoTorneo.objects.create(
                torneo=self.torneo,
                fase=fase,
                inscripcion_equipo1=participantes[idx1],
                inscripcion_equipo2=participantes[idx2],
                orden_en_fase=self._get_match_order(ronda_actual, i, total_rondas),
                tipo='Regular'
            )
            partidos_ronda.append(partido)

        # Si no es la final, crear siguiente ronda
        if ronda_actual > 1:
            # Crear placeholders para siguiente ronda
            siguiente_ronda = [None] * n_partidos

            # Crear partidos de siguiente ronda recursivamente
            partidos_siguiente = self._create_elimination_bracket(
                fase, siguiente_ronda, ronda_actual - 1, total_rondas
            )

            # Conectar partidos
            for i, partido in enumerate(partidos_ronda):
                partido_siguiente = partidos_siguiente[i // 2]
                partido.siguiente_partido = partido_siguiente
                partido.es_lado_equipo1 = (i % 2 == 0)
                partido.save()

        return partidos_ronda

    def _get_match_order(self, ronda, posicion, total_rondas):
        """Calcula el orden del partido en la fase"""
        # Los partidos se ordenan desde la final (orden 1) hacia atrás
        base = sum(2 ** i for i in range(1, total_rondas - ronda + 1))
        return base + posicion + 1

    def _generate_ranking_draw(self, inscripciones):
        """Genera torneo tipo ranking (todos contra todos)"""
        # Crear fase única
        fase = FaseTorneo.objects.create(
            torneo=self.torneo,
            tipo='Eliminacion',  # Usamos este tipo pero es round-robin
            nombre='Liga - Todos contra Todos',
            orden=1
        )

        # Crear todos los partidos posibles
        orden = 1
        for i, equipo1 in enumerate(inscripciones):
            for equipo2 in inscripciones[i + 1:]:
                PartidoTorneo.objects.create(
                    torneo=self.torneo,
                    fase=fase,
                    inscripcion_equipo1=equipo1,
                    inscripcion_equipo2=equipo2,
                    orden_en_fase=orden,
                    tipo='Regular'
                )
                orden += 1

        logger.info(f"Creados {orden - 1} partidos para torneo ranking")

    def _generate_groups_draw(self, inscripciones):
        """Genera fase de grupos + eliminación"""
        if not self.torneo.numero_grupos:
            raise ValueError("Debe especificar número de grupos")

        # Fase 1: Grupos
        fase_grupos = FaseTorneo.objects.create(
            torneo=self.torneo,
            tipo='Grupos',
            nombre='Fase de Grupos',
            orden=1
        )

        # Distribuir equipos en grupos
        grupos = self._distribute_in_groups(inscripciones, self.torneo.numero_grupos)

        # Crear grupos y partidos
        for letra, equipos in grupos.items():
            grupo = GrupoTorneo.objects.create(
                fase=fase_grupos,
                nombre=f"Grupo {letra}"
            )
            grupo.inscripciones.set(equipos)

            # Crear partidos del grupo (todos contra todos)
            orden = 1
            for i, equipo1 in enumerate(equipos):
                for equipo2 in equipos[i + 1:]:
                    PartidoTorneo.objects.create(
                        torneo=self.torneo,
                        fase=fase_grupos,
                        grupo=grupo,
                        inscripcion_equipo1=equipo1,
                        inscripcion_equipo2=equipo2,
                        orden_en_fase=orden,
                        tipo='Regular'
                    )
                    orden += 1

        # Fase 2: Eliminación (se creará cuando terminen los grupos)
        # Por ahora solo creamos la fase vacía
        FaseTorneo.objects.create(
            torneo=self.torneo,
            tipo='Eliminacion',
            nombre='Fase Eliminatoria',
            orden=2,
            activa=False
        )

    def _distribute_in_groups(self, inscripciones, n_grupos):
        """Distribuye equipos en grupos equilibradamente"""
        # Separar por ranking
        sembrados = [i for i in inscripciones if i.ranking_inicial]
        no_sembrados = [i for i in inscripciones if not i.ranking_inicial]

        sembrados.sort(key=lambda x: x.ranking_inicial)
        random.shuffle(no_sembrados)

        # Crear grupos vacíos
        grupos = {}
        for i in range(n_grupos):
            grupos[chr(65 + i)] = []  # A, B, C, etc.

        # Distribuir sembrados en serpentín
        grupo_idx = 0
        direccion = 1
        for inscripcion in sembrados:
            grupos[chr(65 + grupo_idx)].append(inscripcion)
            grupo_idx += direccion
            if grupo_idx == n_grupos or grupo_idx == -1:
                direccion *= -1
                grupo_idx += direccion

        # Distribuir no sembrados
        for i, inscripcion in enumerate(no_sembrados):
            grupo_letra = chr(65 + (i % n_grupos))
            grupos[grupo_letra].append(inscripcion)

        return grupos

    def start_tournament(self):
        """Inicia el torneo"""
        with transaction.atomic():
            errors = self.validate_can_start()
            if errors:
                raise ValueError(f"No se puede iniciar: {', '.join(errors)}")

            # Cambiar estado
            self.torneo.estado = 'En_Curso'
            self.torneo.save()

            # Activar primera fase
            primera_fase = self.torneo.fases.order_by('orden').first()
            if primera_fase:
                primera_fase.activa = True
                primera_fase.save()

            logger.info(f"Torneo {self.torneo.nombre} iniciado")
            return True

    def process_phase_completion(self, fase):
        """Procesa la finalización de una fase"""
        with transaction.atomic():
            # Verificar que todos los partidos estén completos
            partidos_pendientes = fase.partidos.filter(
                Q(partido__isnull=True) | ~Q(partido__estado='Finalizado')
            ).count()

            if partidos_pendientes > 0:
                raise ValueError(f"Aún hay {partidos_pendientes} partidos pendientes")

            # Marcar fase como completada
            fase.completada = True
            fase.activa = False
            fase.save()

            # Procesar según tipo de torneo
            if self.torneo.tipo == 'Grupos' and fase.tipo == 'Grupos':
                self._process_groups_to_elimination(fase)

            # Activar siguiente fase si existe
            siguiente_fase = self.torneo.fases.filter(
                orden__gt=fase.orden
            ).order_by('orden').first()

            if siguiente_fase:
                siguiente_fase.activa = True
                siguiente_fase.save()
            else:
                # Torneo finalizado
                self._finalize_tournament()

    def _process_groups_to_elimination(self, fase_grupos):
        """Procesa el paso de grupos a eliminación"""
        # Obtener clasificados de cada grupo
        clasificados = []

        for grupo in fase_grupos.grupos.all():
            tabla = grupo.get_tabla_posiciones()
            # Tomar los que clasifican
            for i in range(min(self.torneo.clasifican_por_grupo, len(tabla))):
                clasificados.append({
                    'inscripcion': tabla[i]['inscripcion'],
                    'grupo': grupo.nombre,
                    'posicion': i + 1,
                    'puntos': tabla[i]['puntos']
                })

        # Ordenar clasificados para el bracket
        # (1° del A vs 2° del B, etc.)
        clasificados.sort(key=lambda x: (x['posicion'], -x['puntos']))

        # Obtener fase de eliminación
        fase_eliminacion = self.torneo.fases.filter(tipo='Eliminacion').first()
        if not fase_eliminacion:
            raise ValueError("No se encontró fase de eliminación")

        # Crear bracket de eliminación
        inscripciones = [c['inscripcion'] for c in clasificados]
        n_rondas = math.ceil(math.log2(len(inscripciones)))

        self._create_elimination_bracket(
            fase_eliminacion, inscripciones, n_rondas, n_rondas
        )

    def _finalize_tournament(self):
        """Finaliza el torneo y genera clasificaciones"""
        with transaction.atomic():
            self.torneo.estado = 'Finalizado'
            self.torneo.fecha_fin = timezone.now()
            self.torneo.save()

            # Generar clasificaciones finales
            clasificaciones = self._calculate_final_standings()

            for posicion, data in enumerate(clasificaciones, 1):
                ClasificacionTorneo.objects.create(
                    torneo=self.torneo,
                    inscripcion=data['inscripcion'],
                    posicion_final=posicion,
                    partidos_jugados=data['partidos_jugados'],
                    partidos_ganados=data['partidos_ganados'],
                    partidos_perdidos=data['partidos_perdidos'],
                    sets_ganados=data['sets_ganados'],
                    sets_perdidos=data['sets_perdidos'],
                    juegos_ganados=data['juegos_ganados'],
                    juegos_perdidos=data['juegos_perdidos']
                )

            logger.info(f"Torneo {self.torneo.nombre} finalizado")

    def _calculate_final_standings(self):
        """Calcula las posiciones finales"""
        standings = []

        for inscripcion in self.torneo.inscripciones.filter(estado='Confirmada'):
            stats = {
                'inscripcion': inscripcion,
                'partidos_jugados': 0,
                'partidos_ganados': 0,
                'partidos_perdidos': 0,
                'sets_ganados': 0,
                'sets_perdidos': 0,
                'juegos_ganados': 0,
                'juegos_perdidos': 0,
                'ultima_ronda': 0  # Para eliminación
            }

            # Obtener todos los partidos
            partidos = PartidoTorneo.objects.filter(
                Q(inscripcion_equipo1=inscripcion) | Q(inscripcion_equipo2=inscripcion),
                partido__estado='Finalizado'
            )

            for partido_torneo in partidos:
                partido = partido_torneo.partido
                es_equipo1 = partido_torneo.inscripcion_equipo1 == inscripcion

                stats['partidos_jugados'] += 1

                # Ganó o perdió
                if (es_equipo1 and partido.equipo_ganador == 1) or \
                        (not es_equipo1 and partido.equipo_ganador == 2):
                    stats['partidos_ganados'] += 1
                else:
                    stats['partidos_perdidos'] += 1

                # Estadísticas detalladas
                for set_obj in partido.sets.all():
                    if es_equipo1:
                        if set_obj.equipo_ganador == 1:
                            stats['sets_ganados'] += 1
                        else:
                            stats['sets_perdidos'] += 1
                        stats['juegos_ganados'] += set_obj.juegos_equipo1
                        stats['juegos_perdidos'] += set_obj.juegos_equipo2
                    else:
                        if set_obj.equipo_ganador == 2:
                            stats['sets_ganados'] += 1
                        else:
                            stats['sets_perdidos'] += 1
                        stats['juegos_ganados'] += set_obj.juegos_equipo2
                        stats['juegos_perdidos'] += set_obj.juegos_equipo1

                # Para eliminación: en qué ronda quedó
                if partido_torneo.fase.tipo == 'Eliminacion':
                    stats['ultima_ronda'] = max(
                        stats['ultima_ronda'],
                        partido_torneo.fase.numero_ronda or 0
                    )

            standings.append(stats)

        # Ordenar según tipo de torneo
        if self.torneo.tipo == 'Ranking':
            # Por puntos (victorias), luego diferencias
            standings.sort(
                key=lambda x: (
                    x['partidos_ganados'],
                    x['sets_ganados'] - x['sets_perdidos'],
                    x['juegos_ganados'] - x['juegos_perdidos']
                ),
                reverse=True
            )
        else:
            # Por ronda alcanzada, luego estadísticas
            standings.sort(
                key=lambda x: (
                    x['ultima_ronda'],
                    x['partidos_ganados'],
                    x['sets_ganados'] - x['sets_perdidos']
                ),
                reverse=True
            )

        return standings

    def get_tournament_status(self):
        """Obtiene el estado actual del torneo"""
        status = {
            'estado': self.torneo.get_estado_display(),
            'participantes': self.torneo.participantes_registrados,
            'fase_actual': None,
            'partidos_totales': 0,
            'partidos_jugados': 0,
            'partidos_en_curso': 0,
            'partidos_pendientes': 0,
            'total_fases': self.torneo.fases.count(),
            'fases_completadas': self.torneo.fases.filter(completada=True).count()
        }

        # Fase actual
        fase_activa = self.torneo.fases.filter(activa=True).first()
        if fase_activa:
            status['fase_actual'] = fase_activa.nombre

        # Estadísticas de partidos
        partidos = PartidoTorneo.objects.filter(torneo=self.torneo)
        status['partidos_totales'] = partidos.count()

        for partido in partidos:
            if partido.partido:
                if partido.partido.estado == 'Finalizado':
                    status['partidos_jugados'] += 1
                elif partido.partido.estado == 'En Juego':
                    status['partidos_en_curso'] += 1
                else:
                    status['partidos_pendientes'] += 1
            else:
                status['partidos_pendientes'] += 1

        # Líderes actuales (top 3)
        if self.torneo.estado in ['En_Curso', 'Finalizado']:
            if self.torneo.estado == 'Finalizado':
                clasificaciones = ClasificacionTorneo.objects.filter(
                    torneo=self.torneo
                ).order_by('posicion_final')[:3]

                status['lideres'] = [
                    {
                        'posicion': c.posicion_final,
                        'nombre': c.inscripcion.nombre_equipo,
                        'pg': c.partidos_ganados,
                        'pp': c.partidos_perdidos
                    }
                    for c in clasificaciones
                ]
            else:
                # Calcular líderes actuales
                standings = self._calculate_current_standings()[:3]
                status['lideres'] = [
                    {
                        'posicion': i + 1,
                        'nombre': s['inscripcion'].nombre_equipo,
                        'pg': s['partidos_ganados'],
                        'pp': s['partidos_perdidos']
                    }
                    for i, s in enumerate(standings)
                ]

        return status

    def _calculate_current_standings(self):
        """Calcula standings actuales (versión simplificada)"""
        standings = []

        for inscripcion in self.torneo.inscripciones.filter(estado='Confirmada'):
            stats = {
                'inscripcion': inscripcion,
                'partidos_ganados': 0,
                'partidos_perdidos': 0
            }

            partidos = PartidoTorneo.objects.filter(
                Q(inscripcion_equipo1=inscripcion) | Q(inscripcion_equipo2=inscripcion),
                partido__estado='Finalizado'
            )

            for partido_torneo in partidos:
                es_equipo1 = partido_torneo.inscripcion_equipo1 == inscripcion
                if (es_equipo1 and partido_torneo.partido.equipo_ganador == 1) or \
                        (not es_equipo1 and partido_torneo.partido.equipo_ganador == 2):
                    stats['partidos_ganados'] += 1
                else:
                    stats['partidos_perdidos'] += 1

            standings.append(stats)

        standings.sort(key=lambda x: x['partidos_ganados'], reverse=True)
        return standings

    def schedule_matches(self, fecha_inicio, canchas_disponibles, partidos_por_dia=8):
        """Programa automáticamente los partidos del torneo"""
        with transaction.atomic():
            # Obtener partidos sin programar
            partidos = PartidoTorneo.objects.filter(
                torneo=self.torneo,
                fecha_programada__isnull=True
            ).order_by('fase__orden', 'orden_en_fase')

            if not partidos:
                return 0

            # Variables de programación
            fecha_actual = fecha_inicio
            partidos_dia_actual = 0
            cancha_idx = 0
            programados = 0

            for partido in partidos:
                # Asignar cancha (rotar entre disponibles)
                if canchas_disponibles:
                    partido.cancha_asignada = canchas_disponibles[cancha_idx % len(canchas_disponibles)]
                    cancha_idx += 1

                # Asignar fecha y hora
                hora = 8 + (partidos_dia_actual * 2)  # Cada 2 horas
                partido.fecha_programada = fecha_actual.replace(hour=hora, minute=0)
                partido.save()

                programados += 1
                partidos_dia_actual += 1

                # Si alcanzamos el límite diario, pasar al siguiente día
                if partidos_dia_actual >= partidos_por_dia:
                    fecha_actual = fecha_actual + timezone.timedelta(days=1)
                    partidos_dia_actual = 0
                    cancha_idx = 0

            logger.info(f"Programados {programados} partidos para {self.torneo.nombre}")
            return programados