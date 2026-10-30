# Security policy

ARGUS-NEURO is a research prototype with a hardened deployment recipe ([docs/PRODUCTION.md](docs/PRODUCTION.md)). It has not been audited by a third party and must not be the only safeguard for any safety-relevant decision.

## Reporting a vulnerability

Please open a private security advisory for this repository on GitHub (Security tab, "Report a vulnerability") and do not post details in a public issue. Include the version or commit, what you did and what happened.

## Things to know before deploying

- The application has no login of its own: put it behind the proxy in `docker-compose.prod.yml` and never publish port 8000.
- The proxy login is one shared user without lockout; use a long random password and restrict access by network.
- `/api/ingest/*` is protected by one bearer token (`ARGUS_INGEST_TOKEN`); rotate it by changing the variable and restarting.
- Secrets live in `.env`, which is git-ignored. Do not commit it or paste it into issues.
