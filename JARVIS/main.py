"""ASGI entrypoint for `uvicorn main:app` from the project directory."""

from jarvis.api import app

__all__ = ["app"]
