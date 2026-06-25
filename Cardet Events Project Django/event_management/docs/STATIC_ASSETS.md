# Static & Vendor Asset Handling

## Context

During the OWASP ZAP security remediation (see [README.md](../../../README.md)), the CDN-loaded
JS/CSS libraries (Tailwind, jQuery, SweetAlert2, etc.) were replaced with self-hosted copies in
`core/static/vendor/`. Those files — plus `staticfiles/` (the `collectstatic` output) — used to be
committed directly to git. That worked, but meant every dependency bump or fresh checkout required
someone to manually re-run a pile of `curl` commands and remember to re-run `collectstatic`.

Both directories are now gitignored and **regenerated automatically** on every container start.

## How it works

```
Dockerfile  ──ENTRYPOINT──>  docker-entrypoint.sh  ──>  scripts/fetch_vendor_assets.sh
                                     │                          │
                                     │                          ├─ downloads any missing
                                     │                          │  vendor JS/CSS file (skips
                                     │                          │  if it already exists)
                                     │                          └─ builds core/static/vendor/css/tailwind.css
                                     │                             via the standalone Tailwind CLI
                                     │                             (skipped if it already exists)
                                     │
                                     └─>  python manage.py collectstatic --noinput
                                     └─>  exec "$@"   (runs whatever CMD/command was passed —
                                                        gunicorn in prod, runserver locally)
```

- **[scripts/fetch_vendor_assets.sh](../scripts/fetch_vendor_assets.sh)** — one `fetch()` call per
  vendor file, each a no-op if the destination already exists. Pinned versions match exactly what's
  referenced in the templates (see the table below). Tailwind CSS is *built*, not downloaded: the
  standalone CLI (`v3.4.17`, matching the version the old `cdn.tailwindcss.com` play script served)
  is fetched once to `/tmp`, then run against [tailwind.config.js](../tailwind.config.js) and
  [core/static/css/tailwind-input.css](../core/static/css/tailwind-input.css) to produce a purged,
  minified stylesheet scoped to this project's actual templates (plus `crispy_tailwind`'s own
  templates, so its form-rendering classes aren't purged away).
- **[docker-entrypoint.sh](../docker-entrypoint.sh)** — runs the fetch script, then `collectstatic`,
  then hands off to the container's normal command via `exec "$@"`.
- **Why an entrypoint and not a `Dockerfile RUN` step at build time:** docker-compose bind-mounts the
  whole project directory over `/app` (`volumes: - .:/app`), so anything baked into the image at
  build time is invisible at runtime — the live host files take over. The entrypoint runs *after*
  that mount is active, so the files it creates land directly on the host disk (and are gitignored,
  so they never get committed back).

### Currently self-hosted libraries

| File | Pinned version | Note |
|---|---|---|
| jQuery | 3.6.0 | |
| Flatpickr | 4.6.13 | version jsdelivr was actually resolving for the old unpinned CDN URL |
| Select2 | 4.1.0-rc.0 | |
| SweetAlert2 | 11.26.25 | resolved version for the old `@11` CDN tag |
| FullCalendar | 6.1.11 | JS only — v6 injects its own CSS, no separate stylesheet ships |
| SortableJS | 1.15.3 | |
| html5-qrcode | 2.0.3 | **not** npm's "latest" (2.3.8) — confirmed byte-for-byte this is what the old unpinned CDN URL was actually serving |
| Signature Pad | 4.0.0 | |
| DataTables + Buttons | 1.13.4 / 2.3.6 | only used on `event_detail.html` |
| JSZip / pdfmake | 3.10.1 / 0.2.7 | DataTables export buttons, `event_detail.html` only |
| Tailwind CSS | 3.4.17 | built locally from `tailwind.config.js`, not downloaded |

`js.stripe.com` (used on the payment page) is **not** self-hosted — Stripe requires their JS be
loaded directly from their own CDN for PCI compliance. It's explicitly allowlisted in the
Content-Security-Policy instead (see `CONTENT_SECURITY_POLICY` in `settings.py`).

## Maintaining it

- **Bumping a library version:** edit the URL (and version-specific filename if relevant) in
  `fetch_vendor_assets.sh`, delete the old file from `core/static/vendor/`, restart the `django`
  container (or run `sh scripts/fetch_vendor_assets.sh` manually inside it).
- **Added new Tailwind classes to a template and they're not showing up:** the compiled
  `tailwind.css` is only rebuilt when it doesn't already exist. Delete
  `core/static/vendor/css/tailwind.css` and restart the container (or re-run the fetch script) to
  force a rebuild against the current templates.
- **`celery`/`celery_beat`/`flower` containers:** these build from the same `Dockerfile` but don't
  need static assets at all. Their images weren't rebuilt when this was implemented — do it on the
  next deploy for consistency, but it's not urgent.

### How this was verified

`core/static/vendor/` and `staticfiles/` were deleted entirely, the `django` image was rebuilt, and
the container was recreated (`docker compose up -d --force-recreate django`) to simulate a fresh
checkout. The entrypoint re-downloaded all 19 vendor files, rebuilt `tailwind.css`, ran
`collectstatic` (1428 files), and the site came back up fully working with zero manual steps.

---

# Future: Moving static/media to DigitalOcean Spaces

This section is a **plan for later**, not something implemented yet. Today, static files are served
by WhiteNoise from local disk, and user-uploaded media (`media/`) sits on the droplet's disk, served
directly by nginx. That's fine at the current scale, but two things would justify moving to object
storage + CDN eventually: the droplet's disk filling up with uploaded media over time, and wanting
edge caching/CDN delivery without relying on nginx alone.

The droplet IP (`198.199.79.173`) is in a DigitalOcean range, so **DigitalOcean Spaces** (S3-compatible
object storage with a built-in free CDN) is the natural fit — same steps would work for AWS S3 with a
different endpoint.

## Recommendation: start with media only

Static files (`core/static/vendor/`, app CSS/JS) are small, already cache-busted by WhiteNoise, and
now auto-regenerate per the section above — there's little benefit to moving them. **Media** (event
images, certificates, signatures, RSVP exports) is the part that grows unboundedly and actually
benefits from offloading the droplet's disk and getting CDN delivery. Recommend doing media only,
and revisit static separately later if WhiteNoise ever becomes a bottleneck.

## ⚠️ Privacy consideration before doing this

This app stores participant signatures, certificates, and personal data in `media/`. A default
"public-read" Spaces bucket would make every uploaded file fetchable by anyone who guesses or
obtains the URL. **Decide on either:**
- a **private** bucket with signed, time-limited URLs (`AWS_QUERY_STRING_AUTH = True` in
  `django-storages`), or
- a **public** bucket only for genuinely public assets (e.g. event header images), with anything
  containing personal data (signatures, certificates, participant exports) kept private/signed.

Don't default to public-read for everything without making this decision explicitly.

## Step-by-step

1. **Create the Space** — DigitalOcean control panel → *Spaces Object Storage* → *Create a Space*.
   Pick the region closest to the droplet (lower latency, no egress cost between same-region
   Droplet ↔ Spaces). Name it something like `cardet-events-media`. Enable the **CDN** option (free)
   to get a `https://<space-name>.<region>.cdn.digitaloceanspaces.com` endpoint.
2. **Generate API keys** — *API* → *Spaces Keys* → *Generate New Key*. Save the Access Key ID and
   Secret Key somewhere safe — **never commit them**. They go in the production server's `.env` only.
3. **Add the dependency** — add `django-storages[s3]` to `requirements.txt`, rebuild the `django`
   image.
4. **Add environment variables** to production's `.env` (not committed):
   ```
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   AWS_STORAGE_BUCKET_NAME=cardet-events-media
   AWS_S3_ENDPOINT_URL=https://<region>.digitaloceanspaces.com
   AWS_S3_CUSTOM_DOMAIN=cardet-events-media.<region>.cdn.digitaloceanspaces.com
   ```
5. **Update `settings.py`** — add a `STORAGES` entry (Django 4.2+ style, already in use given this
   project is on Django 5.1.6) pointing the `default` (media) backend at
   `storages.backends.s3.S3Storage`, reading the settings above from `os.getenv(...)`. Leave
   `staticfiles` on the existing WhiteNoise backend. Set `AWS_DEFAULT_ACL` and `AWS_QUERY_STRING_AUTH`
   per the privacy decision above, and `AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}`
   for sane edge caching.
6. **Migrate existing files** — the current `media/` directory needs to be copied up to the bucket
   once. Use `s3cmd` or `rclone` configured with the Spaces endpoint/keys to sync the droplet's
   `media/` folder to the bucket (`s3cmd sync media/ s3://cardet-events-media/`). Existing database
   rows referencing those files don't need to change — `django-storages` generates the new bucket
   URLs automatically from the same relative paths.
7. **Update nginx** — once media is confirmed serving correctly from the bucket/CDN, remove the
   `location /media/ { alias /media/; }` block from `nginx/default.conf` (Django/the storage backend
   now generates the correct CDN URLs directly; nginx no longer needs to proxy media itself).
8. **Test on staging first** — upload a new event image/certificate/signature, confirm it lands in
   the bucket and the served URL is correct (signed if private). Confirm old, already-uploaded media
   still resolves.
9. **Rollback plan** — keep the droplet's local `media/` files in place (don't delete them) until
   confident in the new setup. Reverting just means changing the `STORAGES` setting back to the
   filesystem backend — no template or model changes needed either way, since all usages just call
   `.url` on the file field.

**Cost ballpark:** DigitalOcean Spaces starts at $5/month for 250 GB storage + 1 TB outbound
transfer, with the CDN included at no extra charge.
