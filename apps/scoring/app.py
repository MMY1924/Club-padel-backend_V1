from django.apps import AppConfig

class ScoringConfig(AppConfig):
    """
        Configuración de la aplicación 'scoring'.
        Define parámetros básicos y carga automática de señales.
        """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.scoring'

    def ready(self):
        """
        Se ejecuta automáticamente cuando la aplicación está lista.
        Importa las señales necesarias para que se registren al inicio.
        """
        import apps.scoring.signals

