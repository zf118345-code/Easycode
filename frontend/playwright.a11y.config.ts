import { defineConfig } from '@playwright/test'

const baseURL = process.env.EASYCODE_A11Y_BASE_URL?.trim() || 'http://127.0.0.1:5173'

export default defineConfig({
    testDir: './e2e',
    outputDir: '../output/playwright/accessibility/artifacts',
    fullyParallel: false,
    workers: 1,
    retries: 0,
    timeout: 30_000,
    expect: { timeout: 8_000 },
    reporter: [
        ['list'],
        ['json', { outputFile: '../output/playwright/accessibility/results.json' }]
    ],
    use: {
        baseURL,
        channel: process.env.EASYCODE_A11Y_BROWSER_CHANNEL?.trim() || 'msedge',
        viewport: { width: 1440, height: 900 },
        colorScheme: 'dark',
        reducedMotion: 'reduce',
        locale: 'zh-CN',
        screenshot: 'only-on-failure',
        trace: 'retain-on-failure'
    }
})
