"""Orbit Agent OS facade (Vault, Self-Learn, Prompt Forge, DOTS Tasks, Intake & Rules)."""

from __future__ import annotations

__all__ = ["get_orbit_engine"]


def get_orbit_engine(db=None):
    from db_engine import BrainDB
    from orbit_engine import OrbitEngine

    return OrbitEngine(db or BrainDB())
