"""Pytest fixtures. Run from repo root with PYTHONPATH=."""
import sys
from pathlib import Path

# Ensure repo root is on path so backend package is found
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from fastapi.testclient import TestClient

from apps.backend.main import app


def client() -> TestClient:
    return TestClient(app)
