# 🔄 Guía de Migración a Poetry + Docker

Esta guía te ayudará a migrar tu proyecto padel_backend desde requirements.txt a Poetry + Docker Compose.

## Checklist de Migración

### 1. Preparación del Entorno

- [ ] Hacer backup del proyecto actual
- [ ] Verificar que Docker y Docker Compose estén instalados
- [ ] Instalar Poetry (`pip install poetry`)
- [ ] Crear rama para la migración (`git checkout -b migration/poetry-docker`)

### 2. Archivos a Crear

Copia estos archivos en tu proyecto:

- [ ] `pyproject.toml` - Configuración de Poetry
- [ ] `Dockerfile` - Imagen Docker para Django
- [ ] `docker-compose.yml` - Servicios (Django, MySQL, Redis, Nginx)
- [ ] `.dockerignore` - Archivos a ignorar en Docker
- [ ] `.env.example` - Template de variables de entorno
- [ ] `Makefile` - Comandos automatizados
- [ ] `docker/mysql/init.sql` - Inicialización de MySQL
- [ ] `docker/nginx/nginx.conf` - Configuración de Nginx
- [ ] `README.md` - Documentación actualizada

### 3. Configurar Variables de Entorno

```bash
# Crear archivo .env desde el template
cp .env.example .env

# Editar con tus configuraciones específicas
nano .env
```

**Variables importantes a configurar:**
- `SECRET_KEY`: Tu clave secreta de Django
- `DB_PASSWORD`: Contraseña segura para MySQL
- `FIREBASE_*`: Configuraciones de Firebase (si las usas)
- `ALLOWED_HOSTS`: Dominios permitidos

### 4. Migración de Dependencias

#### Opción A: Usar Poetry desde el inicio

```bash
# Instalar dependencias con Poetry
poetry install

# Verificar que todo funcione
poetry run python manage.py check
```

#### Opción B: Migración gradual

```bash
# Mantener requirements.txt temporalmente
# Instalar también con Poetry
poetry install

# Probar ambos entornos
pip install -r requirements.txt  # Método anterior
poetry shell && python manage.py check  # Método nuevo
```

### 5. Configurar Docker

```bash
# Crear directorios necesarios
mkdir -p docker/mysql docker/nginx

# Construir imágenes
docker-compose build

# Iniciar servicios
docker-compose up -d
```

### 6. Migrar Base de Datos

#### Si tienes datos existentes:

```bash
# Hacer backup de la DB actual
mysqldump -u root -p padel_db > backup_before_migration.sql

# Iniciar contenedores
docker-compose up -d

# Restaurar datos
docker-compose exec -T db mysql -u root -ppadel_password padel_db < backup_before_migration.sql

# Ejecutar migraciones
docker-compose exec web python manage.py migrate
```

#### Si es un proyecto nuevo:

```bash
# Simplemente ejecutar migraciones
make migrate
# O: docker-compose exec web python manage.py migrate
```

### 7. Verificar Funcionamiento

```bash
# Verificar que todos los servicios estén corriendo
docker-compose ps

# Ver logs para detectar problemas
make logs

# Probar endpoints básicos
curl http://localhost:8000/health/

# Probar Django admin
docker-compose exec web python manage.py createsuperuser
```

### 8. Limpiar Archivos Antiguos (Opcional)

Una vez que todo funcione correctamente:

```bash
# Mover requirements.txt a backup
mv requirements.txt requirements.txt.backup

# Eliminar entorno virtual anterior (si usabas venv)
rm -rf venv/

# Eliminar archivos .bat si no los usas más
rm -f *.bat
```

##  Solución de Problemas Comunes

### Error: "Port 3306 already in use"

```bash
# Detener MySQL local
sudo service mysql stop

# O cambiar puerto en docker-compose.yml
ports:
  - "3307:3306"  # Cambiar a puerto diferente
```

### Error: "Permission denied" al crear directorios

```bash
# Crear directorios manualmente
sudo mkdir -p docker/mysql docker/nginx
sudo chown -R $USER:$USER docker/
```

### Error: Poetry no encuentra Python

```bash
# Especificar versión de Python
poetry env use python3.12

# O usar pyenv si lo tienes instalado
pyenv local 3.12
poetry install
```

### Error: "mysqlclient" no se instala

En el Dockerfile ya está solucionado, pero para desarrollo local:

```bash
# Ubuntu/Debian
sudo apt-get install default-libmysqlclient-dev

# CentOS/RHEL
sudo yum install mysql-devel

# macOS
brew install mysql
```

### Error: Django no encuentra configuraciones

Verifica que tu archivo `.env` tenga todas las variables necesarias:

```bash
# Verificar variables
cat .env

# Comparar con el template
diff .env .env.example
```

## Verificación Post-Migración

### Checklist de Funcionalidad

- [ ] El servidor Django inicia correctamente
- [ ] La base de datos MySQL se conecta
- [ ] Las migraciones se ejecutan sin errores
- [ ] Los endpoints de API responden
- [ ] Los WebSockets funcionan (si los usas)
- [ ] Los archivos estáticos se sirven correctamente
- [ ] Los tests pasan

### Comandos de Verificación

```bash
# Estado de servicios
make up && docker-compose ps

# Logs sin errores
make logs | grep -i error

# Tests pasan
make test

# Endpoints responden
curl -f http://localhost:8000/health/ || echo "Health check failed"
```

## 🚀 Siguiente Pasos

### Para Desarrollo

1. **Configurar IDE**: Asegúrate de que tu IDE use el intérprete de Poetry
2. **Pre-commit hooks**: Configurar hooks para formateo automático
3. **Debugging**: Configurar debugging con Docker si lo necesitas

### Para Producción

1. **SSL/HTTPS**: Configurar certificados SSL en Nginx
2. **Secrets**: Usar Docker secrets o variables de entorno seguras
3. **Monitoring**: Configurar logs centralizados
4. **Backup**: Automatizar backups de base de datos
5. **CI/CD**: Configurar pipeline de despliegue

## Rollback Plan

Si necesitas volver al setup anterior:

```bash
# Detener Docker
docker-compose down

# Restaurar requirements.txt
mv requirements.txt.backup requirements.txt

# Recrear entorno virtual
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Restaurar base de datos si es necesario
mysql -u root -p padel_db < backup_before_migration.sql
```

## ✨ Beneficios Obtenidos

Después de la migración tendrás:

- **Reproducibilidad**: Mismo entorno en desarrollo y producción
- **Gestión de dependencias**: Poetry maneja versiones automáticamente
- **Aislamiento**: Cada servicio en su contenedor
- **Escalabilidad**: Fácil agregar nuevos servicios
- **Desarrollo**: Comandos automatizados con Makefile
- **Producción**: Setup listo para producción con Nginx
-  **Mantenimiento**: Fácil actualización y backup

