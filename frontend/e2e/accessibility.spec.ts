import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

type AxeViolation = {
    id: string
    impact: string | null
    help: string
    helpUrl: string
    nodes: Array<{ target: string[]; failureSummary?: string }>
}

function formatViolations(violations: AxeViolation[]) {
    return violations
        .map((violation) => {
            const targets = violation.nodes
                .slice(0, 5)
                .map((node) => `  - ${node.target.join(' ')}`)
                .join('\n')
            return `[${violation.impact || 'unknown'}] ${violation.id}: ${violation.help}\n${targets}\n  ${violation.helpUrl}`
        })
        .join('\n\n')
}

test('EasyCode 当前工作区没有严重或致命的自动无障碍缺陷', async ({ page }, testInfo) => {
    await page.goto('/')
    await expect(page.locator('.vnext-root')).toBeVisible()
    await expect(page.locator('.startup')).toHaveCount(0)

    const results = await new AxeBuilder({ page })
        .include('.vnext-root')
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze()

    await testInfo.attach('axe-results', {
        body: Buffer.from(JSON.stringify(results, null, 2), 'utf8'),
        contentType: 'application/json'
    })

    const blocking = results.violations.filter((violation) =>
        violation.impact === 'critical' || violation.impact === 'serious'
    ) as AxeViolation[]

    expect(blocking, formatViolations(blocking)).toEqual([])
})
