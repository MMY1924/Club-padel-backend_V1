# apps/scoring/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Partido
from .serializers import PartidoLiveSerializer


class PartidoConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket para manejar la transmisión en vivo del estado de un partido.
    Se encarga de:
    - Verificar que el partido existe.
    - Gestionar la conexión y desconexión de los clientes.
    - Enviar actualizaciones del estado del partido a los clientes conectados.
    """

    def __init__(self, *args, **kwargs):
        """
        Inicializa el consumer y define los atributos esperados.
        """
        super().__init__(*args, **kwargs)
        self.partido_id = None
        self.room_group_name = None

    async def connect(self):
        """
        Une al cliente al grupo del partido si este existe y envía el estado inicial.
        """
        self.partido_id = self.scope['url_route']['kwargs']['partido_id']
        self.room_group_name = f'partido_{self.partido_id}'

        # Verificar que el partido existe antes de conectar
        partido_existe = await self.partido_exists()
        if not partido_existe:
            await self.close()
            return

        # Unirse al grupo de canales del partido
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Enviar estado inicial del partido al cliente
        partido_data = await self.get_partido_data()
        await self.send(text_data=json.dumps({
            'type': 'partido_inicial',
            'data': partido_data
        }))

    async def disconnect(self, close_code):
        """
        Elimina al cliente del grupo del partido.
        """
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data=None, bytes_data=None):
        """
        Manejo de mensajes entrantes desde el cliente WebSocket.
        Actualmente, responde a mensajes tipo 'ping' con un 'pong'.
        """
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')

            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))

        except json.JSONDecodeError:
            # Ignorar mensajes con formato inválido
            pass

    async def partido_update(self, event):
        """
        Envía los datos actualizados a todos los clientes conectados al grupo.
        """
        await self.send(text_data=json.dumps({
            'type': 'partido_update',
            'data': event['data']
        }))

    @database_sync_to_async
    def partido_exists(self):
        """
        Verifica si el partido con el ID proporcionado existe en la base de datos.
        Retorna True si existe, False en caso contrario.
        """
        try:
            Partido.objects.get(id=self.partido_id)
            return True
        except Partido.DoesNotExist:
            return False

    @database_sync_to_async
    def get_partido_data(self):
        """
        Obtiene los datos serializados del partido para enviarlos al cliente.
        Retorna None si el partido no existe.
        """
        try:
            partido = Partido.objects.get(id=self.partido_id)
            serializer = PartidoLiveSerializer(partido)
            return serializer.data
        except Partido.DoesNotExist:
            return None
