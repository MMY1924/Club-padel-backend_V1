
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class Jugador(models.Model):
    SEXO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('O', 'Otro'),
    ]

    # UUID auto-generado
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # ✅ USER OBLIGATORIO - Todos los jugadores deben tener usuario
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='jugador',
        help_text="Usuario Django asociado (obligatorio)"
    )

    # ✅ CAMPOS QUE SE MANTIENEN EN LA TABLA JUGADORES
    edad = models.PositiveIntegerField(
        validators=[
            MinValueValidator(8, message="La edad mínima es 8 años"),
            MaxValueValidator(120, message="La edad máxima es 120 años")
        ],
        help_text="Edad del jugador",
        null=True,
        blank=True
    )

    sexo = models.CharField(
        max_length=1,
        choices=SEXO_CHOICES,
        help_text="Sexo del jugador",
        blank=True
    )

    telefono = models.CharField(
        max_length=20,
        blank=True,
        help_text="Teléfono de contacto"
    )

    # Campos de control
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)

    # ❌ CAMPOS QUE YA NO EXISTEN EN LA BD:
    # nombre = models.CharField(...)           # Eliminado - viene de user.first_name
    # apellido = models.CharField(...)         # Eliminado - viene de user.last_name
    # email = models.EmailField(...)           # Eliminado - viene de user.email
    # nivel_habilidad = models.PositiveIntegerField(...)  # Eliminado completamente
    # es_invitado = models.BooleanField(...)   # Eliminado

    class Meta:
        db_table = 'jugadores'
        verbose_name = 'Jugador'
        verbose_name_plural = 'Jugadores'
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return f"{self.nombre_completo} {'(Invitado)' if self.es_jugador_invitado() else ''}"

    # ✅ PROPIEDADES PARA ACCEDER A DATOS DE AUTH_USER
    @property
    def nombre(self):
        """Obtiene el nombre del usuario relacionado"""
        return self.user.first_name

    @property
    def apellido(self):
        """Obtiene el apellido del usuario relacionado"""
        return self.user.last_name

    @property
    def email(self):
        """Obtiene el email del usuario relacionado"""
        return self.user.email

    @property
    def username(self):
        """Obtiene el username del usuario relacionado"""
        return self.user.username

    @property
    def nombre_completo(self):
        """Obtiene el nombre completo del usuario"""
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username

    # ✅ MÉTODOS DE UTILIDAD
    def es_jugador_invitado(self):
        """Verifica si es un jugador invitado genérico por el username"""
        return self.user.username.startswith('jugador_invitado_')

    def puede_hacer_reservas(self):
        """Verifica si puede hacer reservas"""
        return self.activo

    def actualizar_perfil(self, nombre=None, apellido=None, email=None):
        """Actualiza datos en auth_user"""
        if nombre:
            self.user.first_name = nombre
        if apellido:
            self.user.last_name = apellido
        if email:
            self.user.email = email
        self.user.save()


# ✅ MANAGER PERSONALIZADO
class JugadorManager(models.Manager):
    def get_queryset(self):
        """Siempre incluye los datos del usuario"""
        return super().get_queryset().select_related('user')

    def activos(self):
        """Solo jugadores activos"""
        return self.filter(activo=True)

    def registrados(self):
        """Solo jugadores registrados (no invitados)"""
        return self.exclude(user__username__startswith='jugador_invitado_')

    def invitados(self):
        """Solo jugadores invitados genéricos"""
        return self.filter(user__username__startswith='jugador_invitado_')

    def disponibles_para_invitados(self):
        """Jugadores invitados disponibles para usar"""
        return self.filter(
            user__username__startswith='jugador_invitado_',
            activo=True
        ).order_by('user__username')


# Asignar el manager
Jugador.add_to_class('objects', JugadorManager())


# ✅ FUNCIONES DE UTILIDAD
def obtener_jugador_invitado_disponible():
    """Obtiene el primer jugador invitado disponible"""
    return Jugador.objects.disponibles_para_invitados().first()


def obtener_todos_jugadores_invitados():
    """Obtiene todos los jugadores invitados"""
    return Jugador.objects.disponibles_para_invitados()


def crear_jugador_registrado(username, email, first_name, last_name, password, **kwargs):
    """Crear jugador con usuario en una sola operación"""
    from django.db import transaction

    with transaction.atomic():
        # Crear usuario
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password
        )

        # Crear jugador
        jugador = Jugador.objects.create(user=user, **kwargs)
        return jugador