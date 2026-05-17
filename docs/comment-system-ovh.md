# Systeme de commentaires MDJ en PHP

Cette solution ajoute des commentaires moderes au site Hugo statique
`lemotdujour.fr` sans WordPress. Elle fonctionne avec un hebergement OVH
classique qui fournit PHP et MySQL.

Le principe est celui de solutions de commentaires pour sites statiques comme
Staticman, Isso ou Commento: le blog reste statique, et une petite application
separee recoit, stocke, modere et expose les commentaires.

## Composants

- `php-comments-app/index.php`: API publique pour lister et soumettre les
  commentaires.
- `php-comments-app/admin.php`: page d'administration pour valider les
  commentaires et gerer les regles de filtrage.
- `php-comments-app/install.php`: assistant d'installation a supprimer apres
  usage.
- `php-comments-app/config.sample.php`: modele de configuration MySQL, securite
  et origine autorisee.
- `layouts/partials/mdj-comments.html`: widget Hugo ajoute aux articles.
- `static/js/mdj-comments.js`: chargement, affichage et envoi des commentaires.
- `static/css/mdj-comments.css`: style du widget.
- `hugo.toml`: activation du widget et URL de l'API.

## Fonctionnement

L'application cree deux tables MySQL:

- `mdj_comments`: commentaires, article associe, statut de moderation.
- `mdj_comment_rules`: regles de filtrage.

L'API publique est volontairement minimale:

- `GET /index.php?post_path=/post/.../`: liste les commentaires valides d'un
  article.
- `POST /index.php`: soumet un commentaire, en attente de validation par defaut.

Les visiteurs ne voient que les commentaires `approved`. Les nouveaux
commentaires sont `pending`, sauf si une regle les valide ou si
`auto_approve` est active dans `config.php`.

## Deploiement OVH

### 1. Creer l'espace PHP

1. Creer un sous-domaine dedie, par exemple `comments.lemotdujour.fr`.
2. Le faire pointer vers un dossier web OVH dedie, par exemple
   `www/comments/`.
3. Activer une version PHP recente dans OVH, idealement PHP 8.1 ou plus.
4. Creer ou reutiliser une base MySQL OVH.

### 2. Copier l'application

Copier le contenu du dossier `php-comments-app/` dans le dossier web du
sous-domaine:

```text
www/comments/
├── .htaccess
├── admin.css
├── admin.php
├── config.sample.php
├── index.php
├── install.php
└── lib.php
```

Puis creer `config.php` a partir de `config.sample.php` sur le serveur:

```bash
cp config.sample.php config.php
```

Renseigner:

- `dsn`: hote et nom de la base MySQL OVH;
- `user` et `password`: identifiants MySQL;
- `allowed_origins`: au minimum `https://lemotdujour.fr`;
- `setup_key`: une longue valeur aleatoire temporaire;
- `password_hash`: hash du mot de passe admin.

Si tu n'as pas de ligne de commande PHP locale, `install.php` peut generer le
hash: ouvrir `https://comments.lemotdujour.fr/install.php?key=...`, saisir le
mot de passe, puis copier le hash affiche dans `config.php`.

### 3. Creer les tables

Ouvrir:

```text
https://comments.lemotdujour.fr/install.php?key=VALEUR_DE_SETUP_KEY
```

Cliquer **Creer ou mettre a jour les tables**.

Ensuite, supprimer `install.php` du serveur. C'est important: ce fichier ne doit
servir qu'a l'installation.

### 4. Tester l'administration

Ouvrir:

```text
https://comments.lemotdujour.fr/admin.php
```

Se connecter avec le mot de passe configure. La page permet de:

- valider un commentaire;
- marquer un commentaire comme spam;
- envoyer un commentaire a la corbeille;
- ajouter une regle de filtrage.

### 5. Configurer Hugo

Dans `hugo.toml`, activer le widget et pointer vers l'API PHP:

```toml
[params.comments]
  enabled = true
  endpoint = "https://comments.lemotdujour.fr/index.php"
```

Puis construire le site:

```bash
rtk hugo --minify
```

Deployer ensuite le dossier `public/` avec la methode OVH habituelle du projet
FTP, SFTP ou rsync.

### 6. Tester de bout en bout

1. Ouvrir un article public du site.
2. Envoyer un commentaire de test.
3. Verifier dans `admin.php` qu'il apparait en `pending`.
4. Cliquer **Valider**.
5. Recharger l'article: le commentaire doit etre visible.

Test API optionnel:

```bash
curl "https://comments.lemotdujour.fr/index.php?post_path=/post/2025-05-17/"
```

## Regles de filtrage

Types de regles disponibles:

- `Contient`: cherche un mot ou fragment dans le champ choisi.
- `Expression reguliere`: utile pour motifs plus precis.
- `Domaine e-mail`: cible le domaine apres `@`.
- `Egal a`: correspondance exacte.

Actions disponibles:

- `Rejeter`: le commentaire n'est pas stocke; le visiteur recoit un succes
  generique.
- `Garder en attente`: force la moderation.
- `Valider`: valide automatiquement si la regle correspond.

Regles conseillees au depart:

- rejeter les commentaires contenant `casino`, `crypto`, `viagra`;
- rejeter les domaines e-mail jetables identifies;
- garder en attente les commentaires contenant des mots sensibles propres au
  site.

## Maintenance

- Sauvegarder la base MySQL OVH: les donnees sont dans `mdj_comments` et
  `mdj_comment_rules`.
- Garder `auto_approve` a `false` tant que le volume reste faible.
- Si le domaine public change, ajouter la nouvelle origine dans `config.php`
  avant de redeployer Hugo.
- Pour desactiver les commentaires sans supprimer les donnees, mettre
  `enabled = false` dans `hugo.toml` puis redeployer Hugo.
- Garder `config.php` hors git: il contient les secrets MySQL et le hash admin.

## Limites connues

- Les visiteurs ne peuvent pas modifier ou supprimer eux-memes un commentaire
  apres envoi.
- Aucun e-mail de notification n'est envoye dans cette premiere version.
- L'anti-spam reste simple: honeypot, delai minimal et regles manuelles.
