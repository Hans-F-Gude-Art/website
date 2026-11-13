# frozen_string_literal: true

require 'jekyll'

module Jekyll
  module Infrastructure
    # The one reading of a front-matter `image` value, used by
    # ImageDerivatives to list a collection's images.
    #
    # An image is a string path or URL. Any other shape, a hash included,
    # stops the build rather than being stringified into a URL. Alt text is
    # the separate top-level `image_alt` key.
    module FrontMatterImage
      # @param value [String, nil] The raw `image` value.
      # @param source [String, nil] Names the document in error messages.
      # @return [String, nil] The stripped path or URL, or nil when blank.
      # @raise [Jekyll::Errors::FatalException] For any value that is
      #   neither a string nor nil.
      def self.path(value, source: nil)
        return nil if value.nil?

        raise_shape_error(value, source) unless value.is_a?(String)

        stripped = value.strip
        stripped.empty? ? nil : stripped
      end

      # Names a document or page in error messages: its source file, or its
      # URL when it has none.
      # @param item [Jekyll::Document, Jekyll::Page, Jekyll::Drops::Drop, nil]
      # @return [String, nil]
      def self.source_name(item)
        return nil if item.nil?

        file = item.relative_path if item.respond_to?(:relative_path)
        file.to_s.empty? ? item.url : file
      end

      def self.raise_shape_error(value, source)
        where = source ? " in '#{source}'" : ''
        raise Jekyll::Errors::FatalException,
              "Front-matter image#{where} must be a string path or URL, got #{value.inspect}. " \
              'Put alt text in the top-level image_alt key.'
      end
      private_class_method :raise_shape_error
    end
  end
end
