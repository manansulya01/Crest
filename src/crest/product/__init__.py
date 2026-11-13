"""CREST 1.0 product layer.

This package contains the installable application around the existing CREST
research engine: persistent task storage, provider adapters, policy
enforcement, planning, verification, the High-Risk Gate, audit, and the
FastAPI service used by the web and desktop clients.

The research runtime in ``crest.agent_runtime`` and the benchmark packages are
not modified by this layer.
"""

__all__ = ["__version__"]

__version__ = "1.0.0"
