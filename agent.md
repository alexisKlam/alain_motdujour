# Agent Notes: BlogAlain

## Project Overview

This repository is the Hugo rebuild of the WordPress site
[`lemotdujour.fr`](https://lemotdujour.fr/), "Le mot du jour d'Alain".

The site is a French personal blog built around daily "mot du jour" posts:
quotations, reflections, cultural notes, literature, history, politics, and
personal essays. The Hugo version should preserve the spirit, URLs, archives,
tags, images, and reading experience of the original WordPress site while
moving the site to static generation.

Current Hugo basics:

- Main config: `hugo.toml`
- Base URL: `https://lemotdujour.fr/`
- Language: French (`fr`)
- Title: `Le mot du jour d'Alain`
- Tagline: `« Le contraire du savoir ce n'est pas l'ignorance mais les certitudes ! »`
- Active theme in config: `ananke`
- Custom local theme also present: `themes/motdujour/`
- Main content: `content/post/`
- Static migrated WordPress assets: `static/wp-content/uploads/`
- Custom templates: `layouts/` and `themes/motdujour/layouts/`
- Production output: `public/` (generated, do not edit by hand)

## Migration Goals

- Keep imported WordPress content readable and faithful to the original site.
- Preserve existing public URLs where possible, especially posts, pages, tags,
  archives, and uploaded media paths.
- Maintain French typography and accents. Do not ASCII-fold French content.
- Treat `static/wp-content/uploads/` as migrated source assets. Rename or move
  media only when references are updated and verified.
- Prefer small, reversible Hugo/template changes over broad rewrites.
- Keep the site simple, fast, and static; avoid adding client-side complexity
  unless there is a clear need.

## Common Commands

Always prefix shell commands with `rtk` when possible:

```bash
rtk hugo server
rtk hugo server -D
rtk hugo --minify
rtk hugo config
rtk hugo list all
rtk git status --short
```

If `rtk` cannot proxy a command shape, use the smallest direct command or
`rtk proxy <cmd>`.

## Superpowers Docs

- Never commit Superpowers-generated spec or plan documents by default.
- Files created under `docs/superpowers/specs/` or `docs/superpowers/plans/` must remain uncommitted unless explicitly requested.

## Git Preferences

- When integrating completed work back to `master` or another base branch locally, prefer rebase or fast-forward over merge commits so history stays linear and clean.

## Editing Guidance

- Do not edit generated `public/` files directly.
- Keep front matter valid for Hugo and compatible with existing taxonomies
  (`categories`, `tags`).
- Use existing layout and theme patterns before introducing new abstractions.
- When changing templates or CSS, run a Hugo build and inspect the affected
  page type if possible.
- Be careful with the current working tree: this repo may contain unrelated
  migration edits or imported assets. Do not revert user changes unless asked.
