import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { createHash } from 'node:crypto';
import { apiLogin } from './auth-helpers';

const routes = [['inicio', 'Centro de análisis'], ['analisis', 'Análisis de datos'], ['fuentes', 'Fuentes abiertas'], ['geografia', 'Geolocalización'], ['fichas', 'Fichas de identificación']];
test.beforeAll(async ({ request }) => {
  const csrf = await apiLogin(request);
  const resources = await (await request.get('http://127.0.0.1:8000/api/resources')).json();
  const resource = resources.items.find((r: { name: string; folder: string }) => r.name === '6271218386.csv' && r.folder.includes('estructuracion'));
  expect(resource).toBeTruthy();
  expect((await request.post('http://127.0.0.1:8000/api/datasets/resource/' + resource.id, { headers: { 'X-CSRF-Token': csrf } })).ok()).toBeTruthy();
});
test.beforeEach(async ({ page }) => { await apiLogin(page.request); });

test('cinco vistas sin desbordamiento y con revisión automática de accesibilidad', async ({ page }, info) => {
  const failures: string[] = []; page.on('pageerror', error => failures.push(error.message));
  for (const [route, heading] of routes) {
    await page.goto('/#' + route);
    await expect(page.locator('main h1')).toHaveText(heading);
    if (route === 'analisis') {
      await expect(page.getByRole('heading', { name: 'Registro de eventos' })).toBeVisible();
      if (info.project.use.viewport!.width >= 768) await expect(page.getByLabel('Tipo de interacción')).toBeVisible();
      else {
        await page.locator('.filters summary').click();
        await expect(page.getByLabel('Tipo de interacción')).toBeVisible();
        await page.locator('.filters summary').click();
      }
    }
    if (route === 'geografia') await expect(page.getByRole('region', { name: /^Mapa interactivo/ })).toBeVisible();
    const overflow = await page.evaluate(() => ({ content: document.documentElement.scrollWidth, viewport: window.innerWidth }));
    expect(overflow.content, route).toBeLessThanOrEqual(overflow.viewport + 1);
    const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
    expect(accessibility.violations.map(v => `${v.id}: ${v.nodes.map(n => n.target.join(' ')).join(', ')}`), route).toEqual([]);
    await page.screenshot({ path: `../data/screenshots/${info.project.name}-${route}.png`, fullPage: true });
  }
  expect(failures).toEqual([]);
});

test('menú, teclado, tema y ampliación al 200 por ciento', async ({ page }, info) => {
  await page.goto('/');
  await expect(page.locator('main h1')).toHaveText('Centro de análisis');
  await page.keyboard.press('Tab'); await expect(page.getByRole('link', { name: 'Saltar al contenido' })).toBeFocused();
  await page.keyboard.press('Enter'); await expect(page.locator('main')).toBeFocused();
  if (info.project.use.viewport!.width < 1024) {
    await page.getByRole('button', { name: 'Abrir menú' }).tap();
    await expect(page.getByRole('dialog', { name: 'Menú de navegación' })).toBeVisible();
    await page.getByRole('dialog').getByRole('link', { name: /Análisis de datos/ }).tap();
  } else await page.getByRole('navigation').getByRole('link', { name: /Análisis de datos/ }).click();
  await expect(page.locator('main h1')).toHaveText('Análisis de datos');
  await page.getByRole('button', { name: 'Activar modo claro' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  const lightAudit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
  expect(lightAudit.violations.map(v => v.id)).toEqual([]);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
  const overflow = await page.evaluate(() => ({ content: document.documentElement.scrollWidth, viewport: window.innerWidth }));
  expect(overflow.content).toBeLessThanOrEqual(overflow.viewport + 1);
  await page.evaluate(() => { document.documentElement.style.zoom = ''; });
});

test('vínculos, mapa, evidencia con hash y ficha revisada exportable', async ({ page, request }, info) => {
  await page.goto('/#analisis');
  const filters = page.locator('.filters');
  if (!await filters.getAttribute('open').then(v => v !== null)) await filters.locator('summary').click();
  await page.getByLabel('Tipo de interacción').selectOption('VOZ ENTRANTE');
  await page.getByRole('button', { name: 'Aplicar', exact: true }).click();
  await expect(page.locator('.event-type').first()).toHaveText('VOZ ENTRANTE');
  await page.getByRole('button', { name: 'Limpiar', exact: true }).click();
  await expect(page.getByLabel('Tipo de interacción')).toHaveValue('');
  await page.getByRole('tab', { name: 'Red de vínculos' }).click();
  await page.getByRole('button', { name: 'Pantalla completa', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Red de interacciones' })).toBeVisible();
  await page.getByRole('button', { name: 'Acercar red' }).last().click();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: 'Red de interacciones' })).not.toBeVisible();
  await page.goto('/#geografia');
  await expect(page.getByRole('region', { name: /^Mapa interactivo/ })).toBeVisible();
  await page.getByRole('button', { name: 'Acercar mapa' }).click();
  await page.locator('.timeline-item').first().click();
  await expect(page.getByText('EVENTO SELECCIONADO')).toBeVisible();
  await page.goto('/#fuentes');
  const title = 'Fuente ficticia de prueba ' + info.project.name + ' ' + Date.now();
  await page.getByLabel('Título de la fuente').fill(title);
  await page.getByLabel('URL pública').fill('https://example.org/evidencia-ficticia');
  await page.getByRole('button', { name: 'Guardar fuente' }).click();
  const card = page.locator('.source-card').filter({ hasText: title });
  await card.locator('summary').click();
  const bytes = Buffer.from('Evidencia ficticia para prueba automatizada');
  await card.locator('input[type=file]').setInputFiles({ name: 'evidencia-ficticia.txt', mimeType: 'text/plain', buffer: bytes });
  await expect(card.getByText(createHash('sha256').update(bytes).digest('hex'))).toBeVisible();
  await page.goto('/#fichas');
  await page.getByRole('button', { name: 'Crear demostración ficticia' }).click();
  await page.getByLabel('Nombre completo').fill('Persona ficticia para pruebas');
  await page.getByRole('button', { name: 'Continuar', exact: true }).click();
  await page.getByRole('button', { name: 'Continuar', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Descargar PDF' })).toBeDisabled();
  await page.getByRole('checkbox', { name: /Confirmo que revisé/ }).check();
  await page.getByRole('button', { name: 'Guardar progreso' }).click();
  await expect(page.getByRole('button', { name: 'Descargar PDF' })).toBeEnabled();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Descargar PDF' }).click();
  expect((await downloaded).suggestedFilename()).toBe('centinela-ficha.pdf');
});
