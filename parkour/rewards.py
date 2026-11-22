"""Reward and episode rules."""

from dataclasses import dataclass
from enum import Enum
from math import hypot
from typing import TypedDict


class Frame(TypedDict):
    """One physics frame from `node src/minecraft.ts` (see src/controls.ts)."""

    position: tuple[float, float, float]  # blocks
    velocity: tuple[float, float, float]  # blocks per tick
    on_ground: bool


@dataclass(frozen=True)
class Platform:
    """Axis-aligned top surface of a target platform, in block coordinates."""

    min_x: float
    max_x: float
    min_z: float
    max_z: float
    top_y: float


class Outcome(Enum):
    RUNNING = "running"
    LANDED = "landed"
    FELL = "fell"
    TIMEOUT = "timeout"


# tune once we see real episodes
LAND_REWARD = 100.0
FALL_REWARD = -100.0
STEP_PENALTY = -1.0
PROGRESS_WEIGHT = 0.0  # set > 0 to reward getting closer to the target
FALL_MARGIN = 1.0  # blocks below the platform top that count as a fall
MAX_STEPS = 50
LAND_TOLERANCE = 0.1  # blocks between feet and platform top that still count


def is_landing(frame: Frame, target: Platform) -> bool:
    """True when the player is standing on the target platform."""
    x, y, z = frame["position"]
    return (
        frame["on_ground"]
        and target.min_x <= x <= target.max_x
        and target.min_z <= z <= target.max_z
        and abs(y - target.top_y) <= LAND_TOLERANCE
    )


def is_fall(frame: Frame, target: Platform) -> bool:
    """True when the player has dropped too far below the target to recover."""
    return frame["position"][1] < target.top_y - FALL_MARGIN


def outcome(frame: Frame, target: Platform, steps: int) -> Outcome:
    """Classify the state after a step; anything but RUNNING ends the episode."""
    if is_landing(frame, target):
        return Outcome.LANDED
    if is_fall(frame, target):
        return Outcome.FELL
    if steps >= MAX_STEPS:
        return Outcome.TIMEOUT
    return Outcome.RUNNING


def distance_to(frame: Frame, target: Platform) -> float:
    """Horizontal distance from the player to the platform's center."""
    x, _, z = frame["position"]
    center_x = (target.min_x + target.max_x) / 2
    center_z = (target.min_z + target.max_z) / 2
    return hypot(x - center_x, z - center_z)


def reward(
    prev: Frame, action: str, next: Frame, target: Platform, steps: int
) -> float:
    """Score one transition (prev --action--> next) toward the target."""
    total = STEP_PENALTY
    result = outcome(next, target, steps)
    if result is Outcome.LANDED:
        total += LAND_REWARD
    elif result is Outcome.FELL:
        total += FALL_REWARD
    total += PROGRESS_WEIGHT * (distance_to(prev, target) - distance_to(next, target))
    return total
