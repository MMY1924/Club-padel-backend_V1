# apps/tournaments/flow_services.py

from django.utils import timezone
from datetime import timedelta
from .models import Torneo, InscripcionTorneo, FaseTorneo, PartidoTorneo
from .services import TournamentService
import json


class TournamentFlowService:
    """Servicio para generar flujos visuales de torneos"""

    def __init__(self, torneo):
        self.torneo = torneo
        self.service = TournamentService(torneo)

    def get_tournament_flow(self):
        """Obtiene el flujo completo del torneo según su tipo"""
        flows = {
            'Eliminacion': self._get_elimination_flow(),
            'Ranking': self._get_ranking_flow(),
            'Grupos': self._get_groups_flow()
        }

        return flows.get(self.torneo.tipo, {})

    def _get_elimination_flow(self):
        """Flujo para torneo de eliminación directa"""
        participantes = self.torneo.participantes_registrados
        fases = self._calculate_elimination_rounds(participantes)

        flow = {
            'type': 'Eliminación Directa',
            'description': 'Sistema de eliminación directa - pierdes y sales del torneo',
            'icon': '🏆',
            'duration_estimate': self._estimate_duration(participantes, 'eliminacion'),
            'participants_info': {
                'registered': participantes,
                'max': self.torneo.max_participantes,
                'min': self.torneo.min_participantes
            },
            'phases': [
                {
                    'id': 1,
                    'name': 'Inscripción',
                    'description': 'Período de inscripción de equipos',
                    'status': self._get_phase_status('inscripcion'),
                    'details': [
                        f'Participantes: {participantes}/{self.torneo.max_participantes}',
                        f'Costo: ${self.torneo.costo_inscripcion:,.0f}',
                        f'Modalidad: {self.torneo.modalidad}',
                        f'Fecha límite: {self.torneo.fecha_inicio.strftime("%d/%m/%Y")}'
                    ],
                    'requirements': ['Mínimo 4 equipos', 'Pago confirmado', 'Jugadores válidos']
                },
                {
                    'id': 2,
                    'name': 'Sorteo y Bracket',
                    'description': 'Generación del bracket de eliminación',
                    'status': self._get_phase_status('sorteo'),
                    'details': [
                        f'Rondas necesarias: {len(fases)}',
                        f'Bracket size: {self._next_power_of_2(participantes)}',
                        'Sembrado por ranking',
                        'Byes automáticos'
                    ],
                    'bracket_info': fases
                },
                {
                    'id': 3,
                    'name': 'Fase Eliminatoria',
                    'description': 'Partidos de eliminación directa',
                    'status': self._get_phase_status('eliminatoria'),
                    'rounds': self._get_elimination_rounds_detail(fases),
                    'details': [
                        f'Total partidos: {sum(fase["partidos"] for fase in fases)}',
                        f'Sets para ganar: {self.torneo.sets_para_ganar}',
                        'Sin segundas oportunidades'
                    ]
                },
                {
                    'id': 4,
                    'name': 'Final y Premiación',
                    'description': 'Partido final y entrega de premios',
                    'status': self._get_phase_status('final'),
                    'details': [
                        'Partido por el campeonato',
                        'Partido por 3er lugar (opcional)',
                        'Ceremonia de premiación'
                    ]
                }
            ],
            'current_phase': self._get_current_phase(),
            'progress': self._calculate_progress()
        }

        return flow

    def _get_ranking_flow(self):
        """Flujo para torneo tipo ranking/liga"""
        participantes = self.torneo.participantes_registrados
        total_partidos = (participantes * (participantes - 1)) // 2

        flow = {
            'type': 'Liga/Ranking',
            'description': 'Todos contra todos - sistema de puntos',
            'icon': '📊',
            'duration_estimate': self._estimate_duration(participantes, 'ranking'),
            'participants_info': {
                'registered': participantes,
                'max': self.torneo.max_participantes,
                'min': self.torneo.min_participantes
            },
            'phases': [
                {
                    'id': 1,
                    'name': 'Inscripción',
                    'description': 'Período de inscripción de equipos',
                    'status': self._get_phase_status('inscripcion'),
                    'details': [
                        f'Participantes: {participantes}/{self.torneo.max_participantes}',
                        f'Cada equipo juega {participantes - 1} partidos',
                        f'Total partidos: {total_partidos}',
                        'Sistema de puntos: 3-1-0'
                    ]
                },
                {
                    'id': 2,
                    'name': 'Sorteo de Fixture',
                    'description': 'Generación del calendario de partidos',
                    'status': self._get_phase_status('sorteo'),
                    'details': [
                        'Todos contra todos',
                        'Programación equitativa',
                        'Distribución de canchas',
                        'Fechas balanceadas'
                    ]
                },
                {
                    'id': 3,
                    'name': 'Fase Regular',
                    'description': 'Desarrollo de la liga',
                    'status': self._get_phase_status('liga'),
                    'details': [
                        f'Total partidos: {total_partidos}',
                        'Victoria: 3 puntos',
                        'Derrota: 0 puntos',
                        'Tabla en tiempo real'
                    ],
                    'league_table': self._get_current_standings()
                },
                {
                    'id': 4,
                    'name': 'Clasificación Final',
                    'description': 'Determinación del campeón',
                    'status': self._get_phase_status('final'),
                    'details': [
                        'Criterio 1: Puntos',
                        'Criterio 2: Diferencia de sets',
                        'Criterio 3: Diferencia de juegos',
                        'Criterio 4: Enfrentamiento directo'
                    ]
                }
            ],
            'current_phase': self._get_current_phase(),
            'progress': self._calculate_progress(),
            'scoring_system': {
                'win': 3,
                'loss': 0,
                'tiebreakers': ['Puntos', 'Dif. Sets', 'Dif. Juegos', 'H2H']
            }
        }

        return flow

    def _get_groups_flow(self):
        """Flujo para torneo de grupos + eliminación"""
        participantes = self.torneo.participantes_registrados
        grupos = self.torneo.numero_grupos or 2
        clasifican = self.torneo.clasifican_por_grupo or 2

        flow = {
            'type': 'Grupos + Eliminación',
            'description': 'Fase de grupos seguida de eliminación directa',
            'icon': '🏟️',
            'duration_estimate': self._estimate_duration(participantes, 'grupos'),
            'participants_info': {
                'registered': participantes,
                'groups': grupos,
                'per_group': participantes // grupos,
                'qualify_per_group': clasifican
            },
            'phases': [
                {
                    'id': 1,
                    'name': 'Inscripción',
                    'description': 'Período de inscripción de equipos',
                    'status': self._get_phase_status('inscripcion'),
                    'details': [
                        f'Participantes: {participantes}/{self.torneo.max_participantes}',
                        f'Grupos: {grupos}',
                        f'Equipos por grupo: {participantes // grupos}',
                        f'Clasifican por grupo: {clasifican}'
                    ]
                },
                {
                    'id': 2,
                    'name': 'Sorteo de Grupos',
                    'description': 'Distribución de equipos en grupos',
                    'status': self._get_phase_status('sorteo'),
                    'details': [
                        'Sembrado por ranking',
                        'Distribución balanceada',
                        'Serpentín para equilibrio',
                        f'{grupos} grupos de {participantes // grupos} equipos'
                    ],
                    'groups_info': self._get_groups_composition()
                },
                {
                    'id': 3,
                    'name': 'Fase de Grupos',
                    'description': 'Todos contra todos en cada grupo',
                    'status': self._get_phase_status('grupos'),
                    'details': [
                        'Liga en cada grupo',
                        'Sistema de puntos 3-1-0',
                        f'Top {clasifican} clasifican',
                        'Tablas independientes'
                    ],
                    'groups_tables': self._get_groups_standings()
                },
                {
                    'id': 4,
                    'name': 'Fase Eliminatoria',
                    'description': 'Eliminación directa con clasificados',
                    'status': self._get_phase_status('eliminatoria'),
                    'details': [
                        f'{grupos * clasifican} equipos clasificados',
                        'Cruce entre grupos',
                        'Eliminación directa',
                        'Final entre ganadores'
                    ]
                },
                {
                    'id': 5,
                    'name': 'Final y Premiación',
                    'description': 'Definición del campeón',
                    'status': self._get_phase_status('final'),
                    'details': [
                        'Final entre ganadores',
                        'Partido por 3er lugar',
                        'Ceremonia de premiación'
                    ]
                }
            ],
            'current_phase': self._get_current_phase(),
            'progress': self._calculate_progress()
        }

        return flow

    def _calculate_elimination_rounds(self, participants):
        """Calcula las rondas necesarias para eliminación"""
        if participants < 2:
            return []

        import math
        rounds_needed = math.ceil(math.log2(participants))
        next_power = 2 ** rounds_needed

        rounds = []
        current_teams = next_power

        for round_num in range(rounds_needed, 0, -1):
            round_name = self._get_round_name(round_num, rounds_needed)
            matches = current_teams // 2

            rounds.append({
                'round': round_num,
                'name': round_name,
                'teams': current_teams,
                'partidos': matches,
                'eliminados': matches
            })

            current_teams = matches

        return rounds

    def _get_round_name(self, round_num, total_rounds):
        """Obtiene el nombre de la ronda"""
        if round_num == 1:
            return "Final"
        elif round_num == 2:
            return "Semifinal"
        elif round_num == 3:
            return "Cuartos de Final"
        elif round_num == 4:
            return "Octavos de Final"
        else:
            return f"Ronda {total_rounds - round_num + 1}"

    def _next_power_of_2(self, n):
        """Encuentra la siguiente potencia de 2"""
        import math
        return 2 ** math.ceil(math.log2(n))

    def _estimate_duration(self, participants, tournament_type):
        """Estima la duración del torneo"""
        if tournament_type == 'eliminacion':
            rounds = len(self._calculate_elimination_rounds(participants))
            return f"{rounds} días (aprox.)"
        elif tournament_type == 'ranking':
            total_matches = (participants * (participants - 1)) // 2
            days_needed = math.ceil(total_matches / 8)  # 8 partidos por día
            return f"{days_needed} días (aprox.)"
        elif tournament_type == 'grupos':
            group_days = 3  # Fase de grupos
            elimination_days = 2  # Fase eliminatoria
            return f"{group_days + elimination_days} días (aprox.)"

        return "Por determinar"

    def _get_phase_status(self, phase_name):
        """Obtiene el estado de una fase"""
        if self.torneo.estado == 'Inscripcion':
            return 'active' if phase_name == 'inscripcion' else 'pending'
        elif self.torneo.estado == 'Preparacion':
            if phase_name == 'inscripcion':
                return 'completed'
            elif phase_name == 'sorteo':
                return 'active'
            else:
                return 'pending'
        elif self.torneo.estado == 'En_Curso':
            if phase_name in ['inscripcion', 'sorteo']:
                return 'completed'
            elif phase_name in ['grupos', 'liga', 'eliminatoria']:
                return 'active'
            else:
                return 'pending'
        elif self.torneo.estado == 'Finalizado':
            return 'completed'

        return 'pending'

    def _get_current_phase(self):
        """Obtiene la fase actual del torneo"""
        if self.torneo.estado == 'Inscripcion':
            return {'id': 1, 'name': 'Inscripción'}
        elif self.torneo.estado == 'Preparacion':
            return {'id': 2, 'name': 'Sorteo'}
        elif self.torneo.estado == 'En_Curso':
            fase_activa = self.torneo.fases.filter(activa=True).first()
            if fase_activa:
                if fase_activa.tipo == 'Grupos':
                    return {'id': 3, 'name': 'Fase de Grupos'}
                elif fase_activa.tipo == 'Eliminacion':
                    return {'id': 4, 'name': 'Fase Eliminatoria'}
            return {'id': 3, 'name': 'En Desarrollo'}
        elif self.torneo.estado == 'Finalizado':
            return {'id': 5, 'name': 'Finalizado'}

        return {'id': 1, 'name': 'Iniciando'}

    def _calculate_progress(self):
        """Calcula el progreso del torneo"""
        estado = self.service.get_tournament_status()

        if estado['partidos_totales'] == 0:
            return 0

        progress = (estado['partidos_jugados'] / estado['partidos_totales']) * 100
        return round(progress, 1)

    def _get_elimination_rounds_detail(self, fases):
        """Obtiene detalles de las rondas eliminatorias"""
        rounds_detail = []

        for fase in fases:
            round_info = {
                'name': fase['name'],
                'teams_in': fase['teams'],
                'matches': fase['partidos'],
                'teams_out': fase['teams'] // 2,
                'status': 'pending'  # Se actualizaría según el estado real
            }
            rounds_detail.append(round_info)

        return rounds_detail

    def _get_current_standings(self):
        """Obtiene la tabla actual (para torneos de ranking)"""
        if self.torneo.tipo != 'Ranking':
            return []

        # Aquí iría la lógica para calcular la tabla actual
        # Por ahora retornamos una estructura vacía
        return []

    def _get_groups_composition(self):
        """Obtiene la composición de grupos"""
        if self.torneo.tipo != 'Grupos':
            return []

        groups = []
        fase_grupos = self.torneo.fases.filter(tipo='Grupos').first()

        if fase_grupos:
            for grupo in fase_grupos.grupos.all():
                group_info = {
                    'name': grupo.nombre,
                    'teams': [
                        inscripcion.nombre_equipo
                        for inscripcion in grupo.inscripciones.all()
                    ]
                }
                groups.append(group_info)

        return groups

    def _get_groups_standings(self):
        """Obtiene las tablas de los grupos"""
        if self.torneo.tipo != 'Grupos':
            return []

        tables = []
        fase_grupos = self.torneo.fases.filter(tipo='Grupos').first()

        if fase_grupos:
            for grupo in fase_grupos.grupos.all():
                table = grupo.get_tabla_posiciones()
                group_table = {
                    'group_name': grupo.nombre,
                    'standings': [
                        {
                            'position': i + 1,
                            'team': pos['inscripcion'].nombre_equipo,
                            'points': pos['puntos'],
                            'played': pos['partidos_jugados'],
                            'won': pos['partidos_ganados'],
                            'lost': pos['partidos_perdidos'],
                            'sets_diff': pos['diferencia_sets']
                        }
                        for i, pos in enumerate(table)
                    ]
                }
                tables.append(group_table)

        return tables


# VIEW HELPER FUNCTIONS

def get_tournament_flow_data(torneo_id):
    """Función helper para obtener datos de flujo desde las vistas"""
    try:
        torneo = Torneo.objects.get(id=torneo_id)
        flow_service = TournamentFlowService(torneo)
        return flow_service.get_tournament_flow()
    except Torneo.DoesNotExist:
        return {'error': 'Torneo no encontrado'}


def get_all_tournament_flows():
    """Obtiene flujos de ejemplo para todos los tipos de torneo"""
    flows = {
        'eliminacion': {
            'name': 'Eliminación Directa',
            'description': 'Sistema de eliminación directa - pierdes y sales',
            'ideal_for': ['Torneos rápidos', 'Pocos participantes', 'Eventos de un día'],
            'pros': ['Rápido', 'Emocionante', 'Fácil de seguir'],
            'cons': ['Una sola oportunidad', 'Algunos juegan poco'],
            'duration': '1-3 días',
            'complexity': 'Baja'
        },
        'ranking': {
            'name': 'Liga/Ranking',
            'description': 'Todos contra todos - sistema de puntos',
            'ideal_for': ['Torneos largos', 'Evaluar consistencia', 'Muchos partidos'],
            'pros': ['Justo', 'Muchos partidos', 'Tabla clara'],
            'cons': ['Largo', 'Puede ser predecible'],
            'duration': '1-4 semanas',
            'complexity': 'Media'
        },
        'grupos': {
            'name': 'Grupos + Eliminación',
            'description': 'Combina fase de grupos con eliminación directa',
            'ideal_for': ['Torneos grandes', 'Equilibrio justo/emocionante', 'Eventos importantes'],
            'pros': ['Equilibrado', 'Segunda oportunidad', 'Emocionante final'],
            'cons': ['Más complejo', 'Duración media'],
            'duration': '3-7 días',
            'complexity': 'Alta'
        }
    }

    return flows


def generate_tournament_recommendations(participants, duration_days, complexity_preference):
    """Genera recomendaciones de tipo de torneo"""
    recommendations = []

    if participants <= 8 and duration_days <= 2:
        recommendations.append({
            'type': 'eliminacion',
            'score': 95,
            'reason': 'Ideal para pocos participantes y tiempo limitado'
        })

    if participants >= 6 and duration_days >= 7:
        recommendations.append({
            'type': 'ranking',
            'score': 90,
            'reason': 'Permite que todos jueguen muchos partidos'
        })

    if participants >= 8 and duration_days >= 4:
        recommendations.append({
            'type': 'grupos',
            'score': 85,
            'reason': 'Equilibra justicia y emoción'
        })

    return sorted(recommendations, key=lambda x: x['score'], reverse=True)