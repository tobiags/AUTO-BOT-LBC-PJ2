# Revue complete du projet AutoTransfert P2

Date de revue : 12 juillet 2026  
Branche : `main`  
Portee : API FastAPI, workers Celery, frontend Next.js, PostgreSQL, Redis, scraping, Browser Use, webhooks, laboratoire experimental et deploiement Coolify.

## Resume executif

Le projet possede une base fonctionnelle coherente : separation API/services/workers, workflows persistants, idempotence sur plusieurs traitements, dashboard operateur, tests backend et frontend, et deploiement separe de l'API, du worker et du frontend.

Le verdict est cependant **Request Changes avant exploitation autonome en production**. Les campagnes et diagnostics simples fonctionnent, mais quatre domaines restent bloquants : la protection des routes historiques et des webhooks, la creation de comptes LBC, la garantie de collecte des annonces anciennes et nouvelles, et la terminaison fiable de tous les workflows en cas d'erreur.

## Verification executee

| Verification | Resultat |
|---|---|
| Tests backend | `150 passed, 9 skipped` |
| Tests frontend | `18 passed` |
| Build Next.js | Succes |
| ESLint | Succes |
| Ruff | Echec : 2 erreurs corrigibles dans `app/api/operations.py` |
| Audit dependances production | 2 vulnerabilites moderees (`next` / `postcss`) |
| Inspection production | API, Redis et worker disponibles ; aucun compte LBC actif |

## Problemes critiques

### 1. Routes metier historiques accessibles sans authentification

Les routes `/accounts`, `/campaigns`, `/analyzer`, `/listings` et `/api/v1/dashboard` sont montees directement dans FastAPI. Plusieurs mutations sensibles, par exemple la creation de compte, le demarrage de campagne, la modification d'un statut de compte et la mise a jour d'un solde, ne passent pas par `_authorize()`.

Le middleware Next.js protege uniquement les pages et proxies du frontend. Un appel direct a `api.ecovente.com` contourne ce middleware.

Impact : creation de comptes, lancement de campagnes ou modification de donnees par un client non authentifie.

Decision recommandee : rendre les anciennes routes en lecture seule ou les retirer de la surface publique, et imposer l'authentification Control Tower sur toute mutation.

### 2. Webhooks non authentifies et code OTP expose

Les webhooks SMS, appels, fonds et Mailgun n'utilisent pas les secrets de signature declares dans la configuration. Le webhook Mailgun journalise le code de verification et le retourne dans la reponse HTTP.

Impact : falsification d'evenements, modification de soldes, ajout arbitraire a la blacklist, fuite d'OTP dans les logs ou la reponse.

Decision recommandee : verifier la signature du fournisseur avant tout traitement, ne jamais retourner ni journaliser l'OTP, puis ajouter des tests de signature invalide et de rejeu.

### 3. Les comptes crees ne sont pas raccordes a la messagerie LBC

La messagerie ne selectionne que les comptes `ACTIF` possedant `browser_use_profile_id`. Or le workflow de creation persiste seulement `session_path` et ne renseigne jamais ce profil.

Le mode A produit une session Patchright locale, tandis que la messagerie utilise Browser Use Cloud. Le mode B arrete sa session Browser Use et ne conserve ni profil reutilisable ni identifiant de session dans `PlatformAccount`.

Impact : meme apres une creation reussie, la campagne LBC affiche `No active Browser Use profile`.

Decision recommandee : choisir explicitement un modele de session par compte :

- soit messagerie locale via la session Patchright du mode A ;
- soit creation et persistance d'un profil Browser Use reutilisable pour le mode B.

Ne pas marquer un compte `ACTIF` tant que la session choisie n'a pas passe un diagnostic de messagerie.

### 4. Validation email impossible dans le flux actuel

Le webhook Mailgun cherche le compte par email afin de deposer le code dans Redis. Le compte n'est pourtant insere en base qu'apres la fin de la navigation et des validations SMS/email.

Impact : si LBC demande un code email, le webhook ne trouve aucun compte et le worker attend jusqu'au timeout.

Decision recommandee : creer un enregistrement `EN_CREATION` avant la navigation, avec l'email et l'identifiant de workflow, puis le completer ou le supprimer proprement selon le resultat.

## Problemes majeurs

### 5. La collecte ne garantit pas toutes les annonces anciennes et nouvelles

Le traitement de campagne parcourt bien toutes les annonces deja presentes en base par lots de 25. En revanche, le scraper LBC ouvre une seule page et limite l'extraction a 100 liens. La Centrale ne boucle pas non plus sur les pages de resultats.

Impact : la promesse de backfill complet n'est pas satisfaite si les annonces ne sont jamais importees en base.

Decision recommandee : ajouter un curseur de pagination persistant par recherche, un mode `backfill` du plus ancien au plus recent, un mode incremental, et un checkpoint permettant de reprendre sans doublon.

### 6. Certains workflows peuvent encore rester RUNNING/PENDING

Les campagnes LBC et la creation de comptes enregistrent maintenant leurs erreurs, mais Browser Use, le laboratoire et plusieurs dispatchs Celery n'appliquent pas tous la meme garantie. Une exception apres le passage a `RUNNING` peut laisser un workflow sans etat terminal.

Decision recommandee : centraliser un wrapper de tache qui applique toujours : `RUNNING`, heartbeat, `COMPLETED` ou `FAILED`, `finished_at`, code d'erreur et message tronque sans secret.

### 7. Le WebSocket du dashboard est public

`/ws` accepte une connexion sans session ni token. Les evenements peuvent contenir un numero appelant et des informations d'annonce.

Decision recommandee : authentifier la connexion, limiter les origines et filtrer les champs personnels.

### 8. Double gestion du schema

Alembic est present et execute au demarrage du worker, mais l'API lance egalement `Base.metadata.create_all()` et plusieurs `ALTER TABLE IF NOT EXISTS` dans `schema_sync.py`.

Impact : divergence entre le schema reel, les migrations et les environnements de test.

Decision recommandee : conserver Alembic comme source unique, puis retirer progressivement les DDL de compatibilite apres verification des instances.

### 9. Observabilite encore partielle

Les workflows et audits sont persistants et visibles. Il manque toutefois un identifiant de correlation commun API/Celery/fournisseur, un heartbeat explicite et une politique de retention/export des erreurs.

Decision recommandee : ajouter `correlation_id`, `last_heartbeat_at`, codes d'erreur normalises, export JSON et alerte sur workflow sans heartbeat.

## Problemes mineurs

- Ruff signale un import inutilise et un bloc d'import non trie dans `app/api/operations.py`.
- `schema_sync.py` indique qu'Alembic n'existe pas alors que huit migrations sont presentes.
- Le README contient plusieurs caracteres mal encodes et des versions de stack qui ne correspondent plus exactement aux dependances installees.
- Le filtre `vehicle_type` repose uniquement sur le titre de l'annonce ; il peut exclure des SUV dont le titre ne contient pas le mot `SUV`.
- L'audit npm remonte deux vulnerabilites moderees transitives liees a PostCSS. Verifier une mise a jour Next.js compatible plutot que d'appliquer un downgrade automatique.

## Points positifs

- Bonne separation entre API, services metier, boundaries externes et workers.
- Utilisation d'idempotency keys et d'upserts PostgreSQL sur plusieurs flux.
- Campagnes traitees par lots bornes avec deduplication des messages.
- Session frontend HttpOnly signee et roles viewer/operator/admin.
- Laboratoire Camoufox/Obscura isole et desactive par defaut.
- Tests nombreux et rapides sur les chemins principaux.
- Deploiements applicatifs separes des bases de donnees.

## Ordre de correction recommande

1. Fermer les routes directes non authentifiees et signer tous les webhooks.
2. Reparer le cycle de vie `EN_CREATION` et persister une session utilisable par la messagerie.
3. Ajouter pagination/backfill avec checkpoint pour LBC et La Centrale.
4. Generaliser le wrapper de workflow et le heartbeat.
5. Unifier la gestion du schema sous Alembic.
6. Corriger Ruff, l'encodage documentaire et les dependances moderees.

## Verdict

**Request Changes** pour une exploitation autonome ou multi-utilisateur.  
**Utilisable avec supervision** pour les diagnostics Browser Use, le dashboard, les campagnes sur un jeu d'annonces deja collecte et les fonctions experimentales isolees.
