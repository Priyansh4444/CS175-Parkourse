import json
from io import StringIO
from random import Random
from unittest import TestCase

from .courses import COURSES
from .q_learning import QTable
from .rewards import Frame, Outcome
from .train import train_episode


class TrainTest(TestCase):
    def test_map_reset_and_first_tick_landing(self) -> None:
        course = COURSES["1"]
        start: Frame = {
            "position": course.start,
            "velocity": (0, 0, 0),
            "on_ground": True,
        }
        landing: Frame = {**start, "position": (19.5, -6, 13.5)}
        fall: Frame = {**start, "position": (19.5, -8, 14.5), "on_ground": False}
        requests = StringIO()
        replies = StringIO(
            json.dumps({"result": start})
            + "\n"
            + json.dumps({"result": [landing, fall]})
            + "\n"
        )
        table: QTable = {}

        self.assertEqual(
            train_episode(requests, replies, course, table, 0.5, Random(17)),
            (Outcome.LANDED, 1),
        )
        reset, step = map(json.loads, requests.getvalue().splitlines())
        self.assertEqual(reset, {"op": "reset", "start": [19.5, -7, 10.5], "yaw": 0})
        self.assertEqual(step["op"], "step")
        self.assertEqual(len(table), 1)
