# Gestion locale du blog

Outil web local en Python standard library pour gerer le blog Hugo.

## Lancer

Depuis la racine du depot:

```bash
python3 blog-manager/app.py
```

Sur Windows:

```powershell
py blog-manager\app.py
```

L'application ouvre `http://127.0.0.1:8765/`.

## Fonctions

- Creer un nouvel article Markdown Hugo.
- Ouvrir et modifier un article existant.
- Editer en mode visuel proche d'un traitement de texte avec barre d'outils.
- Basculer en Markdown brut.
- Importer un fichier `.docx` en article Markdown.
- Extraire les images Word vers `static/wp-content/uploads/YYYY/MM`.
- Importer un media dans le format du blog.
- Choisir l'article de premiere page, ou revenir au dernier article par date.
- Lancer `hugo --minify`.
- Voir les changements Git, choisir les fichiers, commit et push.

Les sauvegardes automatiques des articles modifies sont stockees dans
`.blog-manager/backups/`, ignore par Git.

## Limites

L'import Word couvre les usages courants: paragraphes, titres, gras, italique et
images. Les mises en page complexes de Word, tableaux imbriques et styles
specifiques peuvent demander une relecture apres import.
