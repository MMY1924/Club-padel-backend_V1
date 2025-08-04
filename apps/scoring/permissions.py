# apps/scoring/permissions.py
from rest_framework.permissions import BasePermission


class IsPlayerInMatch(BasePermission):
    """
    Permiso que permite solo a los jugadores del partido agregar/deshacer puntos
    """

    def has_object_permission(self, request, view, obj):
        # obj es el partido
        user = request.user

        # Verificar si el usuario es uno de los 4 jugadores del partido
        jugadores_del_partido = [
            obj.jugador1_equipo1.user if obj.jugador1_equipo1 else None,
            obj.jugador2_equipo1.user if obj.jugador2_equipo1 else None,
            obj.jugador1_equipo2.user if obj.jugador1_equipo2 else None,
            obj.jugador2_equipo2.user if obj.jugador2_equipo2 else None,
        ]

        return user in jugadores_del_partido and user is not None