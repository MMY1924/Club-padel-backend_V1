# apps/scoring/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Partido
from .serializers import PartidoLiveSerializer


class PartidoConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.partido_id = self.scope['url_route']['kwargs']['partido_id']
        self.room_group_name = f'partido_{self.partido_id}'

        # Verificar que el partido existe
        partido_existe = await self.partido_exists()
        if not partido_existe:
            await self.close()
            return

        # Unirse al grupo del partido
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Enviar estado actual del partido
        partido_data = await self.get_partido_data()
        await self.send(text_data=json.dumps({
            'type': 'partido_inicial',
            'data': partido_data
        }))

    async def disconnect(self, close_code):
        # Salir del grupo del partido
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # Manejar mensajes del jugador
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')

            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))

        except json.JSONDecodeError:
            pass

    # Recibir mensaje del grupo
    async def partido_update(self, event):
        # Enviar datos al WebSocket
        await self.send(text_data=json.dumps({
            'type': 'partido_update',
            'data': event['data']
        }))

    @database_sync_to_async
    def partido_exists(self):
        try:
            Partido.objects.get(id=self.partido_id)
            return True
        except Partido.DoesNotExist:
            return False

    @database_sync_to_async
    def get_partido_data(self):
        try:
            partido = Partido.objects.get(id=self.partido_id)
            serializer = PartidoLiveSerializer(partido)
            return serializer.data
        except Partido.DoesNotExist:
            return None