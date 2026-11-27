"""Smoke-test the headless Minecraft runner and the bot on a disposable world."""

import hashlib
import json
import math
import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Literal, TypedDict, cast
from urllib.request import urlopen

VERSION = "26.1.2"
MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
Vec = tuple[float, float, float]
START: Vec = (0.5, -60.0, 0.5)
ROOT = Path(__file__).resolve().parent.parent


class ResetRequest(TypedDict):
    op: Literal["reset"]
    start: Vec
    yaw: float


class StepRequest(TypedDict):
    op: Literal["step"]
    action: Literal["run_jump"]


class Frame(TypedDict):
    position: Vec
    velocity: Vec
    on_ground: bool


def object_fields(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object, got {value!r}")
    # All object keys from json.loads are strings.
    return cast(dict[str, object], value)


def array_items(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"Expected a JSON array, got {value!r}")
    return cast(list[object], value)


def decode_vector(value: object) -> Vec:
    items = array_items(value)
    if len(items) != 3:
        raise ValueError(f"Expected three coordinates, got {items!r}")
    x, y, z = items
    return coordinate(x), coordinate(y), coordinate(z)


def coordinate(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
    ):
        raise ValueError(f"Expected a finite coordinate, got {value!r}")
    return float(value)


def decode_frame(value: object) -> Frame:
    fields = object_fields(value)
    on_ground = fields.get("on_ground")
    if not isinstance(on_ground, bool):
        raise ValueError(f"Expected a boolean on_ground, got {on_ground!r}")
    return {
        "position": decode_vector(fields.get("position")),
        "velocity": decode_vector(fields.get("velocity")),
        "on_ground": on_ground,
    }


def reply_value(line: str) -> object:
    response = object_fields(json.loads(line))
    if "result" not in response:
        raise RuntimeError(
            f"Bot request failed with {response.get('error', response)!r}"
        )
    return response["result"]


def download(url: str, sha1: str | None = None) -> bytes:
    with urlopen(url, timeout=45) as response:
        data = response.read()
    if sha1 is not None and hashlib.sha1(data).hexdigest() != sha1:
        raise RuntimeError(f"Download checksum mismatch for {url}")
    return data


def download_entry(entry: dict[str, object]) -> bytes:
    url = entry.get("url")
    checksum = entry.get("sha1")
    if not isinstance(url, str) or not isinstance(checksum, str):
        raise ValueError("Mojang download entry must include a URL and SHA-1")
    return download(url, checksum)


def download_server(jar: Path) -> None:
    manifest = object_fields(json.loads(download(MANIFEST)))
    for raw in array_items(manifest.get("versions")):
        entry = object_fields(raw)
        if entry.get("id") == VERSION:
            metadata = object_fields(json.loads(download_entry(entry)))
            downloads = object_fields(metadata.get("downloads"))
            jar.write_bytes(download_entry(object_fields(downloads.get("server"))))
            return
    raise RuntimeError(f"Minecraft {VERSION} was not in Mojang's manifest")


def verify_jump(env: dict[str, str]) -> None:
    reset: ResetRequest = {"op": "reset", "start": START, "yaw": 0}
    jump_request: StepRequest = {"op": "step", "action": "run_jump"}
    result = subprocess.run(
        ["node", "src/minecraft.ts"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        input="".join(
            json.dumps(message) + "\n" for message in (reset, jump_request, reset)
        ),
        timeout=30,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    lines = result.stdout.splitlines()
    if len(lines) != 3:
        raise RuntimeError(f"Expected three bot replies, got {lines!r}")
    first = decode_frame(reply_value(lines[0]))
    first_tick, second_tick = array_items(reply_value(lines[1]))
    decode_frame(first_tick)
    jump = decode_frame(second_tick)
    restored = decode_frame(reply_value(lines[2]))
    if any(
        not frame["on_ground"]
        or math.dist(frame["position"], START) >= 0.15
        or math.hypot(frame["velocity"][0], frame["velocity"][2]) >= 0.03
        for frame in (first, restored)
    ):
        raise RuntimeError(f"Unexpected reset frames {first!r}, {restored!r}")
    if jump["position"][1] <= first["position"][1] or jump["on_ground"]:
        raise RuntimeError(f"Bot did not leave the ground with a jump {jump!r}")


def run_server(
    jar: Path,
    runtime: Path,
    env: dict[str, str],
    world: Path | None = None,
) -> None:
    bash = "bash"
    if sys.platform == "win32":
        bash = str(Path(os.environ["PROGRAMFILES"]) / "Git/bin/bash.exe")
    command = [bash, "./scripts/headless", jar.as_posix()]
    if world is not None:
        command.append(world.as_posix())
    log = runtime.with_suffix(".log")
    with log.open("w") as output:
        server = subprocess.Popen(
            command,
            cwd=ROOT,
            text=True,
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
            env=dict(env, PARKOURSE_RUN_DIR=runtime.as_posix()),
        )
        try:
            deadline = time.monotonic() + 90
            while "Done (" not in log.read_text(errors="replace"):
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Minecraft did not become ready")
                time.sleep(0.25)
            if world is not None:
                verify_jump(env)
        except Exception:
            print(log.read_text(errors="replace")[-6000:], file=sys.stderr)
            raise
        finally:
            try:
                if server.poll() is None and server.stdin is not None:
                    with suppress(BrokenPipeError):
                        server.stdin.write("stop\n")
                        server.stdin.flush()
                server.communicate(timeout=25)
            except subprocess.TimeoutExpired:
                server.kill()
                server.communicate()


def main() -> None:
    if os.environ.get("MINECRAFT_EULA") != "true":
        raise SystemExit(
            "Read https://www.minecraft.net/eula and set MINECRAFT_EULA=true if you accept it."
        )
    if len(sys.argv) > 2:
        raise SystemExit("Usage: uv run --locked python scripts/smoke.py [server.jar]")
    with tempfile.TemporaryDirectory(prefix="parkourse-smoke-") as directory:
        root = Path(directory).resolve()
        jar = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / "server.jar"
        if len(sys.argv) == 1:
            download_server(jar)
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            port = reserved.getsockname()[1]

        # The smoke test uses an isolated server and world directory.
        env = dict(os.environ, PARKOURSE_PORT=str(port))
        run_server(jar, root / "source", env)
        world = root / "source/world"
        original = (world / "level.dat").read_bytes()
        run_server(jar, root / "world copy", env, world)
        if (world / "level.dat").read_bytes() != original:
            raise RuntimeError("Source world changed")
        print("Loaded a copy of a Minecraft save, jumped for two ticks, and reset.")


if __name__ == "__main__":
    main()
