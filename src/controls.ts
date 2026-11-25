import { createInterface } from "node:readline";

const actions = {
  idle: [],
  walk: ["forward"],
  run: ["forward", "sprint"],
  walk_jump: ["forward", "jump"],
  run_jump: ["forward", "sprint", "jump"],
  back: ["back"],
  sneak: ["sneak"],
  left: ["left"],
  right: ["right"],
  run_left: ["forward", "left", "sprint"],
} as const;

type Action = keyof typeof actions;
type Button = (typeof actions)[Action][number];
type Vec = readonly [x: number, y: number, z: number];
export type Frame = { position: Vec; velocity: Vec; on_ground: boolean };
export type ActionFrames = readonly [Frame] | readonly [Frame, Frame];
type StepTicks = 1 | 2;

type Request =
  | { op: "reset"; start: Vec; yaw: number }
  | { op: "step"; action: Action; yaw?: number; ticks: StepTicks };

type Reply = { result: Frame | ActionFrames } | { error: string };

interface Player {
  reset(start: Vec, yaw: number): Promise<Frame>;
  step(
    buttons: readonly Button[],
    yaw: number | undefined,
    ticks: StepTicks,
  ): Promise<ActionFrames>;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isPosition(value: unknown): value is Vec {
  return (
    Array.isArray(value) &&
    value.length === 3 &&
    isFiniteNumber(value[0]) &&
    isFiniteNumber(value[1]) &&
    isFiniteNumber(value[2])
  );
}

function isAction(value: unknown): value is Action {
  return typeof value === "string" && Object.hasOwn(actions, value);
}

function parseRequest(line: string): Request {
  const message: unknown = JSON.parse(line);
  if (
    typeof message !== "object" ||
    message === null ||
    Array.isArray(message)
  ) {
    throw new Error("Expected a JSON object");
  }

  if ("op" in message && message.op === "reset") {
    if (
      !("start" in message) ||
      !isPosition(message.start) ||
      !("yaw" in message) ||
      !isFiniteNumber(message.yaw)
    ) {
      throw new Error("reset requires a finite [x, y, z] start and yaw");
    }
    return { op: "reset", start: message.start, yaw: message.yaw };
  }
  if ("op" in message && message.op === "step") {
    const action = "action" in message ? message.action : undefined;
    if (!isAction(action)) {
      throw new Error(`Unknown action: ${String(action)}`);
    }
    const ticks = "ticks" in message ? message.ticks : 2;
    if (ticks !== 1 && ticks !== 2) {
      throw new Error("step ticks must be 1 or 2");
    }
    if ("yaw" in message) {
      if (!isFiniteNumber(message.yaw)) {
        throw new Error("step yaw must be a finite number");
      }
      return { op: "step", action, yaw: message.yaw, ticks };
    }
    return { op: "step", action, ticks };
  }
  throw new Error("Expected op reset or step");
}

async function handle(player: Player, line: string): Promise<Reply> {
  try {
    const request = parseRequest(line);
    switch (request.op) {
      case "reset":
        return { result: await player.reset(request.start, request.yaw) };
      case "step":
        return {
          result: await player.step(
            actions[request.action],
            request.yaw,
            request.ticks,
          ),
        };
    }
  } catch (error) {
    return { error: error instanceof Error ? error.message : String(error) };
  }
}

export async function serve(
  player: Player,
  input: NodeJS.ReadableStream = process.stdin,
  output: NodeJS.WritableStream = process.stdout,
): Promise<void> {
  const lines = createInterface({ input, crlfDelay: Infinity });

  for await (const line of lines) {
    const reply = await handle(player, line);
    output.write(`${JSON.stringify(reply)}\n`);
  }
}
