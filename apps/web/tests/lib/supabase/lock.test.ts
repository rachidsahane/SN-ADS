import { describe, expect, it } from "vitest";

import { serialLock } from "@/lib/supabase/lock";

const tick = () => new Promise((resolve) => setTimeout(resolve, 5));

describe("serialLock", () => {
  it("returns the value of the operation", async () => {
    await expect(serialLock("lock:test", -1, async () => 42)).resolves.toBe(42);
  });

  it("runs concurrent operations one after the other, in call order", async () => {
    const events: string[] = [];
    const first = serialLock("lock:test", -1, async () => {
      events.push("first:start");
      await tick();
      events.push("first:end");
    });
    const second = serialLock("lock:test", 0, async () => {
      events.push("second:start");
    });
    await Promise.all([first, second]);
    expect(events).toEqual(["first:start", "first:end", "second:start"]);
  });

  it("never fails because the lock is busy (no acquire timeout, unlike the Navigator lock)", async () => {
    const slow = serialLock("lock:test", -1, async () => tick());
    await expect(serialLock("lock:test", 0, async () => "ran")).resolves.toBe("ran");
    await slow;
  });

  it("keeps working after an operation failed, and reports that failure to its own caller", async () => {
    const failing = serialLock("lock:test", -1, async () => {
      throw new Error("boom");
    });
    await expect(failing).rejects.toThrow("boom");
    await expect(serialLock("lock:test", -1, async () => "next")).resolves.toBe("next");
  });
});
