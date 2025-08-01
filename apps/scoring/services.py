# apps/scoring/services.py - VERSION COMPLETA ACTUALIZADA

from django.db import transaction
from django.utils import timezone
from .models import Partido, Set, Juego, Punto
import logging

logger = logging.getLogger(__name__)


class PadelScoringService:
    def __init__(self, partido_id):
        self.partido = Partido.objects.get(id=partido_id)

    @staticmethod
    def create_match(match_data):
        """Crear partido nuevo con estructura inicial"""
        with transaction.atomic():
            partido = Partido.objects.create(**match_data)

            # Crear primer set automáticamente
            primer_set = Set.objects.create(
                partido=partido,
                numero_set=1,
                finalizado=False
            )

            # Crear primer juego automáticamente
            Juego.objects.create(
                set=primer_set,
                numero_juego=1,
                finalizado=False,
                equipo_que_saca=1  # Empieza equipo 1
            )

            logger.info(f"Partido creado: {partido} con estructura inicial")
            return partido

    def start_match(self):
        """Iniciar partido"""
        with transaction.atomic():
            if self.partido.estado != 'Pendiente':
                raise ValueError("El partido ya fue iniciado")

            self.partido.estado = 'En Juego'
            self.partido.fecha_inicio = timezone.now()
            self.partido.save()

            logger.info(f"Partido iniciado: {self.partido}")
            return True

    def add_point(self, equipo_ganador, descripcion=''):
        """Agregar punto con información detallada de resultados"""
        with transaction.atomic():
            if self.partido.estado not in ['En Juego']:
                raise ValueError("El partido no está en progreso")

            if equipo_ganador not in [1, 2]:
                raise ValueError("equipo_ganador debe ser 1 o 2")

            # Obtener juego actual
            juego_actual = self._get_current_game()
            if not juego_actual:
                raise ValueError("No hay juego activo")

            # Crear punto
            numero_punto = juego_actual.puntos.count() + 1
            punto = Punto.objects.create(
                juego=juego_actual,
                equipo_ganador=equipo_ganador,
                numero_punto=numero_punto,
                descripcion=descripcion
            )

            # Actualizar puntos del juego
            if equipo_ganador == 1:
                juego_actual.puntos_equipo1 += 1
            else:
                juego_actual.puntos_equipo2 += 1

            juego_actual.save()

            # MEJORA: Crear objeto de resultado para tracking
            resultado = {
                'punto_agregado': True,
                'juego_finalizado': False,
                'set_finalizado': False,
                'partido_finalizado': False,
                'nuevo_juego_creado': False,
                'nuevo_set_creado': False,
                'ganador_juego': None,
                'ganador_set': None,
                'ganador_partido': None
            }

            # Verificar si se gana el juego
            if self._check_game_completion(juego_actual):
                ganador_juego = self._get_game_winner(juego_actual)
                self._complete_game(juego_actual, ganador_juego)

                resultado['juego_finalizado'] = True
                resultado['ganador_juego'] = ganador_juego

                # Verificar si se gana el set
                set_actual = juego_actual.set
                if self._check_set_completion(set_actual):
                    ganador_set = self._get_set_winner(set_actual)
                    self._complete_set(set_actual, ganador_set)

                    resultado['set_finalizado'] = True
                    resultado['ganador_set'] = ganador_set

                    # Verificar si se gana el partido
                    if self._check_match_completion():
                        self._complete_match()
                        resultado['partido_finalizado'] = True
                        resultado['ganador_partido'] = self.partido.equipo_ganador
                    else:
                        # Crear nuevo set
                        self._create_new_set()
                        resultado['nuevo_set_creado'] = True
                        resultado['nuevo_juego_creado'] = True
                else:
                    # Crear nuevo juego en el mismo set
                    self._create_new_game(set_actual)
                    resultado['nuevo_juego_creado'] = True

            # MEJORA: Logging y retorno detallado
            logger.info(f"Punto procesado: Equipo {equipo_ganador} - Resultado: {resultado}")
            return punto, resultado

    def undo_last_point(self):
        """Deshacer último punto con validaciones mejoradas"""
        with transaction.atomic():
            ultimo_punto = Punto.objects.filter(
                juego__set__partido=self.partido
            ).order_by('-timestamp').first()

            if not ultimo_punto:
                raise ValueError("No hay puntos para deshacer")

            juego = ultimo_punto.juego

            # MEJORA: Validar que el juego no esté finalizado
            if juego.finalizado:
                raise ValueError("No se puede deshacer un punto de un juego finalizado")

            # MEJORA: Validaciones de consistencia
            if ultimo_punto.equipo_ganador == 1:
                if juego.puntos_equipo1 <= 0:
                    raise ValueError("No se puede reducir más los puntos del equipo 1")
                juego.puntos_equipo1 -= 1
            else:
                if juego.puntos_equipo2 <= 0:
                    raise ValueError("No se puede reducir más los puntos del equipo 2")
                juego.puntos_equipo2 -= 1

            juego.save()
            ultimo_punto.delete()

            # MEJORA: Logging
            logger.info(f"Punto deshecho: Juego {juego} ahora {juego.puntos_equipo1}:{juego.puntos_equipo2}")
            return True

    def _get_current_game(self):
        """Obtener juego actual"""
        set_actual = self.partido.sets.filter(finalizado=False).first()
        if set_actual:
            return set_actual.juegos.filter(finalizado=False).first()
        return None

    def _check_game_completion(self, juego):
        """Verificar si el juego está completo"""
        p1, p2 = juego.puntos_equipo1, juego.puntos_equipo2

        # Juego normal (4 puntos y 2 de diferencia)
        if (p1 >= 4 or p2 >= 4) and abs(p1 - p2) >= 2:
            return True

        return False

    def _get_game_winner(self, juego):
        """Obtener ganador del juego"""
        return 1 if juego.puntos_equipo1 > juego.puntos_equipo2 else 2

    def _complete_game(self, juego, ganador):
        """Finalizar juego"""
        juego.finalizado = True
        juego.equipo_ganador = ganador
        juego.fecha_fin = timezone.now()
        juego.save()

        # Actualizar juegos del set
        set_obj = juego.set
        if ganador == 1:
            set_obj.juegos_equipo1 += 1
        else:
            set_obj.juegos_equipo2 += 1

        set_obj.save()
        logger.info(f"Juego completado: {juego} - Ganador: Equipo {ganador}")

    def _check_set_completion(self, set_obj):
        """Verificar si el set está completo"""
        j1, j2 = set_obj.juegos_equipo1, set_obj.juegos_equipo2

        # Set normal (6 juegos y 2 de diferencia)
        if (j1 >= 6 or j2 >= 6) and abs(j1 - j2) >= 2:
            return True

        return False

    def _get_set_winner(self, set_obj):
        """Obtener ganador del set"""
        return 1 if set_obj.juegos_equipo1 > set_obj.juegos_equipo2 else 2

    def _complete_set(self, set_obj, ganador):
        """Finalizar set"""
        set_obj.finalizado = True
        set_obj.equipo_ganador = ganador
        set_obj.fecha_fin = timezone.now()
        set_obj.save()
        logger.info(f"Set completado: {set_obj} - Ganador: Equipo {ganador}")

    def _check_match_completion(self):
        """Verificar si el partido está completo"""
        sets_ganados_1 = self.partido.sets.filter(equipo_ganador=1).count()
        sets_ganados_2 = self.partido.sets.filter(equipo_ganador=2).count()

        return (sets_ganados_1 >= self.partido.sets_para_ganar or
                sets_ganados_2 >= self.partido.sets_para_ganar)

    def _complete_match(self):
        """Finalizar partido"""
        sets_ganados_1 = self.partido.sets.filter(equipo_ganador=1).count()
        sets_ganados_2 = self.partido.sets.filter(equipo_ganador=2).count()

        self.partido.estado = 'Finalizado'
        self.partido.fecha_fin = timezone.now()
        self.partido.equipo_ganador = 1 if sets_ganados_1 > sets_ganados_2 else 2
        self.partido.save()
        logger.info(f"Partido completado: {self.partido} - Ganador: Equipo {self.partido.equipo_ganador}")

    def _create_new_set(self):
        """Crear nuevo set con primer juego"""
        ultimo_set = self.partido.sets.order_by('-numero_set').first()
        nuevo_numero = ultimo_set.numero_set + 1 if ultimo_set else 1

        nuevo_set = Set.objects.create(
            partido=self.partido,
            numero_set=nuevo_numero,
            finalizado=False
        )

        # Crear primer juego del nuevo set
        self._create_new_game(nuevo_set)
        logger.info(f"Nuevo set creado: {nuevo_set}")
        return nuevo_set

    def _create_new_game(self, set_obj):
        """Crear nuevo juego"""
        ultimo_juego = set_obj.juegos.order_by('-numero_juego').first()
        nuevo_numero = ultimo_juego.numero_juego + 1 if ultimo_juego else 1

        # Alternar quien saca
        equipo_saca = 2 if ultimo_juego and ultimo_juego.equipo_que_saca == 1 else 1

        nuevo_juego = Juego.objects.create(
            set=set_obj,
            numero_juego=nuevo_numero,
            finalizado=False,
            equipo_que_saca=equipo_saca
        )

        logger.info(f"Nuevo juego creado: {nuevo_juego}")
        return nuevo_juego

    def get_live_score(self):
        """Obtener marcador en vivo con información completa"""
        set_actual = self.partido.sets.filter(finalizado=False).first()
        juego_actual = self._get_current_game()

        # Contar sets ganados
        sets_ganados_1 = self.partido.sets.filter(equipo_ganador=1).count()
        sets_ganados_2 = self.partido.sets.filter(equipo_ganador=2).count()

        # MEJORA: Información completa de todos los sets
        sets_info = []
        for set_obj in self.partido.sets.all().order_by('numero_set'):
            sets_info.append({
                'numero': set_obj.numero_set,
                'juegos_equipo1': set_obj.juegos_equipo1,
                'juegos_equipo2': set_obj.juegos_equipo2,
                'finalizado': set_obj.finalizado,
                'ganador': set_obj.equipo_ganador
            })

        return {
            'partido_id': str(self.partido.id),
            'estado': self.partido.estado,
            'modalidad': self.partido.modalidad,
            'equipo1': self.partido.equipo1_nombre,
            'equipo2': self.partido.equipo2_nombre,
            'sets': {
                'equipo1': sets_ganados_1,
                'equipo2': sets_ganados_2
            },
            'sets_detalle': sets_info,
            'set_actual': {
                'numero': set_actual.numero_set if set_actual else None,
                'juegos_equipo1': set_actual.juegos_equipo1 if set_actual else 0,
                'juegos_equipo2': set_actual.juegos_equipo2 if set_actual else 0,
                'finalizado': set_actual.finalizado if set_actual else True
            },
            'juego_actual': {
                'numero': juego_actual.numero_juego if juego_actual else None,
                'puntos_equipo1': juego_actual.puntos_equipo1 if juego_actual else 0,
                'puntos_equipo2': juego_actual.puntos_equipo2 if juego_actual else 0,
                'puntos_display_1': juego_actual.puntos_display_equipo1 if juego_actual else "0",
                'puntos_display_2': juego_actual.puntos_display_equipo2 if juego_actual else "0",
                'equipo_saca': juego_actual.equipo_que_saca if juego_actual else None,
                'finalizado': juego_actual.finalizado if juego_actual else True
            },
            'ganador': self.partido.equipo_ganador if self.partido.estado == 'Finalizado' else None,
            'total_puntos': Punto.objects.filter(juego__set__partido=self.partido).count()
        }

    # ===== MÉTODOS NUEVOS MEJORADOS =====

    def get_match_summary(self):
        """Obtener resumen completo del partido"""
        resumen = self.get_live_score()

        # Agregar estadísticas adicionales
        resumen.update({
            'fecha_inicio': self.partido.fecha_inicio,
            'fecha_fin': self.partido.fecha_fin,
            'duracion': None,
            'sets_jugados': self.partido.sets.count(),
            'juegos_totales': Juego.objects.filter(set__partido=self.partido).count(),
            'puntos_totales': Punto.objects.filter(juego__set__partido=self.partido).count()
        })

        if self.partido.fecha_inicio and self.partido.fecha_fin:
            resumen['duracion'] = self.partido.fecha_fin - self.partido.fecha_inicio

        return resumen

    def validate_match_state(self):
        """Validar que el estado del partido sea consistente"""
        errores = []

        # Verificar sets
        sets_activos = self.partido.sets.filter(finalizado=False)
        if sets_activos.count() > 1:
            errores.append("Hay múltiples sets activos")

        if self.partido.estado == 'Finalizado' and sets_activos.exists():
            errores.append("Partido finalizado pero hay sets activos")

        if self.partido.estado == 'En Juego' and not sets_activos.exists():
            errores.append("Partido en juego pero no hay sets activos")

        # Verificar juegos
        for set_obj in self.partido.sets.all():
            juegos_activos = set_obj.juegos.filter(finalizado=False)

            if set_obj.finalizado and juegos_activos.exists():
                errores.append(f"Set {set_obj.numero_set} finalizado pero tiene juegos activos")

            if not set_obj.finalizado and juegos_activos.count() != 1:
                errores.append(
                    f"Set {set_obj.numero_set} debería tener exactamente 1 juego activo, tiene {juegos_activos.count()}")

        return errores

    def get_detailed_score_history(self):
        """Obtener historial detallado de puntuación"""
        historial = []

        for set_obj in self.partido.sets.all().order_by('numero_set'):
            set_data = {
                'set_numero': set_obj.numero_set,
                'resultado_final': f"{set_obj.juegos_equipo1}-{set_obj.juegos_equipo2}",
                'ganador': set_obj.equipo_ganador,
                'finalizado': set_obj.finalizado,
                'juegos': []
            }

            for juego in set_obj.juegos.all().order_by('numero_juego'):
                juego_data = {
                    'juego_numero': juego.numero_juego,
                    'resultado_final': f"{juego.puntos_display_equipo1}-{juego.puntos_display_equipo2}",
                    'ganador': juego.equipo_ganador,
                    'finalizado': juego.finalizado,
                    'equipo_saque': juego.equipo_que_saca,
                    'puntos': []
                }

                for punto in juego.puntos.all().order_by('numero_punto'):
                    juego_data['puntos'].append({
                        'numero': punto.numero_punto,
                        'ganador': punto.equipo_ganador,
                        'descripcion': punto.descripcion,
                        'timestamp': punto.timestamp
                    })

                set_data['juegos'].append(juego_data)

            historial.append(set_data)

        return historial

    # ===== MÉTODOS ESTÁTICOS PARA USAR SIN INSTANCIA =====

    @staticmethod
    def procesar_punto_simple(juego, equipo_ganador, descripcion=""):
        """Método simple para procesar un punto directamente (sin lógica completa)"""
        with transaction.atomic():
            # Crear punto
            numero_punto = juego.puntos.count() + 1
            punto = Punto.objects.create(
                juego=juego,
                equipo_ganador=equipo_ganador,
                numero_punto=numero_punto,
                descripcion=descripcion
            )

            # Actualizar puntos
            if equipo_ganador == 1:
                juego.puntos_equipo1 += 1
            else:
                juego.puntos_equipo2 += 1

            juego.save()

            return {
                'punto_creado': True,
                'juego_actual': {
                    'puntos_equipo1': juego.puntos_equipo1,
                    'puntos_equipo2': juego.puntos_equipo2,
                    'display_equipo1': juego.puntos_display_equipo1,
                    'display_equipo2': juego.puntos_display_equipo2
                }
            }

    @staticmethod
    def get_estado_partido_simple(partido):
        """Obtener estado simple del partido"""
        set_actual = partido.sets.filter(finalizado=False).first()
        juego_actual = set_actual.juegos.filter(finalizado=False).first() if set_actual else None

        return {
            'partido': str(partido),
            'estado': partido.estado,
            'set_actual': f"Set {set_actual.numero_set}: {set_actual.juegos_equipo1}-{set_actual.juegos_equipo2}" if set_actual else "No hay set activo",
            'juego_actual': f"Juego {juego_actual.numero_juego}: {juego_actual.puntos_display_equipo1}-{juego_actual.puntos_display_equipo2}" if juego_actual else "No hay juego activo"
        }

    @staticmethod
    def get_active_matches():
        """Obtener todos los partidos activos con su estado"""
        partidos_activos = []

        for partido in Partido.objects.filter(estado='En Juego'):
            try:
                servicio = PadelScoringService(partido.id)
                estado = servicio.get_live_score()
                partidos_activos.append(estado)
            except Exception as e:
                logger.error(f"Error obteniendo estado de {partido}: {str(e)}")
                # Agregar partido con error
                partidos_activos.append({
                    'partido_id': str(partido.id),
                    'estado': 'Error',
                    'error': str(e),
                    'equipo1': partido.equipo1_nombre,
                    'equipo2': partido.equipo2_nombre
                })

        return partidos_activos

    @staticmethod
    def get_match_statistics(partido_id):
        """Obtener estadísticas específicas de un partido"""
        try:
            partido = Partido.objects.get(id=partido_id)
        except Partido.DoesNotExist:
            return {'error': 'Partido no encontrado'}

        # Estadísticas por equipo
        puntos_equipo1 = Punto.objects.filter(
            juego__set__partido=partido,
            equipo_ganador=1
        ).count()

        puntos_equipo2 = Punto.objects.filter(
            juego__set__partido=partido,
            equipo_ganador=2
        ).count()

        # Juegos ganados por equipo
        juegos_equipo1 = Juego.objects.filter(
            set__partido=partido,
            equipo_ganador=1
        ).count()

        juegos_equipo2 = Juego.objects.filter(
            set__partido=partido,
            equipo_ganador=2
        ).count()

        # Sets ganados por equipo
        sets_equipo1 = partido.sets.filter(equipo_ganador=1).count()
        sets_equipo2 = partido.sets.filter(equipo_ganador=2).count()

        return {
            'partido_id': str(partido.id),
            'partido': str(partido),
            'estado': partido.estado,
            'estadisticas': {
                'puntos': {
                    'equipo1': puntos_equipo1,
                    'equipo2': puntos_equipo2,
                    'total': puntos_equipo1 + puntos_equipo2
                },
                'juegos': {
                    'equipo1': juegos_equipo1,
                    'equipo2': juegos_equipo2,
                    'total': juegos_equipo1 + juegos_equipo2
                },
                'sets': {
                    'equipo1': sets_equipo1,
                    'equipo2': sets_equipo2,
                    'total': sets_equipo1 + sets_equipo2
                }
            },
            'porcentajes': {
                'puntos_equipo1': round((puntos_equipo1 / (puntos_equipo1 + puntos_equipo2)) * 100, 1) if (
                                                                                                                      puntos_equipo1 + puntos_equipo2) > 0 else 0,
                'juegos_equipo1': round((juegos_equipo1 / (juegos_equipo1 + juegos_equipo2)) * 100, 1) if (
                                                                                                                      juegos_equipo1 + juegos_equipo2) > 0 else 0
            }
        }