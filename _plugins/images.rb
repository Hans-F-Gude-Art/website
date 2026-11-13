# frozen_string_literal: true

# Entry point for the build-time image pipeline. Jekyll loads every file
# under _plugins/; this file states the load order in one place.
require_relative 'src/infrastructure/image_dimensions_injector'
