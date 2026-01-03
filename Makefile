# Makefile
IMAGE := jekyll-image-hfgudeart
MOUNT := /workspace

# Define Ruby version by reading .ruby-version file, ignoring comments/whitespace
RUBY_VERSION := $(shell grep -v '^\#' .ruby-version)

# Define Bundler version directly in the Makefile
BUNDLER_VERSION := 2.6.8

# Define base image using the determined Ruby version
BASE_RUBY_IMAGE := ruby:$(RUBY_VERSION)

# Get the current user's UID and GID to run Docker commands as the host user.
# This prevents Docker from creating files (e.g., _site, coverage) as root.
# We also set HOME=/tmp to give the user a writable home directory inside the
# container, which prevents certain permission errors with Jekyll and Bundler.
USER_ID := $(shell id -u)
GROUP_ID := $(shell id -g)
DOCKER_RUN_OPTS := --user $(USER_ID):$(GROUP_ID) -e HOME=/tmp

# Define reusable Docker run command to reduce boilerplate
DOCKER_RUN := docker run --rm $(DOCKER_RUN_OPTS) -v $(PWD):$(MOUNT) -w $(MOUNT) $(IMAGE)

# Tier 1: Daily drivers
.PHONY: serve build clean debug

# Tier 2: Command variants
.PHONY: serve-drafts serve-profile

# Tier 3: Domain operations
.PHONY: image-build image-rebuild deps-lock validate

# Internal targets
.PHONY: all

# Tier 4: Backward compatibility aliases
.PHONY: image refresh lock drafts profile

all: serve

# Install pre-commit hook if it doesn't exist (symlinks version-controlled script)
.git/hooks/pre-commit: _scripts/pre-commit-hook.sh
	@echo "Installing pre-commit hook..."
	@ln -sf ../../_scripts/pre-commit-hook.sh $@
	@echo "Pre-commit hook installed."

# Run gallery validation manually
validate:
	@python3 _scripts/validate_galleries.py

# Manual target to update Gemfile.lock using the correct base Docker image and Bundler version.
# Uses 'bundle lock --update --normalize-platforms' to regenerate the lockfile.
deps-lock: .ruby-version # Dependency on .ruby-version
	@echo "Updating and normalizing Gemfile.lock using Docker ($(BASE_RUBY_IMAGE) with Bundler $(BUNDLER_VERSION))..."
	@echo "Running 'bundle lock --update --normalize-platforms' inside container..."
	@docker run --rm \
		$(DOCKER_RUN_OPTS) \
		-v $(PWD):$(MOUNT) \
		-w $(MOUNT) \
		$(BASE_RUBY_IMAGE) \
		/bin/bash -c "echo 'Installing Bundler $(BUNDLER_VERSION)...' && \
		              gem install bundler -v $(BUNDLER_VERSION) --no-document && \
		              echo 'Running bundle lock --update --normalize-platforms...' && \
		              bundle lock --update --normalize-platforms"
	@echo "Gemfile.lock updated and normalized successfully. Please commit Gemfile, Gemfile.lock, and .ruby-version."

# Build the Docker image using '.' as build context.
# Pass the Ruby and Bundler versions as build arguments.
image-build: Dockerfile Gemfile Gemfile.lock .ruby-version
	@echo "Building Docker image $(IMAGE) using Ruby $(RUBY_VERSION) and Bundler $(BUNDLER_VERSION)..."
	@if [ ! -f .dockerignore ]; then \
		echo "Warning: .dockerignore file not found. Build context might be large or include unwanted files."; \
	fi
	@docker build \
	    --build-arg RUBY_VERSION=$(RUBY_VERSION) \
	    --build-arg BUNDLER_VERSION=$(BUNDLER_VERSION) \
	    . -f Dockerfile -t $(IMAGE)

# Rebuild the Docker image without cache.
image-rebuild: Dockerfile Gemfile Gemfile.lock .ruby-version
	@echo "Rebuilding Docker image $(IMAGE) with --no-cache using Ruby $(RUBY_VERSION) and Bundler $(BUNDLER_VERSION)..."
	@if [ ! -f .dockerignore ]; then \
		echo "Warning: .dockerignore file not found. Build context might be large or include unwanted files."; \
	fi
	@docker build \
	    --build-arg RUBY_VERSION=$(RUBY_VERSION) \
	    --build-arg BUNDLER_VERSION=$(BUNDLER_VERSION) \
	    --no-cache . -f Dockerfile -t $(IMAGE)

# Clean out _site and other caches. Requires the image to exist.
clean: image-build
	@echo "Cleaning Jekyll build artifacts..."
	@$(DOCKER_RUN) bundle exec jekyll clean

# Build the site for production. Depends on image-build and clean.
build: .git/hooks/pre-commit image-build clean
	@echo "Building site for production..."
	@docker run --rm $(DOCKER_RUN_OPTS) -v $(PWD):$(MOUNT) -w $(MOUNT) -e JEKYLL_ENV=production $(IMAGE) bundle exec jekyll build

# Profile the site build. Depends on image-build and clean.
serve-profile: image-build clean
	@echo "Profiling Jekyll build..."
	@echo "Output will be in '_site' and Liquid profiles in '_profile/'."
	@$(DOCKER_RUN) bundle exec jekyll build --profile

# Serves the site for local development, with live reloading.
# This target contains the solution to the '0.0.0.0' URL issue in browsers.
serve: .git/hooks/pre-commit image-build clean
	@echo "Serving site at http://localhost:4000..."
	@docker run --rm $(DOCKER_RUN_OPTS) -v $(PWD):$(MOUNT) -w $(MOUNT) -p 4000:4000 -p 35729:35729 -e JEKYLL_ENV=docker $(IMAGE) \
		bundle exec jekyll serve --config _config.yml,_config_docker.yml --watch --incremental --livereload
#
# WHY THIS COMMAND IS STRUCTURED THIS WAY:
#
# We DO NOT set `--host 0.0.0.0` here on the command line. The reason is
# critical: the `--host` flag has the highest precedence and forces Jekyll to
# automatically set `site.url` to "http://0.0.0.0:4000", which completely
# ignores any `url` setting from our config files. Modern browsers block
# 0.0.0.0 for security, and so this would prevent local builds from rendering
# correctly.
#
# Instead, we delegate all configuration to the files loaded via `--config`.
# The `_config_docker.yml` file is responsible for two things:
#   1. `host: 0.0.0.0`: Makes the server accessible to Docker.
#   2. `url: ""`:       Generates browser-friendly relative links.
#
# The `-e JEKYLL_ENV=docker` flag helps ensure this file-based configuration is
# properly loaded and respected by the Jekyll `serve` command.

# Serve the site with drafts. Depends on image-build and clean.
# Uses same logic to avoid 0.0.0.0 bug as serve
serve-drafts: image-build clean
	@echo "Serving site with drafts at http://localhost:4000..."
	@docker run --rm $(DOCKER_RUN_OPTS) -v $(PWD):$(MOUNT) -w $(MOUNT) -p 4000:4000 -p 35729:35729 -e JEKYLL_ENV=docker $(IMAGE) \
		bundle exec jekyll serve --config _config.yml,_config_docker.yml --drafts --future --watch --incremental --livereload

# Interactive session within the image. Depends on image-build existing.
debug: image-build
	@echo "Starting interactive debug session in container..."
	@docker run -it $(DOCKER_RUN_OPTS) -p 4000:4000 -v $(PWD):$(MOUNT) -w $(MOUNT) $(IMAGE) /bin/bash

# --- Tier 4: Backward Compatibility Aliases ---
# These aliases maintain backward compatibility for muscle memory.
# All aliases point to the new hybrid-named targets.

image: image-build
refresh: image-rebuild
lock: deps-lock
drafts: serve-drafts
profile: serve-profile
