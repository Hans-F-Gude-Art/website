# hfgudeart.com

Jekyll site for hfgudeart.

## Prerequisites

- Docker
- Make
- Git

## Getting Started

1. Clone the repository
2. Build the Docker image: `make image-build`
3. Generate Gemfile.lock: `make deps-lock`
4. Start development server: `make serve`
5. Visit http://localhost:4000

## Available Commands

- `make serve` - Start development server
- `make build` - Build for production
- `make clean` - Clean build artifacts
- `make debug` - Interactive bash session in container
- `make serve-drafts` - Serve with draft posts
- `make image-rebuild` - Rebuild Docker image without cache

## Deployment

Push to main branch to trigger automatic deployment to GitHub Pages via GitHub Actions.
