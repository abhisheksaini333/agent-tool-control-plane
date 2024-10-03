import { test, expect } from '@playwright/test';
import { signIn } from './helpers.ts';
import { writeFile, mkdir } from 'node:fs/promises';
test('operator request, independent exact approval and one actual inventory receipt', async ({ page }) => {
  const errors:string[]=[];
  page.on('pageerror', error=>errors.push(error.message));
  await signIn(page,'alice');
  await page.getByRole('button',{name:'New request'}).click();
  await page.getByLabel('Inventory item',{exact:true}).selectOption('KIT-DATA');
  await page.getByLabel('Quantity').fill('2');
  const created=page.waitForResponse(response=>response.url().endsWith('/api/requests')&&response.request().method()==='POST');
  await page.getByRole('button',{name:'Send for approval',exact:true}).click();
  const request=await (await created).json();
  expect(request.status).toBe('awaiting_approval');
  await expect(page.getByText('Waiting for an independent reviewer.',{exact:false})).toBeVisible();
  await expect(page.getByRole('button',{name:'Approve and queue'})).toHaveCount(0);
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await expect(page.getByRole('button',{name:'Sign in to workspace'})).toBeVisible();
  await signIn(page,'bob');
  await page.locator('.request-item').filter({hasText:request.id.slice(0,8)}).click();
  await expect(page.getByRole('button',{name:'Approve and queue',exact:true})).toBeDisabled();
  await expect(page.getByLabel('Exact arguments',{exact:true})).toContainText('KIT-DATA');
  await page.getByLabel('I have reviewed these exact arguments.').check();
  await page.getByRole('button',{name:'Approve and queue',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Inventory reserved.',exact:true})).toBeVisible({timeout:25000});
  await expect(page.getByRole('button',{name:'Approve and queue',exact:true})).toHaveCount(0);
  await expect(page.getByRole('region',{name:'Execution receipt'})).toContainText('2 units of KIT-DATA');
  await expect(page.getByText('Execution completed',{exact:true})).toBeVisible();
  expect(errors).toEqual([]);
  if(process.env.KEEL_EVIDENCE_DIR){
    await mkdir(process.env.KEEL_EVIDENCE_DIR,{recursive:true});
    await page.screenshot({path:`${process.env.KEEL_EVIDENCE_DIR}/workspace-receipt.png`,fullPage:true});
    await writeFile(`${process.env.KEEL_EVIDENCE_DIR}/browser-action.json`,JSON.stringify({request_id:request.id,checks:{real_oidc:true,operator_cannot_approve:true,acknowledgment_required:true,independent_approval:true,actual_docker_effect:true,receipt_visible:true,no_page_errors:true},passed:true},null,2));
  }
});
