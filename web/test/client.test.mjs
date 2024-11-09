import { test } from "node:test";
import assert from "node:assert/strict";
import { moduleFrom } from "./load.mjs";
const { ApiClient, ApiError } = await moduleFrom("src/client.ts");
test("mutations send only current bearer authority and explicit idempotency key", async () => {
  let options;
  globalThis.fetch = async (url, input) => {
    assert.equal(url, "http://localhost:5484/api/requests");
    options = input;
    return { ok: true, json: async () => ({ id: "one" }) };
  };
  const client = new ApiClient("http://localhost:5484", {
    accessToken: async () => "current",
  });
  assert.equal(
    (
      await client.post(
        "/api/requests",
        { tool: "text.digest" },
        "stable-retry-key"
      )
    ).id,
    "one"
  );
  assert.equal(options.headers.Authorization, "Bearer current");
  assert.equal(options.headers["Idempotency-Key"], "stable-retry-key");
  assert.equal(options.credentials, "omit");
});
test("HTTP conflicts expose actionable server errors without automatic mutation retries", async () => {
  let count = 0;
  globalThis.fetch = async () => {
    count++;
    return {
      ok: false,
      status: 409,
      json: async () => ({ message: "Request changed; refresh it" }),
    };
  };
  const client = new ApiClient("http://localhost:5484", {
    accessToken: async () => "current",
  });
  await assert.rejects(
    client.post("/api/requests/one/approval", {}),
    (error) =>
      error instanceof ApiError &&
      error.status === 409 &&
      error.message === "Request changed; refresh it"
  );
  assert.equal(count, 1);
});
