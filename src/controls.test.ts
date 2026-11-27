import assert from "node:assert/strict";
import { Readable, Writable } from "node:stream";
import { test } from "node:test";
import { type Frame, serve } from "./controls.ts";

test("validates requests and keeps serving in order after errors", async () => {
  const reset: Frame = {
    position: [1, 2, 3],
    velocity: [0, 0, 0],
    on_ground: true,
  };
  const airborne: Frame = {
    position: [1, 3, 3],
    velocity: [0, 1, 0],
    on_ground: false,
  };
  const input = Readable.from([
    'null\n{"op":"reset","start":[1,2,"3"],"yaw":0}\n',
    '{"op":"step","action":"__proto__"}\n{"op":"reset","start":[1,2,3],"yaw":90}\n',
    '{"op":"step","action":"idle"}\n{"op":"step","action":"run_jump","yaw":null}\n{"op":"step","action":"run_jump","yaw":90}',
  ]);
  const replies: unknown[] = [];
  const output = new Writable({
    write(chunk: Buffer, _encoding, done) {
      replies.push(JSON.parse(chunk.toString()));
      done();
    },
  });

  await serve(
    {
      async reset(start, yaw) {
        assert.deepEqual(start, [1, 2, 3]);
        assert.equal(yaw, 90);
        return reset;
      },
      async step(buttons, yaw) {
        if (buttons.length === 0) throw new Error("Physics timed out");
        assert.deepEqual(buttons, ["forward", "sprint", "jump"]);
        assert.equal(yaw, 90);
        return [reset, airborne];
      },
    },
    input,
    output,
  );

  assert.deepEqual(replies, [
    { error: "Expected a JSON object" },
    { error: "reset requires a finite [x, y, z] start and yaw" },
    { error: "Unknown action: __proto__" },
    { result: reset },
    { error: "Physics timed out" },
    { error: "step yaw must be a finite number" },
    { result: [reset, airborne] },
  ]);
});
