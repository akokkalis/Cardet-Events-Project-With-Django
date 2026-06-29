# Future improvements & team onboarding

Companion to `TODO.md` (which tracks the initial deployment) and the runbook at
`C:\Users\Kokkalis\.claude\plans\can-you-make-the-polished-planet.md`. This file covers
what's left for security hardening, ongoing server maintenance, bringing a colleague onto
the project, and setting up a proper local development database.



/opt/cardet-events/
├── docker-compose.yml          ← synced from docker-compose.prod.yml on every deploy
├── .env                        ← production secrets, created manually (Step 9), never touched by deploys
├── nginx/
│   └── default.conf            ← synced from the repo's nginx/default.conf on every deploy
├── certbot/
│   ├── conf/                   ← the actual TLS cert + key live here (Let's Encrypt)
│   └── www/                    ← ACME challenge webroot
└── media/                      ← user-uploaded files (persists across redeploys)


---

## 1. Local development database (do this first)

**Problem found:** `event_management/settings.py`'s `DATABASES` block unconditionally reads
`db_name` / `db_username` / `db_password` / `db_host` / `db_port` — and in your local `.env`,
those are the **production DigitalOcean-managed Postgres credentials**. The separate
`POSTGRES_*` vars and the `db` Postgres container already defined in the dev
`docker-compose.yml` exist but are never actually used by Django. In practice: right now,
running this project locally talks to the **live production database**. Migrations, test
data, accidental deletes — all of it would hit real data.

### The fix

1. **Code change** in `event_management/settings.py` — prefer local Postgres when
   `POSTGRES_HOST` is set, fall back to the managed DB only when it isn't:

   ```python
   if os.getenv("POSTGRES_HOST"):
       DATABASES = {
           "default": {
               "ENGINE": "django.db.backends.postgresql",
               "NAME": os.getenv("POSTGRES_DB"),
               "USER": os.getenv("POSTGRES_USER"),
               "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
               "HOST": os.getenv("POSTGRES_HOST"),
               "PORT": os.getenv("POSTGRES_PORT", "5432"),
           }
       }
   else:
       DATABASES = {
           "default": {
               "ENGINE": "django.db.backends.postgresql",
               "NAME": os.getenv("db_name"),
               "USER": os.getenv("db_username"),
               "PASSWORD": os.getenv("db_password"),
               "HOST": os.getenv("db_host"),
               "PORT": os.getenv("db_port"),
               "CONN_MAX_AGE": None,
               "CONN_HEALTH_CHECKS": True,
           }
       }
   ```

   No `.env` changes needed for this to work: your local `.env` already has
   `POSTGRES_HOST=db` (the dev-compose Postgres container), and the production `.env` on the
   droplet only has `db_*` vars — so this naturally routes each environment to the right
   database with zero risk of accidentally pointing at prod.

2. **Bring up the local DB and run migrations against it:**
   ```bash
   docker compose up -d db
   docker compose run --rm django python manage.py migrate
   docker compose run --rm django python manage.py createsuperuser
   ```

3. **Seed it with data.** Two options:
   - Fresh/empty — just create test events/participants by hand through the admin/UI.
   - A sanitized copy of production — `pg_dump` the managed DB, **scrub personal data**
     (participant emails/names/signatures) before importing locally, then `pg_restore` into
     the local `db` container. Don't copy production personal data into a local dev DB
     unscrubbed — treat it the same as any other PII handling decision.

4. **Add a `.env.example`** (local-dev-focused, distinct from `.env.production.example`)
   documenting `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_HOST=db` /
   `POSTGRES_PORT=5432` plus the other non-secret dev defaults, so a new developer can copy
   it to `.env` and be running in minutes without ever touching production credentials.

5. **Optional safety net:** a startup check in `settings.py` that raises loudly if
   `DJANGO_DEBUG=True` but the resolved DB host string contains `ondigitalocean.com` —
   catches the exact misconfiguration found above if it ever creeps back in.

---

## 2. Bringing a colleague onto the project

Two completely separate credentials are involved here — worth being explicit about which is
which:

### a) Git/GitHub access (for writing code) — nothing to do with the server
- Invite them as a **Collaborator** on the GitHub repo (Settings → Collaborators).
- They generate **their own** SSH key (`ssh-keygen -t ed25519`) and add the *public* key to
  **their own GitHub account** (GitHub Settings → SSH and GPG keys) — standard `git push`
  auth, unrelated to anything we built for deployment.
- They should never need or see the `DEPLOY_SSH_KEY` GitHub Actions secret — that key exists
  solely for the Actions runner to reach the droplet, and isn't tied to any individual person.

### b) Deploying — also nothing they need to set up
- Deploys happen automatically when code is merged to `master`, via the GitHub Actions
  workflow already wired up. A colleague with repo write access can merge a PR and the
  pipeline builds/pushes/deploys without them ever touching SSH or the droplet.
- **Recommended now that merging = deploying to production:** turn on branch protection on
  `master` (Settings → Branches → Add rule) requiring at least one PR review before merge.
  Right now nothing stops a direct push or an unreviewed merge from going straight to prod.

### c) If they need actual SSH access to the droplet (debugging, logs, manual psql, etc.)
- **Don't share the `DEPLOY_SSH_KEY`** — that's the CI automation credential, not a personal
  login. Generate a **separate** personal keypair for them instead:
  ```bash
  ssh-keygen -t ed25519 -f colleague_key -C "<their-name>"
  ```
  Add their public key to `/home/deploy/.ssh/authorized_keys` on the droplet (same pattern as
  Step 6 in the original runbook). This keeps individual access auditable and revocable
  (remove their line from `authorized_keys` when they leave/no longer need it) without
  touching the automation key or anyone else's access.
- If they'll regularly need elevated access (installing packages, restarting services as
  root), consider giving them their own sudo-capable account rather than sharing root, for
  the same auditability reason.

---

## 3. Server / security follow-ups (not done yet)

Roughly in priority order:

- [ ] **Lock down SSH further**: now that the `deploy` user + key auth works, disable
  password authentication and root SSH login in `/etc/ssh/sshd_config`
  (`PasswordAuthentication no`, `PermitRootLogin no`), then `systemctl restart sshd`.
- [ ] **fail2ban** for SSH brute-force protection (`apt install fail2ban`).
- [ ] **Unattended security upgrades**: `apt install unattended-upgrades` so OS/kernel CVEs
  get patched automatically.
- [ ] **DigitalOcean Cloud Firewall** as a second layer in front of/alongside `ufw` (network
  level vs. host level — defense in depth, free on DO).
- [ ] **Docker log rotation** — container logs (`json-file` driver) grow unbounded by default
  and can fill the disk. Add to `/etc/docker/daemon.json`:
  ```json
  { "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }
  ```
  then `systemctl restart docker` (recreates containers' log config on next `up`).
- [ ] **Per-service resource limits** in `docker-compose.prod.yml` (`mem_limit`/`cpus`) — RAM
  is tight (1.9GB + 2GB swap); a heavy Gotenberg PDF render or a Celery spike shouldn't be
  able to starve Django/Postgres connections for everyone else.
- [ ] **Healthchecks** on the `django`/`nginx`/`celery` services so Docker can detect and
  restart a hung (not just crashed) container — `restart: always` only covers crashes.
- [ ] **Error monitoring** (e.g. Sentry's free/low tier) — right now the only visibility into
  production exceptions is `docker compose logs`, which isn't searchable/alertable.
- [ ] **Uptime/resource alerting** — DigitalOcean Monitoring (free, has alert policies) or an
  external check (UptimeRobot) hitting `https://qrscanner.innovedu.com` so you hear about
  downtime before a user reports it.
- [ ] **Back up `media/`** — the managed Postgres DB has DigitalOcean's own backup story, but
  uploaded files in `/opt/cardet-events/media` only exist on the droplet's disk. A simple
  nightly `rclone`/`rsync` to DO Spaces (or even a snapshot) closes this gap.
- [ ] **Re-run the OWASP ZAP scan** against the live deployment to confirm the `README.md`
  remediations (CSP, cookie flags, `server_tokens off`, etc.) actually hold in production —
  noted as a follow-up in the README itself and never done against this droplet yet.
- [ ] **Prune old GHCR image tags** — every push creates a new `:<sha>` tag that's never
  cleaned up; will quietly accumulate storage over time. GHCR has a "keep last N" retention
  policy you can set in the package settings.
- [ ] **Capacity**: `performance.md` showed failures starting around 40–60 concurrent users
  even before this droplet existed. Worth a fresh load test against the new setup, and a plan
  for vertical (bigger droplet) or horizontal (multiple app servers + load balancer) scaling
  if real usage approaches those numbers.
- [ ] **Stripe keys** are still blank in production `.env` — add real ones and test the
  payment flow end-to-end before relying on it live.
- [ ] **Decommission the old droplet** (`198.199.79.173`) if it's truly unused — an unpatched,
  unmonitored box sitting around is itself a security liability.

---

## 4. Quick reference

| Need | Where |
|---|---|
| Full original deployment runbook | `C:\Users\Kokkalis\.claude\plans\can-you-make-the-polished-planet.md` |
| Current deployment status / what's left from the first rollout | `TODO.md` (gitignored, local only) |
| Production env template | `Cardet Events Project Django/event_management/.env.production.example` |
| Deploy workflow | `.github/workflows/deploy.yml` |
| Production compose file (synced to droplet on every deploy) | `Cardet Events Project Django/event_management/docker-compose.prod.yml` |
| Droplet deploy path | `/opt/cardet-events` |
