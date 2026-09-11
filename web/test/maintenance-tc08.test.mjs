import { test } from "node:test";
import assert from "node:assert/strict";
import {
  fixture,
  AuthSession,
  config,
  storage,
} from "./maintenance-fixtures.mjs";
import { moduleFrom } from "./load.mjs";
test("nonrotating refresh tokens survive multiple signed refresh responses", async () => {
  const f = await fixture();
  const id = await f.token();
  const supplied = [];
  let exchanges = 0;
  globalThis.fetch = async (url, options) => {
    if (String(url).endsWith("/certs"))
      return { ok: true, json: async () => ({ keys: [f.jwk] }) };
    exchanges++;
    if (exchanges > 1) supplied.push(options.body.get("refresh_token"));
    return {
      ok: true,
      json: async () => ({
        access_token: `access-${exchanges}`,
        id_token: id,
        expires_in: 1,
        ...(exchanges === 1
          ? { refresh_token: "original" }
          : exchanges === 3
          ? { refresh_token: "rotated" }
          : {}),
      }),
    };
  };
  await f.session.finish(f.callback);
  assert.equal(await f.session.accessToken(), "access-2");
  assert.equal(await f.session.accessToken(), "access-3");
  assert.equal(await f.session.accessToken(), "access-4");
  assert.deepEqual(supplied, ["original", "original", "rotated"]);
});
