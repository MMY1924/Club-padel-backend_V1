# apps/scoring/serializers.py
from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from datetime import datetime, timedelta
from .models import (
    Partido, Set, Juego, Punto, HistorialJugador, EstadisticasJugador,
    Cancha, Reserva
)
from apps.players.models import Jugador

# SERIALIZERS PARA CANCHA
class CanchaSerializer(serializers.ModelSerializer):
    partidos_activos = serializers.SerializerMethodField()

    class Meta:
        model = Cancha
        fields = [
            'id', 'nombre', 'numero', 'tipo', 'estado',
            'descripcion', 'capacidad_espectadores', 'tiene_iluminacion',
            'fecha_creacion', 'activa', 'partidos_activos'
        ]
        read_only_fields = ['id', 'fecha_creacion']

    def get_partidos_activos(self, obj):
        """Cuenta partidos activos en la cancha"""
        return obj.partidos.filter(estado__in=['Pendiente', 'En Juego']).count()

    def validate_numero(self, value):
        """Validar que el número de cancha sea único"""
        if self.instance:
            if Cancha.objects.filter(numero=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("Ya existe una cancha con este número")
        else:
            if Cancha.objects.filter(numero=value).exists():
                raise serializers.ValidationError("Ya existe una cancha con este número")
        return value


class CanchaListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados"""
    partidos_hoy = serializers.SerializerMethodField()

    class Meta:
        model = Cancha
        fields = ['id', 'nombre', 'numero', 'tipo', 'estado', 'partidos_hoy']

    def get_partidos_hoy(self, obj):
        hoy = timezone.now().date()
        return obj.partidos.filter(fecha_creacion__date=hoy).count()


class CanchaConReservasSerializer(CanchaSerializer):
    """Serializer de cancha que incluye información de reservas"""
    reservas_hoy = serializers.SerializerMethodField()
    proxima_reserva = serializers.SerializerMethodField()
    disponible_ahora = serializers.SerializerMethodField()

    class Meta(CanchaSerializer.Meta):
        fields = CanchaSerializer.Meta.fields + [
            'reservas_hoy', 'proxima_reserva', 'disponible_ahora'
        ]

    def get_reservas_hoy(self, obj):
        hoy = timezone.now().date()
        reservas = obj.reservas.filter(
            fecha_inicio__date=hoy,
            estado__in=['Confirmada', 'En_Uso']
        ).count()
        return reservas

    def get_proxima_reserva(self, obj):
        proxima = obj.reservas.filter(
            fecha_inicio__gt=timezone.now(),
            estado__in=['Confirmada', 'Pendiente']
        ).order_by('fecha_inicio').first()

        if proxima:
            return {
                'codigo': proxima.codigo_reserva,
                'fecha_inicio': proxima.fecha_inicio.strftime('%d/%m/%Y %H:%M'),
                'tipo': proxima.tipo_reserva
            }
        return None

    def get_disponible_ahora(self, obj):
        ahora = timezone.now()
        reserva_actual = obj.reservas.filter(
            fecha_inicio__lte=ahora,
            fecha_fin__gte=ahora,
            estado__in=['Confirmada', 'En_Uso']
        ).exists()

        return not reserva_actual and obj.estado == 'Disponible'

# SERIALIZERS PARA PARTIDO
class PartidoSerializer(serializers.ModelSerializer):
    # Información adicional calculada
    equipo1_display = serializers.SerializerMethodField()
    equipo2_display = serializers.SerializerMethodField()
    cancha_info = serializers.SerializerMethodField()
    duracion_formateada = serializers.SerializerMethodField()
    total_jugadores = serializers.SerializerMethodField()

    # Información de jugadores
    jugador1_equipo1_info = serializers.SerializerMethodField()
    jugador2_equipo1_info = serializers.SerializerMethodField()
    jugador1_equipo2_info = serializers.SerializerMethodField()
    jugador2_equipo2_info = serializers.SerializerMethodField()

    class Meta:
        model = Partido
        fields = [
            'id', 'modalidad', 'cancha', 'cancha_info',
            'jugador1_equipo1', 'jugador2_equipo1', 'jugador1_equipo2', 'jugador2_equipo2',
            'jugador1_equipo1_info', 'jugador2_equipo1_info', 'jugador1_equipo2_info', 'jugador2_equipo2_info',
            'estado', 'tipo', 'sets_para_ganar', 'juegos_para_ganar_set',
            'fecha_inicio', 'fecha_fin', 'fecha_creacion', 'equipo_ganador',
            'equipo1_display', 'equipo2_display', 'duracion_formateada', 'total_jugadores'
        ]
        read_only_fields = ['id', 'fecha_creacion', 'equipo_ganador', 'fecha_inicio', 'fecha_fin']

    def get_equipo1_display(self, obj):
        return obj.equipo1_nombre

    def get_equipo2_display(self, obj):
        return obj.equipo2_nombre

    def get_cancha_info(self, obj):
        if obj.cancha:
            return {
                'id': obj.cancha.id,
                'nombre': obj.cancha.nombre,
                'numero': obj.cancha.numero,
                'tipo': obj.cancha.tipo
            }
        return None

    def get_duracion_formateada(self, obj):
        if obj.fecha_inicio and obj.fecha_fin:
            duracion = obj.fecha_fin - obj.fecha_inicio
            horas = duracion.seconds // 3600
            minutos = (duracion.seconds % 3600) // 60
            if horas > 0:
                return f"{horas}h {minutos}m"
            return f"{minutos}m"
        return None

    def get_total_jugadores(self, obj):
        return len(obj.get_jugadores_list())

    def get_jugador1_equipo1_info(self, obj):
        return {
            'id': obj.jugador1_equipo1.id,
            'nombre': obj.jugador1_equipo1.nombre,
            'apellido': obj.jugador1_equipo1.apellido,
            'nombre_completo': obj.jugador1_equipo1.nombre_completo
        }

    def get_jugador2_equipo1_info(self, obj):
        if obj.jugador2_equipo1:
            return {
                'id': obj.jugador2_equipo1.id,
                'nombre': obj.jugador2_equipo1.nombre,
                'apellido': obj.jugador2_equipo1.apellido,
                'nombre_completo': obj.jugador2_equipo1.nombre_completo
            }
        return None

    def get_jugador1_equipo2_info(self, obj):
        return {
            'id': obj.jugador1_equipo2.id,
            'nombre': obj.jugador1_equipo2.nombre,
            'apellido': obj.jugador1_equipo2.apellido,
            'nombre_completo': obj.jugador1_equipo2.nombre_completo
        }

    def get_jugador2_equipo2_info(self, obj):
        if obj.jugador2_equipo2:
            return {
                'id': obj.jugador2_equipo2.id,
                'nombre': obj.jugador2_equipo2.nombre,
                'apellido': obj.jugador2_equipo2.apellido,
                'nombre_completo': obj.jugador2_equipo2.nombre_completo
            }
        return None

    def validate(self, data):
        """Validaciones personalizadas"""
        modalidad = data.get('modalidad')

        # Validar jugadores según modalidad
        if modalidad == 'Individual':
            if data.get('jugador2_equipo1') or data.get('jugador2_equipo2'):
                raise serializers.ValidationError(
                    "Los partidos individuales solo requieren 1 jugador por equipo"
                )
        elif modalidad == 'Dobles':
            if not data.get('jugador2_equipo1') or not data.get('jugador2_equipo2'):
                raise serializers.ValidationError(
                    "Los partidos de dobles requieren 2 jugadores por equipo"
                )

        # Validar que no se repitan jugadores
        jugadores = []
        campos_jugadores = ['jugador1_equipo1', 'jugador2_equipo1', 'jugador1_equipo2', 'jugador2_equipo2']

        for campo in campos_jugadores:
            jugador = data.get(campo)
            if jugador:
                if jugador in jugadores:
                    raise serializers.ValidationError(
                        f"El jugador {jugador.nombre_completo} está repetido"
                    )
                jugadores.append(jugador)

        # Validar cancha disponible
        cancha = data.get('cancha')
        if cancha and cancha.estado == 'Fuera_Servicio':
            raise serializers.ValidationError("La cancha seleccionada está fuera de servicio")

        return data


class PartidoCreateSerializer(serializers.ModelSerializer):
    """Serializer específico para crear partidos"""

    class Meta:
        model = Partido
        fields = [
            'modalidad', 'cancha', 'tipo',
            'jugador1_equipo1', 'jugador2_equipo1',
            'jugador1_equipo2', 'jugador2_equipo2',
            'sets_para_ganar', 'juegos_para_ganar_set'
        ]

    def validate(self, data):
        """Validaciones para creación"""
        data = super().validate(data)

        # Usar las mismas validaciones de PartidoSerializer
        serializer = PartidoSerializer()
        return serializer.validate(data)

    def create(self, validated_data):
        """Crear partido y actualizar estado de cancha si es necesario"""
        cancha = validated_data.get('cancha')
        if cancha and cancha.estado == 'Disponible':
            cancha.estado = 'Ocupada'
            cancha.save()

        return super().create(validated_data)


class PartidoListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados"""
    equipo1_display = serializers.SerializerMethodField()
    equipo2_display = serializers.SerializerMethodField()
    cancha_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Partido
        fields = [
            'id', 'modalidad', 'estado', 'tipo',
            'equipo1_display', 'equipo2_display', 'cancha_nombre',
            'fecha_creacion', 'equipo_ganador'
        ]

    def get_equipo1_display(self, obj):
        return obj.equipo1_nombre

    def get_equipo2_display(self, obj):
        return obj.equipo2_nombre

    def get_cancha_nombre(self, obj):
        return obj.cancha.nombre if obj.cancha else None

# SERIALIZERS BÁSICOS PARA GAME OBJECTS
class SetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Set
        fields = '__all__'
        read_only_fields = ['id', 'fecha_inicio', 'fecha_fin']


class JuegoSerializer(serializers.ModelSerializer):
    puntos_display_equipo1 = serializers.ReadOnlyField()
    puntos_display_equipo2 = serializers.ReadOnlyField()

    class Meta:
        model = Juego
        fields = '__all__'
        read_only_fields = ['id', 'fecha_inicio', 'fecha_fin']


class PuntoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Punto
        fields = '__all__'
        read_only_fields = ['id', 'timestamp', 'numero_punto']

class PartidoSimpleSerializer(serializers.ModelSerializer):
    equipo1_display = serializers.SerializerMethodField()
    equipo2_display = serializers.SerializerMethodField()
    cancha_nombre = serializers.CharField(source='cancha.nombre', read_only=True)

    class Meta:
        model = Partido
        fields = ['id', 'modalidad', 'tipo', 'estado', 'cancha_nombre', 'fecha_inicio', 'fecha_fin', 'equipo1_display', 'equipo2_display']

    def get_equipo1_display(self, obj):
        return obj.equipo1_nombre

    def get_equipo2_display(self, obj):
        return obj.equipo2_nombre


class HistorialJugadorSerializer(serializers.ModelSerializer):
    jugador_info = serializers.SerializerMethodField()
    partido = serializers.SerializerMethodField()
    oponentes = serializers.SerializerMethodField()
    compañero_info = serializers.SerializerMethodField()

    class Meta:
        model = HistorialJugador
        fields = '__all__'

    def get_jugador_info(self, obj):
        return {
            'id': obj.jugador.id,
            'nombre_completo': obj.jugador.nombre_completo
        }

    def get_oponentes(self, obj):
        return obj.get_oponentes_display()

    def get_compañero_info(self, obj):
        if obj.compañero:
            return {
                'id': obj.compañero.id,
                'nombre_completo': obj.compañero.nombre_completo
            }
        return None

class EstadisticasJugadorSerializer(serializers.ModelSerializer):
    jugador_info = serializers.SerializerMethodField()
    ultimos_partidos = serializers.SerializerMethodField()
    porcentaje_victorias = serializers.SerializerMethodField()  # 👈 agregado

    class Meta:
        model = EstadisticasJugador
        fields = '__all__'
        read_only_fields = ['ultima_actualizacion']

    def get_jugador_info(self, obj):
        return {
            'id': obj.jugador.id,
            'nombre_completo': obj.jugador.nombre_completo,
            'email': obj.jugador.email
        }

    def get_ultimos_partidos(self, obj):
        """Trae los últimos 5 partidos finalizados del jugador."""
        ultimos = obj.jugador.historial.filter(
            partido__estado='Finalizado'
        ).select_related('partido').order_by('-fecha_partido')[:5]
        return HistorialJugadorSerializer(ultimos, many=True).data

    def get_porcentaje_victorias(self, obj):
        """Expone el porcentaje de victorias calculado."""
        return obj.porcentaje_victorias


class ReservaSerializer(serializers.ModelSerializer):
    cancha_info = serializers.SerializerMethodField()
    duracion_display = serializers.ReadOnlyField()
    es_hoy = serializers.ReadOnlyField()
    tiempo_restante = serializers.ReadOnlyField()
    puede_cancelar = serializers.ReadOnlyField()

    # Campos para integración con partidos
    puede_crear_partido = serializers.ReadOnlyField()
    partido_info = serializers.SerializerMethodField()

    class Meta:
        model = Reserva
        fields = [
            'id', 'codigo_reserva', 'cancha', 'cancha_info',
            'fecha_inicio', 'fecha_fin', 'duracion_minutos', 'duracion_display',
            'estado', 'tipo_reserva', 'precio_hora', 'precio_total', 'pagado',
            'numero_jugadores', 'observaciones', 'equipamiento_incluido',
            'fecha_creacion', 'creado_por', 'partido',
            'es_hoy', 'tiempo_restante', 'puede_cancelar',
            'puede_crear_partido', 'partido_info'
        ]
        read_only_fields = ['id', 'codigo_reserva', 'precio_total', 'fecha_creacion']

    def get_cancha_info(self, obj):
        if obj.cancha:
            return {
                'id': obj.cancha.id,
                'nombre': obj.cancha.nombre,
                'numero': obj.cancha.numero,
                'tipo': obj.cancha.tipo,
                'tiene_iluminacion': obj.cancha.tiene_iluminacion
            }
        return None

    def get_partido_info(self, obj):
        """Información del partido asociado"""
        if obj.partido:
            return {
                'id': obj.partido.id,
                'modalidad': obj.partido.modalidad,
                'estado': obj.partido.estado,
                'equipo1': obj.partido.equipo1_nombre,
                'equipo2': obj.partido.equipo2_nombre
            }
        return None

    def validate(self, data):
        # Validar que la fecha de inicio sea futura
        if data.get('fecha_inicio') and data['fecha_inicio'] <= timezone.now():
            raise serializers.ValidationError("La fecha de inicio debe ser futura")

        # Validar horario de funcionamiento (6:00 AM a 11:00 PM)
        if data.get('fecha_inicio'):
            hora_inicio = data['fecha_inicio'].time()
            if hora_inicio < datetime.strptime('06:00', '%H:%M').time() or \
                    hora_inicio > datetime.strptime('23:00', '%H:%M').time():
                raise serializers.ValidationError("El horario debe estar entre 6:00 AM y 11:00 PM")

        return data


class ReservaListSerializer(serializers.ModelSerializer):
    cancha_nombre = serializers.CharField(source='cancha.nombre', read_only=True)
    duracion_display = serializers.ReadOnlyField()

    class Meta:
        model = Reserva
        fields = [
            'id', 'codigo_reserva', 'cancha_nombre',
            'fecha_inicio', 'fecha_fin', 'duracion_display', 'estado',
            'tipo_reserva', 'precio_total', 'pagado', 'numero_jugadores'
        ]


class ReservaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reserva
        fields = [
            'cancha', 'fecha_inicio', 'fecha_fin', 'duracion_minutos',
            'tipo_reserva', 'precio_hora', 'numero_jugadores', 'observaciones',
            'equipamiento_incluido', 'creado_por'
        ]

    def validate(self, data):
        # Validación de disponibilidad
        cancha = data.get('cancha')
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')

        if cancha and fecha_inicio and fecha_fin:
            # Verificar que la cancha esté disponible
            if cancha.estado != 'Disponible':
                raise serializers.ValidationError(f"La cancha {cancha.nombre} no está disponible")

            # Verificar solapamiento
            reservas_existentes = Reserva.objects.filter(
                cancha=cancha,
                estado__in=['Confirmada', 'En_Uso', 'Pendiente'],
                fecha_inicio__lt=fecha_fin,
                fecha_fin__gt=fecha_inicio
            )

            if reservas_existentes.exists():
                reserva_conflicto = reservas_existentes.first()
                raise serializers.ValidationError(
                    f"Ya existe una reserva en ese horario (Código: {reserva_conflicto.codigo_reserva})"
                )

        return data

# SERIALIZERS PARA ENDPOINTS ESPECIALES

class AddPointSerializer(serializers.Serializer):
    """Serializer para agregar puntos"""
    equipo_ganador = serializers.IntegerField(min_value=1, max_value=2)
    tipo_punto = serializers.ChoiceField(choices=Punto.TIPO_PUNTO_CHOICES, default='Punto')
    descripcion = serializers.CharField(required=False, allow_blank=True)


class IniciarPartidoSerializer(serializers.Serializer):
    """Serializer para iniciar partido"""

    def validate(self, data):
        partido = self.context.get('partido')
        if not partido:
            raise serializers.ValidationError("Partido no encontrado")

        if partido.estado != 'Pendiente':
            raise serializers.ValidationError("Solo se pueden iniciar partidos pendientes")

        return data


class DisponibilidadSerializer(serializers.Serializer):
    """Serializer para consultar disponibilidad de canchas"""
    cancha = serializers.UUIDField()
    fecha = serializers.DateField()
    hora_inicio = serializers.TimeField(required=False)
    hora_fin = serializers.TimeField(required=False)

    def validate(self, data):
        # Verificar que la cancha existe
        try:
            cancha = Cancha.objects.get(id=data['cancha'])
            data['cancha_obj'] = cancha
        except Cancha.DoesNotExist:
            raise serializers.ValidationError("La cancha especificada no existe")

        return data


class CalendarioReservasSerializer(serializers.Serializer):
    """Serializer para vista de calendario"""
    fecha_inicio = serializers.DateField()
    fecha_fin = serializers.DateField()
    cancha = serializers.UUIDField(required=False)

    def validate(self, data):
        if data['fecha_fin'] <= data['fecha_inicio']:
            raise serializers.ValidationError("La fecha fin debe ser posterior a la fecha inicio")

        # Limitar rango máximo a 31 días
        delta = data['fecha_fin'] - data['fecha_inicio']
        if delta.days > 31:
            raise serializers.ValidationError("El rango máximo es de 31 días")

        return data


class CambiarEstadoReservaSerializer(serializers.Serializer):
    """Serializer para cambiar estado de reserva"""
    estado = serializers.ChoiceField(choices=Reserva.ESTADO_CHOICES)
    motivo = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_estado(self, value):
        reserva = self.context.get('reserva')
        if not reserva:
            return value

        # Validaciones de cambio de estado
        estado_actual = reserva.estado

        if estado_actual == 'Cancelada' and value != 'Cancelada':
            raise serializers.ValidationError("No se puede cambiar el estado de una reserva cancelada")

        if estado_actual == 'Completada' and value not in ['Completada', 'Cancelada']:
            raise serializers.ValidationError("No se puede cambiar el estado de una reserva completada")

        return value


class CrearJugadorSerializer(serializers.Serializer):
    """Serializer para crear un jugador"""
    edad = serializers.IntegerField(min_value=8, max_value=120, default=25)
    sexo = serializers.ChoiceField(choices=[('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')], default='M')


class CrearPartidoDesdeReservaSerializer(serializers.Serializer):
    """Serializer para crear un partido desde una reserva"""
    jugadores_adicionales = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text="IDs de jugadores adicionales para completar el partido"
    )
    modalidad = serializers.ChoiceField(
        choices=[('Individual', 'Individual'), ('Dobles', 'Dobles')],
        required=False,
        help_text="Modalidad del partido (si no se especifica, se determina automáticamente)"
    )

    def validate(self, data):
        reserva = self.context.get('reserva')
        if not reserva:
            raise serializers.ValidationError("Reserva no proporcionada")

        jugadores_adicionales = data.get('jugadores_adicionales', [])
        modalidad = data.get('modalidad')

        # Validar modalidad según número de jugadores
        if modalidad == 'Individual' and len(jugadores_adicionales) != 1:
            raise serializers.ValidationError("Para modalidad Individual se requiere exactamente 1 jugador adicional")
        elif modalidad == 'Dobles' and len(jugadores_adicionales) != 3:
            raise serializers.ValidationError("Para modalidad Dobles se requieren exactamente 3 jugadores adicionales")

        # Validar que los jugadores existen
        if jugadores_adicionales:
            jugadores_existentes = Jugador.objects.filter(id__in=jugadores_adicionales).count()
            if jugadores_existentes != len(jugadores_adicionales):
                raise serializers.ValidationError("Algunos jugadores especificados no existen")

        return data
