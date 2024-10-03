import { expect } from '@playwright/test';
export async function signIn(page: import('@playwright/test').Page, username: string) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Sign in to workspace' }).click();
  await page.locator('#username').fill(username);
  await page.locator('#password').fill('keel-demo-password');
  await page.locator('#kc-login').click();
  await expect(page.getByRole('heading', { name: 'Action desk', exact: true })).toBeVisible();
}
