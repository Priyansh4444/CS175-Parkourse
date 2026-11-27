"""Tabular Q-learning for a jump toward a given platform."""

from enum import StrEnum, auto
from math import floor
from random import Random
from typing import NamedTuple

from .rewards import Frame, Outcome, Platform, outcome, reward


class Action(StrEnum):
    """Movement commands sent to the Minecraft controller."""

    IDLE = auto()
    WALK = auto()
    RUN = auto()
    WALK_JUMP = auto()
    RUN_JUMP = auto()
    BACK = auto()
    SNEAK = auto()


ACTIONS = tuple(Action)
POSITION_BINS_PER_BLOCK = 2
VELOCITY_BINS_PER_BLOCK_PER_TICK = 10


class State(NamedTuple):
    """Discretized target offset, player velocity, and ground contact."""

    target_dx_bin: int
    """X offset from player to target in half-block bins."""
    target_dy_bin: int
    """Vertical offset from the player's feet to the target surface in half-block bins."""
    target_dz_bin: int
    """Z offset from player to target in half-block bins."""
    vx_bin: int
    """Player X velocity in bins of 0.1 blocks per tick."""
    vy_bin: int
    """Player Y velocity in bins of 0.1 blocks per tick."""
    vz_bin: int
    """Player Z velocity in bins of 0.1 blocks per tick."""
    on_ground: bool
    """Whether the player is touching the ground."""


QTable = dict[tuple[State, Action], float]


def encode(frame: Frame, target: Platform) -> State:
    """Bin target-relative position by half a block and velocity by 0.1 blocks per tick."""
    x, y, z = frame["position"]
    vx, vy, vz = frame["velocity"]
    center_x = (target.min_x + target.max_x) / 2
    center_z = (target.min_z + target.max_z) / 2
    return State(
        target_dx_bin=floor((center_x - x) * POSITION_BINS_PER_BLOCK),
        target_dy_bin=floor((target.top_y - y) * POSITION_BINS_PER_BLOCK),
        target_dz_bin=floor((center_z - z) * POSITION_BINS_PER_BLOCK),
        vx_bin=floor(vx * VELOCITY_BINS_PER_BLOCK_PER_TICK),
        vy_bin=floor(vy * VELOCITY_BINS_PER_BLOCK_PER_TICK),
        vz_bin=floor(vz * VELOCITY_BINS_PER_BLOCK_PER_TICK),
        on_ground=frame["on_ground"],
    )


def choose_action(
    table: QTable, state: State, *, epsilon: float, rng: Random
) -> Action:
    """Choose randomly when exploring or when several actions share the highest value."""
    if not 0 <= epsilon <= 1:
        raise ValueError("epsilon must be between 0 and 1")
    if rng.random() < epsilon:
        return rng.choice(ACTIONS)
    best = max(table.get((state, action), 0.0) for action in ACTIONS)
    return rng.choice(
        [action for action in ACTIONS if table.get((state, action), 0.0) == best]
    )


def update(
    table: QTable,
    prev: Frame,
    action: Action,
    next_frame: Frame,
    target: Platform,
    steps: int,
    *,
    alpha: float,
    gamma: float,
) -> Outcome:
    """Update one state-action value using the existing reward and episode rules."""
    if not 0 < alpha <= 1 or not 0 <= gamma <= 1:
        raise ValueError("alpha must be in (0, 1] and gamma in [0, 1]")
    key = encode(prev, target), action
    result = outcome(next_frame, target, steps)
    target_value = reward(prev, next_frame, target, steps)
    # Future actions contribute value only while this episode is still running.
    if result is Outcome.RUNNING:
        next_state = encode(next_frame, target)
        best_next_value = max(
            table.get((next_state, choice), 0.0) for choice in ACTIONS
        )
        target_value += gamma * best_next_value
    old = table.get(key, 0.0)
    table[key] = old + alpha * (target_value - old)
    return result
