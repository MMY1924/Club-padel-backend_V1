from django.apps import AppConfig


class ScoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.scoring'
    verbose_name = 'Sistema de Puntuación'

    def ready(self):
        """
        Se ejecuta cuando la app está lista.
        Importa las señales para que se registren automáticamente.
        """
        import apps.scoring.signals
        print(" Señales de scoring cargadas automáticamente")
