from unittest import TestCase

from .full_course import DATA, fit_policy, load_platforms, matching_frame
from .rewards import Frame


class FullCourseTest(TestCase):
    def test_map_one_demonstration_covers_every_jump(self) -> None:
        platforms = load_platforms(DATA / "map1-platforms.csv")
        self.assertEqual(len(platforms) - 1, 28)
        policy = fit_policy(DATA / "map1-demonstration.csv", len(platforms) - 1)
        self.assertEqual({platform for platform, _ in policy}, set(range(28)))
        self.assertEqual({choice.yaw for choice in policy.values()}, {0, 90, 180, 270})

    def test_different_velocity_is_a_route_deviation(self) -> None:
        frame: Frame = {
            "position": (19.5, -7, 10.5),
            "velocity": (0, 0, 0),
            "on_ground": True,
        }
        self.assertTrue(matching_frame(frame, frame))
        self.assertFalse(matching_frame({**frame, "velocity": (0, 0, 0.2)}, frame))
