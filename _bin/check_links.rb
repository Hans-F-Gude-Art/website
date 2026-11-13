#!/usr/bin/env ruby
# frozen_string_literal: true

# Checks the built site in _site/ with html-proofer: internal links,
# images (including alt text), scripts, the favicon, Open Graph tags, and
# the heading outline (heading_outline_check.rb). External links are not
# fetched. Run with `make check-links`.

require 'html-proofer'
require_relative 'heading_outline_check'

options = {
  # v5 removed 'disable_external'. We must use ignore_urls to skip them.
  ignore_urls: [
    %r{/livereload.js},
    /^http/, # Regex to ignore all http/https links (external)
  ],

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
