from unittest import TestCase

from .full_course import DATA, fit_policy, load_platforms, matching_frame
from .rewards import Frame


class FullCourseTest(TestCase):
    def test_demonstrations_cover_the_documented_landings(self) -> None:
        courses = (
            ("map1", 28),
            ("map2", 24),
            ("map3", 28),
        )
        for name, total in courses:
            with self.subTest(course=name):
                platforms = load_platforms(DATA / f"{name}-platforms.csv")
                self.assertEqual(len(platforms) - 1, total)
                policy = fit_policy(DATA / f"{name}-demonstration.csv", total)
                self.assertEqual(
                    {platform for platform, _ in policy}, set(range(total))
                )

    def test_different_velocity_is_a_route_deviation(self) -> None:
        frame: Frame = {
            "position": (19.5, -7, 10.5),
            "velocity": (0, 0, 0),
            "on_ground": True,
        }
        self.assertTrue(matching_frame(frame, frame))
        self.assertFalse(matching_frame({**frame, "velocity": (0, 0, 0.2)}, frame))
