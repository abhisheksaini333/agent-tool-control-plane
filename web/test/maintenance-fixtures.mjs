import { moduleFrom } from "./load.mjs";
const { AuthSession } = await moduleFrom("src/auth.ts");
export const config = {
  authority: "http://localhost:8294/realms/keel",
  clientId: "keel-console",
  redirectUri: "http://localhost:5294/",
};
export function storage() {
  const values = new Map();
  return {
    getItem: (k) => values.get(k) ?? null,
    setItem: (k, v) => values.set(k, v),
    removeItem: (k) => values.delete(k),
  };
}
export { AuthSession };
export async function fixture() {
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
