"""v1 minimal build zone allocator.

Assigns each task a deterministic, non-overlapping build area based on a
simple grid layout.  Each zone is a rectangular region identified by
origin coordinates and dimensions.

The allocator uses the task's sequential index (derived from a counter)
to compute a grid position, ensuring tasks don't collide in the same area.
"""
from __future__ import annotations

from dataclasses import dataclass


# Grid parameters — each zone is a 64x64 build area, but allocations are placed
# on a much sparser lattice so repeated builds remain visually separate.
ZONE_SIZE_X = 64
ZONE_SIZE_Z = 64
ZONE_ORIGIN_X = 100
ZONE_ORIGIN_Z = 200
ZONE_PITCH_X = 192
ZONE_PITCH_Z = 192
GRID_COLUMNS = 8  # wrap after 8 sparse columns in X direction

# World-type-aware base Y mapping.
# Each value is the first air layer above the surface in that world type.
WORLD_TYPE_Y = {
    "superflat": -59,   # default superflat grass at Y=-60, first air at -59
    "normal": 64,       # plains grass ~Y=63, first air at 64
}
DEFAULT_WORLD_TYPE = "superflat"


@dataclass
class BuildZone:
    """A rectangular build area in Minecraft world coordinates."""
    origin_x: int
    origin_z: int
    y: int
    size_x: int
    size_z: int
    zone_index: int

    def to_assignment_str(self):
        """Serialize to a compact string for storage in task.zone_assignment."""
        return "zone:%d@%d,%d,%d/%dx%d" % (
            self.zone_index, self.origin_x, self.y, self.origin_z,
            self.size_x, self.size_z,
        )

    @staticmethod
    def from_assignment_str(s):
        """Parse a zone assignment string back to a BuildZone."""
        if not s or not s.startswith("zone:"):
            return None
        try:
            rest = s[5:]  # after "zone:"
            idx_part, coords_part = rest.split("@", 1)
            origin_part, size_part = coords_part.split("/", 1)
            ox, y, oz = origin_part.split(",")
            sx, sz = size_part.split("x")
            return BuildZone(
                origin_x=int(ox), origin_z=int(oz), y=int(y),
                size_x=int(sx), size_z=int(sz), zone_index=int(idx_part),
            )
        except (ValueError, IndexError):
            return None


# Module-level counter remains for isolated tests, but real task creation should
# pass an explicit persisted index from the task repository so allocations stay
# stable across fresh Python processes.
_zone_counter = 0


def zone_y_for_world_type(world_type: str) -> int:
    """Return the base Y-level for a given world type."""
    return WORLD_TYPE_Y.get(world_type, WORLD_TYPE_Y[DEFAULT_WORLD_TYPE])


def build_zone_for_index(index: int, zone_y: int | None = None) -> BuildZone:
    """Build a deterministic zone for a specific sequential index."""
    if zone_y is None:
        zone_y = WORLD_TYPE_Y[DEFAULT_WORLD_TYPE]

    col = index % GRID_COLUMNS
    row = index // GRID_COLUMNS

    origin_x = ZONE_ORIGIN_X + col * ZONE_PITCH_X
    origin_z = ZONE_ORIGIN_Z + row * ZONE_PITCH_Z

    return BuildZone(
        origin_x=origin_x,
        origin_z=origin_z,
        y=zone_y,
        size_x=ZONE_SIZE_X,
        size_z=ZONE_SIZE_Z,
        zone_index=index,
    )


def allocate_zone(index: int | None = None, zone_y: int | None = None):
    """Allocate the next build zone deterministically.

    When *index* is provided, derive the zone directly from that persisted
    sequence number. Otherwise, fall back to the in-process counter for tests.
    """
    global _zone_counter
    if index is None:
        index = _zone_counter
        _zone_counter += 1
    return build_zone_for_index(int(index), zone_y=zone_y)


def reset_zone_counter():
    """Reset the zone counter. For tests."""
    global _zone_counter
    _zone_counter = 0


def preflight_check(zone):
    """Run minimal v1 preflight checks on a zone.

    Returns (ok: bool, issues: list[str]).
    Currently checks:
    - Zone coordinates are within sane world bounds
    - Zone doesn't overlap with the spawn protection area (0,0 ± 16)
    """
    issues = []

    # World bounds check (stay within ±30000 blocks)
    if abs(zone.origin_x) > 29000 or abs(zone.origin_z) > 29000:
        issues.append("zone_out_of_world_bounds")

    # Spawn protection check (avoid 0,0 ± 16)
    if (abs(zone.origin_x) < 16 and abs(zone.origin_z) < 16):
        issues.append("zone_overlaps_spawn")

    return len(issues) == 0, issues
