# apps/players/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Jugador


@receiver(post_save, sender=User)
def create_jugador_profile(sender, instance, created, **kwargs):
    """
    Señal que se ejecuta automáticamente cada vez que se crea un User.
    Crea automáticamente un Jugador asociado.
    """
    if created:
        # Solo crear Jugador si no existe ya uno asociado
        if not hasattr(instance, 'jugador'):
            Jugador.objects.create(
                user=instance,
                nombre=instance.first_name or '',
                apellido=instance.last_name or '',
                email=instance.email,
                es_invitado=False,  # Es un jugador registrado
                activo=True,
                nivel_habilidad=1  # Nivel principiante por defecto
            )


@receiver(post_save, sender=User)
def save_jugador_profile(sender, instance, **kwargs):
    """
    Señal que se ejecuta cada vez que se actualiza un User.
    Sincroniza los datos del User con su Jugador asociado.
    """
    if hasattr(instance, 'jugador') and not instance.jugador.es_invitado:
        jugador = instance.jugador

        # Sincronizar datos básicos si el jugador no tiene datos propios
        if not jugador.nombre and instance.first_name:
            jugador.nombre = instance.first_name

        if not jugador.apellido and instance.last_name:
            jugador.apellido = instance.last_name

        if not jugador.email and instance.email:
            jugador.email = instance.email

        jugador.save()
