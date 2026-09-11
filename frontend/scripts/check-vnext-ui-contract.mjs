import { readFileSync, readdirSync } from 'node:fs'
import { extname, join, relative } from 'node:path'

const root = join(process.cwd(), 'src', 'vnext')
const allowedRawHeaderActions = new Set([
    'program/ProgramBottomFeedbackPanel.vue', // tablist owns a different keyboard contract
    'program/ProgramProblemsPanel.vue', // severity tablist is not a generic header action
])

function collect(directory) {
    return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
        const path = join(directory, entry.name)
        return entry.isDirectory() ? collect(path) : extname(entry.name) === '.vue' ? [path] : []
    })
}

const failures = []
for (const path of collect(root)) {
    const name = relative(root, path).replaceAll('\\', '/')
    const source = readFileSync(path, 'utf8')
    if (name !== 'components/ui/VNextNavigationItem.vue' && /class=["'][^"']*app-navigation-item/.test(source)) {
        failures.push(`${name}: 左侧列表项必须使用 VNextNavigationItem`)
    }
    if (!allowedRawHeaderActions.has(name)) {
        for (const block of source.matchAll(/<VNextPaneHeader\b[^>]*[^\/]>([\s\S]*?)<\/VNextPaneHeader>/g)) {
            const actions = block[0].match(/<template\s+#actions>[\s\S]*?<\/template>/)?.[0] || ''
            if (/<button\b/.test(actions)) failures.push(`${name}: PaneHeader 动作必须使用共享 Button/IconButton`)
        }
    }
    if (!name.startsWith('components/ui/') && /\.vnext-(?:button|icon-button|text-field|select|textarea)\b/.test(source)) {
        failures.push(`${name}: 页面不能覆盖共享原语内部样式`)
    }
}

if (failures.length) {
    console.error(`UI contract failed (${failures.length})\n${failures.map((item) => `- ${item}`).join('\n')}`)
    process.exit(1)
}
console.log('UI contract passed')
