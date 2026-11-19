import mineflayer from "mineflayer";
import { type ActionFrames, type Frame, serve } from "./controls.ts";

const port = Number(process.env.PARKOURSE_PORT ?? "25566");
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error("PARKOURSE_PORT must be a port from 1 to 65535");
}

// Keep stdout available for the JSON-lines responses.
console.log = console.error;
const bot = mineflayer.createBot({
  host: "127.0.0.1",
  port,
  username: "ParkourseBot",
  version: "26.1.2",
  auth: "offline",
});

let corrections = 0;
bot.on("forcedMove", () => {
  corrections++;
});
bot.on("error", (error) => {
  console.error(error.message);
  process.exitCode = 1;
});
bot.on("kicked", (reason) => {
  console.error("Minecraft kicked ParkourseBot:", reason);
  process.exitCode = 1;
});

function frame(): Frame {
  const { position, velocity, onGround } = bot.entity;
  return {
    position: [position.x, position.y, position.z],
    velocity: [velocity.x, velocity.y, velocity.z],
    on_ground: onGround,
  };
}

function runPhysics<T>(sample: () => T | undefined): Promise<T> {
  return new Promise((resolve, reject) => {
    const stop = () => {
      bot.physicsEnabled = false;
      bot.clearControlStates();
      bot.off("physicsTick", onTick);
      clearTimeout(timeout);
    };
    const onTick = () => {
      try {
        const result = sample();
        if (result === undefined) return;
        stop();
        resolve(result);
      } catch (error) {
        stop();
        reject(error);
      }
    };
    const timeout = setTimeout(() => {
      stop();
      reject(
        new Error(
          "Minecraft physics timed out. Check the server and start coordinates.",
        ),
      );
    }, 5000);
    bot.on("physicsTick", onTick);
    bot.physicsEnabled = true;
  });
}

let closing = false;
bot.once("end", (reason) => {
  if (closing) return;
  console.error("Minecraft disconnected:", reason);
  process.exit(1);
});

try {
  await new Promise<void>((resolve, reject) => {
    bot.once("error", reject);
    bot.once("spawn", () => {
      bot.off("error", reject);
      resolve();
    });
  });
  await bot.waitForChunksToLoad();
  bot.physicsEnabled = false;
  console.error("ParkourseBot ready");
  let lastReset = corrections;

  await serve({
    async reset([x, y, z], yaw) {
      const before = corrections;
      let stillTicks = 0;
      const settled = runPhysics(() => {
        const { position, velocity, onGround } = bot.entity;
        const nearStart =
          Math.hypot(position.x - x, position.y - y, position.z - z) < 0.15;
        const still = Math.hypot(velocity.x, velocity.z) < 0.03;
        stillTicks =
          corrections > before && onGround && nearStart && still
            ? stillTicks + 1
            : 0;
        return stillTicks === 2 ? frame() : undefined;
      });

      bot.chat(`/tp @s ${x} ${y} ${z} ${yaw} 0`);
      const resetFrame = await settled;
      lastReset = corrections;
      return resetFrame;
    },

    async step(buttons) {
      if (corrections !== lastReset) {
        throw new Error(
          "Minecraft corrected the bot's position. Reset before continuing.",
        );
      }
      for (const button of buttons) bot.setControlState(button, true);
      let first: Frame | undefined;
      return runPhysics<ActionFrames>(() => {
        if (corrections !== lastReset) {
          throw new Error(
            "Minecraft corrected the bot's position. Reset before continuing.",
          );
        }
        const current = frame();
        if (first !== undefined) return [first, current];
        first = current;
      });
    },
  });
} finally {
  closing = true;
  bot.quit();
}
