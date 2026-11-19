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

Each action returns two client physics frames with position in blocks, velocity in blocks per tick, and ground contact. Replies are JSON lines on stdout with either a `result` or an `error`. Reset settles within 0.15 blocks of the start. The actions are `idle`, `walk`, `run`, `walk_jump`, `run_jump`, `back`, and `sneak`.

The headless server runs without a game window and plays on a copy of the map. Set `JAVA` to your Java 25 binary if needed. Set `PARKOURSE_RUN_DIR` to an unused folder for a fresh copy. Set `PARKOURSE_PORT` in each terminal to change the default port. Type `stop` in the server console before switching maps.

## Watch in Minecraft

Join `127.0.0.1:25566` in Minecraft Java 26.1.2, or launch a configured [Prism instance](https://prismlauncher.org/wiki/getting-started/command-line-interface/) with `./scripts/headful YOUR_INSTANCE_ID`.

Keep the bot terminal open. In the server console, run `gamemode spectator YourName` to fly around, then `spectate ParkourseBot YourName` to follow the bot.

## Test it

```sh
npm run check
MINECRAFT_EULA=true uv run --locked python scripts/smoke.py /path/to/server.jar
```

The first command runs lint, type checks, and the bot protocol test. The second starts a disposable Minecraft server, tests a jump, and checks that reset restores the starting position. CI runs the smoke test on Linux, macOS, and Windows.

## Where to add training

1. Add episode endings and the core reward math in [parkour/rewards.py](parkour/rewards.py). Start with the previous state, action, next state, and target platform.
2. Add the training loop in [parkour/q_learning.py](parkour/q_learning.py). Turn observations into Q-table keys, update the table during training, and freeze it during evaluation.
3. Add next-platform selection in [parkour/routing.py](parkour/routing.py) (try a DQN for routing). Give the selected platform to the jump policy.

Have Python start `node src/minecraft.ts` as a subprocess and read one JSON reply per request. Use the reset reply as the initial state and the last frame from each step as the next state. See `scripts/smoke.py` for a working subprocess example.

Once the trainer has an entry point, run it from the repo root with `uv run --locked python -m parkour.q_learning`.

## Scripts

| Entry point | What it does |
| --- | --- |
| `scripts/headless` | Starts the local server and optionally copies in a map |
| `scripts/headful` | Opens a Prism client on that server |
| `node src/minecraft.ts` | Reads reset and movement requests and returns raw player state |
| `scripts/smoke.py` | Checks the world copy, jump, and reset in a disposable server |
| `npm run check` | Runs lint, strict type checks, and the protocol test |
