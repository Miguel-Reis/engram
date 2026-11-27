"""Web Studio OS routing and zero-build static asset serving."""

from engram.web.router import RouteRegistry
from engram.web.static_assets import resolve_static_asset

__all__ = ["RouteRegistry", "resolve_static_asset"]
