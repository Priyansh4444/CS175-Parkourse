"""Fit a course policy from a demonstration and run it on the supplied world."""

import argparse
import csv
import json
import math
import os
import socket
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import IO

from scripts.smoke import array_items, decode_frame

from .q_learning import ACTIONS, Action
from .rewards import Frame, Platform, is_landing
from .train import ROOT, request

DATA = Path(__file__).parent / "maps"


@dataclass(frozen=True)
class Decision:
    frame: Frame
    action: Action
    yaw: float


class Options(argparse.Namespace):
    map: int
    jar: Path
    world: Path


def matching_frame(actual: Frame, expected: Frame) -> bool:
    return (
        actual["on_ground"] == expected["on_ground"]
        and math.dist(actual["position"], expected["position"]) < 0.08
        and math.dist(actual["velocity"], expected["velocity"]) < 0.03
    )


def load_platforms(path: Path) -> list[Platform]:
    platforms: list[Platform] = []
    with path.open(newline="", encoding="utf8") as source:
        for row in csv.DictReader(source):
            if int(row["platform"]) != len(platforms):
                raise ValueError("Platforms must be numbered in landing order")
            platforms.append(
                Platform(
                    *(
                        float(row[key])
                        for key in ("min_x", "max_x", "min_z", "max_z", "top_y")
                    )
                )
            )
    if len(platforms) < 2:
        raise ValueError("A course needs a starting platform and a landing")
    return platforms


def fit_policy(path: Path, jumps: int) -> dict[tuple[int, int], Decision]:
    """Fit the demonstrated action and heading for each observed state in a jump."""
    policy: dict[tuple[int, int], Decision] = {}
    names: dict[str, Action] = {action: action for action in ACTIONS}
    expected_platform, expected_step = 0, 0
    with path.open(newline="", encoding="utf8") as source:
        for row in csv.DictReader(source):
            platform, step = int(row["platform"]), int(row["step"])
            if expected_step and (platform, step) == (expected_platform + 1, 0):
                expected_platform, expected_step = platform, 0
            if (platform, step) != (
                expected_platform,
                expected_step,
            ) or platform >= jumps:
                raise ValueError(
                    f"Invalid demonstration order at platform {platform}, step {step}"
                )
            if row["on_ground"] not in ("0", "1"):
                raise ValueError("Expected 0 or 1 for demonstration ground contact")
            x, y, z, vx, vy, vz, yaw = (
                float(row[key]) for key in ("x", "y", "z", "vx", "vy", "vz", "yaw")
            )
            if not all(map(math.isfinite, (x, y, z, vx, vy, vz, yaw))):
                raise ValueError("Demonstration coordinates and heading must be finite")
            frame: Frame = {
                "position": (x, y, z),
                "velocity": (vx, vy, vz),
                "on_ground": row["on_ground"] == "1",
            }
            policy[(platform, step)] = Decision(frame, names[row["action"]], yaw)
            expected_step += 1
    if not policy or expected_platform != jumps - 1:
        raise ValueError("The demonstration must cover every jump")
    return policy


def run_policy(
    stdin: IO[str],
    stdout: IO[str],
    platforms: list[Platform],
    policy: dict[tuple[int, int], Decision],
) -> None:
    start = platforms[0]
    pose = (
        (start.min_x + start.max_x) / 2,
        start.top_y,
        (start.min_z + start.max_z) / 2,
    )
    frame = decode_frame(
        request(stdin, stdout, {"op": "reset", "start": pose, "yaw": 0})
    )
    number, step = 0, 0
    for _ in range(len(policy)):
        decision = policy.get((number, step))
        if decision is None or not matching_frame(frame, decision.frame):
            raise RuntimeError(
                f"Bot left the demonstrated trajectory before jump {number + 1}, step {step + 1}: "
                f"observed {frame!r}; expected {None if decision is None else decision.frame!r}"
            )
        ticks = array_items(
            request(
                stdin,
                stdout,
                {"op": "step", "action": decision.action, "yaw": decision.yaw},
            )
        )
        if len(ticks) != 2:
            raise RuntimeError(f"Expected two physics frames, got {len(ticks)}")
        first, frame = map(decode_frame, ticks)
        target = platforms[number + 1]
        if is_landing(first, target) or is_landing(frame, target):
            number += 1
            step = 0
            print(
                json.dumps({"landed": number, "jumps": len(platforms) - 1}), flush=True
            )
            if number == len(platforms) - 1:
                return
        else:
            step += 1
    raise RuntimeError(f"Policy ended after {number} of {len(platforms) - 1} jumps")


def wait_for_log(server: subprocess.Popen[str], log: Path, line: str) -> None:
    deadline = time.monotonic() + 90
    while line not in log.read_text(errors="replace"):
        if server.poll() is not None or time.monotonic() > deadline:
            raise RuntimeError(f"Minecraft console did not report {line!r}")
        time.sleep(0.25)


@contextmanager
def headless_server(jar: Path, world: Path) -> Generator[dict[str, str], None, None]:
    with TemporaryDirectory(prefix="parkourse-course-") as folder:
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            port = reserved.getsockname()[1]
        env = dict(os.environ, PARKOURSE_PORT=str(port), PARKOURSE_RUN_DIR=folder)
        bash = "bash"
        if sys.platform == "win32":
            bash = str(Path(os.environ["ProgramFiles"]) / "Git/bin/bash.exe")
        log = Path(folder) / "server.log"
        with (
            log.open("w", encoding="utf8") as output,
            subprocess.Popen(
                [bash, "./scripts/headless", jar.as_posix(), world.as_posix()],
                cwd=ROOT,
                env=env,
                stdin=subprocess.PIPE,
                stdout=output,
                stderr=subprocess.STDOUT,
                text=True,
            ) as server,
        ):
            try:
                wait_for_log(server, log, "Done (")
                if server.stdin is None:
                    raise RuntimeError("Could not open the server console")
                # Match the demonstration's rules on this disposable copy.
                server.stdin.write("gamerule fall_damage false\n")
                server.stdin.flush()
                wait_for_log(server, log, "Gamerule fall_damage is now set to: false")
                yield env
            except Exception:
                print(log.read_text(errors="replace")[-4000:], file=sys.stderr)
                raise
            finally:
                if server.poll() is None and server.stdin is not None:
                    with suppress(BrokenPipeError):
                        server.stdin.write("stop\n")
                        server.stdin.flush()
                try:
                    server.communicate(timeout=25)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.communicate()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=int, choices=(1, 2), default=1)
    parser.add_argument("jar", type=Path)
    parser.add_argument(
        "world", type=Path, help="Original course folder containing level.dat"
    )
    options = parser.parse_args(namespace=Options())
    try:
        name = f"map{options.map}"
        platforms = load_platforms(DATA / f"{name}-platforms.csv")
        policy = fit_policy(DATA / f"{name}-demonstration.csv", len(platforms) - 1)
        with (
            headless_server(options.jar.resolve(), options.world.resolve()) as env,
            subprocess.Popen(
                ["node", "src/minecraft.ts"],
                cwd=ROOT,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
            ) as bot,
        ):
            if bot.stdin is None or bot.stdout is None:
                raise RuntimeError("Could not open the bot pipes")
            try:
                run_policy(bot.stdin, bot.stdout, platforms, policy)
            finally:
                with suppress(BrokenPipeError):
                    bot.stdin.close()
                try:
                    bot.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    bot.kill()
                    bot.wait()
            if bot.returncode:
                raise RuntimeError(f"Bot exited with status {bot.returncode}")
        print(
            json.dumps(
                {
                    "completed_jumps": len(platforms) - 1,
                    "resets": 1,
                    "policy_entries": len(policy),
                }
            )
        )
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        raise SystemExit(f"Course run stopped: {error}") from error


if __name__ == "__main__":
    main()
