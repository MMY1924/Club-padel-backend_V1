# apps/players/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Jugador

@receiver(post_save, sender=User)
def create_jugador_profile(sender, instance, created, **kwargs):
    """
    Señal que se ejecuta automáticamente cada vez que se crea un User.
    Crea automáticamente un Jugador asociado si no existe.
    """
    if created and not hasattr(instance, 'jugador'):
        Jugador.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_jugador_profile(sender, instance, **kwargs):
    """
    Señal que sincroniza los datos del User con el Jugador asociado.
    (En este modelo ya no es necesario copiar nombre/apellido/email,
    porque se acceden directamente desde User)
    """
    if hasattr(instance, 'jugador'):
        instance.jugador.save()
