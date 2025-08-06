from django.apps import AppConfig


class PlayersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.players'
    verbose_name = 'Gestion de Jugadores'

    def ready(self):
        """
        Metody que se ejecuta cuando la aplicación está completamente cargada.
        Se utiliza para importar y registrar automáticamente las señales de la aplicación.
        """
        import apps.players.signals  # Importa las señales de la aplicación para su registro

