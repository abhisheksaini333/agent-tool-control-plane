import { test } from "node:test";
import assert from "node:assert/strict";
import { moduleFrom } from "./load.mjs";
const { fetchBounded } = await moduleFrom("src/transport.ts");
test("stalled browser requests abort within their configured budget", async () => {
  let signal;
  globalThis.fetch = async (url, options) =>
    new Promise((resolve, reject) => {
      signal = options.signal;
      signal.addEventListener("abort", () =>
        reject(new DOMException("aborted", "AbortError"))
      );
    });
  await assert.rejects(
    fetchBounded("http://localhost:5484", {}, 5),
    /timed out/
  );
  assert.equal(signal.aborted, true);
});
