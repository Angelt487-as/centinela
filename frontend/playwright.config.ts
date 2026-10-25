import { defineConfig } from '@playwright/test';

const sizes = [[360, 800], [390, 844], [768, 1024], [1024, 768], [1366, 768], [1920, 1080]];
export default defineConfig({
  testDir: './tests', timeout: 60000, expect: { timeout: 15000 }, fullyParallel: false, workers: 1,
  reporter: [['list'], ['json', { outputFile: '../data/ui-results.json' }]],
  outputDir: '../data/ui-artifacts',
  use: { baseURL: 'http://127.0.0.1:5173', channel: 'msedge', trace: 'off', screenshot: 'only-on-failure' },
  projects: sizes.map(([width, height]) => ({ name: `${width}x${height}`, use: { viewport: { width, height }, hasTouch: width <= 1024, isMobile: width < 768 } })),
});
