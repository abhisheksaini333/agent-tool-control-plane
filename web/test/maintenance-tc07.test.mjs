import { test } from "node:test";
import assert from "node:assert/strict";
import {
  fixture,
  AuthSession,
  config,
  storage,
} from "./maintenance-fixtures.mjs";
import { moduleFrom } from "./load.mjs";
test("malformed identity envelopes and nonfinite expiration fail before key lookup", async () => {
  const session = new AuthSession(config, storage());
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    throw Error("unexpected key lookup");
  };
  const b64 = (value) => Buffer.from(value).toString("base64url");
  for (const [head, body] of [
    ["null", "{}"],
    ['{"alg":"RS256","kid":"one"}', "null"],
    [
      '{"alg":"RS256","kid":"one"}',
      `{"sub":"alice","iss":"${config.authority}","aud":"${config.clientId}","exp":1e999}`,
    ],
  ]) {
    await assert.rejects(
      session.verifyIdToken(`${b64(head)}.${b64(body)}.eA`),
      /Invalid identity/
    );
  }
  assert.equal(calls, 0);
  const f = await fixture();
  const id = await f.token();
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({ keys: [null] }),
  });
  await assert.rejects(f.session.verifyIdToken(id), /signing key/);
});
