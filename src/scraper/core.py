"""Compatibility facade for the pre-refactor ``core`` module.

This module keeps the old import surface alive while the implementation lives
in smaller modules such as ``pipeline``, ``sheets``, ``scraping`` and
``html_export``.
"""

try:
    from .html_export import *  # noqa: F401,F403
    from .pipeline import *  # noqa: F401,F403
    from .scraping import *  # noqa: F401,F403
    from .sheets import *  # noqa: F401,F403
except ImportError:
    from html_export import *  # noqa: F401,F403
    from pipeline import *  # noqa: F401,F403
    from scraping import *  # noqa: F401,F403
    from sheets import *  # noqa: F401,F403

