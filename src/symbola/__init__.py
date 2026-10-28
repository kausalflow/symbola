"""Symbola: trustable contracts between agents."""

__version__ = "0.2.0"

# Sent on every request: Cloudflare, in front of symbola.sh, refuses Python's default "Python-urllib/3.x".
USER_AGENT = f"symbola/{__version__} (+https://symbola.sh)"
