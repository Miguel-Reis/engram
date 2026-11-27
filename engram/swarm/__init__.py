"""Swarm orchestration, AST symbol lookup, CoW sandboxes, Office 3D, and Model Router."""

from __future__ import annotations

__all__ = ["get_swarm_engine", "get_runtime_profile"]


def get_swarm_engine(db=None):
    from db_engine import BrainDB
    from swarm_engine import SwarmEngine

    return SwarmEngine(db or BrainDB())


def get_runtime_profile(**kwargs):
    from runtime_detector import detect_runtime_profile

    return detect_runtime_profile(**kwargs)
