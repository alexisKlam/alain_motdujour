# Le mot du jour d'Alain - Hugo Blog

Blog quotidien de citations, réflexions et pensées d'Alain.

## Prerequisites

- [Hugo](https://gohugo.io/installation/) (Extended version recommended)
- Git (for theme management)

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd BlogAlain
```

2. The Ananke theme is already configured in the `themes/` directory.

## Running the Blog

### Development Server

Start the Hugo development server with live reload:

```bash
hugo server
```

The site will be available at `http://localhost:1313/`

### Development Server with Drafts

To include draft posts:

```bash
hugo server -D
```

### Development Server with Detailed Output

For debugging purposes, use verbose mode:

```bash
hugo server --verbose
```

### Development Server - Bind to All Interfaces

To access the server from other devices on your network:

```bash
hugo server --bind 0.0.0.0
```

## Building for Production

Generate static files for deployment:

```bash
hugo
```

The generated site will be in the `public/` directory.

### Build with Minification

For optimized production builds:

```bash
hugo --minify
```

## Debugging

### Check Hugo Version

```bash
hugo version
```

### Verify Configuration

Display the site configuration:

```bash
hugo config
```

### List All Content

Show all content files:

```bash
hugo list all
```

### Check for Broken Links

```bash
hugo --logLevel info
```

### Enable Debug Logging

```bash
hugo server --logLevel debug
```

### Template Debugging

When debugging templates, add this to your templates:

```go
{{ printf "%#v" . }}
```

### Common Issues

1. **Port Already in Use**: Change the port with `hugo server -p 1314`
2. **Theme Not Found**: Ensure the theme exists in `themes/ananke/`
3. **Content Not Showing**: Check front matter and publication dates
4. **Images Not Loading**: Verify paths in `static/` or `content/` directories

## Project Structure

```
BlogAlain/
├── archetypes/       # Content templates
├── content/          # Blog posts and pages
│   ├── page/         # Static pages
│   └── post/         # Blog posts
├── data/             # Data files (months.json)
├── layouts/          # Custom templates
├── static/           # Static assets (images, etc.)
├── themes/           # Hugo themes
│   ├── ananke/       # Main theme
│   └── motdujour/    # Custom theme
├── public/           # Generated site (git ignored)
└── hugo.toml         # Site configuration
```

## Creating New Content

Create a new post:

```bash
hugo new post/YYYY-MM-DD.md
```

The post will be created in `content/post/` with the default archetype.

## Utility Scripts

This project includes several bash scripts for maintenance:

- `cleanup-posts.sh` - Post cleanup utilities
- `fix-urls.sh` - Fix URL references
- `remove-thumbnails.sh` - Remove thumbnail images

## Configuration

Main configuration file: `hugo.toml`

Key settings:
- **baseURL**: `https://lemotdujour.fr/`
- **languageCode**: `fr`
- **theme**: `ananke`
- **Pagination**: 10 posts per page

## Deployment

### Manual Deployment

1. Build the site: `hugo --minify`
2. Deploy the `public/` directory to your web server
3. Ensure your web server is configured to serve the site from the `public/` directory

### Automated Deployment with GitHub Actions

This project includes three GitHub Actions workflows for automatic deployment to OVH:

#### Option 1: FTP/FTPS Deployment (`.github/workflows/deploy.yml`)
Uses FTP-Deploy-Action for FTPS deployment.

**Required GitHub Secrets:**
- `OVH_FTP_SERVER` - Your OVH FTP server (e.g., `ftp.cluster000.hosting.ovh.net`)
- `OVH_FTP_USERNAME` - Your FTP username
- `OVH_FTP_PASSWORD` - Your FTP password

#### Option 2: SFTP Deployment (`.github/workflows/deploy-sftp.yml`)
Uses SFTP-Deploy-Action for SSH-based deployment.

**Required GitHub Secrets:**
- `OVH_SFTP_HOST` - Your OVH SSH/SFTP host
- `OVH_SFTP_USERNAME` - Your SSH username
- `OVH_SSH_PRIVATE_KEY` - Your SSH private key (entire key content)

#### Option 3: Rsync Deployment (`.github/workflows/deploy-rsync.yml`)
Uses rsync for efficient, incremental deployments.

**Required GitHub Secrets:**
- `OVH_SSH_HOST` - Your OVH SSH host
- `OVH_SSH_USERNAME` - Your SSH username
- `OVH_SSH_PRIVATE_KEY` - Your SSH private key (entire key content)

#### Setting Up GitHub Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each required secret based on your chosen deployment method

#### Choosing a Deployment Method

- **FTP/FTPS**: Best for basic OVH hosting plans with FTP access
- **SFTP**: Recommended if you have SSH access and want secure file transfer
- **Rsync**: Most efficient for large sites (only transfers changed files)

**Note:** Keep only the workflow file you plan to use and delete the others to avoid confusion.

#### Deployment Trigger

The workflows are triggered on:
- Every push to the `main` branch
- Manual trigger via GitHub Actions tab (workflow_dispatch)

The site will be deployed to the `/newBlog/` folder on your OVH server.

## Resources

- [Hugo Documentation](https://gohugo.io/documentation/)
- [Ananke Theme Documentation](https://github.com/theNewDynamic/gohugo-theme-ananke)
- [Hugo Community Forum](https://discourse.gohugo.io/)

## License

See LICENSE file for details.
