import { test, expect, Page } from '@playwright/test';
import { resolve } from 'node:path';

async function openAI(page: Page) {
  await page.goto('/');
  if ((page.viewportSize()?.width ?? 1600) < 768) {
    await page.getByRole('button', { name: 'Collapse sidebar', exact: true }).click();
  }
  await page.getByRole('tab', { name: '3B Ay küresi', exact: true }).click();
  await page.locator('iframe[title$=".lunar_sight"]').scrollIntoViewIfNeeded({ timeout: 45_000 });
  const globe = page.frameLocator('iframe[title$=".lunar_sight"]');
  await globe.getByRole('button', { name: 'LunarSight AI', exact: true }).click();
  const dialog = globe.getByRole('dialog');
  await expect(dialog.getByRole('button', { name: 'Yüzeyi analiz et', exact: true })).toBeEnabled();
  await page.locator('iframe[title$=".lunar_sight"]').evaluate(element => element.scrollIntoView({ block: 'center' }));
  return { globe, dialog };
}

test('existing LunarSight AI prepares real DEM, capture and upload through Python bridge', async ({ page }) => {
  const { globe, dialog } = await openAI(page);
  await expect(dialog.locator('canvas')).toHaveJSProperty('width', 801);
  await expect(dialog).toContainText('LOLA DEM hillshade');
  await expect(dialog).not.toContainText('Moondream');
  await expect(dialog).toContainText('nvidia/nemotron-3.5-super-vl-120b-a12b');
  await page.screenshot({ path: '../data/cache/lunar_ai_dem.png', fullPage: true });
  await dialog.getByRole('button', { name: '3B Sahneyi Yakala' }).click();
  await expect(dialog).toContainText('3B görünümden alınan kare');
  await expect(dialog.getByRole('button', { name: 'Yüzeyi analiz et', exact: true })).toBeEnabled();
  await dialog.locator('input[type=file]').setInputFiles(resolve('../app/static/moon/textures/moon_trek_wac_2k.jpg'));
  await expect(dialog).toContainText('Kullanıcı yüklemesi');
  await expect(dialog.locator('canvas')).toHaveJSProperty('width', 1024);
  await dialog.getByRole('button', { name: 'LunarSight AI penceresini kapat' }).click();
  await globe.getByRole('button', { name: /Shackleton Rim.*Site04/ }).click();
  await globe.getByRole('button', { name: 'LunarSight AI', exact: true }).click();
  await expect(dialog).toContainText('Site04_final_adj_5mpp_surf.tif');
  await expect(dialog).not.toContainText('Kullanıcı yüklemesi');
});

test('live model analysis and follow-up come back into the existing modal', async ({ page }) => {
  test.skip(process.env.LUNA_LIVE_AI !== '1', 'Explicit live API smoke run only');
  const { dialog } = await openAI(page);
  await dialog.getByRole('button', { name: 'Yüzeyi analiz et', exact: true }).click();
  await expect(dialog).toContainText('Gerçek model yanıtı alındı.', { timeout: 120_000 });
  await expect(dialog.getByRole('button', { name: 'Analiz JSON indir' })).toBeVisible();
  await dialog.getByText('Kayıtlı bilimsel ölçümler · K2/K3', { exact: true }).click();
  await expect(dialog).toContainText('-0.372568');
  await page.screenshot({ path: '../data/cache/lunar_ai_live_result.png', fullPage: true });
  await dialog.getByRole('tab', { name: 'Soru-Cevap', exact: true }).click();
  await dialog.getByRole('textbox', { name: 'Görüntü hakkında sorunuz' }).fill('Bu görüntü gerçek bir fotoğraf mı? İki kısa cümleyle açıkla.');
  await dialog.getByRole('button', { name: 'Soruyu gönder' }).click();
  await expect(dialog.getByText('LunarSight AI', { exact: true })).toHaveCount(2, { timeout: 100_000 });
  await expect(dialog.getByRole('alert')).toHaveCount(0);
  await page.screenshot({ path: '../data/cache/lunar_ai_followup.png', fullPage: true });
});

test('LunarSight AI remains reachable on a phone-sized screen', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { dialog } = await openAI(page);
  await expect(dialog).toContainText('LOLA DEM hillshade');
  expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBeTruthy();
  await dialog.getByRole('button', { name: 'LunarSight AI penceresini kapat' }).click();
  await expect(dialog).not.toBeVisible();
});
