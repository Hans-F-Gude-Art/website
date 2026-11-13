# frozen_string_literal: true

require 'html-proofer'
require 'uri'

# HTMLProofer check, run by check_links.rb over every page in _site/: each
# `og:image` and `twitter:image` must be an absolute URL on the site's own
# origin that names a file in _site/.
#
# html-proofer's OpenGraph check treats an absolute URL as external, and
# external URLs are not fetched, so a share image pointing at a missing
# file would otherwise pass. head.html writes these URLs with
# `absolute_url`, so they always carry the origin.
class SocialImage < HTMLProofer::Check
  SELECTOR = 'meta[property="og:image"], meta[name="twitter:image"]'

  class << self
    # @param site_url [String] The site origin, such as `https://hfgude.com`.
    # @param site_dir [String] The built site directory.
    def configure(site_url:, site_dir:)
      @origin = %r{\A#{Regexp.escape(site_url.chomp('/'))}(?=/)}
      @site_dir = site_dir
    end

    attr_reader :origin, :site_dir
  end

  def run
    @html.css(SELECTOR).each { |node| check(node) }
  end

  private

  def check(node)
    url = node['content'].to_s.strip
    name = node['property'] || node['name']
    element = create_element(node)
    unless url.match?(self.class.origin)
      return add_failure("#{name} '#{url}' is not an absolute URL on the site's own origin", element: element)
    end

    path = URI::DEFAULT_PARSER.unescape(url.sub(self.class.origin, '').sub(/[?#].*\z/m, ''))
    return if File.file?(File.join(self.class.site_dir, path))

    add_failure("#{name} '#{url}' names no file in #{self.class.site_dir}", element: element)
  end
end
