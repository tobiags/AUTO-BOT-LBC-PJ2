# Pool d'identites e-mail du domaine operationnel

## Objectif

Produire et administrer, depuis le dashboard, des identites e-mail reelles du
domaine operationnel. Chaque identite comprend un prenom, un nom et une adresse
unique. La reception est assuree par la route Mailgun generique du domaine ; le
systeme ne cree pas de boites LWS individuelles.

## Perimetre

- Generation manuelle de lots de 10, 15 ou 20 identites.
- Liste variable et paginee dans le dashboard.
- Consultation du prenom, nom, e-mail, etat, date de creation et association
  eventuelle a un compte interne.
- Actions operateur : copier, reserver, liberer, desactiver et supprimer une
  identite non utilisee.
- Reservation atomique par les parcours internes autorises afin qu'une
  identite disponible ne soit jamais attribuee deux fois.

La fonctionnalite ne pilote pas l'inscription ni la verification de comptes
sur des services tiers. Elle fournit uniquement les identites et leur cycle de
vie au sein du projet.

## Donnees

Nouvelle table `email_identities` :

| Champ | Description |
| --- | --- |
| `id` | UUID de l'identite |
| `first_name` | Prenom genere depuis un jeu de donnees francais embarque |
| `last_name` | Nom genere depuis un jeu de donnees francais embarque |
| `email` | Adresse unique `prenom.nom-suffixe@OPERATIONAL_DOMAIN` |
| `status` | `available`, `reserved`, `used`, `disabled` |
| `reserved_by` | Identifiant du flux interne ayant reserve l'identite |
| `reserved_at` | Date de reservation |
| `used_at` | Date d'utilisation interne |
| `created_at` | Date de generation |
| `updated_at` | Derniere modification |

Une contrainte unique protege `email`. Les noms et prenoms sont conserves
separes afin d'etre affiches et reutilisables dans les interfaces internes.

## Flux

1. Un administrateur choisit une taille de lot (10, 15 ou 20) dans le
   dashboard.
2. Le backend valide la configuration Mailgun et le domaine operationnel, puis
   genere et enregistre le lot dans une transaction.
3. La liste se rafraichit avec les nouvelles identites `available`.
4. Un parcours interne demande une identite : le backend verrouille une ligne
   disponible, passe son statut a `reserved` et retourne uniquement les champs
   necessaires.
5. Le parcours confirme l'utilisation interne (`used`) ou libere la reservation
   en cas d'echec avant utilisation.

## Dashboard

La page Comptes LBC devient une surface distincte en deux sections :

1. **Identites e-mail** : compteur par etat, generation de lot et table
   prenom/nom/e-mail/etat/creation/actions.
2. **Comptes de plateforme** : table existante des comptes et de leurs
   identifiants deja associes.

Les valeurs sont copiees explicitement, sans jamais afficher le contenu des
messages entrants ni un code OTP.

## Erreurs et securite

- Generation refusee si `OPERATIONAL_DOMAIN` ou la configuration Mailgun sont
  absents.
- Une collision d'adresse regenere uniquement le suffixe dans la transaction.
- Les reservations ont un delai d'expiration configurable et sont liberables
  par une tache de reconciliation.
- Toutes les actions de gestion sont tracees dans `AuditEvent`.
- Les routes de gestion restent derriere le middleware et exigent le role
  administrateur pour generer ou supprimer un lot.

## Verification

- Tests unitaires : format, unicite et transitions d'etat.
- Tests API : lot de 10/15/20, droits, collision et reservation concurrente.
- Tests front : affichage du nom complet, boutons de copie et retour d'action.
- Migration appliquee sur une base vide et une base comportant deja des comptes.
