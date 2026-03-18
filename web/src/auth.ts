import { fetchBounded } from "./transport";
export interface AuthConfig {
  authority: string;
  clientId: string;
  redirectUri: string;
}
interface PendingLogin {
  state: string;
  nonce: string;
  verifier: string;
  created: number;
}
interface Tokens {
  access_token: string;
  refresh_token?: string;
  id_token: string;
  expires_in: number;
}
const pendingKey = "keel.login";
const encoder = new TextEncoder();
const base64url = (bytes: Uint8Array) =>
  btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
const random = () => base64url(crypto.getRandomValues(new Uint8Array(32)));
function decode(value: string): Uint8Array {
  return Uint8Array.from(
    atob(value.replace(/-/g, "+").replace(/_/g, "/")),
    (c) => c.charCodeAt(0)
  );
}

/** Tokens live only in this object; only the one-use PKCE transaction survives redirects. */
export class AuthSession {
  private tokens?: Tokens;
  private expiresAt = 0;
  private subject?: string;
  private generation = 0;
  private refreshing?: Promise<string>;
  constructor(private config: AuthConfig, private storage: Storage) {}

  async begin(): Promise<string> {
    this.clear();
    const pending: PendingLogin = {
      state: random(),
      nonce: random(),
      verifier: random(),
      created: Date.now(),
    };
    this.storage.setItem(pendingKey, JSON.stringify(pending));
    const challenge = base64url(
      new Uint8Array(
        await crypto.subtle.digest("SHA-256", encoder.encode(pending.verifier))
      )
    );
    const url = new URL(
      `${this.config.authority}/protocol/openid-connect/auth`
    );
    url.search = new URLSearchParams({
      client_id: this.config.clientId,
      redirect_uri: this.config.redirectUri,
      response_type: "code",
      scope: "openid profile",
      state: pending.state,
      nonce: pending.nonce,
      code_challenge: challenge,
      code_challenge_method: "S256",
    }).toString();
    return url.toString();
  }

  async finish(callback: string): Promise<void> {
    const raw = this.storage.getItem(pendingKey);
    this.storage.removeItem(pendingKey);
    const url = new URL(callback);
    const target = new URL(this.config.redirectUri);
    let pending: PendingLogin | undefined;
    try {
      pending = raw ? JSON.parse(raw) : undefined;
    } catch {
      /* Reject corrupt transaction below. */
    }
    if (
      !pending ||
      typeof pending !== "object" ||
      ![pending.state, pending.nonce, pending.verifier].every(
        (value) =>
          typeof value === "string" && /^[A-Za-z0-9_-]{43}$/.test(value)
      ) ||
      url.origin !== target.origin ||
      url.pathname !== target.pathname ||
      url.searchParams.getAll("code").length !== 1 ||
      url.searchParams.getAll("state").length !== 1 ||
      !url.searchParams.get("code") ||
      url.searchParams.get("state") !== pending.state ||
      !Number.isFinite(pending.created) ||
      Date.now() - pending.created < 0 ||
      Date.now() - pending.created > 300000
    ) {
      throw new Error(
        "Sign-in response expired or did not match this browser. Sign in again."
      );
    }
    const generation = this.generation;
    const tokens = await this.exchange({
      grant_type: "authorization_code",
      code: url.searchParams.get("code")!,
      redirect_uri: this.config.redirectUri,
      code_verifier: pending.verifier,
    });
    const subject = await this.verifyIdToken(tokens.id_token, pending.nonce);
    if (generation !== this.generation)
      throw new Error("Sign-in was cancelled.");
    this.subject = subject;
    this.save(tokens);
  }

  private async exchange(fields: Record<string, string>): Promise<Tokens> {
    const response = await fetchBounded(
      `${this.config.authority}/protocol/openid-connect/token`,
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          client_id: this.config.clientId,
          ...fields,
        }),
        credentials: "omit",
      }
    );
    if (!response.ok) throw new Error("Your session expired. Sign in again.");
    const tokens = await response.json().catch(() => null);
    if (
      !tokens ||
      typeof tokens !== "object" ||
      Array.isArray(tokens) ||
      typeof tokens.access_token !== "string" ||
      !tokens.access_token.trim() ||
      typeof tokens.id_token !== "string" ||
      !tokens.id_token.trim() ||
      typeof tokens.expires_in !== "number" ||
      !Number.isFinite(tokens.expires_in) ||
      tokens.expires_in <= 0 ||
      tokens.expires_in > 86400 ||
      (tokens.refresh_token !== undefined &&
        (typeof tokens.refresh_token !== "string" ||
          !tokens.refresh_token.trim()))
    ) {
      throw new Error("Identity service returned an invalid session.");
    }
    return tokens;
  }

  private async verifyIdToken(token: string, nonce?: string): Promise<string> {
    if (token.length > 16384 || token.split(".").length !== 3)
      throw new Error("Invalid identity token.");
    const [head, payload, signature] = token.split(".");
    const header = JSON.parse(new TextDecoder().decode(decode(head)));
    const claims = JSON.parse(new TextDecoder().decode(decode(payload)));
    if (
      header.alg !== "RS256" ||
      typeof header.kid !== "string" ||
      header.kid.length > 128 ||
      typeof claims.sub !== "string" ||
      !claims.sub ||
      claims.iss !== this.config.authority ||
      ![claims.aud].flat().includes(this.config.clientId) ||
      (claims.azp !== undefined && claims.azp !== this.config.clientId) ||
      typeof claims.exp !== "number" ||
      claims.exp <= Date.now() / 1000 ||
      (nonce !== undefined && claims.nonce !== nonce)
    )
      throw new Error("Invalid identity token.");
    const response = await fetchBounded(
      `${this.config.authority}/protocol/openid-connect/certs`,
      { credentials: "omit" }
    );
    if (!response.ok) throw new Error("Identity verification is unavailable.");
    const { keys } = await response.json();
    if (!Array.isArray(keys) || keys.length > 32)
      throw new Error("Invalid signing keys.");
    const matches = keys.filter(
      (k) =>
        k.kid === header.kid &&
        k.kty === "RSA" &&
        k.use === "sig" &&
        k.alg === "RS256"
    );
    if (matches.length !== 1)
      throw new Error("Identity signing key is unavailable.");
    const key = await crypto.subtle.importKey(
      "jwk",
      matches[0],
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
      false,
      ["verify"]
    );
    if (
      !(await crypto.subtle.verify(
        "RSASSA-PKCS1-v1_5",
        key,
        decode(signature),
        encoder.encode(`${head}.${payload}`)
      ))
    ) {
      throw new Error("Invalid identity signature.");
    }
    return claims.sub;
  }

  private save(tokens: Tokens): void {
    this.tokens = tokens;
    this.expiresAt = Date.now() + tokens.expires_in * 1000;
  }

  async accessToken(): Promise<string> {
    if (!this.tokens) throw new Error("Sign in to continue.");
    if (Date.now() + 30000 < this.expiresAt) return this.tokens.access_token;
    if (!this.tokens.refresh_token)
      throw new Error("Your session expired. Sign in again.");
    if (!this.refreshing) {
      const generation = this.generation;
      const refreshToken = this.tokens.refresh_token;
      this.refreshing = (async () => {
        const tokens = await this.exchange({
          grant_type: "refresh_token",
          refresh_token: refreshToken,
        });
        const subject = await this.verifyIdToken(tokens.id_token);
        if (subject !== this.subject && generation === this.generation)
          throw new Error("Identity changed during refresh. Sign in again.");
        if (generation !== this.generation)
          throw new Error("Session was signed out.");
        this.save(tokens);
        return tokens.access_token;
      })()
        .catch((error) => {
          if (generation === this.generation) this.clear();
          throw error;
        })
        .finally(() => {
          if (generation === this.generation) this.refreshing = undefined;
        });
    }
    return this.refreshing;
  }

  signOut(): string {
    const hint = this.tokens?.id_token;
    this.clear();
    const url = new URL(
      `${this.config.authority}/protocol/openid-connect/logout`
    );
    url.search = new URLSearchParams({
      client_id: this.config.clientId,
      post_logout_redirect_uri: this.config.redirectUri,
      ...(hint ? { id_token_hint: hint } : {}),
    }).toString();
    return url.toString();
  }

  clear(): void {
    this.generation++;
    this.tokens = undefined;
    this.subject = undefined;
    this.refreshing = undefined;
    this.expiresAt = 0;
    this.storage.removeItem(pendingKey);
  }
}
