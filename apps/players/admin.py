# apps/players/admin.py
from django.contrib import admin
from .models import Jugador

@admin.register(Jugador)
class JugadorAdmin(admin.ModelAdmin):
    list_display = ['nombre_completo', 'user_email', 'edad', 'sexo', 'activo', 'fecha_creacion']
    list_filter = ['sexo', 'activo', 'fecha_creacion']
    search_fields = ['user__first_name', 'user__last_name', 'user__email']
    list_per_page = 25

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
    readonly_fields = ['id', 'fecha_creacion', 'fecha_actualizacion', 'nombre_completo', 'user_email']

    # Métodos para mostrar datos del user
    def nombre_completo(self, obj):
        return obj.nombre_completo
    nombre_completo.short_description = 'Nombre Completo'

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
