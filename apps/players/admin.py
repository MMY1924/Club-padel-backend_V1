# apps/players/admin.py
from django.contrib import admin
from .models import Jugador

@admin.register(Jugador)
class JugadorAdmin(admin.ModelAdmin):
    list_display = ['nombre_completo', 'email', 'edad', 'sexo', 'activo', 'fecha_creacion']
    list_filter = ['sexo', 'activo', 'fecha_creacion']
    search_fields = ['nombre', 'apellido', 'email']
    readonly_fields = ['id', 'fecha_creacion', 'fecha_actualizacion']
    list_per_page = 25
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre', 'apellido', 'email', 'edad', 'sexo')
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
        ('Información del Sistema', {
            'fields': ('id', 'fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )
    
    def nombre_completo(self, obj):
        return obj.nombre_completo
    nombre_completo.short_description = 'Nombre Completo'
