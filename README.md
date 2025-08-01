
# Padel Backend 

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

=======
# backend



## Getting started

To make it easy for you to get started with GitLab, here's a list of recommended next steps.

Already a pro? Just edit this README.md and make it your own. Want to make it easy? [Use the template at the bottom](#editing-this-readme)!

## Add your files

- [ ] [Create](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#create-a-file) or [upload](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#upload-a-file) files
- [ ] [Add files using the command line](https://docs.gitlab.com/topics/git/add_files/#add-files-to-a-git-repository) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin https://gitlab.com/ourala/padel/backend.git
git branch -M main
git push -uf origin main
```

## Integrate with your tools

- [ ] [Set up project integrations](https://gitlab.com/ourala/padel/backend/-/settings/integrations)

## Collaborate with your team

- [ ] [Invite team members and collaborators](https://docs.gitlab.com/ee/user/project/members/)
- [ ] [Create a new merge request](https://docs.gitlab.com/ee/user/project/merge_requests/creating_merge_requests.html)
- [ ] [Automatically close issues from merge requests](https://docs.gitlab.com/ee/user/project/issues/managing_issues.html#closing-issues-automatically)
- [ ] [Enable merge request approvals](https://docs.gitlab.com/ee/user/project/merge_requests/approvals/)
- [ ] [Set auto-merge](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)

## Test and Deploy

Use the built-in continuous integration in GitLab.

- [ ] [Get started with GitLab CI/CD](https://docs.gitlab.com/ee/ci/quick_start/)
- [ ] [Analyze your code for known vulnerabilities with Static Application Security Testing (SAST)](https://docs.gitlab.com/ee/user/application_security/sast/)
- [ ] [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/ee/topics/autodevops/requirements.html)
- [ ] [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/ee/user/clusters/agent/)
- [ ] [Set up protected environments](https://docs.gitlab.com/ee/ci/environments/protected_environments.html)

***

# Editing this README

When you're ready to make this README your own, just edit this file and use the handy template below (or feel free to structure it however you want - this is just a starting point!). Thanks to [makeareadme.com](https://www.makeareadme.com/) for this template.

## Suggestions for a good README

Every project is different, so consider which of these sections apply to yours. The sections used in the template are suggestions for most open source projects. Also keep in mind that while a README can be too long and detailed, too long is better than too short. If you think your README is too long, consider utilizing another form of documentation rather than cutting out information.

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

## Badges
On some READMEs, you may see small images that convey metadata, such as whether or not all the tests are passing for the project. You can use Shields to add some to your README. Many services also have instructions for adding a badge.

## Visuals
Depending on what you are making, it can be a good idea to include screenshots or even a video (you'll frequently see GIFs rather than actual videos). Tools like ttygif can help, but check out Asciinema for a more sophisticated method.

## Installation
Within a particular ecosystem, there may be a common way of installing things, such as using Yarn, NuGet, or Homebrew. However, consider the possibility that whoever is reading your README is a novice and would like more guidance. Listing specific steps helps remove ambiguity and gets people to using your project as quickly as possible. If it only runs in a specific context like a particular programming language version or operating system or has dependencies that have to be installed manually, also add a Requirements subsection.

## Usage
Use examples liberally, and show the expected output if you can. It's helpful to have inline the smallest example of usage that you can demonstrate, while providing links to more sophisticated examples if they are too long to reasonably include in the README.

## Support
Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
State if you are open to contributions and what your requirements are for accepting them.

For people who want to make changes to your project, it's helpful to have some documentation on how to get started. Perhaps there is a script that they should run or some environment variables that they need to set. Make these steps explicit. These instructions could also be useful to your future self.

You can also document commands to lint the code or run tests. These steps help to ensure high code quality and reduce the likelihood that the changes inadvertently break something. Having instructions for running tests is especially helpful if it requires external setup, such as starting a Selenium server for testing in a browser.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
If you have run out of energy or time for your project, put a note at the top of the README saying that development has slowed down or stopped completely. Someone may choose to fork your project or volunteer to step in as a maintainer or owner, allowing your project to keep going. You can also make an explicit request for maintaine 
 gitlab/main
