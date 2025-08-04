import pytest
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from apps.players.models import Jugador
from django.db import connection

@pytest.mark.django_db(transaction=True)
class TestFlujoPartido(TransactionTestCase):
    reset_sequences = True  # Reinicia automáticamente las secuencias

    def test_partido_flujo_completo(self):
        # Limpiar y reiniciar IDs
        with connection.cursor() as cursor:
            cursor.execute('TRUNCATE TABLE jugadores RESTART IDENTITY CASCADE;')
            cursor.execute('TRUNCATE TABLE auth_user RESTART IDENTITY CASCADE;')

        # Helper
        def crear_jugador_registrado(nombre, apellido, telefono):
            user = User.objects.create_user(
                username=f"{nombre}_{apellido}",
                email=f"{nombre}.{apellido}@test.com",
                password="test1234"
            )
            return Jugador.objects.create(user=user, telefono=telefono)

        # Crear 4 jugadores
        jugadores = [
            crear_jugador_registrado("juan", "perez", "1234"),
            crear_jugador_registrado("maria", "gomez", "5678"),
            crear_jugador_registrado("pedro", "lopez", "9101"),
            crear_jugador_registrado("ana", "martinez", "1121"),
        ]

        # Verificar
        assert Jugador.objects.count() == 4
        assert all(j.user_id for j in jugadores)
