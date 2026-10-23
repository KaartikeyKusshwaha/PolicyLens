"""Thin clients; all permissions, budgets and evidence verification stay server-side."""

from .client import PolicyLens, PolicyLensError

__all__ = ["PolicyLens", "PolicyLensError"]
