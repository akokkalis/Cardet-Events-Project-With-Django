# Security Report

This security assessment was performed using **OWASP ZAP** (Zed Attack Proxy) combined with targeted manual testing. The purpose of the scan was to identify vulnerabilities in the QR Scanner application (`https://qrscanner.innovedu.com`). The findings highlight several weaknesses that require remediation.

---

## Scan Summary

- **Tool Used:** OWASP ZAP 2.16.1  
- **Scan Date:** 14 Nov 2025  
- **Scan Type:** Active + Passive  
- **Scope:** Public pages including Login and Homepage  

ZAP reported multiple vulnerabilities across High, Medium, Low and Informational severity levels.

---

## High-Risk Vulnerabilities

### **1. SQL Injection – SQLite (Time Based)**  
**Risk:** High  
**Evidence:** SQL injection was detected on the login POST request.  
**Endpoint:**  
```
POST https://qrscanner.innovedu.com/login/?next=/
```  
**Impact:**  
An attacker can potentially extract or manipulate database data. SQL injection compromises confidentiality and integrity.

**Action Required:**  
- Implement parameterized queries  
- Validate & sanitize user input  
- Apply ORM query protections  
- Add WAF monitoring where possible  

---

## Medium-Risk Vulnerabilities

### **1. Content Security Policy (CSP) Header Missing**
**Risk:** Medium  
**Description:**  
The application does not define a CSP header, which increases vulnerability to XSS attacks.

**Action Required:**  
Add a CSP header similar to:  
```
Content-Security-Policy: default-src 'self';
```

---

## Low-Risk Vulnerabilities

### **1. Cookies Without HttpOnly Flag**
Cookies are missing the `HttpOnly` flag, allowing JavaScript access.

### **2. Cookies Without Secure Flag**
Cookies transmitted over HTTPS still lack the `Secure` flag.

### **3. Cross-Domain JavaScript Inclusion**
Third-party JS loaded from external domains:
```
https://cdn.tailwindcss.com
https://cdn.jsdelivr.net/...
```
**Risk:** Supply-chain compromise.

---

## Recommendations

1. **Fix SQL Injection immediately.**  
2. Add **CSP header** with restrictive policies.  
3. Apply **Secure**, **HttpOnly**, and **SameSite** flags to all cookies.  
4. Remove or self-host external JS where possible.  
5. Add secure cache-control policies.  
6. Hide server version information.

---

This report summarizes the critical and important issues found during the ZAP security scan and should be used as a basis for remediation and follow-up testing.

---

## Remediation Notes

### 1. SQL Injection (High) — Investigated, false positive
The login view (`login_view` in `core/views.py`) authenticates exclusively through Django's `authenticate()` and the ORM (`Staff.objects.filter(...)`), both of which use parameterized queries. No raw SQL, `.raw()`, `.extra()`, or string-built queries exist anywhere in the authentication path. ZAP's time-based SQLi probe most likely mistook normal authentication-failure latency for a timing signal. As defense-in-depth, the login endpoint now has IP-based rate limiting (5 POSTs/minute via `django-ratelimit`).

### 2. CSP header (Medium) — Fixed
Added `django-csp` middleware with a restrictive policy.

### 3. Cookie flags / transport hardening (Low) — Fixed
Added `Secure`, `HttpOnly`, and `SameSite` flags to session and CSRF cookies, plus `SECURE_SSL_REDIRECT` and HSTS. These are gated behind a `DJANGO_BEHIND_TLS_PROXY` environment flag (off by default) rather than `DEBUG`, since this app's `DEBUG` flag only toggles Postgres vs SQLite and doesn't imply real TLS is present — tying SSL enforcement to it caused redirect loops in non-TLS environments during testing. **Deployment action: set `DJANGO_BEHIND_TLS_PROXY=True` in production's `.env`** (nginx already terminates TLS there) to actually activate these protections.

### 4. Cross-domain JavaScript inclusion (Low) — Fixed
All CDN-loaded libraries are now self-hosted as static files: Tailwind CSS (rebuilt with the standalone Tailwind CLI, pinned to the v3.4.17 actually in use), jQuery, SweetAlert2, Flatpickr, Select2, FullCalendar, SortableJS, html5-qrcode, Signature Pad, plus DataTables/JSZip/pdfmake (found on the event details page during remediation, not in the original scan). One exception: `js.stripe.com` is explicitly CSP-allowlisted rather than self-hosted, since Stripe requires its JS be loaded directly from their CDN for PCI compliance.

### 5. Additional hardening done alongside the report
- Fixed a `DEBUG` parsing bug where any non-empty `DJANGO_DEBUG` value (including the literal string `"False"`) was treated as truthy.
- Added a Content-Security-Policy (`django-csp`) covering the Medium "CSP header missing" finding: `default-src 'self'` with `'unsafe-inline'` for scripts/styles (matches the policy this report itself recommended) plus explicit Stripe allowances.

### 6. Self-hosted vendor assets are gitignored, regenerated automatically on container start
`core/static/vendor/` (downloaded libraries) and `staticfiles/` (collectstatic output) are build artifacts, not source — both are now in `.gitignore` (previously `staticfiles/` was committed directly, which is how this was being worked around). `staticfiles/` was untracked from git (`git rm --cached`) without deleting it from disk.

To avoid manually re-running curl commands on every deploy, `docker-entrypoint.sh` + `scripts/fetch_vendor_assets.sh` now run automatically on every container start: they re-download any missing vendor library (skipped if already present, so this is a no-op after the first run) and rebuild `tailwind.css` via the standalone Tailwind CLI, then run `collectstatic`. Verified end-to-end by deleting both directories and recreating the `django` container — everything regenerated correctly and the site came back up with no manual steps.

### Deployment action items (not done from this session — needs the live server)
- Set `DJANGO_BEHIND_TLS_PROXY=True` in production's `.env`.
- Add `server_tokens off;` to both `server {}` blocks in `nginx/default.conf` and rebuild the nginx container, to stop nginx advertising its version (the "hide server version" recommendation).
- Rebuild the `celery`/`celery_beat`/`flower` images too (only `django`'s image was rebuilt locally to test the new entrypoint) — harmless either way since they don't need the static assets, but keeps all 4 images in sync.
- Re-run the OWASP ZAP scan against production once deployed to confirm all findings clear.
