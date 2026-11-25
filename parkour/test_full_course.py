from unittest import TestCase

from .full_course import DATA, fit_policy, load_platforms, matching_frame
from .rewards import Frame


class FullCourseTest(TestCase):
    def test_demonstrations_cover_all_jumps(self) -> None:
        for name, count in (("map1", 28), ("map2", 24)):
            with self.subTest(course=name):
                platforms = load_platforms(DATA / f"{name}-platforms.csv")
                self.assertEqual(len(platforms) - 1, count)
                policy = fit_policy(DATA / f"{name}-demonstration.csv", count)
                self.assertEqual(
                    {platform for platform, _ in policy}, set(range(count))
                )
                self.assertEqual(
                    {choice.yaw for choice in policy.values()}, {0, 90, 180, 270}
                )

    def test_different_velocity_is_a_route_deviation(self) -> None:
        frame: Frame = {
            "position": (19.5, -7, 10.5),
            "velocity": (0, 0, 0),
            "on_ground": True,
        }
        self.assertTrue(matching_frame(frame, frame))
        self.assertFalse(matching_frame({**frame, "velocity": (0, 0, 0.2)}, frame))
