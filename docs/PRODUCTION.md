# Operating ARGUS-NEURO (production stack)

What was done for deployment, what was verified and where the limits are. Verified on Linux x86-64 with Docker Compose v2 only. The Russian version, [PRODUCTION.ru.md](PRODUCTION.ru.md), is the complete one; this page is the short form.

## Intended use

Suitable: remaining-capacity estimates and intervals for laboratory cells (NASA, CALB, HUST), uploading your own capacity history, archiving OCPP 1.6J telemetry, supervised pilots on a closed network.

Not suitable without your own validation: decisions about stopping, admitting or the safety of equipment, vehicles, chargers or drones; EV packs, scooters and power banks (never tested, pack intervals are not calibrated); diagnosis of real chargers (the equipment models were trained on synthetic data). Coverage fell to 83% (CALB) and 73% (NASA) against a nominal 90% when those sources were unseen, see [BACKTEST.md](BACKTEST.md).

## What the stack contains

`docker-compose.prod.yml`: the application (port not published) behind Caddy 2.11.7.

- TLS: Let's Encrypt for a public domain, an internal test CA for `localhost`.
- HTTP Basic login on everything except `/api/health` (open, no data) and `/api/ingest/*` (own bearer token, `ARGUS_INGEST_TOKEN`).
- HSTS, `nosniff`, frame denial, `no-referrer`; 4 MB body limit; real client IP forwarded so the rate limit works per client. No CSP (not verified against the dashboard).
- Containers: non-root, read-only root filesystem, all capabilities dropped, 2 GB / 2 CPU limit on the application, restart on failure, rotated logs (5 x 10 MB).

## Deploy

```bash
cp .env.example .env     # fill in; never commit it
docker run --rm caddy:2.11.7-alpine caddy hash-password --plaintext 'a-long-random-password'
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
docker compose -f docker-compose.prod.yml --env-file .env exec argus bash scripts/train_all.sh
docker compose -f docker-compose.prod.yml --env-file .env restart argus
bash scripts/prod_smoke.sh https://your-domain operator 'password'
```

There is no lockout after failed logins and only one shared user, so use a random password of 16+ characters and restrict access by network or VPN. Keep ports 80 and 443: the HTTP redirect always points at 443.

## Monitoring, backup, upgrade

- `GET /api/health` (open) and `GET /api/metrics` (Prometheus text, behind the login): `argus_up`, `argus_model_backed`, `argus_connected_clients`, `argus_last_tick_age_seconds`, `argus_producer_error`.
- `scripts/backup_volume.sh` and `scripts/restore_volume.sh` (set `ARGUS_COMPOSE` for this stack). The restore refuses archives with absolute or parent paths. Back up before every upgrade; roll back by checking out the previous commit and rebuilding.

## Measured load

Laptop (i5-1235U, 23 GB), whole stack in Docker Desktop, through the TLS proxy with login, 20 s, 24 concurrent requests and 20 WebSocket clients (`scripts/load_test.py`): about 220 requests per second in total with no errors, latency p50 / p95 / p99 about 70 / 320 / 570 ms at full load, 20 of 20 WebSocket clients served, application memory about 258 MB. The application runs as one process; there is no horizontal scaling. Higher load, long runs and failover were not tested.

## Known limits

Single instance, no failover. The OCPP collector is not part of the production Compose file (it needs credentials and `wss` before real chargers connect). Tested on Linux x86-64 only. Public datasets are not in the image (licences). Image vulnerability scanning is not automated; Dependabot watches the dependencies.
