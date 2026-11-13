"""CREST 1.0 API entry point.

The implementation lives in :mod:`crest.product.api`.  This module is kept as
the stable import path used by the desktop launcher and ``uvicorn
crest.api:app``.
"""
from .product.api import app, create_app  # noqa: F401

__all__ = ["app", "create_app"]
