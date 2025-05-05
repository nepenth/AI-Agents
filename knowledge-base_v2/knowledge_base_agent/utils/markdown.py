import logging
from typing import Optional, List, Dict

import bleach
import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.tables import TableExtension

logger = logging.getLogger(__name__)

# Configure allowed tags and attributes for bleach sanitization
# Customize this based on exactly what HTML you want to allow from Markdown
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'a', 'blockquote',
    'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'img', # Allow images if needed
    'div', 'span', # Needed for code highlighting wrappers
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title'],
    '*': ['class'], # Allow 'class' attribute needed by codehilite
}

# Initialize markdown converter with extensions
# Ensure Pygments is installed for codehilite to work correctly
md_converter = markdown.Markdown(
    extensions=[
        FencedCodeExtension(),
        TableExtension(),
        CodeHiliteExtension(guess_lang=True, css_class='highlight', use_pygments=True),
        'markdown.extensions.nl2br', # Convert newlines to <br>
        'markdown.extensions.extra', # Includes things like abbr, footnotes, etc.
    ],
    output_format='html5' # Use HTML5 output format
)


def render_markdown(text: Optional[str]) -> str:
    """
    Converts Markdown text to sanitized HTML.

    Args:
        text: The Markdown text to convert.

    Returns:
        Sanitized HTML string. Returns an empty string if input is None or empty.
    """
    if not text:
        return ""

    logger.debug("Rendering markdown text...")
    try:
        # Convert Markdown to HTML
        html = md_converter.convert(text)

        # Sanitize the generated HTML
        # Note: If using code highlighting, ensure bleach allows the necessary
        # '<span>' and '<div>' tags with 'class' attributes.
        sanitized_html = bleach.clean(
            html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            strip=True # Remove disallowed tags instead of escaping them
        )
        logger.debug("Markdown rendering and sanitization complete.")
        return sanitized_html
    except Exception as e:
        logger.error(f"Error rendering or sanitizing markdown: {e}", exc_info=True)
        # Return a safe value in case of error
        return f"<p>Error rendering content: {e}</p>"
    finally:
         # Reset the markdown converter state if necessary (important if reusing instance)
         md_converter.reset()
