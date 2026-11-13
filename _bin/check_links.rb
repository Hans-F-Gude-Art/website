#!/usr/bin/env ruby
# frozen_string_literal: true

# Checks the built site in _site/ with html-proofer: internal links,
# images (including alt text), scripts, the favicon, Open Graph tags, and
# the heading outline (heading_outline_check.rb). External links are not
# fetched. Run with `make check-links`.

require 'html-proofer'
require 'yaml'
require_relative 'heading_outline_check'

# The site's own origin (`url` in _config.yml). Absolute links to it, such
# as canonical links, are checked as internal links; every other absolute
# URL is external and not fetched.
SITE_URL = YAML.safe_load_file(File.expand_path('../_config.yml', __dir__)).fetch('url').chomp('/')
OWN_ORIGIN = %r{\A#{Regexp.escape(SITE_URL)}(?=/|\z)}

options = {
  # v5 removed 'disable_external'. We must use ignore_urls to skip them.
  # The ignore runs on the URL as written, before swap_urls, so the site's
  # own origin is excluded here or its links would be skipped too.
  ignore_urls: [
    %r{/livereload.js},
    %r{\Ahttps?://(?!#{Regexp.escape(SITE_URL.sub(%r{\Ahttps?://}, ''))}(?:/|\z))},
  ],

  # Rewrites own-origin URLs to root-relative paths checked against _site/.
  swap_urls: { OWN_ORIGIN => '' },

  # v5 requires explicitly listing checks if you want to limit them.
  # HeadingOutline is this site's own check (heading_outline_check.rb).
  checks: %w[Links Images Scripts Favicon OpenGraph HeadingOutline],

  # Standard Jekyll defaults
  assume_extension: true,
  directory_index_file: 'index.html',

  # A missing alt fails; alt="" is allowed. Grid images inside links that
  # carry a visible title use alt="", so the title alone names the link.

  # Speed up by running in parallel
  parallel: { in_processes: 2 },
}

# HTMLProofer reports its own failures and calls exit(1) itself.
HTMLProofer.check_directory('./_site', options).run
