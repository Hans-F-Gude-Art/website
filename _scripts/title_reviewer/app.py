#!/usr/bin/env python3
"""
Flask app for reviewing AI-suggested artwork titles.

Usage:
    uv run --with flask --with pyyaml python3 _scripts/title_reviewer/app.py
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, redirect, render_template, request, jsonify, url_for

app = Flask(__name__)

# Paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
ARTWORKS_DIR = PROJECT_ROOT / "_artworks"
STATUS_FILE = PROJECT_ROOT / "_scripts" / "title_review_status.json"
ASSETS_DIR = PROJECT_ROOT / "assets"


def load_status():
    """Load the title review status file."""
    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_status(status):
    """Save the title review status file."""
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)


def get_reviewable_artworks():
    """Get list of artworks that need review (has_suggestion status)."""
    status = load_status()
    reviewable = []
    for filename, data in status["artworks"].items():
        if data.get("status") == "has_suggestion":
            reviewable.append({
                "filename": filename,
                "title": data.get("title", ""),
                "suggested_title": data.get("suggested_title", ""),
            })
    return reviewable


def get_artwork_image_path(filename):
    """Get the image path for an artwork from its markdown file."""
    artwork_file = ARTWORKS_DIR / filename
    if not artwork_file.exists():
        return None

    with open(artwork_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse frontmatter for image field
    match = re.search(r"^image:\s*(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def update_artwork_title(filename, new_title):
    """Update the title in an artwork's frontmatter."""
    artwork_file = ARTWORKS_DIR / filename
    if not artwork_file.exists():
        return False

    with open(artwork_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace title in frontmatter
    # Handle both quoted and unquoted titles
    new_content = re.sub(
        r'^title:\s*["\']?.*["\']?\s*$',
        f'title: "{new_title}"',
        content,
        count=1,
        flags=re.MULTILINE
    )

    # Remove suggested_title if present
    new_content = re.sub(
        r'^suggested_title:\s*.*\n?',
        '',
        new_content,
        flags=re.MULTILINE
    )

    with open(artwork_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True


def mark_completed(filename, final_title):
    """Mark an artwork as completed in the status file."""
    status = load_status()
    if filename in status["artworks"]:
        status["artworks"][filename]["status"] = "completed"
        status["artworks"][filename]["final_title"] = final_title
        status["artworks"][filename]["completed_at"] = datetime.now(timezone.utc).isoformat()

        # Update statistics
        status["statistics"]["has_suggestion"] = max(0, status["statistics"].get("has_suggestion", 0) - 1)
        status["statistics"]["completed"] = status["statistics"].get("completed", 0) + 1

        save_status(status)
        return True
    return False


@app.route("/")
def index():
    """Redirect to first reviewable artwork or completion page."""
    reviewable = get_reviewable_artworks()
    if reviewable:
        return redirect(url_for("review", filename=reviewable[0]["filename"]))
    return redirect(url_for("complete"))


@app.route("/review/<filename>")
def review(filename):
    """Show review interface for a specific artwork."""
    status = load_status()
    artwork_data = status["artworks"].get(filename)

    if not artwork_data or artwork_data.get("status") != "has_suggestion":
        return redirect(url_for("index"))

    # Get all reviewable for navigation
    reviewable = get_reviewable_artworks()
    current_index = next(
        (i for i, a in enumerate(reviewable) if a["filename"] == filename),
        0
    )

    # Get image path
    image_path = get_artwork_image_path(filename)

    # Determine prev/next
    prev_filename = reviewable[current_index - 1]["filename"] if current_index > 0 else None
    next_filename = reviewable[current_index + 1]["filename"] if current_index < len(reviewable) - 1 else None

    return render_template(
        "review.html",
        filename=filename,
        current_title=artwork_data.get("title", ""),
        suggested_title=artwork_data.get("suggested_title", ""),
        image_path=image_path,
        current_index=current_index + 1,
        total_count=len(reviewable),
        prev_filename=prev_filename,
        next_filename=next_filename,
    )


@app.route("/approve", methods=["POST"])
def approve():
    """Approve and save a title."""
    filename = request.form.get("filename")
    final_title = request.form.get("title", "").strip()

    if not filename or not final_title:
        return redirect(url_for("index"))

    # Update the artwork file
    update_artwork_title(filename, final_title)

    # Mark as completed in status
    mark_completed(filename, final_title)

    # Redirect to next reviewable or completion
    reviewable = get_reviewable_artworks()
    if reviewable:
        return redirect(url_for("review", filename=reviewable[0]["filename"]))
    return redirect(url_for("complete"))


@app.route("/skip", methods=["POST"])
def skip():
    """Skip to the next artwork."""
    filename = request.form.get("filename")

    reviewable = get_reviewable_artworks()
    current_index = next(
        (i for i, a in enumerate(reviewable) if a["filename"] == filename),
        -1
    )

    # Go to next, or wrap to first
    if current_index >= 0 and current_index < len(reviewable) - 1:
        next_filename = reviewable[current_index + 1]["filename"]
    elif reviewable:
        next_filename = reviewable[0]["filename"]
    else:
        return redirect(url_for("complete"))

    return redirect(url_for("review", filename=next_filename))


@app.route("/back", methods=["POST"])
def back():
    """Go back to previous artwork."""
    filename = request.form.get("filename")

    reviewable = get_reviewable_artworks()
    current_index = next(
        (i for i, a in enumerate(reviewable) if a["filename"] == filename),
        0
    )

    # Go to previous, or stay at first
    if current_index > 0:
        prev_filename = reviewable[current_index - 1]["filename"]
        return redirect(url_for("review", filename=prev_filename))

    return redirect(url_for("review", filename=filename))


@app.route("/status")
def status():
    """Return JSON progress status."""
    status_data = load_status()
    reviewable = get_reviewable_artworks()

    return jsonify({
        "total": status_data["statistics"]["total"],
        "needs_review": status_data["statistics"]["needs_review"],
        "has_suggestion": status_data["statistics"]["has_suggestion"],
        "completed": status_data["statistics"]["completed"],
        "good": status_data["statistics"]["good"],
        "remaining": len(reviewable),
    })


@app.route("/complete")
def complete():
    """Show completion page."""
    status_data = load_status()
    return render_template(
        "complete.html",
        completed=status_data["statistics"]["completed"],
        total=status_data["statistics"]["total"],
    )


@app.route("/assets/<path:filepath>")
def serve_asset(filepath):
    """Serve asset files (images)."""
    from flask import send_from_directory
    return send_from_directory(ASSETS_DIR, filepath)


if __name__ == "__main__":
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Artworks dir: {ARTWORKS_DIR}")
    print(f"Status file: {STATUS_FILE}")
    print()
    print("Starting title reviewer at http://localhost:5000")
    app.run(debug=True, port=5000)
