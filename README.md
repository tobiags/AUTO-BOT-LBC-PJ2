# AutoTransfert P2 — Acquisition Véhicules

Système d'automatisation SMS + scraping LeBonCoin / La Centrale pour AutoTransfert SAS.

## Stack

| Couche | Technologie |
|---|---|
| API | FastAPI 0.115 + Python 3.12 |
| Workers | Celery + Redis |
| DB | PostgreSQL 16 (asyncpg + SQLAlchemy 2) |
| Scraping | crawl4ai + Scrapling + Patchright |
| Anti-détection | browser-use Cloud Dev tier |
| SMS | SMSTools (8 SIMs FR) |
| OTP | SmsApp.io (pay-per-delivery) |
| Proxy 4G | iproxy.online (création comptes LBC uniquement) |
| Email catch-all | Mailgun + domaine dédié |
| Monitoring | Sentry |

## Démarrage local

```bash
# 1. DB + Redis
docker-compose up -d postgres redis

# 2. Dépendances
pip install -e ".[dev]"

# 3. Variables d'environnement
cp .env.example .env
# → remplir les clés dans .env (via Bitwarden)

# 4. Migrations
alembic upgrade head

# 5. API
uvicorn app.main:app --reload

# 6. Worker Celery (autre terminal)
celery -A app.tasks worker --loglevel=info

# 7. Tests
pytest
```

## Structure

```
app/
  api/          # routes HTTP
  webhooks/     # SMSTools, Mailgun, appels
  services/     # logique métier
  boundaries.py # SEUL fichier qui appelle des APIs externes
tests/
scripts/        # deploy.sh, verify_server.sh
docs/           # plan d'implémentation HTML
```

## Règles importantes

- **R01** : SMS uniquement 08h–20h heure Paris
- **R02** : STOP blackliste P1 + P2 simultanément
- **R03** : Toutes les clés API via Bitwarden — jamais par email/SMS
- **R07** : Création comptes LBC = iproxy.online 4G uniquement (jamais IP VPS)

## Plan d'implémentation

Voir `docs/Plan_Implementation_Modules.html` pour la documentation complète module par module.

## Déploiement

```bash
./scripts/deploy.sh <VPS_IP>
```
