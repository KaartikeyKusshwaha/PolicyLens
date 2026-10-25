import { afterEach, expect, test, vi } from "vitest";
import { api } from "./api";
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

test("stalled reads time out with a retryable message", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch",vi.fn((url,{signal}) => new Promise((resolve,reject) => {
    signal.addEventListener("abort",() => reject(new DOMException("Aborted","AbortError")));
  })));
  const result = api("/auth/status");
  const assertion = expect(result).rejects.toThrow("taking too long to respond");
  await vi.advanceTimersByTimeAsync(20000);
  await assertion;
});

test("navigation cancellation is preserved instead of reported as timeout", async () => {
  vi.stubGlobal("fetch",vi.fn((url,{signal}) => new Promise((resolve,reject) => {
    signal.addEventListener("abort",() => reject(new DOMException("Aborted","AbortError")));
  })));
  const controller = new AbortController();
  const result = api("/cases",{signal:controller.signal});
  const assertion = expect(result).rejects.toHaveProperty("name","AbortError");
  controller.abort(); await assertion;
});
