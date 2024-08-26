import { test, expect } from '@playwright/test';
export async function signIn(page: import('@playwright/test').Page, username: string) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Sign in to workspace' }).click();
  await page.locator('#username').fill(username);
  await page.locator('#password').fill('keel-demo-password');
  await page.locator('#kc-login').click();
  await expect(page.getByRole('heading', { name: 'Action desk', exact: true })).toBeVisible();
}
test('real OIDC sign-in and issuer logout require credentials for the next user', async ({ page }) => {
  await signIn(page, 'alice');
  await expect(page.getByText('Alice Chen', { exact: true }).first()).toBeVisible();
  const storage = await page.evaluate(() => ({local:{...localStorage},session:{...sessionStorage}}));
  expect(JSON.stringify(storage)).not.toMatch(/access_token|refresh_token|id_token|private-access/);
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await page.getByRole('button', { name: 'Sign in to workspace' }).click();
  await expect(page.locator('#username')).toBeVisible();
});
