# Outil local de gestion du blog

Ce projet contient un outil web local pour gerer le blog Hugo sans installer de
CMS. Il fonctionne avec Python uniquement et vise macOS et Windows.

## Demarrage

macOS:

```bash
python3 blog-manager/app.py
```

Windows:

```powershell
py blog-manager\app.py
```

Le navigateur s'ouvre sur:

```text
http://127.0.0.1:8765/
```

Pour choisir un autre port:

```bash
python3 blog-manager/app.py --port 8780
```

## Workflow conseille

1. Lancer l'outil.
2. Choisir un article dans la colonne gauche, ou cliquer **Nouvel article**.
3. Modifier le titre, la date, les categories et les tags.
4. Ecrire dans l'editeur visuel, ou basculer en **Markdown brut**.
5. Importer les medias necessaires.
6. Cliquer **Enregistrer**.
7. Cliquer **Build Hugo**.
8. Ouvrir **Git**, cocher les fichiers a publier, saisir un message, puis
   lancer le commit/push.

## Import Word

Le bouton **Word vers article** accepte un fichier `.docx`.

L'import:

- cree un article Markdown dans `content/post/`;
- reprend les paragraphes, titres simples, gras, italique;
- extrait les images vers `static/wp-content/uploads/YYYY/MM`;
- insere les images importees dans le Markdown.

Apres import, relire l'article dans l'editeur: Word peut contenir des styles et
mises en page qui ne correspondent pas directement a Markdown.

## Premiere page

Par defaut, la page d'accueil affiche le dernier article par date.

L'outil peut aussi forcer un article precis avec **Mettre en premiere page**.
Cette action ecrit `data/frontpage.json`. Pour revenir au comportement normal,
cliquer **Premiere page = dernier article**.

Le template Hugo `layouts/index.html` lit ce fichier si present, sinon garde le
comportement historique.

## GitHub

Le panneau **Git** affiche les changements detectes par `git status`. Les
fichiers sont cochables pour eviter de committer des changements non voulus.

Le bouton de commit lance:

```bash
git add -- <fichiers coches>
git commit -m "<message>"
git push
```

Le push est optionnel via la case a cocher.

## Sauvegardes

Avant d'ecraser un article existant, l'outil copie l'ancienne version dans:

```text
.blog-manager/backups/
```

Ce dossier est ignore par Git.
