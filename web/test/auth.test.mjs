import { test } from 'node:test';
import assert from 'node:assert/strict';
import { moduleFrom } from './load.mjs';
const { AuthSession } = await moduleFrom('src/auth.ts');
const config = { authority: 'http://localhost:8294/realms/keel', clientId: 'keel-console', redirectUri: 'http://localhost:5294/' };
function storage() { const values = new Map(); return { getItem: k => values.get(k) ?? null, setItem: (k,v) => values.set(k,v), removeItem: k => values.delete(k) }; }

test('login binds one-use state, nonce, age and S256 PKCE to fixed redirect', async () => {
  const store = storage(); const session = new AuthSession(config, store);
  const url = new URL(await session.begin());
  assert.equal(url.searchParams.get('code_challenge_method'), 'S256');
  assert.equal(url.searchParams.get('redirect_uri'), config.redirectUri);
  assert.equal(url.searchParams.get('response_type'), 'code');
  assert.ok(url.searchParams.get('nonce'));
  await assert.rejects(session.finish(`${config.redirectUri}?code=x&state=wrong`), /Sign-in response/);
  assert.equal(store.getItem('keel.login'), null);
  await assert.rejects(session.finish(`${config.redirectUri}?code=x&state=${url.searchParams.get('state')}`), /Sign-in response/);
});

test('duplicate callback parameters and expired sign-in cannot exchange a code', async () => {
  const store = storage(); const session = new AuthSession(config, store);
  let url = new URL(await session.begin());
  await assert.rejects(session.finish(`${config.redirectUri}?code=a&code=b&state=${url.searchParams.get('state')}`), /Sign-in response/);
  url = new URL(await session.begin());
  const pending = JSON.parse(store.getItem('keel.login')); pending.created -= 301000;
  store.setItem('keel.login', JSON.stringify(pending));
  await assert.rejects(session.finish(`${config.redirectUri}?code=a&state=${url.searchParams.get('state')}`), /Sign-in response/);
});
