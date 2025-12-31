#!/usr/bin/env python3
"""
Clean Wix-generated HTML by removing unnecessary bloat while preserving display.
"""

from bs4 import BeautifulSoup, Comment
import re
import argparse
import shutil
from pathlib import Path


def clean_html(input_file, output_file=None, aggressive=False):
    """
    Clean HTML file by removing unnecessary Wix bloat.

    Args:
        input_file: Path to input HTML file
        output_file: Path to output file (defaults to input_file with .clean.html suffix)
        aggressive: If True, remove more elements (may affect functionality)
    """
    # Read the HTML file
    with open(input_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')

    # Track what we're removing
    stats = {
        'scripts_removed': 0,
        'comments_removed': 0,
        'wix_ads_removed': 0,
        'attributes_cleaned': 0,
        'bytes_before': len(html_content),
    }

    # 1. Remove Wix ads and branding
    wix_ads = soup.find_all(id='WIX_ADS')
    for ad in wix_ads:
        ad.decompose()
        stats['wix_ads_removed'] += 1

    # 2. Remove analytics and tracking scripts
    scripts_to_remove = []
    for script in soup.find_all('script'):
        script_content = script.string or ''
        data_url = script.get('data-url', '')

        # Remove if it contains tracking/analytics keywords
        if any(keyword in script_content.lower() or keyword in data_url.lower()
               for keyword in ['bi.inline', 'analytics', 'tracking', 'fedops',
                              'browser-deprecation', 'sendbeat']):
            scripts_to_remove.append(script)
            continue

        # Remove polyfills and legacy browser support (aggressive mode)
        if aggressive and any(keyword in script_content.lower() or keyword in data_url.lower()
                             for keyword in ['polyfill', 'legacy', 'core-js',
                                            'nomodule', 'ie=']):
            scripts_to_remove.append(script)

    for script in scripts_to_remove:
        script.decompose()
        stats['scripts_removed'] += 1

    # 3. Remove HTML comments
    comments = soup.find_all(string=lambda text: isinstance(text, Comment))
    for comment in comments:
        # Keep conditional comments for IE (they might be needed)
        if not comment.strip().startswith('[if'):
            comment.extract()
            stats['comments_removed'] += 1

    # 4. Clean up data-* attributes (optional - more aggressive)
    if aggressive:
        # Keep essential data attributes, remove tracking ones
        tracking_data_attrs = [
            'data-testid',
            'data-media-height-override-type',
            'data-media-position-override',
            'data-hook',
            'data-bg-effect-name',
            'data-has-ssr-src',
        ]

        for tag in soup.find_all(True):  # Find all tags
            attrs_to_remove = []
            for attr in tag.attrs:
                if attr.startswith('data-') and attr in tracking_data_attrs:
                    attrs_to_remove.append(attr)

            for attr in attrs_to_remove:
                del tag[attr]
                stats['attributes_cleaned'] += 1

    # 5. Remove empty style tags
    for style in soup.find_all('style'):
        if not style.string or not style.string.strip():
            style.decompose()

    # 6. Remove warmup data and other Wix-specific scripts
    for script in soup.find_all('script', type='application/json'):
        if 'wix-warmup-data' in str(script.get('id', '')):
            script.decompose()
            stats['scripts_removed'] += 1

    for script in soup.find_all('script', type='wix/htmlEmbeds'):
        script.decompose()
        stats['scripts_removed'] += 1

    # 7. Clean up excessive whitespace in the output
    cleaned_html = str(soup)

    # Calculate stats
    stats['bytes_after'] = len(cleaned_html)
    stats['bytes_saved'] = stats['bytes_before'] - stats['bytes_after']
    stats['percent_reduction'] = (stats['bytes_saved'] / stats['bytes_before']) * 100

    # Determine output file
    if output_file is None:
        input_path = Path(input_file)
        output_file = input_path.parent / f"{input_path.stem}.clean{input_path.suffix}"

    # Write cleaned HTML
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(cleaned_html)

    return stats, output_file


def clean_directory(input_dir, output_dir=None, aggressive=False):
    """
    Clean all HTML files in a directory and recreate the directory structure.

    Args:
        input_dir: Path to input directory
        output_dir: Path to output directory (defaults to input_dir with _cleaned suffix)
        aggressive: If True, remove more elements (may affect functionality)
    """
    input_path = Path(input_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Directory '{input_dir}' not found")

    if not input_path.is_dir():
        raise ValueError(f"'{input_dir}' is not a directory")

    # Determine output directory
    if output_dir is None:
        output_path = input_path.parent / f"{input_path.name}_cleaned"
    else:
        output_path = Path(output_dir)

    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)

    # Track aggregate statistics
    total_stats = {
        'files_processed': 0,
        'html_files': 0,
        'other_files': 0,
        'scripts_removed': 0,
        'comments_removed': 0,
        'wix_ads_removed': 0,
        'attributes_cleaned': 0,
        'bytes_before': 0,
        'bytes_after': 0,
    }

    # Find all files in the input directory
    all_files = list(input_path.rglob('*'))

    print(f"Processing directory: {input_path}")
    print(f"Output directory: {output_path}")
    print(f"Found {len([f for f in all_files if f.is_file()])} files")
    print("=" * 70)

    for file_path in all_files:
        if not file_path.is_file():
            continue

        # Calculate relative path from input directory
        rel_path = file_path.relative_to(input_path)
        output_file = output_path / rel_path

        # Create parent directory if needed
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Process HTML files, copy others
        if file_path.suffix.lower() in ['.html', '.htm']:
            try:
                print(f"Cleaning: {rel_path}")
                stats, _ = clean_html(file_path, output_file, aggressive)

                # Update aggregate stats
                total_stats['html_files'] += 1
                total_stats['scripts_removed'] += stats['scripts_removed']
                total_stats['comments_removed'] += stats['comments_removed']
                total_stats['wix_ads_removed'] += stats['wix_ads_removed']
                total_stats['attributes_cleaned'] += stats['attributes_cleaned']
                total_stats['bytes_before'] += stats['bytes_before']
                total_stats['bytes_after'] += stats['bytes_after']

            except Exception as e:
                print(f"  ERROR: {e}")
        else:
            # Copy non-HTML files as-is
            print(f"Copying:  {rel_path}")
            shutil.copy2(file_path, output_file)
            total_stats['other_files'] += 1

        total_stats['files_processed'] += 1

    # Calculate totals
    total_stats['bytes_saved'] = total_stats['bytes_before'] - total_stats['bytes_after']
    if total_stats['bytes_before'] > 0:
        total_stats['percent_reduction'] = (total_stats['bytes_saved'] / total_stats['bytes_before']) * 100
    else:
        total_stats['percent_reduction'] = 0

    return total_stats, output_path


def print_stats(stats, output_file):
    """Print cleaning statistics for a single file."""
    print("HTML Cleaning Complete!")
    print("=" * 50)
    print(f"Scripts removed:        {stats['scripts_removed']}")
    print(f"Comments removed:       {stats['comments_removed']}")
    print(f"Wix ads removed:        {stats['wix_ads_removed']}")
    print(f"Attributes cleaned:     {stats['attributes_cleaned']}")
    print(f"Size before:            {stats['bytes_before']:,} bytes ({stats['bytes_before']/1024:.1f} KB)")
    print(f"Size after:             {stats['bytes_after']:,} bytes ({stats['bytes_after']/1024:.1f} KB)")
    print(f"Bytes saved:            {stats['bytes_saved']:,} bytes ({stats['bytes_saved']/1024:.1f} KB)")
    print(f"Reduction:              {stats['percent_reduction']:.1f}%")
    print("=" * 50)
    print(f"Output saved to: {output_file}")


def print_directory_stats(stats, output_dir):
    """Print cleaning statistics for directory processing."""
    print("\n" + "=" * 70)
    print("DIRECTORY CLEANING COMPLETE!")
    print("=" * 70)
    print(f"Files processed:        {stats['files_processed']}")
    print(f"  - HTML files:         {stats['html_files']}")
    print(f"  - Other files:        {stats['other_files']}")
    print()
    print(f"Scripts removed:        {stats['scripts_removed']}")
    print(f"Comments removed:       {stats['comments_removed']}")
    print(f"Wix ads removed:        {stats['wix_ads_removed']}")
    print(f"Attributes cleaned:     {stats['attributes_cleaned']}")
    print()
    print(f"Total size before:      {stats['bytes_before']:,} bytes ({stats['bytes_before']/1024:.1f} KB)")
    print(f"Total size after:       {stats['bytes_after']:,} bytes ({stats['bytes_after']/1024:.1f} KB)")
    print(f"Bytes saved:            {stats['bytes_saved']:,} bytes ({stats['bytes_saved']/1024:.1f} KB)")
    print(f"Reduction:              {stats['percent_reduction']:.1f}%")
    print("=" * 70)
    print(f"Output directory: {output_dir}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Clean Wix-generated HTML files by removing unnecessary bloat'
    )
    parser.add_argument('input', help='Input HTML file or directory to clean')
    parser.add_argument('-o', '--output',
                       help='Output file/directory (default: input.clean.html or input_cleaned/)')
    parser.add_argument('-a', '--aggressive', action='store_true',
                       help='Aggressive cleaning (removes more, may affect functionality)')

    args = parser.parse_args()

    input_path = Path(args.input)

    try:
        # Check if input is a directory or file
        if input_path.is_dir():
            # Process directory
            stats, output_dir = clean_directory(args.input, args.output, args.aggressive)
            print_directory_stats(stats, output_dir)
        elif input_path.is_file():
            # Process single file
            stats, output_file = clean_html(args.input, args.output, args.aggressive)
            print_stats(stats, output_file)
        else:
            print(f"Error: '{args.input}' is not a valid file or directory")
            return 1

    except FileNotFoundError:
        print(f"Error: '{args.input}' not found")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
