"""Smoke-test the headless Minecraft runner and the bot on a disposable world."""

import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import TypedDict, cast
from urllib.request import urlopen

VERSION = "26.1.2"
MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
START = [0.5, -60.0, 0.5]


class Download(TypedDict):
    url: str
    sha1: str


class VersionEntry(Download):
    id: str


class Manifest(TypedDict):
    versions: list[VersionEntry]


class Version(TypedDict):
    downloads: dict[str, Download]


class Frame(TypedDict):
    position: list[float]
    on_ground: bool


class Reply(TypedDict):
    result: Frame | list[Frame]


def download(url: str, sha1: str | None = None) -> bytes:
    with urlopen(url, timeout=45) as response:
        data = response.read()
    if sha1 is not None and hashlib.sha1(data).hexdigest() != sha1:
        raise RuntimeError(f"Download checksum mismatch for {url}")
    return data


def download_server(jar: Path) -> None:
    manifest = cast(Manifest, json.loads(download(MANIFEST)))
    entry = next(item for item in manifest["versions"] if item["id"] == VERSION)
    metadata = cast(Version, json.loads(download(entry["url"], entry["sha1"])))
    server = metadata["downloads"]["server"]
    jar.write_bytes(download(server["url"], server["sha1"]))


def verify_jump(env: dict[str, str]) -> None:
    reset = {"op": "reset", "start": START, "yaw": 0}
    messages = [reset, {"op": "step", "action": "run_jump"}, reset]
    result = subprocess.run(
        ["node", "src/minecraft.ts"], env=env, text=True, capture_output=True,
        input="".join(json.dumps(message) + "\n" for message in messages), timeout=30,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    first, jump, restored = [
        cast(Reply, json.loads(line))["result"] for line in result.stdout.splitlines()
    ]
    assert isinstance(first, dict) and first["on_ground"], first
    assert isinstance(jump, list) and len(jump) == 2, jump
    assert jump[-1]["position"][1] > START[1] and not jump[-1]["on_ground"], jump
    assert first == restored, restored


def run_server(
    jar: Path,
    runtime: Path,
    env: dict[str, str],
    world: Path | None = None,
) -> None:
    bash = "bash"
    if sys.platform == "win32":
        bash = str(Path(os.environ["ProgramFiles"]) / "Git/bin/bash.exe")
    command = [bash, "./scripts/headless", jar.as_posix()]
    if world is not None:
        command.append(world.as_posix())
    log = runtime.with_suffix(".log")
    with log.open("w") as output:
        server = subprocess.Popen(
            command, text=True, stdin=subprocess.PIPE, stdout=output,
            stderr=subprocess.STDOUT, env=dict(env, PARKOURSE_RUN_DIR=runtime.as_posix()),
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
                    server.stdin.write("stop\n")
                    server.stdin.flush()
                server.communicate(timeout=25)
            except subprocess.TimeoutExpired:
                server.kill()
                server.communicate()


def main() -> None:
    if os.environ.get("MINECRAFT_EULA") != "true":
        raise SystemExit("Read https://www.minecraft.net/eula and set MINECRAFT_EULA=true if you accept it.")
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
        assert (world / "level.dat").read_bytes() == original, "Source world changed"
        print("Loaded a copy of a Minecraft save, jumped for two ticks, and reset.")


if __name__ == "__main__":
    main()
