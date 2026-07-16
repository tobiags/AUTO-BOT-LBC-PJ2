# Boite de reception des identites e-mail

## Objectif

Permettre a tout utilisateur authentifie du dashboard de consulter les messages
recus par les identites e-mail gerees par l'application. Les contenus sont
conserves sept jours, puis supprimes definitivement.

## Perimetre

- Reception des e-mails entrants envoyes par Mailgun vers le webhook existant.
- Conservation en base des metadonnees et du contenu texte/HTML des messages.
- Consultation dans une boite de reception du dashboard et lecture detaillee.
- Filtrage par identite e-mail, expéditeur et statut lu/non lu.
- Suppression manuelle reservee aux administrateurs.
- Purge automatique quotidienne des messages et pieces jointes de plus de sept
  jours.

Le webhook reste signe par Mailgun. La boite de reception est uniquement
accessible depuis le dashboard authentifie ; aucune route de lecture publique
ne sera ajoutee.

## Modele de donnees

Une table `email_messages` est liee a `email_identities` par `identity_id`.
Elle contient l'expediteur, le destinataire, l'objet, les corps texte et HTML,
la date de reception, l'etat de lecture, une cle idempotente et les
metadonnees de pieces jointes. Les fichiers sont stockes dans le stockage
applicatif configure ; leurs references sont supprimees avec le message.

Les messages dont le destinataire ne correspond pas a une identite geree ne
sont pas enregistres dans cette boite de reception. Les webhooks deja recus
sont dedupliques par leur cle idempotente.

## Flux

1. Mailgun transfere un e-mail entrant a `POST /webhooks/email`.
2. L'API verifie la signature et trouve l'identite par l'adresse destinataire.
3. Elle enregistre le message et les metadonnees de pieces jointes dans une
   transaction idempotente.
4. Le dashboard appelle des endpoints proteges pour lister et lire les
   messages, et peut marquer un message comme lu.
5. Une tache planifiee supprime chaque jour les messages dont la reception est
   anterieure a sept jours.

## Experience dashboard

Une page `Boite de reception` presente une liste paginee avec destinataire,
expediteur, objet, date et statut lu/non lu. L'utilisateur peut filtrer par
adresse et rechercher un expediteur ou objet. La selection d'un message ouvre
un panneau de lecture avec le texte et une version HTML isolee. Tous les
roles connectes peuvent lire et marquer comme lu. Les administrateurs seuls
peuvent supprimer avant l'expiration.

## Securite et retention

- Les endpoints emploient la meme protection dashboard que les autres routes
  de controle.
- La signature Mailgun est verifiee avant toute ecriture.
- Le HTML est rendu dans un contexte isole afin de ne pas executer de scripts
  ou acceder a la session du dashboard.
- Les contenus et fichiers associes sont purges definitivement apres sept
  jours, y compris lors d'une suppression manuelle.

## Verification

- Tests de signature, idempotence, creation et lecture API.
- Tests des droits de suppression et de la purge a J+7.
- Tests frontend de la liste, du filtre et de l'ouverture du lecteur.
- `pytest`, lint et build Next.js avant deploiement.
