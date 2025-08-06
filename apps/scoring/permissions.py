# apps/scoring/permissions.py
from rest_framework.permissions import BasePermission


class IsPlayerInMatch(BasePermission):
    """
    Permiso que permite solo a los jugadores del partido agregar/deshacer puntos
    """

    def has_object_permission(self, request, view, obj):
        """
        Determina si el usuario autenticado tiene permiso para interactuar
        con el partido.

        Parámetros:
        - request: solicitud actual.
        - view: vista que está utilizando este permiso.
        - obj: instancia del modelo Partido sobre la que se aplica el permiso.

        Retorna:
         - True si el usuario es uno de los jugadores del partido.
         - False en caso contrario.
        """
        user = request.user

        # Verificar si el usuario es uno de los 4 jugadores del partido
        jugadores_del_partido = [
            obj.jugador1_equipo1.user if obj.jugador1_equipo1 else None,
            obj.jugador2_equipo1.user if obj.jugador2_equipo1 else None,
            obj.jugador1_equipo2.user if obj.jugador1_equipo2 else None,
            obj.jugador2_equipo2.user if obj.jugador2_equipo2 else None,
        ]
        # El permiso se concede si el usuario está en la lista de jugadores y no es None
        return user in jugadores_del_partido and user is not None