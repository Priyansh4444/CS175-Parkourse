"""Tabular Q-learning for a jump toward a given platform."""

from math import floor
from random import Random
from typing import Literal

from .rewards import Frame, Outcome, Platform, outcome, reward

Action = Literal["idle", "walk", "run", "walk_jump", "run_jump", "back", "sneak"]
ACTIONS: tuple[Action, ...] = (
    "idle",
    "walk",
    "run",
    "walk_jump",
    "run_jump",
    "back",
    "sneak",
)
State = tuple[int, int, int, int, int, int, bool]
QTable = dict[tuple[State, Action], float]


def encode(frame: Frame, target: Platform) -> State:
    """Bin target-relative position by half a block and velocity by 0.1 blocks per tick."""
    x, y, z = frame["position"]
    vx, vy, vz = frame["velocity"]
    center_x = (target.min_x + target.max_x) / 2
    center_z = (target.min_z + target.max_z) / 2
    return (
        floor((center_x - x) * 2),
        floor((target.top_y - y) * 2),
        floor((center_z - z) * 2),
        floor(vx * 10),
        floor(vy * 10),
        floor(vz * 10),
        frame["on_ground"],
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
    estimate = reward(prev, action, next_frame, target, steps)
    if result is Outcome.RUNNING:
        next_state = encode(next_frame, target)
        estimate += gamma * max(
            table.get((next_state, choice), 0.0) for choice in ACTIONS
        )
    old = table.get(key, 0.0)
    table[key] = old + alpha * (estimate - old)
    return result
