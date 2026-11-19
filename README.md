# Parkourse

A CS 175 project on learning to time Minecraft parkour jumps.

## Setup

Use Bash on Linux or macOS, or Git Bash on Windows. Install these tools.

- [Node.js 22.18+ with npm](https://nodejs.org/en/download)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for the Python smoke test
- Java 25 and the [Minecraft Java 26.1.2 server JAR](https://www.minecraft.net/en-us/article/minecraft-java-edition-26-1-2)

Run `npm ci` from the repo root.

## Run the server and bot

Start Minecraft headless (without a game window).

```sh
MINECRAFT_EULA=true ./scripts/headless /path/to/server.jar
```

Wait for `Done`. In another terminal, run `node src/minecraft.ts` and paste these requests, one per line.

```json
{"op":"reset","start":[0.5,-60,0.5],"yaw":0}
{"op":"step","action":"run_jump"}
```

Each action runs for two ticks and returns position, velocity, and ground contact for each tick. The actions are `idle`, `walk`, `run`, `walk_jump`, `run_jump`, `back`, and `sneak`.

Set `JAVA` to your Java 25 binary if needed. The server uses offline mode on `127.0.0.1:25566`. To change the port, set `PARKOURSE_PORT` in each terminal. Type `stop` in the server console to shut it down.

## Watch in Minecraft

Join `127.0.0.1:25566` in Minecraft Java 26.1.2, or launch a configured [Prism instance](https://prismlauncher.org/wiki/getting-started/command-line-interface/) with `./scripts/headful YOUR_INSTANCE_ID`.

Keep the bot terminal open. In the server console, run `gamemode spectator YourName` to fly around, then `spectate ParkourseBot YourName` to follow the bot.

## Course maps

Unzip `maps.zip` outside the repo. Pass the closed world folder containing `level.dat` to the server.

```sh
unzip /path/to/maps.zip -d "$HOME/parkourse-maps"
MINECRAFT_EULA=true ./scripts/headless /path/to/server.jar "$HOME/parkourse-maps/Map 1"
```

Use the map's start coordinates in the reset request. All three maps use yaw `0`.

| Folder | Reset start |
| --- | --- |
| `Map 1` | `[19.5,-7,10.5]` |
| `map 2` | `[4.5,-5,-8.5]` |
| `MAP 3` | `[-1.5,50,5.5]` |

Local server files live under `~/.local/share/parkourse/`. The server plays on a copy of the map. Set `PARKOURSE_RUN_DIR` to an unused folder for a fresh copy.

## Checks

```sh
npm run check
MINECRAFT_EULA=true uv run --no-project --python 3.11 python scripts/smoke.py /path/to/server.jar
```

GitHub Actions runs the TypeScript and Python checks and tests headless Minecraft on Linux, macOS, and Windows.

## TODO

- Define the core reward math and when an episode ends.
- Select the learning observations, implement Q-learning, and evaluate on held-out jumps and courses.

## Layout

- `src/` contains the input code and bot.
- `scripts/` contains the launchers and smoke test.
- `.github/workflows/ci.yml` defines CI.
