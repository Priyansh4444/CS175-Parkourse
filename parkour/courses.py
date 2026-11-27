"""Starting poses and first landing platforms in the shared course worlds."""

from dataclasses import dataclass

from .rewards import Platform


@dataclass(frozen=True)
class Course:
    folder: str
    start: tuple[float, float, float]
    yaw: float
    target: Platform


COURSES: dict[str, Course] = {
    "1": Course("Map 1", (19.5, -7, 10.5), 0, Platform(19, 20, 13, 14, -6)),
    "2": Course("map 2", (4.5, -5, -8.5), 0, Platform(3, 5, -5, -4, -4)),
    "3": Course("MAP 3", (-1.5, 50, 5.5), 0, Platform(-3, -1, 10, 11, 50)),
}
