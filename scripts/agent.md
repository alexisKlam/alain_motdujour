# Scripts du blog

Ce dossier contient des scripts Python reutilisables pour maintenir le contenu Hugo importe depuis WordPress.
Lancer les commandes depuis la racine du depot.

## `fix_malformed_article_links.py`

Corrige des liens d'articles mal formes qui sont rendus par Hugo comme des liens locaux morts.

Commande:

```sh
rtk python3 scripts/fix_malformed_article_links.py
```

Controle sans ecriture:

```sh
rtk python3 scripts/fix_malformed_article_links.py --dry-run
```

## `fix_missing_upload_refs.py`

Corrige les references locales vers `/wp-content/uploads` quand un export WordPress pointe vers une image absente ou vers un `srcset` incomplet.
Le script retire les candidats `srcset` inexistants et remplace les variantes redimensionnees par l'original quand il existe.

Commande:

```sh
rtk python3 scripts/fix_missing_upload_refs.py
```

Controle sans ecriture:

```sh
rtk python3 scripts/fix_missing_upload_refs.py --dry-run
```

## `import_missing_live_articles.py`

Compare les articles publies sur `https://lemotdujour.fr` avec les alias locaux Hugo, importe les articles manquants dans `content/post`, telecharge les fichiers references sous `static/wp-content/uploads`, puis genere un rapport dans `reports/missing-live-articles-report.md`.

Ce script utilise le reseau et interroge WordPress via `?rest_route=/wp/v2/posts`.

Commande:

```sh
rtk python3 scripts/import_missing_live_articles.py
```

Controle sans ecriture:

```sh
rtk python3 scripts/import_missing_live_articles.py --dry-run
```

## `relativize_internal_links.py`

Remplace les liens absolus internes `https://lemotdujour.fr/...` par des liens relatifs locaux.
Le script resout aussi certains anciens liens WordPress de type `?p=...`, `?page_id=...`, `?m=...` et `?s=...` a partir du site Hugo genere dans `public/`.

Preparer `public/` avant l'execution:

```sh
rtk hugo --cleanDestinationDir
```

Commande:

```sh
rtk python3 scripts/relativize_internal_links.py
```

Controle sans ecriture:

```sh
rtk python3 scripts/relativize_internal_links.py --dry-run
```

## `rewrite_root_urls_for_pages.py`

Reecrit les URLs generees qui commencent par `/wp-content`, `/post`, `/page`, `/categories`, `/tags`, `/css` ou `/js` pour les rendre compatibles avec une GitHub Page de projet servie sous `/<repo>/`.
Ce script s'execute apres `hugo` et modifie seulement le dossier `public/`, sans toucher au contenu Markdown.

Commande utilisee par la GitHub Action:

```sh
rtk python3 scripts/rewrite_root_urls_for_pages.py public https://alexisklam.github.io/alain_motdujour/
```

Controle sans ecriture:

```sh
rtk python3 scripts/rewrite_root_urls_for_pages.py public https://alexisklam.github.io/alain_motdujour/ --dry-run
```

## `verify_site_links.py`

Verifie les liens et images dans le site Hugo genere.
Par defaut, le script controle les cibles locales et internes dans `public/**/*.html`.

Verification des articles seulement:

```sh
rtk python3 scripts/verify_site_links.py --articles-only
```

Verification avec liens externes HTTP(S):

```sh
rtk python3 scripts/verify_site_links.py --articles-only --check-external
```

## Sequence de verification recommandee

```sh
rtk hugo --cleanDestinationDir --printPathWarnings --printI18nWarnings
rtk python3 scripts/fix_missing_upload_refs.py --dry-run
rtk python3 scripts/fix_malformed_article_links.py --dry-run
rtk python3 scripts/relativize_internal_links.py --dry-run
rtk python3 scripts/rewrite_root_urls_for_pages.py public https://alexisklam.github.io/alain_motdujour/ --dry-run
rtk python3 scripts/verify_site_links.py --articles-only
```
