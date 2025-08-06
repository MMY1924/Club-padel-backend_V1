from django.core.management.base import BaseCommand
from apps.tournaments.models import Torneo
from apps.tournaments.flow_services import TournamentFlowService
import json


class Command(BaseCommand):
    help = 'Muestra el flujo visual de un torneo'

    def add_arguments(self, parser):
        parser.add_argument('torneo_id', type=str, help='ID del torneo')
        parser.add_argument('--detailed', action='store_true', help='Mostrar información detallada')
        parser.add_argument('--json', action='store_true', help='Salida en formato JSON')

    def handle(self, *args, **options):
        try:
            torneo = Torneo.objects.get(id=options['torneo_id'])
            flow_service = TournamentFlowService(torneo)
            flow_data = flow_service.get_tournament_flow()

            if options['json']:
                self.stdout.write(json.dumps(flow_data, indent=2, default=str))
                return

            self._display_flow(torneo, flow_data, options['detailed'])

        except Torneo.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Torneo {options["torneo_id"]} no encontrado')
            )

    def _display_flow(self, torneo, flow_data, detailed=False):
        """Muestra el flujo de forma visual en consola"""

        self.stdout.write(
            self.style.SUCCESS(f'\n🏆 FLUJO DEL TORNEO: {torneo.nombre}')
        )
        self.stdout.write('=' * 60)

        # Información básica
        self.stdout.write(f'📋 Tipo: {flow_data.get("type", "N/A")}')
        self.stdout.write(f'📝 Descripción: {flow_data.get("description", "N/A")}')
        self.stdout.write(f'⏱️  Duración estimada: {flow_data.get("duration_estimate", "N/A")}')
        self.stdout.write(f'📊 Progreso: {flow_data.get("progress", 0)}%')

        # Información de participantes
        participants_info = flow_data.get('participants_info', {})
        self.stdout.write(
            f'👥 Participantes: {participants_info.get("registered", 0)}/{participants_info.get("max", 0)}')

        # Fase actual
        current_phase = flow_data.get('current_phase', {})
        self.stdout.write(f'🎯 Fase actual: {current_phase.get("name", "N/A")}')

        # Fases del torneo
        self.stdout.write(f'\n📋 FASES DEL TORNEO:')

        phases = flow_data.get('phases', [])
        for phase in phases:
            status_icon = self._get_status_icon(phase.get('status', 'pending'))
            self.stdout.write(f'\n{status_icon} {phase.get("name", "")}')
            self.stdout.write(f'   {phase.get("description", "")}')

            if detailed and phase.get('details'):
                for detail in phase['details']:
                    self.stdout.write(f'   • {detail}')

            # Información específica según el tipo de fase
            if phase.get('bracket_info') and detailed:
                self.stdout.write('   🏆 Información del bracket:')
                for round_info in phase['bracket_info']:
                    self.stdout.write(f'     - {round_info["name"]}: {round_info["partidos"]} partidos')

            if phase.get('groups_info') and detailed:
                self.stdout.write('   🏟️  Composición de grupos:')
                for group in phase['groups_info']:
                    teams = ', '.join(group['teams'])
                    self.stdout.write(f'     - {group["name"]}: {teams}')

        self.stdout.write('\n' + '=' * 60)

    def _get_status_icon(self, status):
        """Obtiene el ícono según el estado"""
        icons = {
            'completed': '✅',
            'active': '🔄',
            'pending': '⏳'
        }
        return icons.get(status, '❓')