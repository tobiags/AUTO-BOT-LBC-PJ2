# Control Tower - exploitation et maintenance

## Services

- API FastAPI: contrats, authentification interne, audit, et lecture PostgreSQL.
- Worker Celery: campagnes par lots, synchronisation LBC, Browser Use et diagnostics.
- Frontend Next.js: session HttpOnly et proxy des commandes; aucune cle fournisseur n'est exposee.
- Lab experimental: Camoufox et Obscura, isole et desactive par defaut.
- PostgreSQL et Redis: services persistants; ils ne doivent pas etre redeployes pour une livraison applicative.

## Configuration minimale

Configurer la meme valeur `CONTROL_TOWER_TOKEN` sur l'API et le frontend. Configurer uniquement sur le frontend:

- `CONTROL_TOWER_SESSION_SECRET`;
- `CONTROL_TOWER_ADMIN_USER` et `CONTROL_TOWER_ADMIN_PASSWORD`;
- facultativement les comptes `OPERATOR` et `VIEWER`.

Les cles Browser Use, iProxy, SMSTools, SmsApp, Mailgun et Sentry restent uniquement cote serveur. Les variables du laboratoire sont `LAB_SERVICE_URL`, `LAB_API_TOKEN`, `LAB_ALLOWED_DOMAINS`, `CAMOUFOX_ENABLED` et `OBSCURA_ENABLED`.

## Ordre de deploiement

1. Sauvegarder PostgreSQL et verifier Redis.
2. Deployer l'API seule.
3. Verifier `/health`, puis la version Alembic `g7c3e9f5b2d4` dans les logs.
4. Verifier les lectures du dashboard et les probes sans mutation.
5. Deployer le worker Celery seul et verifier qu'il rejoint Redis.
6. Executer une commande de diagnostic sans effet metier.
7. Deployer le frontend seul, ouvrir `/login`, puis tester viewer, operator et admin.
8. Deployer le lab separement; laisser ses deux feature flags a `false` tant que `/health` et un corpus autorise ne sont pas valides.

Ne pas redeployer PostgreSQL ou Redis. Une migration de schema n'est pas un redeploiement de base de donnees.

## Verification fonctionnelle

- Dashboard: fraicheur, actions requises, comptes et taux de reponse.
- Campagnes: creation, demarrage, pause, reprise et annulation.
- Messagerie: lots de 25, annonces anciennes et nouvelles, deduplication, synchronisation inbox et extraction E.164.
- Browser Use: cout, session, progression, direct, resultats, captures et arret.
- Connecteurs: statut configure distinct du statut verifie, latence et erreur normalisee.
- Comptes: creation admin, chauffe, inspection, quarantaine et restauration.
- Lab: execution admin uniquement, arret, comparaison et export JSON.
- Workflows: historique, checkpoint, reprise, retry et erreur lisible.

## Incidents et reprise

- `401` ou `403`: corriger les identifiants; ne pas relancer automatiquement.
- `429`: respecter `Retry-After`; conserver le checkpoint avant reprise.
- Redis indisponible: ne pas lancer de nouvelle commande.
- PostgreSQL indisponible: ne pas lancer de mutation; restaurer la connectivite avant le worker.
- Session LBC expiree ou challenge interactif: mettre le compte en quarantaine et demander une intervention.
- Budget Browser Use atteint: la tache est arretee par le plafond configure.
- Lab en echec: laisser la production active; le lab ne partage ni profil ni session de production.

## Maintenance

- Revoir chaque mois les quotas, couts et seuils d'alerte.
- Garder les templates Browser Use versionnes et limites aux domaines autorises.
- Tester les contrats fournisseurs avec des reponses simulees avant toute mise a jour de client.
- Purger les rapports du lab selon la politique de retention; ne jamais y stocker cookies, OTP ou corps complets de conversation.
- Revoquer les tokens temporaires de deploiement apres acceptation de la production.
