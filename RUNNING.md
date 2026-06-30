# Running this project

Two completely separate environments — don't mix their `.env` files or credentials:

| | Local development | Production |
|---|---|---|
| Where | your machine | DigitalOcean droplet `164.92.189.245` |
| Compose file | `docker-compose.yml` | `docker-compose.prod.yml` (synced to the server as `docker-compose.yml` on deploy) |
| Database | local Postgres container (`db` service) | DigitalOcean-managed Postgres |
| How code gets there | bind-mounted from your git checkout | baked into a prebuilt image pulled from GHCR |
| How it deploys | you run `docker compose` yourself | automatic, on merge to `master` (GitHub Actions) |

---

## A. Running locally

### 1. Prerequisites
- Docker Desktop (or Docker Engine + Compose plugin) installed and running.
- This repo cloned.

### 2. First-time setup
```bash
cd "Cardet Events Project Django/event_management"
cp .env.example .env
```
Open `.env` and fill in real values where the example has placeholders (DB password, Flower
credentials, etc.) — none of it needs to be production-grade, this only runs on your machine.
The important line is already correct: `POSTGRES_HOST=db` — that's what makes `settings.py`
use the local Postgres container instead of the production database (see `settings.py`'s
`DATABASES` block if you want to see how that switch works).

### 3. Bring up the stack
```bash
docker compose up -d
```
This starts: `django` (Gunicorn), `db` (local Postgres), `redis`, `celery`, `celery_beat`,
`flower`, `gotenberg`, `nginx`, and `pgadmin`.

### 4. Set up the database (first time, and after pulling new migrations)
```bash
docker compose run --rm django python manage.py migrate
docker compose run --rm django python manage.py createsuperuser
```

### 5. Use it
- App: http://localhost:8000
- Admin: http://localhost:8000/admin
- Flower (Celery monitoring): http://localhost:5555
- pgAdmin: http://localhost:5050
- Gotenberg (PDF conversion, internal use only): http://localhost:3000

### 6. Day-to-day commands
```bash
docker compose logs -f django          # follow Django logs
docker compose logs -f celery          # follow Celery worker logs
docker compose restart django          # restart just Django after a code change*
docker compose down                    # stop everything (data in the "db" volume persists)
docker compose run --rm django python manage.py makemigrations
docker compose run --rm django python manage.py shell
```
\* Code is bind-mounted, so most changes are picked up on a simple restart — no rebuild
needed. You only need `docker compose up -d --build` if you changed `requirements.txt` or the
`Dockerfile`.

### 7. Resetting your local database
```bash
docker compose down
docker volume rm event_management_pgdata
docker compose up -d db
docker compose run --rm django python manage.py migrate
docker compose run --rm django python manage.py createsuperuser
```

---

## B. Running in production

You generally **don't run commands here directly** — deploys are automatic. This section is
for day-to-day operations and the rare manual intervention.

### How a deploy happens
1. Someone merges a PR into `master`.
2. GitHub Actions (`.github/workflows/deploy.yml`) builds the Docker image, pushes it to
   `ghcr.io/akokkalis/cardet-events`, then SSHes into the droplet, syncs
   `docker-compose.prod.yml` → `/opt/cardet-events/docker-compose.yml` and
   `nginx/default.conf` → `/opt/cardet-events/nginx/default.conf`, runs
   `docker compose pull && up -d`, then `python manage.py migrate --noinput`.
3. Watch the run in the GitHub Actions tab. Spot-check `https://qrscanner.innovedu.com`
   afterward — there's no separate staging environment.

### Connecting to the server
```bash
ssh deploy@164.92.189.245
cd /opt/cardet-events
```
(Uses the `deploy` user's key — see `FUTURE_IMPROVEMENTS.md` section 2 if you need to grant a
colleague their own access.)

### Checking status / logs
```bash
docker compose ps                          # is everything up?
docker compose logs -f django              # live Django logs (Ctrl+C to stop watching)
docker compose logs -f django nginx        # multiple services at once
docker compose logs --tail=200 django      # last 200 lines, no follow
```

### Common manual operations
```bash
docker compose exec -T django python manage.py migrate --noinput   # re-run migrations
docker compose exec -T django python manage.py createsuperuser     # create an admin user
docker compose exec -T django python manage.py shell                # Django shell
docker compose restart nginx               # if nginx ever 502s after a django restart
                                            # (should no longer happen — see the resolver
                                            # fix in nginx/default.conf)
docker compose restart django celery celery_beat   # restart app processes without a full redeploy
```

### Flower (Celery monitoring), loopback-only
```bash
ssh -L 5555:127.0.0.1:5555 deploy@164.92.189.245
```
Then open http://127.0.0.1:5555 in your local browser.

### Where things live on the server
```
/opt/cardet-events/
├── docker-compose.yml      ← synced from docker-compose.prod.yml on every deploy
├── .env                    ← production secrets, edited manually, never touched by deploys
├── nginx/default.conf      ← synced from the repo's nginx/default.conf on every deploy
├── certbot/                ← TLS cert (conf/) and ACME webroot (www/)
└── media/                  ← user-uploaded files, persists across redeploys
```

### TLS certificate
Already issued and auto-renewing via a weekly cron job (Mondays 3am) — nothing to do unless
it stops working. Check it manually with:
```bash
docker run --rm -v /opt/cardet-events/certbot/conf:/etc/letsencrypt certbot/certbot certificates
```

---

## More context
- `FUTURE_IMPROVEMENTS.md` — security hardening backlog, colleague onboarding steps.
- `TODO.md` (local only, gitignored) — status of the original deployment rollout.
- `.env.example` — local dev environment template.
- `Cardet Events Project Django/event_management/.env.production.example` — production
  environment template (reference only; the real file lives only on the server).
