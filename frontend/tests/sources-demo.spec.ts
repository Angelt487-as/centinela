import { test, expect, type Download, type Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { apiLogin } from './auth-helpers';

const originalTitle = 'LIMITANTES LEGALES PARA FUENTES ABIERTAS';
const originalName = originalTitle + '.docx';
// Digest independently calculated from the unmodified DOCX entry in the supplied ZIP.
const originalSha256 = 'f13f12669877ee3c99b51ad0718770a925bd64fc17ade01cba02d4d9831e0107';

type DemoRecord = {
  id: string;
  title: string;
  description: string;
  source_type: string;
  document_type: string;
  provenance: string;
  created_at: string;
  url: string | null;
  observed_at: string | null;
  is_demo: boolean;
  evidence: { id: string; name: string; sha256: string }[];
};

async function downloadedBytes(download: Download) {
  const path = await download.path();
  expect(path, 'La descarga debe existir en el equipo de pruebas').toBeTruthy();
  return readFile(path!);
}

function csvRows(content: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [], field = '', quoted = false;
  const text = content.replace(/^\uFEFF/, '');
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (quoted) {
      if (char === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (char === '"') quoted = false;
      else field += char;
    } else if (char === '"') quoted = true;
    else if (char === ',') { row.push(field); field = ''; }
    else if (char === '\r' || char === '\n') {
      if (char === '\r' && text[i + 1] === '\n') i++;
      row.push(field); rows.push(row); row = []; field = '';
    } else field += char;
  }
  if (row.length || field.length) { row.push(field); rows.push(row); }
  return rows;
}

async function noPageOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
}

for (const role of ['admin', 'analyst'] as const) {
  test(`demostración documental real consultable y exportable por ${role}`, async ({ page }, info) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await apiLogin(page.request, role);
    const listResponse = await page.request.get('/api/sources');
    expect(listResponse.status()).toBe(200);
    const records = (await listResponse.json()).items as DemoRecord[];
    const demos = records.filter(source => source.is_demo && source.title === originalTitle);
    expect(demos).toHaveLength(1);
    const source = demos[0];
    expect(source.source_type).toBe('local_reference');
    expect(source.url).toBeNull();
    expect(source.observed_at).toBeNull();
    expect(source.description.trim()).not.toBe('');
    expect(source.provenance).toContain('hakathon');
    expect(Number.isFinite(Date.parse(source.created_at))).toBeTruthy();
    const original = source.evidence.find(file => file.name === originalName);
    expect(original).toBeTruthy();
    expect(original!.sha256).toBe(originalSha256);

    await page.goto('/#fuentes');
    await expect(page.locator('main h1')).toHaveText('Fuentes abiertas');
    const prepared = page.locator('.prepared-demo');
    await expect(prepared.getByRole('heading', { name: 'Demostración preparada', exact: true })).toBeVisible();
    await expect(prepared).toContainText(source.title);
    await expect(prepared).toContainText(source.description);
    await expect(prepared).toContainText(original!.name);
    await expect(prepared).toContainText(/referencia.*hackathon/i);
    await noPageOverflow(page);

    await prepared.getByRole('button', { name: 'Ver detalles', exact: true }).click();
    const details = page.getByRole('dialog', { name: 'Detalles del registro', exact: true });
    await expect(details).toBeVisible();
    await expect(details).toContainText(source.title);
    await expect(details).toContainText(source.provenance);
    await expect(details).toContainText('Sin URL pública');
    await expect(details).toContainText('No aplica: documento local');
    await noPageOverflow(page);
    await page.keyboard.press('Escape');
    await expect(details).not.toBeVisible();

    await prepared.getByRole('button', { name: 'Ver documento', exact: true }).click();
    const document = page.getByRole('dialog', { name: 'Documento de referencia', exact: true });
    await expect(document).toBeVisible();
    await expect(document.locator('.reference-document-text')).toContainText(originalTitle);
    await expect(document.locator('.reference-document-text')).toContainText('Fijación Digital Forense');
    const originalDownload = page.waitForEvent('download');
    await document.getByRole('button', { name: 'Descargar original', exact: true }).click();
    const word = await originalDownload;
    expect(word.suggestedFilename()).toBe(original!.name);
    const raw = await downloadedBytes(word);
    expect(raw.subarray(0, 2).toString('ascii')).toBe('PK');
    expect(createHash('sha256').update(raw).digest('hex')).toBe(originalSha256);
    await noPageOverflow(page);
    await page.keyboard.press('Escape');
    await expect(document).not.toBeVisible();

    await prepared.getByRole('button', { name: 'Ver integridad SHA-256', exact: true }).click();
    const integrity = page.getByRole('dialog', { name: 'Integridad SHA-256', exact: true });
    await expect(integrity).toBeVisible();
    await expect(integrity).toContainText(originalSha256);
    await expect(integrity).toContainText('Hash conservado y hash recalculado coinciden.');
    const checkResponse = await page.request.get(`/api/sources/${source.id}/integrity`);
    expect(checkResponse.status()).toBe(200);
    const check = await checkResponse.json();
    expect(check.stored_sha256).toBe(originalSha256);
    expect(check.computed_sha256).toBe(originalSha256);
    expect(check.matches).toBe(true);
    expect(check.archive_matches).toBe(true);
    await noPageOverflow(page);
    await page.keyboard.press('Escape');
    await expect(integrity).not.toBeVisible();

    const exportDownload = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Exportar bitácora', exact: true }).click();
    const exported = await exportDownload;
    expect(exported.suggestedFilename()).toBe('centinela-bitacora.csv');
    const [headers, ...rows] = csvRows((await downloadedBytes(exported)).toString('utf-8'));
    const column = (name: string) => { const index = headers.indexOf(name); expect(index, `Columna CSV ${name}`).toBeGreaterThanOrEqual(0); return index; };
    const titleIndex = column('titulo'), hashIndex = column('sha256');
    const exportedDemo = rows.filter(row => row[titleIndex] === source.title && row[hashIndex] === originalSha256);
    expect(exportedDemo).toHaveLength(1);
    const row = exportedDemo[0];
    expect(row[column('url')]).toBe('');
    expect(row[column('fecha_observacion')]).toBe('');
    expect(row[column('archivo_evidencia')]).toBe(original!.name);
    expect(row[column('tipo_fuente')]).not.toBe('');
    expect(row[column('tipo_documento')]).not.toBe('');
    expect(row[column('procedencia')]).toBe(source.provenance);
    expect(row[column('fecha_incorporacion')]).toBe(source.created_at);
    expect(row[column('estado_verificacion')]).not.toBe('');
    await noPageOverflow(page);
    await page.screenshot({ path: `../data/screenshots/${info.project.name}-demo-fuentes-${role}.png`, fullPage: true });
    expect(errors).toEqual([]);
  });
}
