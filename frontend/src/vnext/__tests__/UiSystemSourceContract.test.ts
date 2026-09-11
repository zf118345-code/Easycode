import { readFileSync, readdirSync } from 'node:fs'
import { extname, join } from 'node:path'
import { describe, expect, it } from 'vitest'

function vueFiles(root: string): string[] {
    return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
        const path = join(root, entry.name)
        if (entry.isDirectory()) return vueFiles(path)
        return extname(entry.name) === '.vue' ? [path] : []
    })
}

describe('UI system source contract', () => {
    const sourceRoot = join(process.cwd(), 'src', 'vnext')
    const sources = vueFiles(sourceRoot).map((path) => ({ path, text: readFileSync(path, 'utf8') }))

    it('does not reintroduce unreadable literal UI font sizes', () => {
        const violations = sources
            .filter(({ text }) => /font-size:\s*(?:8|9|10|11|12|13|14|15)px/.test(text))
            .map(({ path }) => path.replace(process.cwd(), ''))
        expect(violations).toEqual([])
    })

    it('keeps first-party vNext views on host-owned theme tokens', () => {
        const violations = sources
            .filter(({ text }) => /--ec-[a-z-]+/.test(text))
            .map(({ path }) => path.replace(process.cwd(), ''))
        expect(violations).toEqual([])
    })

    it('keeps every top-level workspace on the shared pane header', () => {
        const workspaces = [
            'VNextResourceWorkspace.vue', 'VNextProjectVariableWorkspace.vue', 'VNextTargetWorkspace.vue',
            'VNextPlayerWorkspace.vue', 'VNextReplayWorkspace.vue', 'VNextScheduleWorkspace.vue',
            'VNextExtensionWorkspace.vue',
        ]
        for (const file of workspaces) {
            const source = readFileSync(join(sourceRoot, 'components', file), 'utf8')
            expect(source, file).toContain('VNextPaneHeader')
        }
    })

    it('defines semantic density and form-rhythm tokens', () => {
        const theme = readFileSync(join(process.cwd(), 'src', 'assets', 'theme.css'), 'utf8')
        for (const token of [
            '--app-list-row-compact', '--app-list-row-default', '--app-list-row-rich', '--app-list-row-multiline',
            '--app-form-heading-field-gap', '--app-form-label-control-gap',
            '--app-form-feedback-gap', '--app-form-field-gap', '--app-form-section-gap',
            '--app-form-section-padding', '--app-form-disclosure-height',
        ]) expect(theme).toContain(token)
        expect(theme).toContain('.app-form-row')
        expect(theme).toContain('.app-form-label')
        expect(theme).toContain('.app-form-control')
    })

    it('keeps single-line project variables on compact list density', () => {
        const source = readFileSync(join(sourceRoot, 'components', 'VNextProjectVariableWorkspace.vue'), 'utf8')
        expect(source).toMatch(/\.variable-list button[^\n]+var\(--app-list-row-compact\)/)
        expect(source).not.toMatch(/\.variable-list button[^\n]+(?:min-)?height:\s*48px/)
    })

    it('keeps workspace lists on the shared density scale', () => {
        const contracts: Array<[string, string]> = [
            ['program/ProgramFunctionLibrary.vue', '--app-list-row-compact'],
            ['components/VNextResourceWorkspace.vue', '--app-control-compact'],
            ['components/VNextProjectVariableWorkspace.vue', '--app-list-row-compact'],
            ['components/VNextTargetWorkspace.vue', '--app-list-row-rich'],
            ['components/VNextPlayerWorkspace.vue', '--app-list-row-compact'],
            ['components/VNextReplayWorkspace.vue', '--app-list-row-multiline'],
            ['components/VNextScheduleWorkspace.vue', '--app-list-row-rich'],
            ['components/VNextExtensionWorkspace.vue', '--app-list-row-rich'],
        ]
        for (const [file, token] of contracts) {
            expect(readFileSync(join(sourceRoot, file), 'utf8'), file).toContain(token)
        }
    })

    it('keeps authoring forms on the shared field rhythm', () => {
        const forms = [
            'program/ProgramParameterControl.vue',
            'program/ProgramStatementInspector.vue',
            'program/ProgramStructureInspector.vue',
            'components/VNextProjectVariableWorkspace.vue',
            'components/VNextTargetWorkspace.vue',
            'components/VNextPlayerWorkspace.vue',
            'components/VNextReplayWorkspace.vue',
            'components/VNextScheduleWorkspace.vue',
            'components/VNextExtensionWorkspace.vue',
            'VNextPlayerApp.vue',
        ]
        for (const file of forms) {
            const source = readFileSync(join(sourceRoot, file), 'utf8')
            expect(source, file).toMatch(/--app-form-(?:heading-field|label-control|field|section)-gap/)
        }
    })

    it('keeps ordinary inspector fields out of browser-specific legend geometry', () => {
        const parameter = readFileSync(join(sourceRoot, 'program', 'ProgramParameterControl.vue'), 'utf8')
        const expression = readFileSync(join(sourceRoot, 'program', 'ProgramExpressionInput.vue'), 'utf8')
        const inspector = readFileSync(join(sourceRoot, 'program', 'ProgramStatementInspector.vue'), 'utf8')

        expect(parameter).not.toContain('<fieldset class="program-parameter"')
        expect(parameter).toContain('<VNextControlField')
        expect(expression).toMatch(/\.expression-surface \{[^\n]+min-height: var\(--app-control-default\)/)
        expect(expression).toContain('class="expression-value"')
        expect(parameter).toContain("'has-actions': hasUnifiedActions")
        expect(inspector).toContain('<summary><span>高级参数</span>')
        expect(inspector).toContain('<summary>步骤备注</summary>')
        expect(inspector).toContain('class="app-inline-action"')
        expect(inspector).toContain('<GitBranchPlus')
        expect(inspector).not.toContain('<summary>其他</summary>')
    })

    it('uses semantic field geometry and keeps complex values transactional', () => {
        const parameter = readFileSync(join(sourceRoot, 'program', 'ProgramParameterControl.vue'), 'utf8')
        const inlineRecord = readFileSync(join(sourceRoot, 'program', 'ProgramRecordInlineEditor.vue'), 'utf8')
        const tree = readFileSync(join(sourceRoot, 'program', 'ProgramValueTreeField.vue'), 'utf8')
        const editor = readFileSync(join(sourceRoot, 'program', 'ProgramStructuredValueEditor.vue'), 'utf8')

        expect(parameter).toContain('class="program-parameter"')
        expect(parameter).toContain(':stacked="shouldStackField"')
        expect(parameter).toContain("control.value !== 'toggle'")
        expect(parameter).not.toContain('open-condition-builder')
        expect(parameter).not.toContain('forceStructuredEditor')
        expect(parameter).toContain("['focused', 'row_list'].includes")
        expect(inlineRecord).toContain('.record-field.is-compact')
        expect(inlineRecord).toContain("return fieldControl(field) === 'toggle'")
        expect(tree).toContain("'is-inline-leaf': inlineLeaf")
        expect(editor).toContain('class="structured-dialog"')
        expect(editor).toContain('@submit.prevent="save"')
        expect(editor).toContain("emit('save', cloneProgramValue(draft.value))")
    })

    it('keeps the complete published Control vocabulary reachable from parameter authoring', () => {
        const types = readFileSync(join(sourceRoot, 'types.ts'), 'utf8')
        const parameter = readFileSync(join(sourceRoot, 'program', 'ProgramParameterControl.vue'), 'utf8')
        const valueControl = readFileSync(join(sourceRoot, 'components', 'VNextValueControl.vue'), 'utf8')
        const controls = [
            'text', 'number', 'toggle', 'select', 'slider-number', 'duration', 'time', 'coordinate', 'region',
            'resource', 'control-selector', 'gesture-path', 'file', 'directory', 'control-reference', 'instance',
            'target', 'application', 'instance-multi-select', 'key-chord', 'json', 'list', 'key-value', 'expression',
        ]

        for (const control of controls) expect(types, control).toContain(`| '${control}'`)
        expect(parameter).toContain(':control-type="control"')
        expect(parameter).not.toMatch(/ui\?\.control[^\n]+(?:filter|includes)/)
        expect(valueControl).toContain("controlType === 'file' || controlType === 'directory'")
    expect(valueControl).toContain("['list','key-value','json','instance-multi-select'].includes(props.controlType)")
    })

    it('keeps secondary form disclosures subordinate to major sections', () => {
        const theme = readFileSync(join(process.cwd(), 'src', 'assets', 'theme.css'), 'utf8')
        expect(theme).toContain('--app-form-disclosure-height')
        expect(theme).toContain('.app-inspector-disclosure')
        const files = [
            'program/ProgramStatementInspector.vue',
            'components/VNextProjectVariableWorkspace.vue',
            'components/VNextPlayerWorkspace.vue',
            'components/VNextScheduleWorkspace.vue',
            'components/VNextExtensionWorkspace.vue',
        ]
        for (const file of files) {
            const source = readFileSync(join(sourceRoot, file), 'utf8')
            expect(source, file).toMatch(/app-inspector-disclosure|--app-form-disclosure-height/)
        }
    })

    it('uses one quiet inline-action grammar for non-primary form operations', () => {
        const theme = readFileSync(join(process.cwd(), 'src', 'assets', 'theme.css'), 'utf8')
        expect(theme).toContain('.app-inline-action')
        expect(theme).toMatch(/\.app-inline-action\s*>\s*span[^}]+line-height:\s*var\(--app-line-height-compact\)/)
        expect(theme).toContain('.sr-only')

        for (const file of [
            'program/ProgramStatementInspector.vue',
            'program/ProgramStructureInspector.vue',
            'program/ProgramJsonValueField.vue',
            'program/ProgramValueTreeField.vue',
            'components/VNextPlayerWorkspace.vue',
            'components/VNextReplayWorkspace.vue',
            'components/VNextScheduleWorkspace.vue',
        ]) {
            expect(readFileSync(join(sourceRoot, file), 'utf8'), file).toContain('app-inline-action')
        }
        const inspector = readFileSync(join(sourceRoot, 'program', 'ProgramStatementInspector.vue'), 'utf8')
        expect(inspector).not.toContain('<small>{{ resultConditionHint }}</small>')
    })

    it('keeps stable image resources direct and exposes side-effect-free vision preview', () => {
        const expression = readFileSync(join(sourceRoot, 'program', 'expressionComposer.ts'), 'utf8')
        const inspector = readFileSync(join(sourceRoot, 'program', 'ProgramStatementInspector.vue'), 'utf8')
        const editor = readFileSync(join(sourceRoot, 'program', 'ProgramEditorSurface.vue'), 'utf8')

        expect(expression).toContain("normalized.startsWith('asset_ref<')")
        expect(inspector).toContain('测试当前画面')
        expect(inspector).toContain('vnextApi.previewVision')
        expect(editor).toContain(':workspace="workspace"')
        expect(editor).toContain(':target-id="targetId"')
    })
})
