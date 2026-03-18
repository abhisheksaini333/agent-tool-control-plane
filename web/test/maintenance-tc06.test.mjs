import { test } from "node:test";
import assert from "node:assert/strict";
import {
  fixture,
  AuthSession,
  config,
  storage,
} from "./maintenance-fixtures.mjs";
import { moduleFrom } from "./load.mjs";
test("invalid identity service token envelopes have a controlled session error", async () => {
  const session = new AuthSession(config, storage());
  for (const value of [
    null,
    [],
    { access_token: "", id_token: "x", expires_in: 300 },
    { access_token: "a", id_token: "x", expires_in: NaN },
    { access_token: "a", id_token: "x", expires_in: 300, refresh_token: "" },
  ]) {
    globalThis.fetch = async () => ({ ok: true, json: async () => value });
    await assert.rejects(
      session.exchange({ grant_type: "refresh_token" }),
      /invalid session/
    );
  }
});
