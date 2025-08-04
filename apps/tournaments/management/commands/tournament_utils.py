# apps/tournaments/management/commands/tournament_utils.py
from django.core.management.base import BaseCommand
from apps.tournaments.models import Torneo
from apps.tournaments.services import TournamentService


class Command(BaseCommand):
    help = 'Utilidades para gestión de torneos'

    def add_arguments(self, parser):
        parser.add_argument('--generar-sorteo', type=str, help='Código del torneo')
        parser.add_argument('--iniciar', type=str, help='Código del torneo a iniciar')
        parser.add_argument('--estado', type=str, help='Ver estado del torneo')

    def handle(self, *args, **options):
        if options['generar_sorteo']:
            torneo = Torneo.objects.get(codigo_torneo=options['generar_sorteo'])
            service = TournamentService(torneo)
            service.generate_draw()
            self.stdout.write(f"Sorteo generado para {torneo.nombre}")

        elif options['iniciar']:
            torneo = Torneo.objects.get(codigo_torneo=options['iniciar'])
            service = TournamentService(torneo)
            service.start_tournament()
            self.stdout.write(f"Torneo {torneo.nombre} iniciado")

        elif options['estado']:
            torneo = Torneo.objects.get(codigo_torneo=options['estado'])
            service = TournamentService(torneo)
            estado = service.get_tournament_status()
            self.stdout.write(f"\nEstado de {torneo.nombre}:")
            for key, value in estado.items():
                self.stdout.write(f"  {key}: {value}")