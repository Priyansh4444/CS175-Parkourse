"""Train a tabular jump policy on a course hosted by the local Minecraft server."""

import argparse
import json
import subprocess
from contextlib import suppress
from pathlib import Path
from random import Random
from typing import IO

from scripts.smoke import array_items, decode_frame, reply_value

from .courses import COURSES, Course
from .q_learning import QTable, choose_action, encode, update
from .rewards import MAX_STEPS, Outcome, outcome

ROOT = Path(__file__).resolve().parent.parent


class Options(argparse.Namespace):
    map: str
    episodes: int
    seed: int


def request(stdin: IO[str], stdout: IO[str], message: dict[str, object]) -> object:
    stdin.write(json.dumps(message) + "\n")
    stdin.flush()
    line = stdout.readline()
    if not line:
        raise RuntimeError(
            "The Minecraft bot disconnected. Check the server and bot logs."
        )
    return reply_value(line)


def train_episode(
    stdin: IO[str],
    stdout: IO[str],
    course: Course,
    table: QTable,
    epsilon: float,
    rng: Random,
) -> tuple[Outcome, int]:
    previous = decode_frame(
        request(
            stdin, stdout, {"op": "reset", "start": course.start, "yaw": course.yaw}
        )
    )
    for steps in range(1, MAX_STEPS + 1):
        action = choose_action(
            table, encode(previous, course.target), epsilon=epsilon, rng=rng
        )
        ticks = array_items(request(stdin, stdout, {"op": "step", "action": action}))
        if len(ticks) != 2:
            raise RuntimeError(f"Expected two physics frames, got {len(ticks)}")

        first, second = map(decode_frame, ticks)
        # Timeout counts actions, so give the second tick a chance to record a landing.
        current = (
            second
            if outcome(first, course.target, steps - 1) is Outcome.RUNNING
            else first
        )
        result = update(
            table,
            previous,
            action,
            current,
            course.target,
            steps,
            alpha=0.5,
            gamma=0.95,
        )
        if result is not Outcome.RUNNING:
            return result, steps
        previous = current

    raise RuntimeError("The reward rules did not terminate the episode")


def train(course: Course, episodes: int, seed: int) -> None:
    table: QTable = {}
    rng = Random(seed)
    with subprocess.Popen(
        ["node", "src/minecraft.ts"],
        cwd=ROOT,
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    ) as bot:
        stdin, stdout = bot.stdin, bot.stdout
        if stdin is None or stdout is None:
            raise RuntimeError("Could not open the bot pipes")

        try:
            for episode in range(1, episodes + 1):
                epsilon = 0.65 - 0.55 * (episode - 1) / max(1, episodes - 1)
                result, steps = train_episode(
                    stdin, stdout, course, table, epsilon, rng
                )
                print(
                    json.dumps(
                        {"episode": episode, "outcome": result.value, "steps": steps}
                    ),
                    flush=True,
                )
        finally:
            with suppress(BrokenPipeError):
                stdin.close()
            try:
                bot.wait(timeout=5)
            except subprocess.TimeoutExpired:
                bot.kill()
                bot.wait()

    if bot.returncode != 0:
        raise RuntimeError(f"The Minecraft bot exited with status {bot.returncode}")
    print(json.dumps({"map": course.folder, "q_entries": len(table)}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", choices=tuple(COURSES), required=True)
    parser.add_argument("--episodes", type=int, default=40)
    parser.add_argument("--seed", type=int, default=17)
    options = parser.parse_args(namespace=Options())
    if options.episodes < 1:
        parser.error("--episodes must be positive")

    try:
        train(COURSES[options.map], options.episodes, options.seed)
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"Training stopped: {error}") from error


if __name__ == "__main__":
    main()
