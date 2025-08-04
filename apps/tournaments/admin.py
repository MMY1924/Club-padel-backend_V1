# apps/tournaments/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from .models import (
    Torneo, InscripcionTorneo, FaseTorneo,
    GrupoTorneo, PartidoTorneo, ClasificacionTorneo
)
from .services import TournamentService


# ==========================================
# INLINES
# ==========================================
class InscripcionInline(admin.TabularInline):
    model = InscripcionTorneo
    extra = 0
    fields = ['jugador1', 'jugador2', 'estado', 'pagado', 'ranking_inicial']
    readonly_fields = ['fecha_inscripcion']


class FaseTorneoInline(admin.TabularInline):
    model = FaseTorneo
    extra = 0
    fields = ['tipo', 'nombre', 'orden', 'activa', 'completada']
    readonly_fields = ['fecha_creacion']


class PartidoTorneoInline(admin.TabularInline):
    model = PartidoTorneo
    extra = 0
    fields = [
        'fase', 'inscripcion_equipo1', 'inscripcion_equipo2',
        'fecha_programada', 'cancha_asignada', 'partido_link'
    ]
    readonly_fields = ['partido_link', 'fecha_creacion']

    def partido_link(self, obj):
        if obj.partido:
            url = reverse('admin:scoring_partido_change', args=[obj.partido.id])
            return format_html('<a href="{}">Ver Partido</a>', url)
        return "Sin partido"

    partido_link.short_description = 'Partido'


# ==========================================
# ADMIN PARA TORNEO
# ==========================================
@admin.register(Torneo)
class TorneoAdmin(admin.ModelAdmin):
    list_display = [
        'codigo_torneo', 'nombre', 'tipo_badge', 'modalidad',
        'estado_badge', 'participantes_info', 'fecha_inicio',
        'activo_badge'
    ]
    list_filter = ['tipo', 'modalidad', 'estado', 'activo', 'fecha_inicio']
    search_fields = ['codigo_torneo', 'nombre', 'descripcion']
    readonly_fields = [
        'id', 'fecha_creacion', 'fecha_modificacion',
        'participantes_registrados', 'esta_lleno', 'puede_iniciar'
    ]
    filter_horizontal = ['canchas']

    fieldsets = (
        ('Información Básica', {
            'fields': (
                'id', 'codigo_torneo', 'nombre', 'descripcion',
                'tipo', 'modalidad', 'estado', 'activo'
            )
        }),
        ('Configuración de Participantes', {
            'fields': (
                'min_participantes', 'max_participantes',
                'participantes_registrados', 'esta_lleno',
                'permite_inscripcion_individual'
            )
        }),
        ('Configuración de Partidos', {
            'fields': (
                'sets_para_ganar', 'juegos_para_ganar_set',
                'canchas'
            )
        }),
        ('Configuración de Grupos', {
            'fields': ('numero_grupos', 'clasifican_por_grupo'),
            'classes': ('collapse',),
            'description': 'Solo aplica para torneos tipo "Grupos + Eliminación"'
        }),
        ('Fechas', {
            'fields': (
                'fecha_inicio', 'fecha_fin',
                'fecha_creacion', 'fecha_modificacion'
            )
        }),
        ('Premios e Inscripción', {
            'fields': ('costo_inscripcion', 'premio_descripcion'),
            'classes': ('collapse',)
        }),
        ('Opciones Adicionales', {
            'fields': ('sorteo_publico', 'puede_iniciar'),
            'classes': ('collapse',)
        })
    )

    inlines = [InscripcionInline, FaseTorneoInline]

    def tipo_badge(self, obj):
        colors = {
            'Eliminacion': 'purple',
            'Ranking': 'blue',
            'Grupos': 'green'
        }
        color = colors.get(obj.tipo, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_tipo_display()
        )

    tipo_badge.short_description = 'Tipo'

    def estado_badge(self, obj):
        colors = {
            'Inscripcion': 'green',
            'Preparacion': 'orange',
            'En_Curso': 'blue',
            'Finalizado': 'gray',
            'Cancelado': 'red'
        }
        color = colors.get(obj.estado, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_estado_display()
        )

    estado_badge.short_description = 'Estado'

    def activo_badge(self, obj):
        return format_html(
            '<span style="color: {};">●</span>',
            'green' if obj.activo else 'red'
        )

    activo_badge.short_description = 'Activo'

    def participantes_info(self, obj):
        color = 'green' if obj.participantes_registrados >= obj.min_participantes else 'orange'
        if obj.esta_lleno:
            color = 'red'
        return format_html(
            '<span style="color: {};">{}/{}</span>',
            color, obj.participantes_registrados, obj.max_participantes
        )

    participantes_info.short_description = 'Participantes'

    actions = [
        'generar_sorteo', 'iniciar_torneos', 'finalizar_torneos',
        'exportar_clasificaciones', 'ver_estado_detallado'
    ]

    def generar_sorteo(self, request, queryset):
        """Genera el sorteo para torneos en preparación"""
        for torneo in queryset.filter(estado='Preparacion'):
            try:
                service = TournamentService(torneo)
                service.generate_draw()
                self.message_user(
                    request,
                    f'Sorteo generado para {torneo.nombre}',
                    level='SUCCESS'
                )
            except Exception as e:
                self.message_user(
                    request,
                    f'Error en {torneo.nombre}: {str(e)}',
                    level='ERROR'
                )

    generar_sorteo.short_description = "Generar sorteo"

    def iniciar_torneos(self, request, queryset):
        """Inicia torneos que estén listos"""
        for torneo in queryset.filter(estado='Preparacion'):
            try:
                service = TournamentService(torneo)
                service.start_tournament()
                self.message_user(
                    request,
                    f'Torneo {torneo.nombre} iniciado correctamente',
                    level='SUCCESS'
                )
            except Exception as e:
                self.message_user(
                    request,
                    f'Error iniciando {torneo.nombre}: {str(e)}',
                    level='ERROR'
                )

    iniciar_torneos.short_description = "Iniciar torneos"

    def ver_estado_detallado(self, request, queryset):
        """Muestra estado detallado de los torneos"""
        for torneo in queryset:
            try:
                service = TournamentService(torneo)
                estado = service.get_tournament_status()

                mensaje = f"{torneo.nombre}:"
                mensaje += f"\n- Estado: {estado['estado']}"
                mensaje += f"\n- Participantes: {estado['participantes']}/{torneo.max_participantes}"
                mensaje += f"\n- Fases: {estado['total_fases']} (Activa: {estado['fase_actual']})"
                mensaje += f"\n- Partidos jugados: {estado['partidos_jugados']}/{estado['partidos_totales']}"

                if estado.get('lideres'):
                    mensaje += "\n- Líderes actuales:"
                    for i, lider in enumerate(estado['lideres'][:3], 1):
                        mensaje += f"\n  {i}. {lider['nombre']}"

                self.message_user(request, mensaje, level='INFO')

            except Exception as e:
                self.message_user(
                    request,
                    f'Error obteniendo estado de {torneo.nombre}: {str(e)}',
                    level='ERROR'
                )

    ver_estado_detallado.short_description = "Ver estado detallado"


# ==========================================
# ADMIN PARA INSCRIPCIÓN
# ==========================================
@admin.register(InscripcionTorneo)
class InscripcionTorneoAdmin(admin.ModelAdmin):
    list_display = [
        'nombre_equipo', 'torneo', 'estado_badge', 'pagado_badge',
        'ranking_inicial', 'fecha_inscripcion'
    ]
    list_filter = ['estado', 'pagado', 'torneo', 'fecha_inscripcion']
    search_fields = [
        'jugador1__nombre', 'jugador1__apellido',
        'jugador2__nombre', 'jugador2__apellido',
        'torneo__nombre'
    ]
    readonly_fields = ['id', 'fecha_inscripcion']

    fieldsets = (
        ('Torneo', {
            'fields': ('torneo',)
        }),
        ('Jugadores', {
            'fields': ('jugador1', 'jugador2')
        }),
        ('Estado y Pago', {
            'fields': ('estado', 'pagado', 'monto_pagado')
        }),
        ('Ranking', {
            'fields': ('ranking_inicial',)
        }),
        ('Información Adicional', {
            'fields': ('notas', 'fecha_inscripcion'),
            'classes': ('collapse',)
        })
    )

    def estado_badge(self, obj):
        colors = {
            'Pendiente': 'orange',
            'Confirmada': 'green',
            'Cancelada': 'red',
            'Eliminado': 'gray'
        }
        color = colors.get(obj.estado, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_estado_display()
        )

    estado_badge.short_description = 'Estado'

    def pagado_badge(self, obj):
        if obj.pagado:
            return format_html(
                '<span style="color: green;">✓ ${}</span>',
                obj.monto_pagado
            )
        return format_html('<span style="color: red;">✗</span>')

    pagado_badge.short_description = 'Pagado'

    actions = ['confirmar_inscripciones', 'cancelar_inscripciones']

    def confirmar_inscripciones(self, request, queryset):
        count = queryset.filter(estado='Pendiente').update(
            estado='Confirmada',
            pagado=True
        )
        self.message_user(
            request,
            f'{count} inscripciones confirmadas',
            level='SUCCESS'
        )

    confirmar_inscripciones.short_description = "Confirmar inscripciones"

    def cancelar_inscripciones(self, request, queryset):
        count = queryset.exclude(estado='Cancelada').update(estado='Cancelada')
        self.message_user(
            request,
            f'{count} inscripciones canceladas',
            level='WARNING'
        )

    cancelar_inscripciones.short_description = "Cancelar inscripciones"


# ==========================================
# ADMIN PARA FASE
# ==========================================
@admin.register(FaseTorneo)
class FaseTorneoAdmin(admin.ModelAdmin):
    list_display = [
        'torneo', 'tipo', 'nombre', 'orden',
        'activa_badge', 'completada_badge', 'partidos_info'
    ]
    list_filter = ['tipo', 'activa', 'completada', 'torneo']
    search_fields = ['nombre', 'torneo__nombre']
    readonly_fields = ['id', 'fecha_creacion']

    def activa_badge(self, obj):
        return format_html(
            '<span style="color: {};">●</span>',
            'green' if obj.activa else 'gray'
        )

    activa_badge.short_description = 'Activa'

    def completada_badge(self, obj):
        return format_html(
            '<span style="color: {};">●</span>',
            'blue' if obj.completada else 'gray'
        )

    completada_badge.short_description = 'Completada'

    def partidos_info(self, obj):
        total = obj.partidos.count()
        jugados = obj.partidos.filter(partido__estado='Finalizado').count()

        if total == 0:
            return "-"

        porcentaje = (jugados / total) * 100
        color = 'green' if porcentaje == 100 else 'orange' if porcentaje > 0 else 'red'

        return format_html(
            '<span style="color: {};">{}/{} ({}%)</span>',
            color, jugados, total, int(porcentaje)
        )

    partidos_info.short_description = 'Partidos'


# ==========================================
# ADMIN PARA GRUPO
# ==========================================
@admin.register(GrupoTorneo)
class GrupoTorneoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'fase', 'participantes_count', 'ver_tabla']
    list_filter = ['fase__torneo', 'fase']
    search_fields = ['nombre', 'fase__torneo__nombre']
    filter_horizontal = ['inscripciones']

    def participantes_count(self, obj):
        return obj.inscripciones.count()

    participantes_count.short_description = 'Participantes'

    def ver_tabla(self, obj):
        return format_html(
            '<a href="#" onclick="alert(\'Función en desarrollo\'); return false;">Ver Tabla</a>'
        )

    ver_tabla.short_description = 'Tabla'

    actions = ['mostrar_tabla_posiciones']

    def mostrar_tabla_posiciones(self, request, queryset):
        """Muestra la tabla de posiciones de los grupos"""
        for grupo in queryset:
            tabla = grupo.get_tabla_posiciones()

            mensaje = f"Tabla de {grupo.nombre}:\n"
            for i, pos in enumerate(tabla, 1):
                mensaje += f"\n{i}. {pos['inscripcion'].nombre_equipo}"
                mensaje += f" - Pts: {pos['puntos']}"
                mensaje += f" - PJ: {pos['partidos_jugados']}"
                mensaje += f" - PG: {pos['partidos_ganados']}"
                mensaje += f" - DS: {pos['diferencia_sets']}"

            self.message_user(request, mensaje, level='INFO')

    mostrar_tabla_posiciones.short_description = "Ver tabla de posiciones"


# ==========================================
# ADMIN PARA PARTIDO TORNEO
# ==========================================
@admin.register(PartidoTorneo)
class PartidoTorneoAdmin(admin.ModelAdmin):
    list_display = [
        'torneo', 'fase', 'grupo', 'versus',
        'fecha_programada', 'cancha_asignada',
        'estado_partido', 'acciones'
    ]
    list_filter = [
        'torneo', 'fase__tipo', 'tipo',
        'fecha_programada', 'cancha_asignada'
    ]
    search_fields = [
        'torneo__nombre',
        'inscripcion_equipo1__jugador1__nombre',
        'inscripcion_equipo2__jugador1__nombre'
    ]
    readonly_fields = ['id', 'fecha_creacion', 'partido']

    fieldsets = (
        ('Información del Torneo', {
            'fields': ('torneo', 'fase', 'grupo', 'tipo', 'orden_en_fase')
        }),
        ('Equipos', {
            'fields': ('inscripcion_equipo1', 'inscripcion_equipo2')
        }),
        ('Programación', {
            'fields': ('fecha_programada', 'cancha_asignada')
        }),
        ('Partido', {
            'fields': ('partido',),
            'description': 'Se crea automáticamente cuando se inicia el partido'
        }),
        ('Bracket (Eliminación)', {
            'fields': ('siguiente_partido', 'es_lado_equipo1'),
            'classes': ('collapse',)
        }),
        ('Adicional', {
            'fields': ('notas', 'fecha_creacion'),
            'classes': ('collapse',)
        })
    )

    def versus(self, obj):
        eq1 = obj.inscripcion_equipo1.nombre_equipo if obj.inscripcion_equipo1 else "Por definir"
        eq2 = obj.inscripcion_equipo2.nombre_equipo if obj.inscripcion_equipo2 else "Por definir"
        return f"{eq1} vs {eq2}"

    versus.short_description = 'Partido'

    def estado_partido(self, obj):
        if not obj.partido:
            return format_html('<span style="color: gray;">Sin crear</span>')

        colors = {
            'Pendiente': 'orange',
            'En Juego': 'green',
            'Finalizado': 'blue',
            'Cancelado': 'red'
        }
        color = colors.get(obj.partido.estado, 'gray')

        estado_text = obj.partido.estado
        if obj.partido.estado == 'Finalizado':
            ganador = "Equipo 1" if obj.partido.equipo_ganador == 1 else "Equipo 2"
            estado_text += f" (Ganó {ganador})"

        return format_html(
            '<span style="color: {};">{}</span>',
            color, estado_text
        )

    estado_partido.short_description = 'Estado'

    def acciones(self, obj):
        if not obj.partido:
            return format_html(
                '<a href="#" onclick="return confirm(\'¿Crear partido?\');" '
                'style="color: green;">Crear Partido</a>'
            )
        else:
            url = reverse('admin:scoring_partido_change', args=[obj.partido.id])
            return format_html(
                '<a href="{}" style="color: blue;">Ver Partido</a>',
                url
            )

    acciones.short_description = 'Acciones'

    actions = [
        'crear_partidos', 'asignar_canchas',
        'procesar_resultados'
    ]

    def crear_partidos(self, request, queryset):
        """Crea los partidos reales para los seleccionados"""
        creados = 0
        errores = []

        for partido_torneo in queryset:
            if partido_torneo.partido:
                continue

            try:
                partido_torneo.crear_partido_real()
                creados += 1
            except Exception as e:
                errores.append(f"{partido_torneo}: {str(e)}")

        if creados > 0:
            self.message_user(
                request,
                f'{creados} partidos creados correctamente',
                level='SUCCESS'
            )

        for error in errores:
            self.message_user(request, error, level='ERROR')

    crear_partidos.short_description = "Crear partidos reales"

    def asignar_canchas(self, request, queryset):
        """Asigna canchas disponibles a los partidos"""
        # Esta es una versión simplificada
        canchas_disponibles = list(
            queryset.first().torneo.canchas.filter(estado='Disponible')
        )

        if not canchas_disponibles:
            self.message_user(
                request,
                'No hay canchas disponibles',
                level='WARNING'
            )
            return

        asignados = 0
        for i, partido in enumerate(queryset.filter(cancha_asignada__isnull=True)):
            partido.cancha_asignada = canchas_disponibles[i % len(canchas_disponibles)]
            partido.save()
            asignados += 1

        self.message_user(
            request,
            f'{asignados} canchas asignadas',
            level='SUCCESS'
        )

    asignar_canchas.short_description = "Asignar canchas"

    def procesar_resultados(self, request, queryset):
        """Procesa los resultados de partidos finalizados"""
        procesados = 0
        errores = []

        for partido_torneo in queryset.filter(
                partido__estado='Finalizado'
        ):
            try:
                partido_torneo.procesar_resultado()
                procesados += 1
            except Exception as e:
                errores.append(f"{partido_torneo}: {str(e)}")

        if procesados > 0:
            self.message_user(
                request,
                f'{procesados} resultados procesados',
                level='SUCCESS'
            )

        for error in errores:
            self.message_user(request, error, level='ERROR')

    procesar_resultados.short_description = "Procesar resultados"


# ==========================================
# ADMIN PARA CLASIFICACIÓN
# ==========================================
@admin.register(ClasificacionTorneo)
class ClasificacionTorneoAdmin(admin.ModelAdmin):
    list_display = [
        'posicion_final', 'inscripcion', 'torneo',
        'estadisticas', 'premio_info'
    ]
    list_filter = ['torneo', 'posicion_final']
    search_fields = [
        'inscripcion__jugador1__nombre',
        'inscripcion__jugador2__nombre',
        'torneo__nombre'
    ]
    readonly_fields = [
        'id', 'fecha_registro',
        'partidos_jugados', 'partidos_ganados', 'partidos_perdidos'
    ]

    def estadisticas(self, obj):
        return format_html(
            'PJ: {} | PG: {} | PP: {}',
            obj.partidos_jugados,
            obj.partidos_ganados,
            obj.partidos_perdidos
        )

    estadisticas.short_description = 'Estadísticas'

    def premio_info(self, obj):
        if obj.premio_monto > 0:
            return format_html(
                '<span style="color: green;">${}</span>',
                obj.premio_monto
            )
        return "-"

    premio_info.short_description = 'Premio'