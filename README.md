# Parkourse

CS 175 project exploring whether a small reinforcement learning agent can learn to time Minecraft parkour jumps.

A course supplies the next platform. The controller holds one of seven actions for two ticks and reports raw player state. The same Minecraft Java world can run headless or be watched in a graphical client.

## Team TODOs

- Set up the observations for learning: distance and height to the next platform, forward and vertical speed, and ground contact.
- Define the core reward math and when an episode ends.
- Implement the Q-learning policy.
- Evaluate on held-out jumps and courses.

## Setup

Use Bash on macOS or Linux, or Git Bash on Windows. Install Node.js 22.18+, Java 25, and the [Minecraft Java 26.1.2 server JAR](https://www.minecraft.net/en-us/article/minecraft-java-edition-26-1-2). Run `npm ci` from the repository root. Install Python 3.11+ if you want to run the smoke test.

## Run Minecraft

Headless runs the server without a game window. Headful lets you watch in the graphical Minecraft client.

1. Read the [Minecraft EULA](https://www.minecraft.net/eula). If you accept it, run `MINECRAFT_EULA=true ./scripts/headless /path/to/server.jar`. Wait for `Done`. Set `JAVA` to a Java 25 binary if needed.
2. Run the controller in a second terminal. This example uses the default flat world. For a course, use its start from the table below.

   ```sh
   node src/minecraft.ts <<'JSON'
   {"op":"reset","start":[0.5,-60,0.5],"yaw":0}
   {"op":"step","action":"run_jump"}
   JSON
   ```

   Reset returns one frame. Each action returns two frames with position, velocity, and ground contact. Actions are `idle`, `walk`, `run`, `walk_jump`, `run_jump`, `back`, and `sneak`.
3. To watch, run `./scripts/headful <prism-instance-id>` with a Minecraft 26.1.2 [Prism Launcher instance](https://prismlauncher.org/wiki/getting-started/command-line-interface/), or join `127.0.0.1:25566` from Minecraft Java. In the server console, use `gamemode spectator YourName` to fly around. Use `spectate ParkourseBot YourName` once the bot is connected to follow it. Keep the bot connected to send actions by hand with `node src/minecraft.ts`, one JSON request per line.

The server uses offline mode on loopback. Set `PARKOURSE_PORT` consistently in all terminals to change the port. The server saves its files under `~/.local/share/parkourse/server` by default. Set `PARKOURSE_RUN_DIR` to use another folder. Type `stop` in its console to shut down.

### Use the course maps

Unzip the team's `maps.zip` into a folder outside the repo. Pass the folder containing `level.dat` as the second argument. Keep the source world closed while you copy it.

```sh
unzip /path/to/maps.zip -d "$HOME/parkourse-maps"
MINECRAFT_EULA=true ./scripts/headless /path/to/server.jar "$HOME/parkourse-maps/Map 1"
```

| Course | Folder in the ZIP | Reset `start` | `yaw` |
| --- | --- | --- | --- |
| 1 | `Map 1` | `[19.5,-7,10.5]` | `0` |
| 2 | `map 2` | `[4.5,-5,-8.5]` | `0` |
| 3 | `MAP 3` | `[-1.5,50,5.5]` | `0` |

Use that row's start and yaw in the reset request, then send an action through the same controller. A grounded reset and two jump frames confirm the connection.

The server copies each world to its own directory under `~/.local/share/parkourse/maps` and saves changes there. Set `PARKOURSE_RUN_DIR` to an unused path for a fresh copy. Stop the current server before starting another map on the same port.

## Checks

Run `npm run check` for the TypeScript and Python type checks. Run either one with `npm run check:ts` or `npm run check:python`.

After accepting the Minecraft EULA, run `MINECRAFT_EULA=true python3 scripts/smoke.py /path/to/server.jar` to test a save copy, jump and reset. In Windows Git Bash, use `python` in place of `python3`. The smoke test uses temporary files. GitHub Actions runs it on Linux, macOS and Windows.

## Layout

- `src/` holds the input handling and Minecraft controller.
- `scripts/` holds the Minecraft launchers and the Python smoke test.
- `.github/workflows/ci.yml` runs the checks on GitHub.
