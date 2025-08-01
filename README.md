# Padel Backend API

Backend API para sistema de gestión de torneos y scoring de padel, construido con Django REST Framework.

## Arquitectura

- **Backend**: Django 4.2.7 + Django REST Framework
- **Base de datos**: MySQL 8.0
- **WebSockets**: Django Channels + Redis
- **Autenticación**: JWT + Firebase Admin
- **Containerización**: Docker + Docker Compose
- **Gestión de dependencias**: Poetry

## Características

- Sistema de autenticación con JWT
- Gestión de jugadores y torneos
- Sistema de scoring en tiempo real (WebSockets)
- Estadísticas de partidos
- API REST completa
- Integración con Firebase
- Configuración con Docker

### Prerrequisitos

- Docker y Docker Compose
- Poetry (opcional, para desarrollo local)
- Git

### 1. Clonar el repositorio

```bash
git clone https://gitlab.com/ourala/padel/backend.git
cd padel_backend
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Edita .env con tus configuraciones
```

### 3. Desarrollo con Docker (Recomendado)

```bash
# Construir e iniciar servicios
make dev-setup

# O manualmente:
docker-compose build
docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py collectstatic --noinput
```

### 4. Desarrollo local con Poetry

```bash
# Instalar dependencias
poetry install

# Activar entorno virtual
poetry shell

# Ejecutar migraciones
poetry run python manage.py migrate

# Iniciar servidor de desarrollo
poetry run python manage.py runserver
```
### Con Make (Recomendado)

```bash
make help                 # Ver todos los comandos disponibles
make up                   # Iniciar servicios
make down                 # Detener servicios
make logs                 # Ver logs
make shell                # Acceder a Django shell
make migrate              # Ejecutar migraciones
make test                 # Ejecutar tests
make clean                # Limpiar contenedores y volúmenes
```

### Con Docker Compose

```bash
docker-compose up -d                              # Iniciar servicios
docker-compose logs -f                            # Ver logs
docker-compose exec web python manage.py shell   # Django shell
docker-compose exec web python manage.py migrate # Migraciones
docker-compose down                               # Detener servicios
```

### Con Poetry (Desarrollo Local)

```bash
poetry run python manage.py runserver    # Servidor de desarrollo
poetry run python manage.py migrate      # Migraciones
poetry run python manage.py shell        # Django shell
poetry run python manage.py test         # Tests
```

## 📁 Estructura del Proyecto

```
padel_backend/
├── apps/                     # Aplicaciones Django
│   ├── authentication/      # Autenticación y usuarios
│   ├── players/             # Gestión de jugadores
│   ├── matches/             # Gestión de partidos
│   ├── scoring/             # Sistema de scoring
│   ├── statistics/          # Estadísticas
│   └── tournaments/         # Gestión de torneos
├── padel_backend/           # Configuración principal
├── docker/                  # Configuraciones Docker
│   ├── mysql/
│   └── nginx/
├── requirements.txt         # Dependencias (legacy)
├── pyproject.toml          # Configuración Poetry
├── docker-compose.yml      # Servicios Docker
├── Dockerfile              # Imagen Docker
└── Makefile               # Comandos automatizados
```

## 🌐 Endpoints Principales

### Autenticación
- `POST /api/auth/login/` - Iniciar sesión
- `POST /api/auth/register/` - Registro de usuario
- `POST /api/auth/refresh/` - Renovar token

### Jugadores
- `GET /api/players/` - Listar jugadores
- `POST /api/players/` - Crear jugador
- `GET /api/players/{id}/` - Detalle de jugador

### Partidos
- `GET /api/matches/` - Listar partidos
- `POST /api/matches/` - Crear partido
- `GET /api/matches/{id}/` - Detalle de partido

### Scoring (WebSockets)
- `ws://localhost:8000/ws/match/{match_id}/` - Scoring en tiempo real


### Variables de Entorno

Las principales variables están en `.env`:

```env
DEBUG=1
DB_NAME=padel_db
DB_USER=root
DB_PASSWORD=123456789a
DB_HOST=db
REDIS_URL=redis://redis:6379/0
```

### Base de Datos

El proyecto usa MySQL con las siguientes configuraciones:
- Charset: utf8mb4
- SQL Mode: TRADITIONAL
- Puerto: 3306

### Redis

Utilizado para Django Channels (WebSockets):
- Puerto: 6379
- Base de datos: 0

## Testing

```bash
# Con Docker
make test

# Con Poetry
poetry run python manage.py test

# Con cobertura
make test-coverage
```

## Despliegue

### Producción con Docker

```bash
# Iniciar con Nginx
make prod-setup

# O manualmente
docker-compose --profile production up -d
```

### Configuraciones de Producción

1. Cambiar `DEBUG=False` en `.env`
2. Configurar `ALLOWED_HOSTS`
3. Usar secretos seguros
4. Configurar SSL en Nginx
5. Configurar backup de base de datos

## 📊 Monitoreo

### Logs

```bash
make logs           # Todos los servicios
make logs-web       # Solo el backend
```

### Health Check

El backend incluye un endpoint de health check:
- `GET /health/` - Estado del servicio

## Migración desde requirements.txt

Si vienes de usar `requirements.txt`:

1. **Mantén el archivo original** como respaldo
2. **Instala Poetry**: `pip install poetry`
3. **Instala dependencias**: `poetry install`
4. **Verifica que todo funcione**: `poetry run python manage.py runserver`

## Contribución

1. Fork el repositorio
2. Crea una rama feature (`git checkout -b feature/nueva-caracteristica`)
3. Commit tus cambios (`git commit -am 'Agregar nueva característica'`)
4. Push a la rama (`git push origin feature/nueva-caracteristica`)
5. Crea un Pull Request

## Notas de Desarrollo

- Usa `make format` antes de hacer commit
- Ejecuta `make lint` para verificar el código
- Los tests deben pasar antes de hacer merge
- Documenta nuevos endpoints en este README

## Solución de Problemas

### Problemas Comunes

1. **Error de conexión a MySQL**: Verifica que el contenedor esté corriendo
2. **Error de dependencias**: Ejecuta `poetry install` o `docker-compose build`
3. **Problemas de permisos**: Verifica los permisos de archivos y directorios
4. **WebSockets no funcionan**: Verifica que Redis esté corriendo

### Logs Útiles

```bash
docker-compose logs db       # Logs de MySQL
docker-compose logs redis    # Logs de Redis
docker-compose logs web      # Logs de Django
```

##  Licencia

