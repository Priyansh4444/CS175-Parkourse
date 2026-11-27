from random import Random
from unittest import TestCase

from .q_learning import Action, QTable, choose_action, encode, update
from .rewards import MAX_STEPS, Frame, Outcome, Platform

TARGET = Platform(min_x=1, max_x=2, min_z=3, max_z=4, top_y=8)
START: Frame = {"position": (0.5, 8, 2.5), "velocity": (0, 0, 0), "on_ground": True}
AIRBORNE: Frame = {
    "position": (0.75, 8.25, 3),
    "velocity": (0.2, 0.1, 0.3),
    "on_ground": False,
}
LANDED: Frame = {"position": (1.5, 8, 3.5), "velocity": (0, 0, 0), "on_ground": True}


class QLearningTest(TestCase):
    def test_encode_keeps_direction_and_ground_contact(self) -> None:
        self.assertEqual(encode(START, TARGET), (2, 0, 2, 0, 0, 0, True))
        airborne = encode(AIRBORNE, TARGET)
        self.assertEqual(airborne, (1, -1, 1, 2, 1, 3, False))
        self.assertEqual(airborne.target_dy_bin, -1)
        self.assertFalse(airborne.on_ground)
        beyond: Frame = {**START, "position": (2.5, 8, 4.5)}
        self.assertEqual(encode(beyond, TARGET), (-2, 0, -2, 0, 0, 0, True))

    def test_running_transition_bootstraps_and_greedy_choice_does_not_write(
        self,
    ) -> None:
        state = encode(START, TARGET)
        table: QTable = {(encode(AIRBORNE, TARGET), Action.WALK): 10.0}
        result = update(
            table, START, Action.RUN_JUMP, AIRBORNE, TARGET, 1, alpha=0.5, gamma=0.5
        )
        self.assertIs(result, Outcome.RUNNING)
        self.assertEqual(table[(state, Action.RUN_JUMP)], 2.0)
        before = table.copy()
        self.assertEqual(
            choose_action(table, state, epsilon=0, rng=Random(0)), Action.RUN_JUMP
        )
        self.assertEqual(table, before)

    def test_landing_and_timeout_do_not_bootstrap(self) -> None:
        state = encode(START, TARGET)
        table: QTable = {
            (encode(LANDED, TARGET), Action.WALK): 1000.0,
            (encode(AIRBORNE, TARGET), Action.WALK): 1000.0,
        }
        result = update(
            table, START, Action.RUN_JUMP, LANDED, TARGET, 1, alpha=1, gamma=1
        )
        self.assertIs(result, Outcome.LANDED)
        self.assertEqual(table[(state, Action.RUN_JUMP)], 99.0)
        result = update(
            table, START, Action.IDLE, AIRBORNE, TARGET, MAX_STEPS, alpha=1, gamma=1
        )
        self.assertIs(result, Outcome.TIMEOUT)
        self.assertEqual(table[(state, Action.IDLE)], -1.0)
