import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import transaction


def generar_username_unico(base_username):
    """Genera un username único agregando sufijos si es necesario."""
    username = base_username
    contador = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}_{contador}"
        contador += 1
    return username


class JugadorManager(models.Manager):
    """Consultas personalizadas"""
    def get_queryset(self):
        return super().get_queryset().select_related('user')

    def activos(self):
        return self.filter(activo=True)

    def registrados(self):
        return self.exclude(user__username__startswith='jugador_invitado_')

    def invitados(self):
        return self.filter(user__username__startswith='jugador_invitado_')

    def disponibles_para_invitados(self):
        return self.filter(
            user__username__startswith='jugador_invitado_',
            activo=True
        ).order_by('user__username')


class Jugador(models.Model):
    # UUID auto-generado
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # USER OBLIGATORIO - Todos los jugadores deben tener usuario
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='jugador',
        help_text="Usuario Django asociado (obligatorio)"
    )

    # CAMPOS QUE SE MANTIENEN EN LA TABLA JUGADORES
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
        choices=[
            ('M', 'Masculino'),
            ('F', 'Femenino'),
            ('O', 'Otro'),
        ],
        help_text="Sexo del jugador",
        blank=True
    )

    telefono = models.CharField(
        max_length=20,
        blank=True,
        help_text="Teléfono de contacto"
    )

    # CAMPOS DE CONTROL
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)

    objects = JugadorManager()

    class Meta:
        db_table = 'jugadores'
        verbose_name = 'Jugador'
        verbose_name_plural = 'Jugadores'
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return f"{self.nombre_completo} {'(Invitado)' if self.es_invitado else ''}"

    #  PROPIEDADES PARA ACCEDER A DATOS DE AUTH_USER -
    @property
    def nombre(self):
        return self.user.first_name

    @property
    def apellido(self):
        return self.user.last_name

    @property
    def email(self):
        return self.user.email

    @property
    def username(self):
        return self.user.username

    @property
    def nombre_completo(self):
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username

    #  PROPIEDADES ADICIONALES USADAS EN VISTAS
    @property
    def es_invitado(self):
        return self.user.username.startswith('jugador_invitado_')

    @property
    def es_registrado(self):
        return not self.es_invitado

    @property
    def email_efectivo(self):
        return self.user.email or "sin_email@no-definido.com"

    @property
    def nivel_habilidad(self):
        # Si no existe el campo real, devuelve un valor por defecto
        return getattr(self, '_nivel_habilidad', 'No definido')

    # MÉTODOS DE UTILIDAD
    def puede_hacer_reservas(self):
        return self.activo

    def actualizar_perfil(self, nombre=None, apellido=None, email=None):
        if nombre:
            self.user.first_name = nombre
        if apellido:
            self.user.last_name = apellido
        if email:
            self.user.email = email
        self.user.save()

    @classmethod
    def crear_con_usuario(cls, username, password=None, nombre=None, apellido=None, email=None, **kwargs):
        """Crea un Jugador junto con su usuario de Django asociado."""
        with transaction.atomic():
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': nombre or "",
                    'last_name': apellido or "",
                    'email': email or ""
                }
            )
            # Si se pasa un password, se asigna; si no, queda como no utilizable
            if password:
                user.set_password(password)
            else:
                user.set_unusable_password()
            user.save()

            jugador, _ = cls.objects.get_or_create(
                user=user,
                defaults=kwargs
            )
        return jugador


#  FUNCIONES DE UTILIDAD
def obtener_jugador_invitado_disponible():
    return Jugador.objects.disponibles_para_invitados().first()

def obtener_todos_jugadores_invitados():
    return Jugador.objects.disponibles_para_invitados()

def crear_jugador_registrado(username, email, first_name, last_name, password, **kwargs):
    """Crea un jugador registrado junto con su usuario de Django (username único)."""
    with transaction.atomic():
        username_unico = generar_username_unico(username)
        user = User.objects.create_user(
            username=username_unico,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password
        )
        # La señal ya creó el jugador automáticamente, solo actualizamos los campos adicionales
        jugador = user.jugador
        for key, value in kwargs.items():
            setattr(jugador, key, value)
        jugador.save()
        return jugador
