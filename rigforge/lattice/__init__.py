"""
RIG Lattice — lattice router, archetypes, and 3-D cell mesh.
"""
from __future__ import annotations

from rigforge.lattice.router import LatticeRouter, RouteResult
from rigforge.triple_diamond import (
    CHIEF_BLOCK,
    LATTICE,
    Cell,
    Diamond,
    LatticeConfig,
    Level,
    Mode,
    Step,
    i1,
    l3d2a4,
    parse_cell_id,
)

__all__ = [
    "CHIEF_BLOCK",
    "LATTICE",
    "Cell",
    "Diamond",
    "LatticeConfig",
    "LatticeRouter",
    "Level",
    "Mode",
    "RouteResult",
    "Step",
    "i1",
    "l3d2a4",
    "parse_cell_id",
]