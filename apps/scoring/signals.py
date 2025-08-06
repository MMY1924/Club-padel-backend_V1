# apps/scoring/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Partido, Set, Juego
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Partido)
def crear_estructura_inicial_partido(sender, instance, created, **kwargs):
    """
    Cuando se crea un partido o se cambia a 'En Juego',
    crear automáticamente Set 1 y Juego 1
    """
    # Si el partido está 'En Juego' y no tiene sets
    if instance.estado == 'En Juego' and instance.sets.count() == 0:
        print(f"Creando estructura inicial para partido {instance.id}")

        # Crear primer set
        primer_set = Set.objects.create(
            partido=instance,
            numero_set=1,
            juegos_equipo1=0,
            juegos_equipo2=0,
            finalizado=False,
            equipo_ganador=0,
            tiene_tiebreak=False,
            puntos_tiebreak_equipo1=0,
            puntos_tiebreak_equipo2=0
        )

        # Crear primer juego
        primer_juego = Juego.objects.create(
            set=primer_set,
            numero_juego=1,
            puntos_equipo1=0,
            puntos_equipo2=0,
            finalizado=False,
            equipo_ganador=0,
            equipo_que_saca=1  # Equipo 1 saca primero
        )

        print(f" Set y Juego creados para partido {instance.id}")

# SEÑALES MEJORADAS PARA HISTORIAL Y ESTADÍSTICAS
@receiver(pre_save, sender=Partido)
def capturar_estado_anterior(sender, instance, **kwargs):
    """Captura el estado anterior antes de guardar"""
    if instance.pk:
        try:
            partido_anterior = Partido.objects.get(pk=instance.pk)
            instance._estado_anterior = partido_anterior.estado
            print(f"🔍 Estado anterior capturado para {instance.id}: {instance._estado_anterior}")
        except Partido.DoesNotExist:
            instance._estado_anterior = None
            print(f"🔍 Partido {instance.id} no existe previamente")
    else:
        instance._estado_anterior = None
        print(f"🔍 Nuevo partido {instance.id}")


@receiver(post_save, sender=Partido)
def procesar_partido_finalizado(sender, instance, created, **kwargs):
    """
    Señal que se ejecuta automáticamente cuando un partido cambia a 'Finalizado'
    """
    # Debug logging mejorado
    estado_anterior = getattr(instance, '_estado_anterior', 'NO_DETECTADO')
    print(f"📊 SEÑAL EJECUTADA - Partido: {instance.id}")
    print(f"   - Created: {created}")
    print(f"   - Estado actual: {instance.estado}")
    print(f"   - Estado anterior: {estado_anterior}")
    print(f"   - Equipo ganador: {instance.equipo_ganador}")
    
    if not created:  # Solo para actualizaciones, no creaciones
        # Si cambió a 'Finalizado' desde otro estado
        if instance.estado == 'Finalizado' and estado_anterior != 'Finalizado':
            print(f" PARTIDO FINALIZADO DETECTADO: {instance.id}")
            
            try:
                # Verificar que tenga equipo ganador
                if not instance.equipo_ganador:
                    print(f"  Partido {instance.id} finalizado sin equipo ganador. Saltando...")
                    return
                
                # Verificar si ya tiene historial (evitar duplicados)
                from .models import HistorialJugador
                historial_existente = HistorialJugador.objects.filter(partido=instance)
                if historial_existente.exists():
                    print(f"  Partido {instance.id} ya tiene historial ({historial_existente.count()} registros). Saltando...")
                    return
                
                print(f" Creando historial para partido {instance.id}...")
                
                # Importar y ejecutar la función de crear historial
                from .services import crear_historial_y_actualizar_estadisticas
                crear_historial_y_actualizar_estadisticas(instance)
                
                print(f"Historial y estadísticas creadas automáticamente para partido {instance.id}")
                logger.info(f"Historial y estadísticas creadas automáticamente para partido {instance.id}")
                
            except Exception as e:
                error_msg = f" Error procesando partido finalizado {instance.id}: {str(e)}"
                print(error_msg)
                logger.error(error_msg)
                import traceback
                traceback.print_exc()
        else:
            print(f"🔄 Cambio de estado no relevante para historial")


@receiver(post_save, sender=Partido)
def log_partido_changes(sender, instance, created, **kwargs):
    """Log de cambios en partidos para debugging"""
    if created:
        print(f"Nuevo partido creado: {instance.id} - {instance}")
        logger.info(f"Nuevo partido creado: {instance.id} - {instance}")
    else:
        estado_anterior = getattr(instance, '_estado_anterior', 'Desconocido')
        if estado_anterior != instance.estado:
            print(f" Partido {instance.id} cambió de estado: {estado_anterior} → {instance.estado}")
            logger.info(f"Partido {instance.id} cambió de estado: {estado_anterior} → {instance.estado}")
