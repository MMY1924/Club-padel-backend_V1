# apps/players/admin.py
from django.contrib import admin
from .models import Jugador


@admin.register(Jugador)
class JugadorAdmin(admin.ModelAdmin):
    # Campos que se muestran en la tabla del admin
    list_display = ['nombre_completo', 'user_email', 'edad', 'sexo', 'activo', 'fecha_creacion']
    list_filter = ['sexo', 'activo', 'fecha_creacion']
    search_fields = ['user__first_name', 'user__last_name', 'user__email']
    list_per_page = 25

    # Secciones agrupadas en el panel de administración
    fieldsets = (
        ('Información Personal', {
            'fields': ('user', 'nombre_completo', 'user_email', 'edad', 'sexo')
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
        ('Información del Sistema', {
            'fields': ('id', 'fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )

    # Campos solo de lectura (evita modificaciones en el admin)
    readonly_fields = ['id', 'fecha_creacion', 'fecha_actualizacion', 'nombre_completo', 'user_email']

    # Métodos para mostrar datos relacionados al usuario
    def nombre_completo(self, obj: Jugador) -> str:
        """Retorna el nombre completo del jugador."""
        return obj.nombre_completo
    nombre_completo.short_description = 'Nombre Completo'

    def user_email(self, obj: Jugador) -> str:
        """Retorna el email asociado al usuario."""
        return obj.user.email
    user_email.short_description = 'Email'
