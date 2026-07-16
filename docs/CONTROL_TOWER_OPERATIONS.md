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

## Apify : configuration et commandes

Generer une cle Fernet distincte par environnement, la placer dans
`APIFY_TOKEN_ENCRYPTION_KEY`, puis redemarrer uniquement l'API et les workers :

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Le token Apify et l'input des Actors sont write-only et chiffres. Ne jamais les
placer dans un log, un ticket ou une capture du dashboard. Exemples de commandes
avec le token interne Control Tower :

```bash
# Tester un compte et resynchroniser son catalogue.
curl -X POST "$API/api/v1/apify/accounts/$ACCOUNT_ID/probe" -H "X-Control-Tower-Token: $CONTROL_TOWER_TOKEN" -H "X-Operator-Role: admin"
curl -X POST "$API/api/v1/apify/accounts/$ACCOUNT_ID/catalog/sync" -H "X-Control-Tower-Token: $CONTROL_TOWER_TOKEN" -H "X-Operator-Role: admin"

# Rotation du token fournisseur.
curl -X PATCH "$API/api/v1/apify/accounts/$ACCOUNT_ID" -H "Content-Type: application/json" -H "X-Control-Tower-Token: $CONTROL_TOWER_TOKEN" -H "X-Operator-Role: admin" -d '{"token":"apify_api_nouveau"}'

# Suspendre manuellement un binding sans toucher aux autres Actors.
curl -X PATCH "$API/api/v1/apify/bindings/$BINDING_ID" -H "Content-Type: application/json" -H "X-Control-Tower-Token: $CONTROL_TOWER_TOKEN" -H "X-Operator-Role: admin" -d '{"enabled":false}'

# Rejouer un import idempotent et restaurer un profil retire.
curl -X POST "$API/api/v1/apify/runs/$RUN_ID/replay" -H "X-Control-Tower-Token: $CONTROL_TOWER_TOKEN" -H "X-Operator-Role: operator"
curl -X POST "$API/api/v1/apify/profiles/$PROFILE_ID/rollback" -H "X-Control-Tower-Token: $CONTROL_TOWER_TOKEN" -H "X-Operator-Role: admin"
```

Pour le webhook, lancer un Actor de test depuis Apify puis verifier un `202` sur
`/webhooks/apify/{account_id}` et un seul import dans les logs. Un appel forge ou
le secret d'un autre compte doit retourner `401`. Le secret genere par le backend
reste chiffre et n'est jamais recopie dans le dashboard.

## Gates de rollout Apify

Les gates sont sequentiels. La premiere livraison garde tous les bindings
desactives et ne passe au gate suivant qu'apres validation des compteurs et des
exceptions du gate courant.

1. **Gate 1 :** compte connecte, catalogue synchronise, aucun run automatique.
2. **Gate 2 :** import historique, sequences desactivees.
3. **Gate 3 :** profil fantome, zero changement de telephone stable.
4. **Gate 4 :** un Actor, campagne de test, quota par SIM reduit.
5. **Gate 5 :** verification des doublons, STOP et fenetre 08:00-20:00 Europe/Paris.
6. **Gate 6 :** extension progressive, puis apprentissage automatique controle.

Le dispatcher de collecte historique s'execute toutes les cinq minutes. Il ne
lance pas tous les secteurs : `get_due_sector_ids()` ne retourne que ceux dont
l'echeance est atteinte. Il n'existe plus de lancement global quotidien a 06:00.
