from django.apps import AppConfig


class PlayersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.players'
    verbose_name = 'Jugadores'

    def ready(self):
        """
        Se ejecuta cuando la app está lista.
        Importa las señales para que se registren automáticamente.
        """
        import apps.players.signals