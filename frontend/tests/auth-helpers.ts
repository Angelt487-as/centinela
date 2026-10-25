import { expect, type APIRequestContext, type Page } from '@playwright/test';

export function credentials(role: 'admin' | 'analyst' = 'admin') {
  const prefix = role === 'admin' ? 'C360_TEST_ADMIN' : 'C360_TEST_ANALYST';
  const username = process.env[prefix + '_USER']; const password = process.env[prefix + '_PASSWORD'];
  if (!username || !password) throw new Error('Ejecuta scripts/probar_interfaz.py para generar cuentas de prueba aisladas.');
  return { username, password };
}

export async function apiLogin(request: APIRequestContext, role: 'admin' | 'analyst' = 'admin') {
  const challenge = await (await request.get('http://127.0.0.1:8000/api/auth/csrf')).json();
  const result = await request.post('http://127.0.0.1:8000/api/auth/login', { data: credentials(role), headers: { 'X-CSRF-Token': challenge.csrf_token } });
  expect(result.status(), 'La cuenta efímera debe iniciar sesión').toBe(200);
  return (await result.json()).csrf_token as string;
}

export async function uiLogin(page: Page, values = credentials()) {
  await page.getByLabel('Nombre de usuario', { exact: true }).fill(values.username);
  await page.getByLabel('Contraseña', { exact: true }).fill(values.password);
  await expect(page.getByRole('button', { name: 'Iniciar sesión', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Inicia sesión', exact: true })).not.toBeVisible();
}
