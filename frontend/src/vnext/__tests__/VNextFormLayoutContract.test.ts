import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const vnextRoot = join(process.cwd(), 'src', 'vnext')

function source(relativePath: string): string {
    return readFileSync(join(vnextRoot, relativePath), 'utf8')
}

function expectRule(
    file: string,
    selector: RegExp,
    declaration: RegExp,
): void {
    const text = source(file)
    const rule = new RegExp(`${selector.source}\\s*\\{[^}]*${declaration.source}`, 's')
    expect(text, `${file} should keep ${selector.source} on the shared form contract`).toMatch(rule)
}

function expectContainerFallback(file: string, fallbackMarker: RegExp): void {
    const text = source(file)
    const fallback = new RegExp(
        `@container\\s*\\([^)]*max-width[^)]*\\)\\s*\\{[\\s\\S]{0,1600}${fallbackMarker.source}`,
    )
    expect(text, `${file} should expose a bounded narrow-pane fallback for ${fallbackMarker.source}`).toMatch(fallback)
}

describe('vNext form shortest-path source contract', () => {
    it('uses one shared inspector grammar across every first-party right pane', () => {
        const uiIndex = source('components/ui/index.ts')
        const inspectorSection = source('components/ui/VNextInspectorSection.vue')
        const theme = readFileSync(join(process.cwd(), 'src', 'assets', 'theme.css'), 'utf8')

        expect(uiIndex).toContain("VNextInspectorSection")
        expect(inspectorSection).toContain('app-inspector-section')
        for (const role of ['app-inspector-body', 'app-inspector-section', 'app-inspector-disclosure', 'app-inspector-feedback']) {
            expect(theme, `shared inspector theme should define ${role}`).toContain(`.${role}`)
        }
        for (const file of [
            'program/ProgramStatementInspector.vue',
            'components/VNextResourceWorkspace.vue',
            'components/VNextProjectVariableWorkspace.vue',
            'components/VNextTargetWorkspace.vue',
            'components/VNextPlayerWorkspace.vue',
            'components/VNextReplayWorkspace.vue',
            'components/VNextExtensionWorkspace.vue',
            'components/VNextScheduleWorkspace.vue',
        ]) {
            expect(source(file), `${file} should consume the shared inspector grammar`).toMatch(/app-inspector-(?:body|form|section|disclosure)/)
        }
    })

    it('defines one canonical 32px label-control-action row with local feedback', () => {
        const theme = readFileSync(join(process.cwd(), 'src', 'assets', 'theme.css'), 'utf8')

        expect(theme).toMatch(/--app-control-default:\s*32px/)
        expect(theme).toContain('.app-form-row')
        expect(theme).toContain('.app-form-label')
        expect(theme).toContain('.app-form-control')
        expect(theme).toContain('.app-form-row > .app-form-help')
        expect(theme).toContain('.app-form-row > .app-form-error')
        expect(theme).toContain('.app-form-row.is-multiline')
        expect(theme).toMatch(/\.app-form-row\s*\{[^}]*display:\s*grid[^}]*grid-template-columns:/s)
        expect(theme).toMatch(/\.app-form-row\s*>\s*\.app-form-(?:help|error)[^{]*\{[^}]*grid-column:\s*2\s*\/\s*-1/s)
    })

    it('gives ordinary controls full width while keeping only compact controls inline', () => {
        const parameter = source('program/ProgramParameterControl.vue')
        expect(parameter).toContain('<VNextControlField')
        expect(parameter).toContain(':stacked="shouldStackField"')
        expect(parameter).toContain("control.value !== 'toggle'")
        expectRule('program/ProgramRecordInlineEditor.vue', /\.record-field/, /display:\s*grid/)
        expectRule('program/ProgramRecordInlineEditor.vue', /\.record-field\.is-compact/, /grid-template-columns:/)
        expectRule('program/ProgramStructureInspector.vue', /\.field-label/, /display:\s*grid/)
        expectRule('program/ProgramStructureInspector.vue', /\.field-label/, /grid-template-columns:/)
        expectRule('program/ProgramStatementInspector.vue', /\.result-control-row/, /display:\s*grid/)
        expectRule('program/ProgramStatementInspector.vue', /\.result-control-row/, /grid-template-columns:/)

        for (const file of [
            'program/ProgramRecordInlineEditor.vue',
            'program/ProgramStructureInspector.vue',
            'program/ProgramStatementInspector.vue',
        ]) {
            expect(source(file), `${file} should size ordinary controls from the 32px token`).toContain('var(--app-control-default)')
        }

        expectContainerFallback('components/ui/VNextControlField.vue', /\.vnext-control-field__heading/)
        expectContainerFallback('program/ProgramRecordInlineEditor.vue', /\.record-field/)
        expectContainerFallback('program/ProgramStructureInspector.vue', /\.field-label/)
        expectContainerFallback('program/ProgramStatementInspector.vue', /\.result-control-row/)
        expect(source('components/ui/VNextControlField.vue')).toMatch(/@container\s*\(max-width:\s*220px\)/)
        expect(source('program/ProgramRecordInlineEditor.vue')).toMatch(/@container\s*\(max-width:\s*220px\)/)
        expect(source('components/VNextValueControl.vue')).toMatch(/\.value-resource\s*\{[^}]*display:\s*flex/s)
        expect(source('components/VNextValueControl.vue')).toMatch(/\.value-resource\s*>\s*select\s*\{[^}]*flex:\s*1/s)
    })

    it('keeps conditions directly editable without a duplicate structured-editor step', () => {
        const parameter = source('program/ProgramParameterControl.vue')
        const structureValue = source('program/ProgramStructureValueField.vue')

        expect(structureValue).not.toContain('conditionBuilder')
        expect(parameter).not.toContain('forceStructuredEditor')
        expect(parameter).toContain('v-else-if="usesUnifiedComposer"')
        expect(parameter).not.toContain('open-condition-builder')
    })

    it.each([
        ['components/VNextProjectVariableWorkspace.vue', /class="field app-form-row/, /@container\s*\(max-width:\s*300px\)/],
        ['components/VNextTargetWorkspace.vue', /class="field app-form-row/, /@container\s*\(max-width:\s*300px\)/],
        ['components/VNextResourceWorkspace.vue', /class="asset-field app-form-row/, /@container\s*\(max-width:\s*260px\)/],
    ])('uses canonical inline rows in %s', (file, rowMarker, narrowFallback) => {
        const text = source(file)
        expect(text).toMatch(rowMarker)
        expect(text).toContain('app-form-label')
        expect(text).toContain('app-form-control')
        expect(text).toContain('var(--app-control-default)')
        expect(text).toMatch(/container-type:\s*inline-size/)
        expect(text).toMatch(narrowFallback)
    })

    it('keeps schedule fields and compound network addresses on one row until the inspector is narrow', () => {
        const schedule = source('components/VNextScheduleWorkspace.vue')

        expectRule('components/VNextScheduleWorkspace.vue', /\.field\b/, /grid-template-columns:/)
        expectRule('components/VNextScheduleWorkspace.vue', /\.compound-address-control/, /grid-template-columns:/)
        expect(schedule).toContain('var(--app-control-default)')
        expect(schedule).toMatch(/\.schedule-inspector\s*\{[^}]*container-type:\s*inline-size/s)
        expectContainerFallback('components/VNextScheduleWorkspace.vue', /\.field\b/)
    })

    it('keeps Player authoring properties and previews on explicit inline rows', () => {
        const workspace = source('components/VNextPlayerWorkspace.vue')
        const canonicalPropertyRow = /<label[^>]*class="[^"]*\bapp-form-row\b[^"]*"/.test(workspace)
        const explicitPropertyRow = /<label[^>]*class="[^"]*\bproperty-field\b[^"]*"/.test(workspace)
            && /\.property-field\s*\{[^}]*display:\s*grid[^}]*grid-template-columns:/s.test(workspace)

        expect(workspace).toContain("'is-inline-field': playerControlUsesInlineLayout(control)")
        expectRule('components/VNextPlayerWorkspace.vue', /\.preview-control\.is-inline-field/, /grid-template-columns:/)
        expect(workspace).toMatch(/\.player-card\.narrow\s+\.preview-control\.is-inline-field\s*\{[^}]*grid-template-columns:/s)
        expect(canonicalPropertyRow || explicitPropertyRow, 'Player 属性面板的普通字段缺少明确的一行表单标记').toBe(true)
        expect(workspace).toContain('var(--app-control-default)')
    })

    it('keeps the standalone Player form inline and retains touch/narrow stacking', () => {
        const player = source('VNextPlayerApp.vue')

        expect(player).toContain("'is-inline-field': playerControlUsesInlineLayout(control)")
        expectRule('VNextPlayerApp.vue', /\.runtime-form\s*>\s*label\.is-inline-field/, /grid-template-columns:/)
        expect(player).toContain('var(--app-control-default)')
        expect(player).toMatch(/@media\s*\(max-width:\s*760px\)[\s\S]*?\.runtime-form\s*>\s*label\.is-inline-field\s*\{[^}]*grid-template-columns:/)
        expect(player).toMatch(/\.android-host\s+\.runtime-form\s*>\s*label\.is-inline-field\s*\{[^}]*grid-template-columns:/)
    })

    it('keeps Player schedules and device connection fields compact, direct, and responsive', () => {
        const schedules = source('components/VNextPlayerSchedules.vue')
        const devices = source('components/VNextPlayerDevices.vue')

        expectRule('components/VNextPlayerSchedules.vue', /\.schedule-editor\s+label/, /grid-template-columns:/)
        expect(schedules).toContain('var(--app-control-default)')
        expectContainerFallback('components/VNextPlayerSchedules.vue', /\.schedule-editor\s+label/)

        expect(devices).toContain('class="device-field"')
        expectRule('components/VNextPlayerDevices.vue', /\.device-field/, /grid-template-columns:/)
        expectRule('components/VNextPlayerDevices.vue', /\.connect-address-control/, /grid-template-columns:/)
        expect(devices).toContain('var(--app-control-default)')
        expectContainerFallback('components/VNextPlayerDevices.vue', /\.device-field/)
    })

    it.each([
        ['components/VNextExtensionWorkspace.vue', /class="inline-field/, /\.create-dialog\s+label\.inline-field/, /@media\s*\(max-width:\s*620px\)/],
        ['components/VNextPublishUpdates.vue', /class="inline-field/, /(?:\.field-grid[^{,]*|\.rollout-tools[^{,]*)label\.inline-field/, /@media\s*\(max-width:\s*620px\)/],
    ])('keeps %s simple fields inline while marking multiline content explicitly', (file, marker, selector, fallback) => {
        const text = source(file)
        expect(text).toMatch(marker)
        expect(text).toContain('multiline-field')
        expectRule(file, selector, /grid-template-columns:/)
        expect(text).toContain('var(--app-control-default)')
        expect(text).toMatch(fallback)
    })

    it('keeps Replay quick controls inline and inspector form fields on the ordinary 32px contract', () => {
        const replay = source('components/VNextReplayWorkspace.vue')

        expectRule('components/VNextReplayWorkspace.vue', /\.compact-field/, /grid-template-columns:/)
        expectRule('components/VNextReplayWorkspace.vue', /\.compact-field\s+input,[^{]*/, /height:\s*var\(--app-control-default\)/)
        expectRule('components/VNextReplayWorkspace.vue', /\.advanced-options\s+label/, /grid-template-columns:/)
        expectRule('components/VNextReplayWorkspace.vue', /\.compare-inputs\s+label/, /grid-template-columns:/)
        expectRule('components/VNextReplayWorkspace.vue', /\.advanced-options\s+input/, /height:\s*var\(--app-control-default\)/)
        expectRule('components/VNextReplayWorkspace.vue', /\.compare-inputs\s+input/, /height:\s*var\(--app-control-default\)/)
        expect(replay).toMatch(/@media\s*\(max-width:\s*420px\)\s*\{[^}]*\.compare-inputs\s*\{[^}]*grid-template-columns:/s)
    })

    it('keeps create-project and IDE name transactions to one inline field without banning their dialogs', () => {
        const createProject = source('components/VNextCreateProjectDialog.vue')
        const ide = source('components/VNextIdeV6.vue')

        expect(createProject).toContain('class="project-path-row app-form-row"')
        expect(createProject).toContain('class="app-form-label"')
        expect(createProject).toContain('class="app-form-control"')
        expect(createProject).toContain('class="app-field-action"')
        expect(createProject).toContain('app-form-help')
        expect(createProject).toContain('app-form-error')
        expect(createProject).toContain('var(--app-control-default)')
        expectContainerFallback('components/VNextCreateProjectDialog.vue', /\.project-path-row/)

        expect(ide.match(/class="dialog-form-row app-form-row"/g)?.length ?? 0).toBeGreaterThanOrEqual(3)
        expect(ide).toContain('class="app-form-label"')
        expect(ide).toContain('class="app-form-control"')
        expect(ide).toContain('app-form-error')
        expect(ide).toContain('var(--app-control-default)')
        expectContainerFallback('components/VNextIdeV6.vue', /\.dialog-form-row/)
    })
})
