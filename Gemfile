# frozen_string_literal: true

# Gemfile
source 'https://rubygems.org'

# Specify Jekyll version 4.x
gem 'jekyll', '~> 4.3'

# Required for `jekyll serve` in Ruby 3+
gem 'webrick', '~> 1.9'

# Required by Jekyll/deps, will be default gem later
gem 'logger', '~> 1.7'

# SEO
gem 'jekyll-sitemap', '~> 1.4'

# For reading SVG image sizes in custom plugins
gem 'nokogiri', '~> 1.19'

# Raster image sizes (and EXIF orientation) for <img> width/height
gem 'fastimage', '~> 2.4'

# Built-site checks (`make check-links`)
group :development, :test do
  gem 'html-proofer', '~> 5.2'
end
