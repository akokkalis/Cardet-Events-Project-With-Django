# Docker Commands Reference for Event Management Project

## Quick Start Commands

### Build and Start All Services

```bash
docker-compose build
docker-compose up
```

### Start in Background (Detached Mode)

```bash
docker-compose up -d
```

### Stop All Services

```bash
docker-compose down
```

## Database Management

### Run Database Migrations

```bash
docker-compose exec django python manage.py migrate
```

### Create Superuser

```bash
docker-compose exec django python manage.py createsuperuser
```

### Access Django Shell

```bash
docker-compose exec django python manage.py shell
```

## Service Management

### Restart Specific Service

```bash
docker-compose restart django
```

### View Service Logs

```bash
docker-compose logs -f django
```

### Check Running Services

```bash
docker-compose ps
```

### Run Only Celery Service

```bash
docker-compose up celery
```

## Development Commands

### View All Available Services

```bash
docker-compose config --services
```

### Restart All Services

```bash
docker-compose restart
```

## Access Points

- **Main Django App**: http://localhost:8000
- **PgAdmin** (Database Admin): http://localhost:5050
  - Email: admin@example.com
  - Password: admin
- **Flower** (Celery Monitoring): http://localhost:5555
- **Gotenberg** (PDF Service): http://localhost:3000

## Services Included

- **django** - Main Django application (port 8000)
- **db** - PostgreSQL database (port 5432)
- **redis** - Redis cache and message broker (port 6379)
- **celery** - Celery worker for background tasks
- **celery_beat** - Celery beat for scheduled tasks
- **flower** - Celery monitoring interface (port 5555)
- **gotenberg** - PDF generation service (port 3000)
- **pgadmin** - Database administration (port 5050)

## Troubleshooting

### Check Container Status

```bash
docker-compose ps
```

### View All Logs

```bash
docker-compose logs
```

### View Specific Service Logs

```bash
docker-compose logs django
docker-compose logs celery
docker-compose logs db
```

### Rebuild and Restart

```bash
docker-compose down
docker-compose build
docker-compose up
```

## Notes

- All services are configured in `docker-compose.yml`
- Environment variables are loaded from `.env` file
- Volumes are mounted for live code changes during development
- Services automatically restart on failure (`restart: always`)
