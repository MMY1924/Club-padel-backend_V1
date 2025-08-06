
# Padel Backend API 

![Python](https://img.shields.io/badge/Python-3.12-blue.svg)
![Django](https://img.shields.io/badge/Django-4.2.7-green.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg)
![Redis](https://img.shields.io/badge/Redis-7-red.svg)
![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg)
![Poetry](https://img.shields.io/badge/Poetry-Enabled-60A5FA.svg)

**Sistema completo de gestión de torneos y scoring de padel en tiempo real**

API REST robusta construida con Django REST Framework que proporciona funcionalidades completas para la gestión de torneos de padel, scoring en tiempo real mediante WebSockets, y estadísticas avanzadas de jugadores.

##  Arquitectura

| Componente | Tecnología | Versión |
|------------|------------|---------|
| **Framework Backend** | Django + DRF | 4.2.7 |
| **Base de Datos** | PostgreSQL | 15 |
| **Cache/Sessions** | Redis | 7 |
| **WebSockets** | Django Channels | 4.2.2 |
| **Autenticación** | Django Token Auth + Firebase | - |
| **Containerización** | Docker Compose | - |
| **Gestión de Dependencias** | Poetry | 1.0+ |
| **Servidor Web** | Nginx (Producción) | Alpine |

## Características Principales

### Sistema de Autenticación
- Autenticación basada en tokens JWT
- Integración con Firebase Admin SDK
- Gestión de sesiones y permisos

### Gestión de Jugadores
- Perfiles completos de jugadores
- Sistema de rankings y estadísticas
- Historial de partidos 

### Torneos y Competiciones
- Creación y gestión de torneos
- Múltiples formatos de competición
- Sistema de brackets automático

### Scoring en Tiempo Real
- WebSockets para actualizaciones instantáneas
- Interfaz de scoring interactiva
- Seguimiento de estadísticas en vivo

### Estadísticas Avanzadas
- Métricas detalladas por jugador
- Análisis de rendimiento
- Reportes exportables

### Herramientas de Desarrollo
- Makefile con comandos automatizados
- Docker Compose para desarrollo y producción
- Tests automatizados con pytest
- Code formatting con Black e isort

##  Inicio Rápido

### Prerrequisitos

- Docker y Docker Compose
- Python 3.12+ (para desarrollo local)
- Poetry (opcional, para gestión de dependencias)
- Git

### Instalación con Docker (Recomendado)

1. **Clonar el repositorio**
```bash
git clone https://gitlab.com/ourala/padel/backend.git
cd padel_backend
```

2. **Configurar variables de entorno**
```bash
cp .env.example .env
# Editar .env con tus configuraciones
```

3. **Ejecutar setup completo**
```bash
make dev-setup
```

Este comando ejecutará automáticamente:
- `docker-compose build`
- `docker-compose up -d`
- Migraciones de base de datos
- Recolección de archivos estáticos

### Instalación con Poetry (Desarrollo Local)

```bash
# Instalar dependencias
poetry install --with dev

# Activar entorno virtual
poetry shell

# Configurar base de datos
poetry run python manage.py migrate

# Iniciar servidor de desarrollo
poetry run python manage.py runserver
```

## Comandos de Desarrollo

### Make Commands (Recomendado)

```bash
make help                 # Ver todos los comandos disponibles
make up                   # Iniciar servicios
make down                 # Detener servicios
make logs                 # Ver logs de todos los servicios
make logs-web             # Ver logs del backend únicamente
make shell                # Acceder a Django shell
make bash                 # Acceder a bash del contenedor
make migrate              # Ejecutar migraciones
make makemigrations       # Crear nuevas migraciones
make test                 # Ejecutar tests
make test-coverage        # Tests con reporte de cobertura
make lint                 # Verificar calidad del código
make format               # Formatear código automáticamente
make clean                # Limpiar contenedores y volúmenes
```

### Docker Compose

```bash
docker-compose up -d                              # Iniciar servicios
docker-compose logs -f                            # Ver logs
docker-compose exec web python manage.py shell   # Django shell
docker-compose exec web python manage.py migrate # Migraciones
docker-compose down                               # Detener servicios
```

### Poetry (Desarrollo Local)

```bash
poetry run python manage.py runserver    # Servidor de desarrollo
poetry run python manage.py migrate      # Migraciones
poetry run python manage.py shell        # Django shell
poetry run python manage.py test         # Tests
poetry run black .                       # Formatear código
poetry run flake8 .                      # Linting
```

## Estructura del Proyecto

```
padel_backend/
├──  apps/                      # Aplicaciones Django
│   ├──  authentication/       # Autenticación y usuarios
│   ├──  players/              # Gestión de jugadores
│   ├──  matches/              # Gestión de partidos  
│   ├──  scoring/              # Sistema de scoring en tiempo real
│   ├──  statistics/           # Estadísticas y métricas
│   └──  tournaments/          # Gestión de torneos
├──   padel_backend/           # Configuración principal Django
├──   docker/                   # Configuraciones Docker
│   ├──   postgres/           # Scripts de inicialización PostgreSQL
│   └──  nginx/               # Configuración Nginx
├──  requirements.txt          # Dependencias (legacy)
├──  pyproject.toml           # Configuración Poetry y herramientas
├──  docker-compose.yml       # Servicios Docker
├──  Dockerfile               # Imagen Docker personalizada
├──  Makefile                 # Comandos automatizados
└──  README.md                # Esta documentación
```

##  API Endpoints

###  Autenticación
```
POST   /api/auth/login/          # Iniciar sesión
POST   /api/auth/register/       # Registro de usuario  
POST   /api/auth/refresh/        # Renovar token
DELETE /api/auth/logout/         # Cerrar sesión
```

###  Jugadores
```
GET    /api/players/             # Listar jugadores
POST   /api/players/             # Crear jugador
GET    /api/players/{id}/        # Detalle de jugador
PUT    /api/players/{id}/        # Actualizar jugador
DELETE /api/players/{id}/        # Eliminar jugador
GET    /api/players/{id}/stats/  # Estadísticas del jugador
```

###  Partidos
```
GET    /api/matches/             # Listar partidos
POST   /api/matches/             # Crear partido
GET    /api/matches/{id}/        # Detalle de partido
PUT    /api/matches/{id}/        # Actualizar partido
DELETE /api/matches/{id}/        # Eliminar partido
```

###  Torneos
```
GET    /api/tournaments/         # Listar torneos
POST   /api/tournaments/         # Crear torneo
GET    /api/tournaments/{id}/    # Detalle de torneo
PUT    /api/tournaments/{id}/    # Actualizar torneo
DELETE /api/tournaments/{id}/    # Eliminar torneo
```

###  Scoring en Tiempo Real (WebSockets)
```
ws://localhost:8000/ws/match/{match_id}/  # Conexión WebSocket para scoring
```

###  Health Check
```
GET    /health/                  # Estado del servicio
GET    /api/health/              # Estado detallado de la API
```

##  Configuración

### Variables de Entorno

Crea un archivo `.env` con las siguientes variables:

```env
# Django
DEBUG=1
SECRET_KEY=tu-clave-secreta-muy-segura
ALLOWED_HOSTS=localhost,127.0.0.1

# Base de Datos PostgreSQL
DB_NAME=padel_db
DB_USER=postgres
DB_PASSWORD=123456789a
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# Firebase (opcional)
FIREBASE_PROJECT_ID=tu-proyecto-firebase
FIREBASE_PRIVATE_KEY_ID=tu-private-key-id
```

### Configuración de Base de Datos

El proyecto está configurado para PostgreSQL con las siguientes características:

- **Motor**: PostgreSQL 15
- **Codificación**: UTF-8
- **Puerto**: 5432
- **SSL Mode**: prefer (configurable)

### Configuración de Redis

Redis se utiliza para:
- Django Channels (WebSockets)
- Cache de sesiones
- Queue de tareas asíncronas

##  Testing

### Ejecutar Tests

```bash
# Con Docker (recomendado)
make test

# Con Poetry
poetry run python manage.py test

# Con cobertura
make test-coverage
```

### Estructura de Tests

```
apps/
├── players/
│   └── tests/
├── scoring/
│   └── tests/
└── tournaments/
    └── tests/
```

##  Despliegue

### Producción con Docker

```bash
# Setup completo para producción
make prod-setup

# O paso a paso
docker-compose --profile production build
docker-compose --profile production up -d
```

### Configuraciones de Producción

1. **Variables de entorno**:
   ```env
   DEBUG=False
   ALLOWED_HOSTS=tu-dominio.com
   SECRET_KEY=clave-super-segura-de-produccion
   ```

2. **Base de datos**: Usar PostgreSQL en un servidor dedicado

3. **SSL/TLS**: Configurar certificados en Nginx

4. **Backup**: Configurar respaldos automáticos de PostgreSQL

5. **Monitoreo**: Implementar logging y métricas

##  Monitoreo y Logs

### Logs de Aplicación

```bash
# Todos los servicios
make logs

# Solo el backend
make logs-web

# Base de datos
docker-compose logs db

# Redis
docker-compose logs redis
```

### Health Checks

El sistema incluye endpoints de salud:

- `/health/` - Estado básico del servicio
- `/api/health/` - Estado detallado con métricas

##  Desarrollo

### Calidad de Código

```bash
# Formatear código
make format

# Verificar linting
make lint

# Verificar antes de commit
make format && make lint && make test
```

### Herramientas Configuradas

- **Black**: Formateador de código Python
- **isort**: Organizador de imports
- **flake8**: Linter para Python
- **pytest**: Framework de testing
- **coverage**: Análisis de cobertura de tests

### Flujo de Desarrollo Recomendado

1. Crear rama feature: `git checkout -b feature/nueva-funcionalidad`
2. Desarrollar y hacer commits frecuentes
3. Ejecutar tests: `make test`
4. Verificar calidad: `make lint`
5. Formatear código: `make format`
6. Push y crear Pull Request


## Solución de Problemas

### Problemas Comunes

| Problema | Solución |
|----------|----------|
| **Error de conexión a PostgreSQL** | Verificar que el contenedor `db` esté corriendo: `docker-compose ps` |
| **Error de dependencias** | Reconstruir contenedores: `docker-compose build` |
| **WebSockets no funcionan** | Verificar Redis: `docker-compose logs redis` |
| **Permisos de archivos** | Verificar permisos en volumes Docker |
| **Puerto 8000 ocupado** | Cambiar puerto en `docker-compose.yml` |

### Logs Útiles para Debug

```bash
# Logs específicos por servicio
docker-compose logs postgres     # Base de datos
docker-compose logs redis        # Cache y WebSockets  
docker-compose logs web         # Aplicación Django
docker-compose logs nginx       # Servidor web (producción)

# Logs en tiempo real
docker-compose logs -f --tail=100 web
```

### Comandos de Diagnóstico

```bash
# Verificar estado de servicios
docker-compose ps

# Verificar conectividad a PostgreSQL
docker-compose exec web python manage.py dbshell

# Verificar Redis
docker-compose exec redis redis-cli ping

# Verificar variables de entorno
docker-compose exec web env | grep DB_
```

##  Recursos Adicionales

- [Documentación Django](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Django Channels](https://channels.readthedocs.io/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
- [Docker Compose Reference](https://docs.docker.com/compose/)



