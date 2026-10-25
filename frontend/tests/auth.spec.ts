import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { randomBytes } from 'node:crypto';
import { apiLogin, credentials, uiLogin } from './auth-helpers';

test('acceso privado, login accesible y cierre de sesión', async ({ page }, info) => {
  await page.goto('/#fichas');
  await expect(page.getByRole('heading', { name: 'Inicia sesión', exact: true })).toBeVisible();
  await expect(page).toHaveURL(/#acceso$/);
  await expect(page.getByRole('heading', { name: 'Fichas de identificación', exact: true })).not.toBeVisible();
  const input = page.getByLabel('Contraseña', { exact: true });
  await page.getByRole('button', { name: 'Mostrar contraseña' }).click(); await expect(input).toHaveAttribute('type', 'text');
  await page.getByRole('button', { name: 'Ocultar contraseña' }).click(); await expect(input).toHaveAttribute('type', 'password');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
  expect(audit.violations.map(v => v.id)).toEqual([]);
  await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
  await page.evaluate(() => { document.documentElement.style.zoom = ''; });
  await page.screenshot({ path: `../data/screenshots/${info.project.name}-login.png`, fullPage: true });
  await page.getByLabel('Nombre de usuario', { exact: true }).fill(credentials().username);
  await input.fill(randomBytes(24).toString('base64url'));
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Usuario o contraseña incorrectos.');
  await uiLogin(page);
  await expect(page.locator('main h1')).toHaveText('Fichas de identificación');
  const stored = await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage }, readableCookies: document.cookie }));
  expect(JSON.stringify(stored)).not.toContain(credentials().password);
  expect(stored.readableCookies).not.toContain('c360_session');
  expect(Object.keys(stored.local).filter(k => /token|password|session|csrf/i.test(k))).toEqual([]);
  await page.getByLabel('Menú de cuenta').click();
  await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Inicia sesión', exact: true })).toBeVisible();
  expect((await page.request.get('/api/dossiers')).status()).toBe(401);
  await expect(page).toHaveURL(/#acceso$/);
  expect((await page.request.get('/api/files/no-existe')).status()).toBe(401);
});

test('gestión de usuarios y bloqueo de permisos de analista', async ({ page, browser }, info) => {
  await apiLogin(page.request); await page.goto('/#usuarios');
  await expect(page.locator('main h1')).toHaveText('Gestión de usuarios');
  const username = 'analista-' + info.project.name + '-' + Date.now(); const password = randomBytes(24).toString('base64url');
  await page.getByLabel('Nombre del nuevo usuario').fill(username);
  await page.getByLabel('Contraseña inicial').fill(password);
  await page.getByRole('button', { name: 'Crear usuario', exact: true }).click();
  const card = page.locator('.managed-user').filter({ hasText: username });
  await expect(card).toBeVisible();
  const context = await browser.newContext({ viewport: info.project.use.viewport, hasTouch: info.project.use.hasTouch, isMobile: info.project.use.isMobile });
  const analyst = await context.newPage();
  try {
    await analyst.goto('/#usuarios'); await uiLogin(analyst, { username, password });
    await expect(analyst.getByText('No tienes permiso para administrar usuarios.')).toBeVisible();
    expect((await analyst.request.get('/api/users')).status()).toBe(403);
    const state = await (await analyst.request.get('/api/auth/session')).json();
    const forbidden = await analyst.request.post('/api/users', { data: { username: 'escalada-no-permitida', password: randomBytes(24).toString('base64url'), role: 'administrador' }, headers: { 'X-CSRF-Token': state.csrf_token } });
    expect(forbidden.status()).toBe(403);
    await analyst.goto('/#analisis'); await expect(analyst.locator('main h1')).toHaveText('Análisis de datos');
    await card.getByLabel('Cuenta activa').uncheck();
    await card.getByRole('button', { name: 'Guardar cambios' }).click();
    await expect(card.getByText('Inactivo', { exact: true })).toBeVisible();
    await analyst.getByRole('button', { name: 'Importar recurso', exact: true }).click();
    await expect(analyst.getByRole('heading', { name: 'Inicia sesión', exact: true })).toBeVisible();
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
    expect(results.violations.map(v => v.id)).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    await page.screenshot({ path: `../data/screenshots/${info.project.name}-usuarios.png`, fullPage: true });
  } finally { await context.close(); }
});

test('sesión revocada redirige al acceso sin conservar el módulo', async ({ page }) => {
  await apiLogin(page.request); await page.goto('/#analisis');
  await expect(page.getByRole('heading', { name: 'Registro de eventos' })).toBeVisible();
  const session = await (await page.request.get('/api/auth/session')).json();
  expect((await page.request.post('/api/auth/logout', { headers: { 'X-CSRF-Token': session.csrf_token } })).ok()).toBeTruthy();
  await page.getByRole('button', { name: 'Exportar CSV', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Inicia sesión', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Registro de eventos' })).not.toBeVisible();
  await expect(page).toHaveURL(/#acceso$/);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Inicia sesión', exact: true })).toBeVisible();
});

test('cambio de contraseña propia cierra sesiones y permite el nuevo acceso', async ({ page }, info) => {
  const csrf = await apiLogin(page.request);
  const username = 'cuenta-' + info.project.name + '-' + Date.now();
  const password = randomBytes(24).toString('base64url'); const next = randomBytes(24).toString('base64url');
  expect((await page.request.post('/api/users', { data: { username, password, role: 'analista' }, headers: { 'X-CSRF-Token': csrf } })).status()).toBe(200);
  await page.request.post('/api/auth/logout', { headers: { 'X-CSRF-Token': csrf } });
  await page.goto('/#cuenta'); await uiLogin(page, { username, password });
  await expect(page.locator('main h1')).toHaveText('Cambiar contraseña');
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
  expect(audit.violations.map(v => v.id)).toEqual([]);
  await page.screenshot({ path: `../data/screenshots/${info.project.name}-cuenta.png`, fullPage: true });
  await page.getByLabel('Contraseña actual', { exact: true }).fill(password);
  await page.getByLabel(/^Nueva contraseña/).fill(next);
  await page.getByLabel('Confirmar nueva contraseña', { exact: true }).fill(next);
  await page.getByRole('button', { name: 'Guardar nueva contraseña', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Inicia sesión', exact: true })).toBeVisible();
  await expect(page).toHaveURL(/#acceso$/);
  await page.getByLabel('Nombre de usuario', { exact: true }).fill(username);
  await page.getByLabel('Contraseña', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Usuario o contraseña incorrectos.');
  await uiLogin(page, { username, password: next });
  await expect(page.locator('main h1')).toHaveText('Cambiar contraseña');
});
