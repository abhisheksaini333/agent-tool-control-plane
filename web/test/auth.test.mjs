import { test } from "node:test";
import assert from "node:assert/strict";
import { moduleFrom } from "./load.mjs";
const { AuthSession } = await moduleFrom("src/auth.ts");
const config = {
  authority: "http://localhost:8294/realms/keel",
  clientId: "keel-console",
  redirectUri: "http://localhost:5294/",
};
function storage() {
  const values = new Map();
  return {
    getItem: (k) => values.get(k) ?? null,
    setItem: (k, v) => values.set(k, v),
    removeItem: (k) => values.delete(k),
  };
}

test("login binds one-use state, nonce, age and S256 PKCE to fixed redirect", async () => {
  const store = storage();
  const session = new AuthSession(config, store);
  const url = new URL(await session.begin());
  assert.equal(url.searchParams.get("code_challenge_method"), "S256");
  assert.equal(url.searchParams.get("redirect_uri"), config.redirectUri);
  assert.equal(url.searchParams.get("response_type"), "code");
  assert.ok(url.searchParams.get("nonce"));
  await assert.rejects(
    session.finish(`${config.redirectUri}?code=x&state=wrong`),
    /Sign-in response/
  );
  assert.equal(store.getItem("keel.login"), null);
  await assert.rejects(
    session.finish(
      `${config.redirectUri}?code=x&state=${url.searchParams.get("state")}`
    ),
    /Sign-in response/
  );
});

test("duplicate callback parameters and expired sign-in cannot exchange a code", async () => {
  const store = storage();
  const session = new AuthSession(config, store);
  let url = new URL(await session.begin());
  await assert.rejects(
    session.finish(
      `${config.redirectUri}?code=a&code=b&state=${url.searchParams.get(
        "state"
      )}`
    ),
    /Sign-in response/
  );
  url = new URL(await session.begin());
  const pending = JSON.parse(store.getItem("keel.login"));
  pending.created -= 301000;
  store.setItem("keel.login", JSON.stringify(pending));
  await assert.rejects(
    session.finish(
      `${config.redirectUri}?code=a&state=${url.searchParams.get("state")}`
    ),
    /Sign-in response/
  );
});

async function fixture() {
  const pair = await crypto.subtle.generateKey(
    {
      name: "RSASSA-PKCS1-v1_5",
      modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]),
      hash: "SHA-256",
    },
    true,
    ["sign", "verify"]
  );
  const jwk = {
    ...(await crypto.subtle.exportKey("jwk", pair.publicKey)),
    kid: "one",
    use: "sig",
    alg: "RS256",
  };
  const store = storage();
  const session = new AuthSession(config, store);
  const url = new URL(await session.begin());
  async function token(extra = {}) {
    const head = Buffer.from(
      JSON.stringify({ alg: "RS256", kid: "one" })
    ).toString("base64url");
    const body = Buffer.from(
      JSON.stringify({
        iss: config.authority,
        aud: config.clientId,
        sub: "alice",
        nonce: url.searchParams.get("nonce"),
        exp: Date.now() / 1000 + 300,
        ...extra,
      })
    ).toString("base64url");
    const sig = await crypto.subtle.sign(
      "RSASSA-PKCS1-v1_5",
      pair.privateKey,
      new TextEncoder().encode(`${head}.${body}`)
    );
    return `${head}.${body}.${Buffer.from(sig).toString("base64url")}`;
  }
  return {
    store,
    session,
    token,
    jwk,
    callback: `${config.redirectUri}?code=code&state=${url.searchParams.get(
      "state"
    )}`,
  };
}

test("signed session keeps tokens in memory and logout ends the issuer session", async () => {
  const f = await fixture();
  const id = await f.token();
  globalThis.fetch = async (url) => ({
    ok: true,
    json: async () =>
      String(url).endsWith("/certs")
        ? { keys: [f.jwk] }
        : {
            access_token: "private-access",
            refresh_token: "private-refresh",
            id_token: id,
            expires_in: 300,
          },
  });
  await f.session.finish(f.callback);
  assert.equal(await f.session.accessToken(), "private-access");
  assert.equal(f.store.getItem("keel.login"), null);
  const logout = new URL(f.session.signOut());
  assert.equal(logout.searchParams.get("id_token_hint"), id);
  assert.equal(
    logout.searchParams.get("post_logout_redirect_uri"),
    config.redirectUri
  );
  await assert.rejects(f.session.accessToken(), /Sign in/);
});

test("ID token signature and nonce are checked before accepting access tokens", async () => {
  for (const scenario of ["nonce", "signature", "subject"]) {
    const f = await fixture();
    let id = await f.token(
      scenario === "nonce"
        ? { nonce: "wrong" }
        : scenario === "subject"
        ? { sub: undefined }
        : {}
    );
    if (scenario === "signature") {
      const parts = id.split(".");
      parts[2] = Buffer.alloc(256).toString("base64url");
      id = parts.join(".");
    }
    globalThis.fetch = async (url) => ({
      ok: true,
      json: async () =>
        String(url).endsWith("/certs")
          ? { keys: [f.jwk] }
          : { access_token: "private", id_token: id, expires_in: 300 },
    });
    await assert.rejects(f.session.finish(f.callback), /Invalid identity/);
    await assert.rejects(f.session.accessToken(), /Sign in/);
  }
});

test("refresh is single flight and a late response cannot revive a signed-out session", async () => {
  const f = await fixture();
  const id = await f.token();
  let exchanges = 0;
  let release;
  globalThis.fetch = async (url) => {
    if (String(url).endsWith("/certs"))
      return { ok: true, json: async () => ({ keys: [f.jwk] }) };
    exchanges++;
    if (exchanges > 1)
      await new Promise((resolve) => {
        release = resolve;
      });
    return {
      ok: true,
      json: async () => ({
        access_token: "access",
        refresh_token: "refresh",
        id_token: id,
        expires_in: 1,
      }),
    };
  };
  await f.session.finish(f.callback);
  const first = f.session.accessToken();
  const second = f.session.accessToken();
  assert.equal(exchanges, 2);
  f.session.clear();
  release();
  await assert.rejects(first, /signed out/);
  await assert.rejects(second, /signed out/);
  await assert.rejects(f.session.accessToken(), /Sign in/);
});
