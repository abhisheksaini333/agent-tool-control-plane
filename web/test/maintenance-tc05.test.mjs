import { test } from "node:test";
import assert from "node:assert/strict";
import {
  fixture,
  AuthSession,
  config,
  storage,
} from "./maintenance-fixtures.mjs";
import { moduleFrom } from "./load.mjs";
test("incomplete stored PKCE transaction cannot exchange a code", async () => {
  for (const field of ["state", "nonce", "verifier"]) {
    const f = await fixture();
    const pending = JSON.parse(f.store.getItem("keel.login"));
    delete pending[field];
    f.store.setItem("keel.login", JSON.stringify(pending));
    let calls = 0;
    globalThis.fetch = async () => {
      calls++;
      throw Error("unexpected network");
    };
    await assert.rejects(f.session.finish(f.callback), /Sign-in response/);
    assert.equal(calls, 0);
  }
});
