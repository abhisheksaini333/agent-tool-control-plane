import { test } from "node:test";
import assert from "node:assert/strict";
import {
  fixture,
  AuthSession,
  config,
  storage,
} from "./maintenance-fixtures.mjs";
import { moduleFrom } from "./load.mjs";
test("caller abort is preserved separately from request timeout", async () => {
  const { fetchBounded } = await moduleFrom("src/transport.ts");
  let calls = 0;
  globalThis.fetch = async (url, options) => {
    calls++;
    if (options.signal.aborted)
      throw new DOMException("cancelled", "AbortError");
    return new Promise((resolve, reject) =>
      options.signal.addEventListener("abort", () =>
        reject(new DOMException("cancelled", "AbortError"))
      )
    );
  };
  const pre = new AbortController();
  pre.abort();
  await assert.rejects(
    fetchBounded("/api", { signal: pre.signal }, 20),
    (e) => e.name === "AbortError"
  );
  const active = new AbortController();
  const result = fetchBounded("/api", { signal: active.signal }, 20);
  active.abort();
  await assert.rejects(result, (e) => e.name === "AbortError");
  let removed = 0;
  const done = new AbortController();
  const original = done.signal.removeEventListener.bind(done.signal);
  done.signal.removeEventListener = (...args) => {
    removed++;
    original(...args);
  };
  globalThis.fetch = async () => ({ ok: true });
  await fetchBounded("/api", { signal: done.signal }, 20);
  assert.equal(removed, 1);
});
