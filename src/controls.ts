import { createInterface } from "node:readline";

export const TICKS_PER_ACTION = 2;

const actions = {
  idle: [],
  walk: ["forward"],
  run: ["forward", "sprint"],
  walk_jump: ["forward", "jump"],
  run_jump: ["forward", "sprint", "jump"],
  back: ["back"],
  sneak: ["sneak"],
} as const;

type Action = keyof typeof actions;
export type Button = (typeof actions)[Action][number];
export type Vec = [x: number, y: number, z: number];
export type Frame = { position: Vec; velocity: Vec; on_ground: boolean };

export interface Player {
  reset(start: Vec, yaw: number): Promise<Frame>;
  step(buttons: readonly Button[], ticks: number): Promise<Frame[]>;
}

function isPosition(value: unknown): value is Vec {
  return Array.isArray(value) && value.length === 3 && value.every(Number.isFinite);
}

async function handle(player: Player, message: unknown) {
  if (typeof message !== "object" || message === null) {
    throw new Error("Expected a JSON object");
  }

  const request = message as Record<string, unknown>;
  if (request.op === "reset") {
    if (!isPosition(request.start) || typeof request.yaw !== "number" || !Number.isFinite(request.yaw)) {
      throw new Error("reset requires a finite [x, y, z] start and yaw");
    }
    return player.reset(request.start, request.yaw);
  }
  if (request.op === "step") {
    const action = request.action;
    if (typeof action !== "string" || !Object.hasOwn(actions, action)) {
      throw new Error(`Unknown action: ${String(action)}`);
    }
    return player.step(actions[action as Action], TICKS_PER_ACTION);
  }
  throw new Error("Expected op reset or step");
}

export async function serve(
  player: Player,
  input: NodeJS.ReadableStream = process.stdin,
  output: NodeJS.WritableStream = process.stdout,
) {
  const lines = createInterface({ input, crlfDelay: Infinity });

  for await (const line of lines) {
    try {
      const result = await handle(player, JSON.parse(line));
      output.write(JSON.stringify({ result }) + "\n");
    } catch (error) {
      output.write(JSON.stringify({ error: error instanceof Error ? error.message : String(error) }) + "\n");
    }
  }
}
