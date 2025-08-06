# apps/scoring/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Partido, Set, Juego, Punto, HistorialJugador, EstadisticasJugador, Cancha, Reserva
from .services import PadelScoringService
from django.forms import ModelForm
from django.db import models


# ADMIN PARA CANCHA
@admin.register(Cancha)
class CanchaAdmin(admin.ModelAdmin):
    list_display = [
        'numero', 'nombre', 'tipo', 'estado_badge', 'tiene_iluminacion',
        'partidos_activos', 'activa_badge', 'fecha_creacion'
    ]
    list_filter = ['tipo', 'estado', 'activa', 'tiene_iluminacion']
    search_fields = ['nombre', 'descripcion']
    readonly_fields = ['id', 'fecha_creacion', 'partidos_activos', 'total_partidos']
    ordering = ['numero']

    fieldsets = (
        ('Información Básica', {'fields': ('id', 'numero', 'nombre', 'tipo')}),
        ('Estado y Configuración', {'fields': ('estado', 'activa', 'tiene_iluminacion', 'capacidad_espectadores')}),
        ('Descripción', {'fields': ('descripcion',), 'classes': ('collapse',)}),
        ('Estadísticas', {'fields': ('partidos_activos', 'total_partidos', 'fecha_creacion'), 'classes': ('collapse',)})
    )

    def estado_badge(self, obj):
        colors = {'Disponible': 'green', 'Ocupada': 'orange', 'Mantenimiento': 'blue', 'Fuera_Servicio': 'red'}
        color = colors.get(obj.estado, 'gray')
        return format_html('<span style="color: {}; font-weight: bold;">●</span> {}', color, obj.get_estado_display())

    estado_badge.short_description = 'Estado'

    def activa_badge(self, obj):
        return format_html(
            '<span style="color: green;">Activa</span>' if obj.activa else '<span style="color: red;">Inactiva</span>')

    activa_badge.short_description = 'Estado General'

    def partidos_activos(self, obj):
        count = obj.partidos.filter(estado__in=['Pendiente', 'En Juego']).count()
        return format_html('<span style="color: orange; font-weight: bold;">{}</span>', count) if count > 0 else '0'

    partidos_activos.short_description = 'Partidos Activos'

    def total_partidos(self, obj):
        return format_html('<strong>{}</strong>', obj.partidos.count())

    total_partidos.short_description = 'Total Partidos'

    actions = ['activar_canchas', 'desactivar_canchas', 'liberar_canchas']

    def activar_canchas(self, request, queryset):
        updated = queryset.update(activa=True)
        self.message_user(request, f'{updated} canchas activadas correctamente.')

    activar_canchas.short_description = "Activar canchas seleccionadas"

    def desactivar_canchas(self, request, queryset):
        updated = queryset.update(activa=False)
        self.message_user(request, f'{updated} canchas desactivadas correctamente.')

    desactivar_canchas.short_description = "Desactivar canchas seleccionadas"

    def liberar_canchas(self, request, queryset):
        canchas_liberadas = 0
        for cancha in queryset:
            if not cancha.partidos.filter(estado='En Juego').exists():
                cancha.estado = 'Disponible'
                cancha.save()
                canchas_liberadas += 1
        self.message_user(request, f'{canchas_liberadas} canchas liberadas correctamente.')

    liberar_canchas.short_description = "Liberar canchas disponibles"


# ==========================================
# ADMIN PARA PARTIDO - MEJORADO
# ==========================================
@admin.register(Partido)
class PartidoAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'modalidad', 'estado_badge', 'tipo', 'cancha',
        'fecha_creacion', 'equipo_ganador'
    ]
    list_filter = ['modalidad', 'estado', 'tipo', 'cancha__tipo', 'fecha_creacion', 'sets_para_ganar']
    search_fields = [
        'jugador1_equipo1__nombre', 'jugador1_equipo1__apellido',
        'jugador2_equipo1__nombre', 'jugador2_equipo1__apellido',
        'jugador1_equipo2__nombre', 'jugador1_equipo2__apellido',
        'jugador2_equipo2__nombre', 'jugador2_equipo2__apellido',
        'cancha__nombre'
    ]
    readonly_fields = ['id', 'fecha_creacion', 'fecha_inicio', 'fecha_fin']
    ordering = ['-fecha_creacion']

    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'modalidad', 'tipo', 'cancha')
        }),
        ('Jugadores Equipo 1', {
            'fields': ('jugador1_equipo1', 'jugador2_equipo1')
        }),
        ('Jugadores Equipo 2', {
            'fields': ('jugador1_equipo2', 'jugador2_equipo2')
        }),
        ('Configuración', {
            'fields': ('sets_para_ganar', 'juegos_para_ganar_set')
        }),
        ('Estado del Partido', {
            'fields': ('estado', 'equipo_ganador')
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_inicio', 'fecha_fin'),
            'classes': ('collapse',)
        })
    )

    def estado_badge(self, obj):
        colors = {'Pendiente': 'orange', 'En Juego': 'green', 'Finalizado': 'blue', 'Cancelado': 'red'}
        color = colors.get(obj.estado, 'gray')
        return format_html('<span style="color: {}; font-weight: bold;">●</span> {}', color, obj.estado)

    estado_badge.short_description = 'Estado'

    # Acciones personalizadas mejoradas
    actions = ['iniciar_partidos_completos', 'finalizar_partidos', 'ver_estados_detallados', 'validar_consistencia',
               'ver_estadisticas']

    def iniciar_partidos_completos(self, request, queryset):
        """Inicia partidos y crea toda la estructura necesaria"""
        count = 0
        errores = []

        for partido in queryset.filter(estado='Pendiente'):
            try:
                servicio = PadelScoringService(partido.id)
                servicio.start_match()
                count += 1
            except Exception as e:
                errores.append(f"Error en {partido}: {str(e)}")

        if count > 0:
            self.message_user(request, f'{count} partidos iniciados correctamente con estructura completa')

        for error in errores:
            self.message_user(request, error, level='ERROR')

    iniciar_partidos_completos.short_description = "Iniciar partidos seleccionados"

    def finalizar_partidos(self, request, queryset):
        """Finaliza partidos seleccionados"""
        count = queryset.filter(estado='En Juego').update(estado='Finalizado')
        self.message_user(request, f'{count} partidos finalizados')

    finalizar_partidos.short_description = "Finalizar partidos seleccionados"

    def ver_estados_detallados(self, request, queryset):
        """Ver estado detallado de partidos seleccionados"""
        for partido in queryset:
            try:
                servicio = PadelScoringService(partido.id)
                estado = servicio.get_live_score()

                mensaje = f"{estado['equipo1']} vs {estado['equipo2']} | Estado: {estado['estado']}"
                if estado['estado'] == 'En Juego':
                    mensaje += f" | Sets: {estado['sets']['equipo1']}-{estado['sets']['equipo2']}"
                    if estado['juego_actual']['numero']:
                        mensaje += f" | Juego {estado['juego_actual']['numero']}: {estado['juego_actual']['puntos_display_1']}-{estado['juego_actual']['puntos_display_2']}"

                # MEJORA: Agregar información adicional
                if estado.get('total_puntos'):
                    mensaje += f" | Total puntos: {estado['total_puntos']}"

                self.message_user(request, mensaje, level='INFO')

            except Exception as e:
                self.message_user(request, f"Error en {partido}: {str(e)}", level='ERROR')

    ver_estados_detallados.short_description = "Ver estados detallados"


    def validar_consistencia(self, request, queryset):
        """Valida la consistencia de los datos de los partidos"""
        for partido in queryset:
            try:
                servicio = PadelScoringService(partido.id)
                errores = servicio.validate_match_state()

                if errores:
                    self.message_user(request, f"Errores en {partido}:", level='WARNING')
                    for error in errores:
                        self.message_user(request, f"  - {error}", level='WARNING')
                else:
                    self.message_user(request, f"Estado consistente: {partido}", level='SUCCESS')
            except Exception as e:
                self.message_user(request, f"Error validando {partido}: {str(e)}", level='ERROR')

    validar_consistencia.short_description = "Validar consistencia de datos"


    def ver_estadisticas(self, request, queryset):
        """Muestra estadísticas detalladas de los partidos"""
        for partido in queryset:
            try:
                estadisticas = PadelScoringService.get_match_statistics(partido.id)

                if 'error' in estadisticas:
                    self.message_user(request, f"Error en {partido}: {estadisticas['error']}", level='ERROR')
                    continue

                stats = estadisticas['estadisticas']
                mensaje = f"Estadísticas {partido}:"
                mensaje += f" Puntos: {stats['puntos']['equipo1']}-{stats['puntos']['equipo2']}"
                mensaje += f" | Juegos: {stats['juegos']['equipo1']}-{stats['juegos']['equipo2']}"
                mensaje += f" | Sets: {stats['sets']['equipo1']}-{stats['sets']['equipo2']}"

                porcentajes = estadisticas['porcentajes']
                mensaje += f" | % Puntos Eq.1: {porcentajes['puntos_equipo1']}%"

                self.message_user(request, mensaje, level='INFO')

            except Exception as e:
                self.message_user(request, f"Error obteniendo estadísticas de {partido}: {str(e)}", level='ERROR')

    ver_estadisticas.short_description = "Ver estadísticas detalladas"


# INLINES

class JuegoInline(admin.TabularInline):
    model = Juego
    extra = 0
    readonly_fields = ['puntos_display_equipo1', 'puntos_display_equipo2', 'fecha_inicio', 'fecha_fin']
    fields = ['numero_juego', 'puntos_equipo1', 'puntos_equipo2', 'puntos_display_equipo1', 'puntos_display_equipo2',
              'finalizado', 'equipo_ganador']


class PuntoInline(admin.TabularInline):
    model = Punto
    extra = 0
    readonly_fields = ['timestamp']
    fields = ['numero_punto', 'equipo_ganador', 'tipo_punto', 'descripcion', 'timestamp']


# ADMIN PARA SET

@admin.register(Set)
class SetAdmin(admin.ModelAdmin):
    list_display = ['partido', 'numero_set', 'juegos_equipo1', 'juegos_equipo2', 'finalizado', 'equipo_ganador']
    list_filter = ['finalizado', 'equipo_ganador', 'partido__modalidad']
    search_fields = ['partido__jugador1_equipo1__nombre', 'partido__cancha__nombre']
    readonly_fields = ['fecha_inicio', 'fecha_fin']
    inlines = [JuegoInline]

    fieldsets = (
        ('Set Info', {
            'fields': ('partido', 'numero_set')
        }),
        ('Puntuación', {
            'fields': ('juegos_equipo1', 'juegos_equipo2', 'finalizado', 'equipo_ganador')
        }),
        ('Fechas', {
            'fields': ('fecha_inicio', 'fecha_fin'),
            'classes': ('collapse',)
        })
    )

# ADMIN PARA JUEGO

@admin.register(Juego)
class JuegoAdmin(admin.ModelAdmin):
    list_display = ['set', 'numero_juego', 'puntos_display_equipo1', 'puntos_display_equipo2', 'finalizado',
                    'equipo_ganador', 'equipo_que_saca']
    list_filter = ['finalizado', 'equipo_ganador', 'equipo_que_saca']
    search_fields = ['set__partido__cancha__nombre']
    readonly_fields = ['fecha_inicio', 'fecha_fin', 'puntos_display_equipo1', 'puntos_display_equipo2']
    inlines = [PuntoInline]


# FORMULARIO PERSONALIZADO PARA PUNTO

class PuntoAdminForm(ModelForm):
    """Formulario que filtra solo juegos de partidos en curso"""

    class Meta:
        model = Punto
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # FILTRAR SOLO JUEGOS ACTIVOS
        juegos_activos = Juego.objects.filter(
            set__partido__estado='En Juego',
            finalizado=False,
            set__finalizado=False
        ).select_related('set__partido').order_by(
            'set__partido__fecha_creacion', 'set__numero_set', 'numero_juego'
        )

        self.fields['juego'].queryset = juegos_activos

        if juegos_activos.exists():
            self.fields['juego'].empty_label = "Selecciona un juego activo..."
        else:
            self.fields['juego'].empty_label = "No hay juegos activos - crear partido 'En Juego'"


# ADMIN PARA PUNTO - ACTUALIZADO PARA SERVICES MEJORADO
@admin.register(Punto)
class PuntoAdmin(admin.ModelAdmin):
    form = PuntoAdminForm

    list_display = [
        'numero_punto', 'juego_info', 'equipo_ganador', 'descripcion_corta',
        'timestamp', 'estado_despues'
    ]
    list_filter = [
        'equipo_ganador', 'tipo_punto',
        'juego__set__partido__estado',
        'juego__set__partido__cancha'
    ]
    search_fields = [
        'juego__set__partido__jugador1_equipo1__nombre',
        'juego__set__partido__jugador1_equipo2__nombre',
        'descripcion'
    ]
    readonly_fields = ['timestamp', 'numero_punto', 'resultado_procesamiento']
    ordering = ['-timestamp']

    fieldsets = (
        ('Agregar Punto', {
            'fields': ('juego', 'equipo_ganador', 'descripcion'),
            'description': 'Al guardar, se procesará automáticamente toda la lógica de puntuación'
        }),
        ('Resultado del Procesamiento', {
            'fields': ('resultado_procesamiento',),
            'classes': ('collapse',)
        }),
        ('Sistema', {
            'fields': ('numero_punto', 'timestamp'),
            'classes': ('collapse',)
        })
    )

    def juego_info(self, obj):
        """Muestra información del partido y juego"""
        if obj.juego and obj.juego.set and obj.juego.set.partido:
            partido = obj.juego.set.partido
            return format_html(
                '<strong>{}</strong><br>'
                '<small>Set {} - Juego {} | Saca: Equipo {}</small><br>'
                '<small style="color: #666;">Estado: {}-{}</small>',
                partido,
                obj.juego.set.numero_set,
                obj.juego.numero_juego,
                obj.juego.equipo_que_saca,
                obj.juego.puntos_display_equipo1,
                obj.juego.puntos_display_equipo2
            )
        return "No disponible"

    juego_info.short_description = 'Partido/Juego'

    def descripcion_corta(self, obj):
        """Descripción truncada"""
        if obj.descripcion:
            return obj.descripcion[:30] + "..." if len(obj.descripcion) > 30 else obj.descripcion
        return "-"

    descripcion_corta.short_description = 'Descripción'

    def estado_despues(self, obj):
        """Estado del juego después de este punto"""
        if obj.juego:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">{}-{}</span>',
                obj.juego.puntos_display_equipo1,
                obj.juego.puntos_display_equipo2
            )
        return ""

    estado_despues.short_description = 'Resultado'

    def resultado_procesamiento(self, obj):
        """Información sobre el procesamiento del punto """
        if hasattr(obj, '_resultado_procesamiento'):
            resultado = obj._resultado_procesamiento
            info_lines = []

            # Información básica
            info_lines.append(f"Punto agregado a Equipo {obj.equipo_ganador}")

            # USAR INFORMACIÓN DETALLADA DEL RESULTADO
            if resultado.get('juego_finalizado'):
                info_lines.append(f"Juego finalizado - Ganador: Equipo {resultado.get('ganador_juego')}")

            if resultado.get('set_finalizado'):
                info_lines.append(f"Set finalizado - Ganador: Equipo {resultado.get('ganador_set')}")

            if resultado.get('partido_finalizado'):
                info_lines.append(f"PARTIDO FINALIZADO - Ganador: Equipo {resultado.get('ganador_partido')}")

            if resultado.get('nuevo_set_creado'):
                info_lines.append("Nuevo set creado automáticamente")

            if resultado.get('nuevo_juego_creado'):
                info_lines.append("Nuevo juego creado automáticamente")

            # MEJORA: Información del estado actual
            if 'estado_actual' in resultado:
                estado = resultado['estado_actual']
                if estado.get('total_puntos'):
                    info_lines.append(f"Total puntos en partido: {estado['total_puntos']}")

            return format_html('<br>'.join(info_lines))

        return "Punto procesado mediante servicio automático"

    resultado_procesamiento.short_description = 'Procesamiento'

    def save_model(self, request, obj, form, change):
        """Procesamiento automático de puntos """

        if not change:  # Solo para puntos nuevos
            try:
                # CAMBIO PRINCIPAL: add_point ahora retorna (punto, resultado)
                servicio = PadelScoringService(obj.juego.set.partido.id)
                punto, resultado = servicio.add_point(
                    equipo_ganador=obj.equipo_ganador,
                    descripcion=obj.descripcion or ""
                )

                # Obtener estado actualizado
                estado_actual = servicio.get_live_score()

                # Guardar info para mostrar en resultado_procesamiento
                obj._resultado_procesamiento = resultado
                obj._resultado_procesamiento['estado_actual'] = estado_actual

                # CONSTRUIR MENSAJE MEJORADO USANDO RESULTADO
                messages = []
                messages.append(f"Punto procesado correctamente para Equipo {obj.equipo_ganador}")

                # Usar información del resultado
                if resultado.get('juego_finalizado'):
                    messages.append(f"Juego completado - Ganador: Equipo {resultado['ganador_juego']}")

                if resultado.get('set_finalizado'):
                    messages.append(f"Set completado - Ganador: Equipo {resultado['ganador_set']}")

                if resultado.get('partido_finalizado'):
                    messages.append(f"PARTIDO FINALIZADO - Ganador: Equipo {resultado['ganador_partido']}")

                if resultado.get('nuevo_set_creado'):
                    messages.append("Nuevo set creado automáticamente")

                if resultado.get('nuevo_juego_creado'):
                    messages.append("Nuevo juego creado automáticamente")

                # Mostrar marcador actual
                juego_info = estado_actual['juego_actual']
                if juego_info.get('puntos_display_1') and juego_info.get('puntos_display_2'):
                    messages.append(
                        f"Marcador actual: {juego_info['puntos_display_1']} - {juego_info['puntos_display_2']}")

                # Sets actuales
                sets_info = estado_actual.get('sets', {})
                if sets_info:
                    messages.append(f"Sets: {sets_info.get('equipo1', 0)}-{sets_info.get('equipo2', 0)}")

                # Total de puntos
                if estado_actual.get('total_puntos'):
                    messages.append(f"Total puntos jugados: {estado_actual['total_puntos']}")

                # Mostrar mensaje completo
                self.message_user(
                    request,
                    format_html('<br>'.join(messages)),
                    level='SUCCESS'
                )

            except Exception as e:
                self.message_user(
                    request,
                    f'Error procesando punto: {str(e)}',
                    level='ERROR'
                )
                # No guardar si hay error
                return
        else:
            # Para ediciones, usar save normal
            super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """Mostrar solo puntos de partidos en juego por defecto"""
        qs = super().get_queryset(request)
        if not request.GET:
            return qs.filter(juego__set__partido__estado='En Juego')
        return qs

    # Acciones adicionales mejoradas
    actions = ['deshacer_puntos_seleccionados', 'ver_estado_partidos', 'ver_historial_detallado']

    def deshacer_puntos_seleccionados(self, request, queryset):
        """Deshace el último punto de cada partido representado"""
        partidos_procesados = set()
        puntos_deshechos = 0
        errores = []

        for punto in queryset.order_by('-timestamp'):
            partido = punto.juego.set.partido

            if partido.id not in partidos_procesados:
                try:
                    servicio = PadelScoringService(partido.id)
                    servicio.undo_last_point()
                    puntos_deshechos += 1
                    partidos_procesados.add(partido.id)
                except Exception as e:
                    errores.append(f"Error en {partido}: {str(e)}")

        # Mensajes de resultado
        if puntos_deshechos > 0:
            self.message_user(request, f"{puntos_deshechos} puntos deshechos correctamente")

        for error in errores:
            self.message_user(request, error, level='WARNING')

    deshacer_puntos_seleccionados.short_description = "Deshacer último punto de cada partido"

    def ver_estado_partidos(self, request, queryset):
        """Muestra el estado actual de los partidos con información mejorada"""
        partidos_info = {}

        for punto in queryset:
            partido = punto.juego.set.partido
            if partido.id not in partidos_info:
                try:
                    servicio = PadelScoringService(partido.id)
                    estado = servicio.get_live_score()
                    partidos_info[partido.id] = estado
                except Exception as e:
                    partidos_info[partido.id] = {'error': str(e)}

        # Mostrar información mejorada
        for partido_id, info in partidos_info.items():
            if 'error' in info:
                self.message_user(request, f"Error en partido {partido_id}: {info['error']}", level='ERROR')
            else:
                mensaje = f"{info['equipo1']} vs {info['equipo2']} | Sets: {info['sets']['equipo1']}-{info['sets']['equipo2']}"
                if info['juego_actual'].get('puntos_display_1'):
                    mensaje += f" | Juego: {info['juego_actual']['puntos_display_1']}-{info['juego_actual']['puntos_display_2']}"

                # MEJORA: Agregar total de puntos
                if info.get('total_puntos'):
                    mensaje += f" | Total puntos: {info['total_puntos']}"

                self.message_user(request, mensaje, level='INFO')

    ver_estado_partidos.short_description = "Ver estado de partidos"

    # NUEVA ACCION: Ver historial detallado
    def ver_historial_detallado(self, request, queryset):
        """Muestra historial detallado de los partidos"""
        partidos_procesados = set()

        for punto in queryset:
            partido = punto.juego.set.partido
            if partido.id not in partidos_procesados:
                try:
                    servicio = PadelScoringService(partido.id)
                    historial = servicio.get_detailed_score_history()

                    self.message_user(request, f"Historial de {partido}:", level='INFO')
                    for set_data in historial:
                        set_msg = f"  Set {set_data['set_numero']}: {set_data['resultado_final']}"
                        if set_data['finalizado']:
                            set_msg += f" (Ganador: Eq.{set_data['ganador']})"
                        else:
                            set_msg += " (En curso)"
                        self.message_user(request, set_msg, level='INFO')

                    partidos_procesados.add(partido.id)

                except Exception as e:
                    self.message_user(request, f"Error obteniendo historial de {partido}: {str(e)}", level='ERROR')

    ver_historial_detallado.short_description = "Ver historial detallado"


# ADMIN PARA HISTORIAL
@admin.register(HistorialJugador)
class HistorialJugadorAdmin(admin.ModelAdmin):
    list_display = ['jugador', 'partido', 'equipo_jugador', 'es_ganador', 'Pareja']
    list_filter = ['es_ganador', 'equipo_jugador', 'partido__modalidad']
    search_fields = ['jugador__nombre', 'jugador__apellido', 'partido__cancha__nombre']


# ADMIN PARA ESTADÍSTICAS
@admin.register(EstadisticasJugador)
class EstadisticasJugadorAdmin(admin.ModelAdmin):
    list_display = ['jugador', 'partidos_jugados', 'partidos_ganados', 'ultima_actualizacion']
    list_filter = ['ultima_actualizacion']
    search_fields = ['jugador__nombre', 'jugador__apellido']
    readonly_fields = ['ultima_actualizacion']

# ADMIN PARA RESERVAS
@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ['codigo_reserva', 'cancha', 'tipo_reserva', 'estado', 'fecha_inicio', 'fecha_fin', 'pagado',
                    'precio_total']
    list_filter = ['estado', 'tipo_reserva', 'pagado', 'cancha']
    search_fields = ['codigo_reserva', 'cancha__nombre']
    date_hierarchy = 'fecha_inicio'
    readonly_fields = ['codigo_reserva', 'precio_total', 'fecha_creacion']

    fieldsets = (
        ('Información Básica', {
            'fields': ('codigo_reserva', 'cancha', 'tipo_reserva', 'estado')
        }),
        ('Horario', {
            'fields': ('fecha_inicio', 'fecha_fin', 'duracion_minutos')
        }),
        ('Precio', {
            'fields': ('precio_hora', 'precio_total', 'pagado')
        }),
        ('Detalles', {
            'fields': ('numero_jugadores', 'observaciones', 'equipamiento_incluido'),
            'classes': ('collapse',)
        }),
        ('Sistema', {
            'fields': ('fecha_creacion', 'creado_por', 'partido'),
            'classes': ('collapse',)
        })
    )
