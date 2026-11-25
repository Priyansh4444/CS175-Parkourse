# Parkourse

A CS 175 project on learning to time Minecraft parkour jumps.

## Setup

Use Bash on Linux or macOS, or Git Bash on Windows. Install these tools.

- [Node.js 22.18+ with npm](https://nodejs.org/en/download)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for Python tools and the smoke test
- Java 25 and the [Minecraft Java 26.1.2 server JAR](https://www.minecraft.net/en-us/article/minecraft-java-edition-26-1-2)

From the repo root, install the locked dependencies.

```sh
npm ci
uv sync --locked --python 3.11
```

## Run a course map

Get the shared `maps.zip` from the project team and unzip it outside the repo. Pass the closed world folder containing `level.dat` to the server.

```sh
unzip /path/to/maps.zip -d "$HOME/parkourse-maps"
MINECRAFT_EULA=true ./scripts/headless /path/to/server.jar "$HOME/parkourse-maps/Map 1"
```

Wait for `Done`, then run `node src/minecraft.ts` in another terminal. Paste the reset request for the world you loaded.

| World folder | Reset request |
| --- | --- |
| `Map 1` | `{"op":"reset","start":[19.5,-7,10.5],"yaw":0}` |
| `map 2` | `{"op":"reset","start":[4.5,-5,-8.5],"yaw":0}` |
| `MAP 3` | `{"op":"reset","start":[-1.5,50,5.5],"yaw":0}` |

Paste `{"op":"step","action":"run_jump"}` to test one action. The bot takes actions you send it. Routing is a TODO.

Each action returns two client physics frames by default with position in blocks, velocity in blocks per tick, and ground contact. Replies are JSON lines on stdout with either a `result` or an `error`. Reset settles within 0.15 blocks of the start. The actions are `idle`, `walk`, `run`, `walk_jump`, `run_jump`, `back`, `sneak`, `left`, `right`, and `run_left`. Set `"ticks":1` on a step to request one frame.

The headless server runs without a game window and plays on a copy of the map. Set `JAVA` to your Java 25 binary if needed. Set `PARKOURSE_RUN_DIR` to an unused folder for a fresh copy. Set `PARKOURSE_PORT` in each terminal to change the default port. Type `stop` in the server console before switching maps.

## Train on a course map

Start the server with the world folder above. Wait for `Done`, then run this in a second terminal with any manual bot session closed.

```sh
uv run --locked python -m parkour.train --map 1 --episodes 40
```

Use `--map 2` with `map 2` or `--map 3` with `MAP 3`. Each attempt resets to the course start and trains toward its first landing platform. The command prints each attempt's result. The Q-table stays in memory for the run. Saving it and evaluating on held-out jumps are tracked in [#9](https://github.com/Priyansh4444/CS175-Parkourse/issues/9).

## Run a full course headless

Use the original course folders from `maps.zip`. This command starts and stops its own server on a temporary copy of the map. It disables fall damage on that copy to match the demonstration.

```sh
MINECRAFT_EULA=true uv run --locked python -m parkour.full_course /path/to/server.jar "$HOME/parkourse-maps/Map 1"
MINECRAFT_EULA=true uv run --locked python -m parkour.full_course --map 2 /path/to/server.jar "$HOME/parkourse-maps/map 2"
MINECRAFT_EULA=true uv run --locked python -m parkour.full_course --map 3 /path/to/server.jar "$HOME/parkourse-maps/MAP 3"
```

Map 1 covers 28 jumps and Map 2 covers 24. The original Map 3 demonstration covers 20 of 28 jumps. Jump 21 has a five-block gap on the recorded route, which exceeds the estimated reach with normal movement. To run all 28 on Map 3, use the same world folder and lower landing 21 and its sign by one block on the temporary copy.

```sh
MINECRAFT_EULA=true uv run --locked python -m parkour.full_course --map 3 --lower-jump-21 /path/to/server.jar "$HOME/parkourse-maps/MAP 3"
```

The runner fits a course-specific policy from a recorded demonstration. Each course or variant has two CSVs in `parkour/maps/`. One lists the landings in order. The other records the demonstrated states, actions, and headings. The bot turns automatically, resets once, and reports each landing as it runs. This run measures completion on the demonstrated course. Use the first-jump command above to train with exploratory tabular Q-learning.

## Watch in Minecraft

Join `127.0.0.1:25566` in Minecraft Java 26.1.2, or launch a configured [Prism instance](https://prismlauncher.org/wiki/getting-started/command-line-interface/) with `./scripts/headful YOUR_INSTANCE_ID`.

Keep the bot terminal open. In the server console, run `gamemode spectator YourName` to fly around, then `spectate ParkourseBot YourName` to follow the bot.

## Test it

```sh
npm run check
MINECRAFT_EULA=true uv run --locked python scripts/smoke.py /path/to/server.jar
```

The first command runs lint, type checks, and the bot protocol test. The second starts a disposable Minecraft server, tests a jump, and checks that reset restores the starting position. CI runs the smoke test on Linux, macOS, and Windows.

## Learning code

- `parkour/courses.py` holds the starting poses and first landing platforms.
- `parkour/rewards.py` scores each action and decides when an attempt ends.
- `parkour/q_learning.py` bins observations and updates the Q-table.
- `parkour/train.py` drives the Minecraft bot and runs the training loop.
- `parkour/routing.py` is the TODO for choosing the next platform (try a DQN).

## Scripts

| Entry point | What it does |
| --- | --- |
| `scripts/headless` | Starts the local server and optionally copies in a map |
| `scripts/headful` | Opens a Prism client on that server |
| `node src/minecraft.ts` | Reads reset and movement requests and returns raw player state |
| `python -m parkour.full_course` | Fits a demonstration policy and runs the course headless |
| `scripts/smoke.py` | Checks the world copy, jump, and reset in a disposable server |
| `npm run check` | Runs lint, strict type checks, and the protocol test |
