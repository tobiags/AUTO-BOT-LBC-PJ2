# Integration Apify multi-comptes, ingestion de leads et automatisation SMS

## Objectif

Ajouter au Control Tower une integration Apify capable de connecter plusieurs
comptes, decouvrir et piloter plusieurs Actors ou Tasks, importer tous leurs
resultats, normaliser automatiquement les leads heterogenes et demarrer la
sequence SMS existante des qu'un numero exploitable est disponible.

Le parcours nominal ne demande aucune validation humaine. L'intervention d'un
operateur est reservee aux conflits graves : plusieurs numeros impossibles a
departager, incoherence entre vendeur et annonce, derive majeure du schema ou
hausse anormale du risque d'envoi au mauvais destinataire.

## Principes directeurs

- Apify est un fournisseur d'ingestion, distinct de la plateforme source du lead.
- Les appels HTTP externes restent centralises dans `app/boundaries.py`.
- Les routes FastAPI deleguent toute logique aux services.
- Les traitements longs, imports et reconciliations passent par Celery.
- Les webhooks, imports, normalisations et creations de sequences sont idempotents.
- Un meme contact ne recoit qu'une sequence par campagne, meme s'il est retrouve
  par plusieurs Actors.
- La precision du numero destinataire prime sur le volume de leads importes.
- L'apprentissage peut modifier des profils de normalisation, jamais le code de
  production, les blacklists, les horaires ou les quotas SMS.

## Architecture

```text
Comptes Apify
  -> Actors et Tasks actives
  -> Runs Apify
  -> Datasets bruts
  -> Normalisation automatique
  -> Contact + contexte de lead (+ Listing si disponible)
  -> Campagne et secteur attribues
  -> Sequence SMS existante
```

### Frontieres applicatives

- `app/boundaries.py` : client Apify asynchrone, validation d'un jeton,
  decouverte du catalogue, lancement d'un run, lecture des metadonnees et
  iteration d'un Dataset.
- Services Apify dedies : comptes, catalogue, runs, ingestion, normalisation,
  profils d'apprentissage et reconciliation.
- `app/tasks.py` : declenchement des runs dus, import d'un run termine,
  reconciliation et evaluation periodique des profils candidats.
- Routes API : operations d'administration et lecture du dashboard, sans logique
  metier ni jeton retourne au client.
- Webhook public Apify : validation du secret, persistance idempotente de
  l'evenement, reponse immediate puis dispatch Celery.

## Modele de donnees

### `apify_accounts`

| Champ | Role |
| --- | --- |
| `id`, `workspace_id` | Identite et isolation du workspace |
| `label` | Nom operateur du compte |
| `apify_user_id`, `username` | Identite verifiee aupres d'Apify |
| `token_ciphertext` | Jeton chiffre, jamais retourne |
| `token_fingerprint` | Detection d'un jeton deja enregistre sans le reveler |
| `status` | `active`, `invalid`, `suspended` |
| `last_checked_at`, `last_error` | Diagnostic masque |
| timestamps | Audit du cycle de vie |

### `apify_actor_bindings`

| Champ | Role |
| --- | --- |
| `account_id` | Compte Apify utilise |
| `resource_type` | `actor` ou `task` |
| `resource_id`, `name` | Ressource distante |
| `workspace_id`, `sector_id`, `campaign_id` | Destination metier automatique |
| `input_ciphertext` | Parametres d'entree chiffres en bloc |
| `enabled` | Activation de l'automatisation |
| `schedule_minutes`, `next_run_at` | Planification interne dynamique |
| `webhook_id` | Webhook distant gere par le backend |
| `schema_fingerprint` | Detection de derive du format de sortie |
| `active_profile_id` | Profil de normalisation utilise |

Tous les bindings doivent avoir une campagne active. Le secteur est pris depuis
le binding, puis depuis la campagne ou le workspace si le binding n'en impose
pas. Un binding incomplet ne peut pas etre active.

### `apify_runs`

Cette table conserve l'identifiant du run distant, son binding, son statut, ses
dates, son `defaultDatasetId`, son cout connu, le nombre d'elements lus,
importes, ignores ou mis en exception, ainsi qu'une erreur bornee et assainie.
L'identifiant distant est unique par compte.

### `apify_items`

Chaque ligne contient le run, l'index du Dataset, une empreinte du contenu, le
JSON brut, le JSON normalise, le score de confiance, le statut de traitement et
les liens eventuels vers `Contact`, `Listing` et `SmsSequence`.

La contrainte `(account_id, run_id, dataset_index, content_hash)` rend la lecture
et le rejeu idempotents. Le JSON brut est conserve pour permettre le rejeu des
normalisateurs et l'audit.

### Profils, experiences et exceptions

- `apify_normalization_profiles` : version, empreinte de schema, mappings,
  alias, priorites, seuils, metriques et etat `candidate`, `active`, `retired`.
- `apify_normalization_experiments` : baseline, candidat, corpus, metriques,
  decision `keep`, `discard`, `crash` et motif.
- `apify_exceptions` : item, categorie grave, donnees utiles masquees, etat et
  resolution. Les absences simples de telephone ne creent pas d'exception.

## Secrets et permissions

Une cle maitre `APIFY_TOKEN_ENCRYPTION_KEY` est injectee cote API et worker
depuis Bitwarden. Elle chiffre les jetons Apify et les inputs d'Actors avant
persistance. Les valeurs sensibles ne figurent ni dans les logs, ni dans les
audits, ni dans Sentry, ni dans les reponses API.

Lors de l'ajout d'un compte, le backend valide le jeton avec l'identite Apify,
stocke uniquement sa forme chiffree et renvoie une representation masquee. Un
jeton peut etre remplace ou revoque, mais jamais relu depuis le dashboard.

Les administrateurs gerent comptes, bindings, campagnes, planifications et
profils. Les operateurs consultent runs, resultats et exceptions sans acces aux
secrets. Chaque webhook utilise un secret propre au compte dans un en-tete
configure par le template Apify et compare en temps constant.

## Cycle d'un Actor ou d'une Task

1. L'administrateur connecte un compte Apify.
2. Le backend decouvre Actors et Tasks accessibles.
3. L'administrateur active une ressource ; secteur, campagne et planification
   sont proposes automatiquement depuis les valeurs par defaut du workspace.
4. Le backend valide le binding et enregistre le webhook de fin de run.
5. Le run est lance manuellement, par le dispatcher des bindings dus, ou depuis
   Apify si la ressource possede deja sa propre planification.
6. Le webhook repond immediatement et lance l'import en arriere-plan.
7. Une reconciliation toutes les cinq minutes recupere aussi les runs termines
   dont le webhook est perdu ou retarde.
8. Le worker lit le Dataset par pagination automatique et traite chaque element
   independamment.

Un binding utilise soit la planification interne, soit une planification Apify,
jamais les deux. Le dashboard indique explicitement l'autorite de planification.

## Normalisation universelle

### Decouverte

Le normaliseur exploite dans cet ordre :

1. schema de Dataset et descriptions de champs exposes par l'Actor ;
2. schema de sortie et liens de stockage exposes sur le run ;
3. structure et types observes sur les premiers elements ;
4. profil actif deja appris pour la meme empreinte de schema.

Les schemas Apify sont utiles mais facultatifs. L'absence de schema ne bloque
donc pas l'ingestion.

### Representation canonique

Le resultat canonique peut contenir :

```text
source_platform, source_item_id, url, title, description,
phone_e164, price, mileage, location, brand, model, year,
seller_type, raw_payload
```

`source_platform` decrit la plateforme metier (`leboncoin`, `la_centrale` ou
autre). La provenance technique Apify reste portee par `apify_items` et ne
remplace pas cette information.

### Resolution des champs

Le JSON est aplati en conservant les chemins. La resolution applique :

1. correspondance explicite issue du schema ;
2. champs structures et types compatibles ;
3. dictionnaire d'alias francais et anglais ;
4. reconnaissance par la valeur ;
5. extraction depuis les textes libres ;
6. IA structuree en dernier recours.

Les numeros sont trouves et valides avec `phonenumbers`, normalises en E.164 et
acceptes pour le canal SMS uniquement s'ils sont possibles pour la region et de
type compatible. Un numero explicitement place dans un objet vendeur/contact a
priorite sur un numero seulement present dans une description.

Un item contenant plusieurs leads est eclate. Plusieurs numeros egalement
plausibles provoquent une exception grave ; le systeme ne choisit pas au hasard.

### Resultats non actionnables

- Aucun numero : `non_actionable`, conserve et visible.
- Numero invalide : `rejected_invalid_phone`, sans intervention.
- Numero blackliste : `blacklisted`, sans sequence.
- Donnees contradictoires : `exception`, Actor maintenu ou suspendu selon le
  taux d'anomalie.

Tous les resultats restent manipulables dans le dashboard. Seuls les resultats
actionnables entrent dans le flux SMS.

## Persistance et demarrage automatique des SMS

Pour une annonce structuree, le service cree ou met a jour `Listing` et
`Contact`. Pour un lead generique, il cree le `Contact` et conserve son contexte
normalise dans `apify_items`, sans inventer de vehicule ou d'URL.

`SmsSequence` est generalisee de facon minimale : elle reste liee au contact et
a la campagne, son `listing_id` devient optionnel et un `context_json` fige les
champs de rendu utiles au moment de la creation. Les appels historiques avec un
Listing continuent de fonctionner. Le rendu omet proprement les placeholders
optionnels absents au lieu de fabriquer des valeurs.

Une contrainte metier garantit une seule sequence par `(contact_id,
campaign_id)`. Une nouvelle annonce du meme contact peut enrichir le contexte,
mais ne redemarre pas la campagne.

Apres creation de la sequence, `run_sms_sequences_task.delay()` est appelee. Le
worker applique le programme de la campagne, les quotas, la blacklist et la
fenetre Europe/Paris 08 h-20 h. La verification Celery toutes les cinq minutes
sert uniquement a reperer les echeances ; elle ne definit pas l'intervalle entre
les messages.

## Boucle d'apprentissage controlee

La boucle adapte le principe de
[`karpathy/autoresearch`](https://github.com/karpathy/autoresearch) : baseline,
experience bornee, mesure, puis `keep` ou `discard`. Les recommandations de
[`multica-ai/andrej-karpathy-skills`](https://github.com/multica-ai/andrej-karpathy-skills)
guident la simplicite, les changements cibles et les criteres verifiables. Aucun
de ces depots n'est ajoute comme dependance d'execution.

```text
Observer
  -> detecter erreur ou derive de schema
  -> produire un profil candidat
  -> rejouer le corpus historique en mode fantome
  -> comparer au profil actif
  -> conserver ou rejeter
  -> promouvoir progressivement
  -> surveiller et restaurer si necessaire
```

### Corpus et metriques

Le corpus comprend les fixtures connues, les resultats historiques stables, les
cas d'exception resolus et les schemas precedents. Les corrections humaines ont
une valeur de reference superieure aux deductions automatiques.

Les metriques couvrent precision des numeros, stabilite des associations,
couverture, exceptions, doublons, cout IA et latence. Un profil candidat ne peut
modifier le numero canonique d'un cas historique stable. Une nouvelle couverture
n'est promue automatiquement que si plusieurs signaux independants concordent et
que tous les invariants de securite passent.

La boucle peut modifier mappings, alias, priorites et seuils. Elle ne peut pas
modifier le code, les horaires, quotas, campagnes, blacklists ou destinations de
webhook. Les experiences ne declenchent jamais de SMS.

## Dashboard

La page generale `Connecteurs` affiche une carte Apify et renvoie vers `/apify`.
La page dediee contient :

1. **Vue d'ensemble** : comptes, Actors, runs, imports, sequences et anomalies.
2. **Comptes** : ajout, test, remplacement, suspension et revocation des jetons.
3. **Actors et Tasks** : catalogue, binding, campagne, secteur, planification,
   lancement, webhook et profil actif.
4. **Runs** : statut, duree, Dataset, cout, compteurs et rejeu idempotent.
5. **Resultats et leads** : brut/normalise, liens Contact/Listing/Sequence,
   recherche, filtres et export administratif.
6. **Apprentissage et exceptions** : profils, metriques, experiences,
   changements de schema, rollback et cas graves.

Le telephone est masque par defaut. Aucun bouton par lead n'est necessaire pour
demarrer une sequence valide.

## Gestion des erreurs et observabilite

- Webhook non `2XX` : retries Apify ; le backend reste idempotent.
- Import interrompu : reprise depuis les items deja persistes.
- Jeton invalide : compte suspendu, bindings conserves.
- Rate limit ou panne Apify : retry borne avec backoff et jitter.
- Schema incompatible : mode fantome puis suspension du seul Actor si le risque
  reste eleve.
- SMSTools indisponible : sequence conservee et retentee selon les regles SMS.
- Anomalie de volume, de telephone ou de doublons : coupe-circuit par binding.

Les metriques exposent latence et succes par compte, runs en retard, taux de
normalisation, taux de leads actionnables, exceptions, deduplication, sequences
creees et couts Apify/IA. Tous les logs utilisent les identifiants internes et
distants comme correlation, jamais les secrets ni le JSON brut complet.

## Verification

### Backend et donnees

- migrations sur base vide et base existante ;
- chiffrement, rotation et non-divulgation des jetons ;
- isolation de plusieurs comptes et workspaces ;
- decouverte Actors/Tasks et validation des bindings ;
- lancement, webhook, reconciliation et pagination ;
- webhook et import rejoues plusieurs fois ;
- reprise apres interruption ;
- normalisation de schemas imbriques, tableaux et champs multilingues ;
- extraction E.164, numeros concurrents et schema changeant ;
- deduplication inter-Actors, blacklist et sequence deja existante ;
- campagne/secteur automatiques et contexte generique ;
- fenetre SMS 08 h-20 h, quotas et templates ;
- evaluation, promotion, rejet et rollback d'un profil.

Les tests utilisent la base reelle de test et mockent uniquement les fonctions
Apify/SMSTools de `boundaries.py`.

### Frontend

- masquage des secrets et controles par role ;
- etats vide, chargement, erreur et suspension ;
- catalogue multi-comptes ;
- filtres de runs et resultats ;
- brut/normalise sans fuite de donnees sensibles ;
- affichage des profils, experiences et exceptions ;
- commandes accessibles au clavier et retours d'action explicites.

### Parcours de bout en bout

Un faux Actor retourne un Dataset pagine avec doublons, numero valide, numero
blackliste, item sans telephone et schema modifie. Le test verifie qu'une seule
sequence est creee pour le bon contact, qu'aucun SMS ne part hors horaire, que
les items non actionnables sont visibles et que la derive cree un profil candidat
sans modifier le profil actif.

## Deploiement progressif

1. Deployer tables, comptes et catalogue sans lancement automatique.
2. Importer un Dataset historique sans creation de sequence.
3. Activer le mode fantome et etablir la baseline.
4. Activer un seul Actor avec quota SMS reduit.
5. Verifier destinataires, doublons, horaires et rollback.
6. Etendre progressivement aux autres Actors et comptes.
7. Activer la promotion automatique des profils apres un corpus suffisant.

## Concordance avec le plan d'origine

L'integration conserve FastAPI comme couche de contrat, Celery pour les travaux
longs, PostgreSQL comme source de verite, Redis comme broker, SMSTools comme canal
et Next.js comme surface operateur. Elle respecte la separation
routes/services/boundaries et l'idempotence imposee aux webhooks.

Les ajustements necessaires sont :

- ajouter Apify comme fournisseur de collecte ;
- ne pas planifier deux collecteurs pour la meme plateforme et le meme secteur ;
- appliquer explicitement R01 dans l'executeur des sequences SMS ;
- remplacer le commentaire obsolete « quotidien a 06 h » : le dispatcher actuel
  tourne toutes les cinq minutes et selectionne les secteurs dus ;
- separer plateforme source et fournisseur d'ingestion ;
- generaliser minimalement `SmsSequence` pour un contexte sans Listing ;
- ajouter des identifiants de correlation fournisseur/run aux workflows.

Apify complete le scraping actuel et corrige la faiblesse de backfill relevee
dans la revue du 12 juillet. Il ne remplace pas les garanties metier de
deduplication, blacklist, quotas, horaires et audit.

## Hors perimetre

- modification ou fork des Actors Apify tiers ;
- contournement de CAPTCHA, limitations ou conditions des plateformes sources ;
- modification autonome du code applicatif par une IA ;
- envoi de SMS depuis un Dataset de test ou une experience en mode fantome ;
- validation manuelle de chaque lead ;
- remplacement de SMSTools ou du moteur de campagnes existant.

## Sources techniques consultees

- [Client Python Apify](https://github.com/apify/apify-client-python)
- [Schema de sortie d'un Actor](https://docs.apify.com/actors/development/actor-definition/output-schema)
- [Schema et stockage Dataset](https://docs.apify.com/storage/dataset-schema)
- [Webhooks Apify](https://docs.apify.com/integrations/webhooks/actions)
- [libphonenumber](https://github.com/google/libphonenumber)
- [Autoresearch](https://github.com/karpathy/autoresearch)
- [Karpathy-inspired coding guidelines](https://github.com/multica-ai/andrej-karpathy-skills)
