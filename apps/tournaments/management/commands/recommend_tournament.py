# apps/tournaments/management/commands/recommend_tournament.py

from django.core.management.base import BaseCommand
from apps.tournaments.flow_services import get_all_tournament_flows, generate_tournament_recommendations


class Command(BaseCommand):
    help = 'Recomienda el mejor tipo de torneo según parámetros'

    def add_arguments(self, parser):
        parser.add_argument('--participants', type=int, default=8, help='Número de participantes')
        parser.add_argument('--duration', type=int, default=3, help='Duración en días')
        parser.add_argument('--complexity', choices=['baja', 'media', 'alta'], default='media',
                            help='Complejidad preferida')
        parser.add_argument('--show-all', action='store_true', help='Mostrar información de todos los tipos')

    def handle(self, *args, **options):
        if options['show_all']:
            self._show_all_types()
        else:
            self._show_recommendations(options)

    def _show_all_types(self):
        """Muestra información de todos los tipos de torneo"""
        flows = get_all_tournament_flows()

        self.stdout.write(
            self.style.SUCCESS('\n🏆 TIPOS DE TORNEOS DISPONIBLES')
        )
        self.stdout.write('=' * 60)

        for key, flow in flows.items():
            self.stdout.write(f'\n📋 {flow["name"]}')
            self.stdout.write(f'   📝 {flow["description"]}')
            self.stdout.write(f'   ⏱️  Duración: {flow["duration"]}')
            self.stdout.write(f'   🎯 Complejidad: {flow["complexity"]}')

            self.stdout.write('   ✅ Ventajas:')
            for pro in flow['pros']:
                self.stdout.write(f'     • {pro}')

            self.stdout.write('   ⚠️  Desventajas:')
            for con in flow['cons']:
                self.stdout.write(f'     • {con}')

            self.stdout.write('   🎯 Ideal para:')
            for ideal in flow['ideal_for']:
                self.stdout.write(f'     • {ideal}')

    def _show_recommendations(self, options):
        """Muestra recomendaciones específicas"""
        participants = options['participants']
        duration = options['duration']
        complexity = options['complexity']

        recommendations = generate_tournament_recommendations(
            participants, duration, complexity
        )

        self.stdout.write(
            self.style.SUCCESS(f'\n🎯 RECOMENDACIONES PARA TU TORNEO')
        )
        self.stdout.write('=' * 50)
        self.stdout.write(f'👥 Participantes: {participants}')
        self.stdout.write(f'📅 Duración: {duration} días')
        self.stdout.write(f'🎚️  Complejidad: {complexity}')

        if not recommendations:
            self.stdout.write(
                self.style.WARNING('\n⚠️  No hay recomendaciones para estos parámetros')
            )
            return

        self.stdout.write(f'\n📊 RECOMENDACIONES (ordenadas por puntuación):')

        for i, rec in enumerate(recommendations, 1):
            score_color = self.style.SUCCESS if rec['score'] >= 90 else \
                self.style.WARNING if rec['score'] >= 70 else \
                    self.style.ERROR

            self.stdout.write(f'\n{i}. {rec["type"].upper()}')
            self.stdout.write(score_color(f'   Puntuación: {rec["score"]}/100'))
            self.stdout.write(f'   💡 Razón: {rec["reason"]}')



# 4. FUNCIÓN PARA VISTA INTERACTIVA


def create_interactive_tournament_flow():
    """Crea un flujo interactivo para demostración"""

    print("🏆 CREADOR INTERACTIVO DE TORNEOS")
    print("=" * 50)

    # Recopilar información
    print("\n📋 Información básica:")
    nombre = input("Nombre del torneo: ") or "Torneo Demo"

    print("\n👥 ¿Cuántos equipos participarán?")
    print("1. 4-8 equipos (Torneo pequeño)")
    print("2. 8-16 equipos (Torneo mediano)")
    print("3. 16+ equipos (Torneo grande)")

    size_choice = input("Selecciona (1-3): ") or "1"
    participants_map = {"1": 6, "2": 12, "3": 20}
    participants = participants_map.get(size_choice, 6)

    print("\n📅 ¿Cuánto tiempo tienes disponible?")
    print("1. 1-2 días (Fin de semana)")
    print("2. 3-5 días (Semana)")
    print("3. 1+ semanas (Liga larga)")

    duration_choice = input("Selecciona (1-3): ") or "1"
    duration_map = {"1": 2, "2": 4, "3": 10}
    duration = duration_map.get(duration_choice, 2)

    print("\n🎚️  ¿Qué complejidad prefieres?")
    print("1. Simple y rápido")
    print("2. Equilibrado")
    print("3. Completo y justo")

    complexity_choice = input("Selecciona (1-3): ") or "2"
    complexity_map = {"1": "baja", "2": "media", "3": "alta"}
    complexity = complexity_map.get(complexity_choice, "media")

    # Generar recomendaciones
    print(f"\n🔍 Generando recomendaciones...")
    recommendations = generate_tournament_recommendations(
        participants, duration, complexity
    )

    print(f"\n🎯 RECOMENDACIONES PARA '{nombre}':")
    print("=" * 50)
    print(f"👥 Participantes: {participants}")
    print(f"📅 Duración: {duration} días")
    print(f"🎚️  Complejidad: {complexity}")

    if recommendations:
        best_rec = recommendations[0]
        print(f"\n🏆 RECOMENDACIÓN PRINCIPAL:")
        print(f"   Tipo: {best_rec['type'].upper()}")
        print(f"   Puntuación: {best_rec['score']}/100")
        print(f"   Razón: {best_rec['reason']}")

        print(f"\n📋 Otras opciones:")
        for rec in recommendations[1:]:
            print(f"   • {rec['type']}: {rec['score']}/100 - {rec['reason']}")

        # Mostrar detalles del tipo recomendado
        flows = get_all_tournament_flows()
        if best_rec['type'] in flows:
            flow_info = flows[best_rec['type']]
            print(f"\n📝 DETALLES DE {flow_info['name'].upper()}:")
            print(f"   {flow_info['description']}")
            print(f"   Duración típica: {flow_info['duration']}")
            print(f"   Ventajas: {', '.join(flow_info['pros'])}")
    else:
        print("⚠️  No se encontraron recomendaciones para estos parámetros")



# 5. UTILIDADES DE TESTING


def test_all_tournament_flows():
    """Función para probar todos los flujos de torneo"""
    from apps.tournaments.models import Torneo

    print("🧪 PROBANDO TODOS LOS FLUJOS DE TORNEO")
    print("=" * 60)

    # Obtener torneos de ejemplo de cada tipo
    tipos = ['Eliminacion', 'Ranking', 'Grupos']

    for tipo in tipos:
        print(f"\n🔍 Probando flujo para tipo: {tipo}")

        torneo = Torneo.objects.filter(tipo=tipo).first()
        if torneo:
            flow_service = TournamentFlowService(torneo)
            flow_data = flow_service.get_tournament_flow()

            print(f"   ✅ Torneo: {torneo.nombre}")
            print(f"   📊 Progreso: {flow_data.get('progress', 0)}%")
            print(f"   🎯 Fase actual: {flow_data.get('current_phase', {}).get('name', 'N/A')}")
            print(f"   📝 Descripción: {flow_data.get('description', 'N/A')}")
        else:
            print(f"   ⚠️  No hay torneos de tipo {tipo}")


def generate_flow_report(torneo_id):
    """Genera un reporte completo del flujo de un torneo"""
    try:
        torneo = Torneo.objects.get(id=torneo_id)
        flow_service = TournamentFlowService(torneo)
        flow_data = flow_service.get_tournament_flow()

        report = {
            'timestamp': timezone.now().isoformat(),
            'tournament': {
                'id': str(torneo.id),
                'name': torneo.nombre,
                'code': torneo.codigo_torneo,
                'type': torneo.tipo,
                'status': torneo.estado,
                'participants': torneo.participantes_registrados,
                'max_participants': torneo.max_participantes
            },
            'flow_analysis': flow_data,
            'recommendations': [],
            'next_actions': []
        }

        # Agregar recomendaciones si es necesario
        if torneo.estado == 'Inscripcion' and torneo.participantes_registrados < torneo.min_participantes:
            report['recommendations'].append("Necesita más participantes para iniciar")

        if torneo.estado == 'Preparacion':
            if not torneo.fases.exists():
                report['next_actions'].append("Generar sorteo")
            else:
                report['next_actions'].append("Iniciar torneo")

        return report

    except Torneo.DoesNotExist:
        return {'error': f'Torneo {torneo_id} no encontrado'}