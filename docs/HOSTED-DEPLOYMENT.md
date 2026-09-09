# Host a private organization library over HTTPS

This recipe runs one organization on a Linux host with Docker Compose. It is suitable for an invited pilot after the owner completes the release checks. Use separate installations for unrelated customers; this release does not implement shared-service organization isolation or subscriptions.

## Prepare the host

Use a domain you control, a Linux host with Docker/Compose, persistent local storage and a backup destination outside that host. Point the hostname's DNS records to the host. Permit incoming TCP 80 and 443; UDP 443 is optional for HTTP/3. Do not expose the application's internal port 8080.

Copy `.env.example` to `.env` in the checkout. Set:

```dotenv
LEGAL_PLATFORM_DOMAIN=library.your-domain.example
LEGAL_PLATFORM_HOST_DATA_DIR=./storage
LEGAL_PLATFORM_STORAGE_LIMIT_MB=2048
```

Replace the example hostname with your real hostname, without `https://` or a path. The hosted Compose file derives the canonical HTTPS origin. Its dedicated Docker network defaults to `172.30.84.0/24`, with Caddy at `172.30.84.2`. If this conflicts with an existing network, set `LEGAL_PLATFORM_PROXY_SUBNET` and `LEGAL_PLATFORM_PROXY_ADDRESS` together to an unused subnet/address pair.

## Start and create the first administrator

```sh
docker compose -f docker-compose.hosted.yml config --quiet
docker compose -f docker-compose.hosted.yml up --build -d
docker compose -f docker-compose.hosted.yml logs --tail=100 caddy legal-platform
docker compose -f docker-compose.hosted.yml exec legal-platform cat /app/storage/setup-code.txt
```

Open your HTTPS address and enter the host's setup code to create the administrator. Then invite the first colleagues and explicitly share their collections. Public signup requests remain pending until approved. Keep two trusted administrators.

Caddy obtains and renews HTTPS certificates and redirects HTTP to HTTPS. This requires correct DNS, reachable challenge ports, and persistent Caddy data. Keep both named Caddy volumes when upgrading. See [automatic HTTPS](https://caddyserver.com/docs/automatic-https) for the certificate requirements and [reverse proxy behavior](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy) for forwarding details.

## How the proxy boundary works

`LEGAL_PLATFORM_PUBLIC_ORIGIN` is a fixed operator setting, not a forwarded browser header. It must be an HTTPS origin. The application uses it for its browser origin checks and Secure cookies, and rejects application requests for an unrelated Host. Minimal health probes remain available inside the container.

`LEGAL_PLATFORM_TRUSTED_PROXIES` accepts explicit IP addresses/CIDRs. The supplied recipe trusts only Caddy's assigned address. Caddy replaces incoming `X-Forwarded-For` with the actual client address. The application accepts one valid forwarded IP only from a configured peer, so separate users retain separate address-based rate limits. It does not trust forwarded scheme or host values.

Keep the backend's host port unpublished and do not attach untrusted containers to this network. If using a different proxy, preserve the public Host, replace incoming forwarding headers, configure the proxy's exact network address and set the canonical HTTPS origin. Ordinary source/LAN runs leave both settings unset and retain their direct-connection behavior.

## Backups and recovery

The Windows launcher has backup/recovery buttons. Linux and Docker operators use the same operations through a maintenance command. Passphrases are prompted privately and never supplied in arguments or environment variables.

Create a backup while the library is running:

```sh
docker compose -f docker-compose.hosted.yml exec --user appuser legal-platform \
  python -m legal_platform.operator backup /app/storage/library-2026-09-08.legalbackup
docker compose -f docker-compose.hosted.yml cp \
  legal-platform:/app/storage/library-2026-09-08.legalbackup ./library-2026-09-08.legalbackup
```

Choose a new filename each time. Move the completed encrypted copy to your separate backup storage. A copy left on the same host does not protect against losing that host. The archive includes accounts, source versions and provider settings; it excludes old sessions, recovery codes and host certificates. Existing backup files are never overwritten.

To test a restore, use a source installation and a new empty destination:

```sh
python -m legal_platform.operator restore ./library-2026-09-08.legalbackup ./restored-library
```

Verify that restored library separately before changing the production data mount. Users must sign in again. For a Docker restore, run the operator command in a disposable container with the backup and empty destination mounted; preserve user 10001 ownership on the resulting data. Keep the original data as a rollback copy and start only one server against a data folder.

If all administrators are locked out, a trusted host operator can recover an **existing active administrator** while the server is stopped:

```sh
docker compose -f docker-compose.hosted.yml stop legal-platform
docker compose -f docker-compose.hosted.yml run --rm --no-deps legal-platform \
  python -m legal_platform.operator recover-admin existing-admin-username
docker compose -f docker-compose.hosted.yml start legal-platform
```

Recovery changes that password, revokes its sessions and recovery codes, and records an audit event. It cannot create an account, promote a member or reactivate a disabled administrator. People with host filesystem control are trusted operators; this is not a browser-accessible recovery route.

## Upgrade and operate

Back up first. Stop the application, update to a reviewed source revision, rebuild with the same Compose project and data mount, then verify sign-in, upload, search, source downloads and saved answers. Preserve the previous package/image and original data until verification completes. Do not use `down --volumes` as an upgrade command.

Check disk space, failed document processing, certificate renewal, host restarts and backup restore results. Agree on support ownership, monitoring, alerts, retention and incident response before onboarding customers. The source image includes Tesseract and Vietnamese language data; real document OCR still needs validation on the chosen host.

## Validation status

The application has regression coverage for canonical HTTPS origin, Secure cookies, CSRF, Host rejection and trusted proxy attribution. A real Caddy 2.11.2 test on Windows passed certificate-verified HTTPS bootstrap, login, document processing, answer generation and source download. That test uses synthetic data, loopback listeners, a test certificate and bounded process cleanup; it does not obtain a public ACME certificate.

The Caddyfile also passed Caddy's configuration validation. A Docker daemon is not available on the development workstation, so the Linux image/Compose deployment and public DNS/ACME flow still need to be exercised on the target host. The optional real-proxy test is `tests/test_reverse_proxy_live.py`; set `LEGAL_PLATFORM_TEST_CADDY` to a verified Caddy binary to run it.
