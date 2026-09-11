/* eslint-disable vue/one-component-per-file, vue/require-default-prop */
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AssetDefinition } from '../types'
import type { ProgramValueNode } from '../program/types'
import type { AvailableFunctionContractDto, ProgramSnapshotDto, ProgramSummaryDto } from '../program/serverTypes'

const apiMocks = vi.hoisted(() => ({
    listAvailableFunctions: vi.fn(), listPrograms: vi.fn(), getProgram: vi.fn(), applyCommand: vi.fn(),
    createProgram: vi.fn(), undo: vi.fn(), redo: vi.fn(), compile: vi.fn(), run: vi.fn(),
    getProjectVariables: vi.fn(),
}))
const captureMocks = vi.hoisted(() => ({
    connect: vi.fn(), update: vi.fn(), disconnect: vi.fn().mockResolvedValue(undefined), capture: vi.fn(),
    captureResource: vi.fn(), openRecordingFrame: vi.fn(),
}))
const scheduleMocks = vi.hoisted(() => ({ hubStatus: vi.fn() }))

vi.mock('../program/api', async () => {
    const actual = await vi.importActual<typeof import('../program/api')>('../program/api')
    return { ...actual, programApi: apiMocks }
})
vi.mock('../captureSession', () => ({ vnextCaptureSession: captureMocks }))
vi.mock('../scheduleApi', () => ({ scheduleApi: scheduleMocks }))

import VNextIdeV6 from '../components/VNextIdeV6.vue'
import { vnextApi } from '../api'
import { ProgramApiError } from '../program/api'
import { useProgramStore } from '../program/store'
import { useVNextStore } from '../store'

const revisionA = `sha256:${'a'.repeat(64)}`
const revisionB = `sha256:${'b'.repeat(64)}`
const chooseAction = { id: 'choose-resource' } as const

function contract(): AvailableFunctionContractDto {
    return {
        function_id: 'official.image.find', namespace: '图像', name: '查找', qualified_name: '图像.查找',
        summary: '查找{image}', layer: 'atomic', return_type: 'unit', opcode: 'vision.find',
        parameters: [{
            parameter_id: 'parameter_image', name: 'image', display_name: '图片', value_type: 'asset_ref<image>',
            required: true, has_default: false, default: null, control: 'resource', constraints: {}, description: '',
            ui: { control: 'resource', actions: [chooseAction] },
        }, {
            parameter_id: 'parameter_tasks', name: 'tasks', display_name: '任务列表', value_type: 'list<string>',
            required: true, has_default: false, default: null, control: 'list', constraints: {}, description: '',
        }],
        host_requirements: ['windows'], target_kinds: ['windows'], target_capabilities: [], permissions: [],
        side_effects: [], errors: [], normal_empty: false, network_level: 'none', dangerous: false,
        implementation_state: 'available', standard_definition_id: '', contract_version: '1.0.0',
        schema_version: 1, contract_fingerprint: 'capture-contract',
    }
}

function snapshot(revision = revisionA, selectedAsset = false): ProgramSnapshotDto {
    return {
        revision, diagnostics: [], can_undo: revision !== revisionA, can_redo: false,
        document: {
            schema_version: 1, document_id: 'document_main',
            function: {
                function_id: 'function_main', display_name: '主程序', parameters: [], return_type: 'unit',
                statements: [{
                    statement_id: 'statement_find', kind: 'call', function_id: 'official.image.find',
                    arguments: {
                        parameter_image: selectedAsset
                            ? { value_id: 'value_image', kind: 'asset_ref', asset_id: 'asset_login', asset_kind: 'image' }
                            : { value_id: 'value_image', kind: 'unset', expected_type: 'asset_ref<image>' },
                        parameter_tasks: {
                            value_id: 'value_tasks', kind: 'list', item_type: 'string',
                            items: [{ value_id: 'value_task_1', kind: 'string', value: '日常任务' }],
                        },
                    },
                    result_binding: null, step_label: null,
                }],
            },
        },
        selected_statement_id: 'statement_find',
    }
}

const summary: ProgramSummaryDto = {
    document_id: 'document_main', function_id: 'function_main', display_name: '主程序', statement_count: 1,
    revision: revisionA, parameters: [], return_type: 'unit', contract_version: '1.0.0', contract_fingerprint: 'main',
}

const asset: AssetDefinition = {
    asset_id: 'asset_login', display_name: '登录按钮', category: 'image', folder: '', path: 'assets/image/login.png',
    extension: '.png', mime_type: 'image/png', size_bytes: 12, width: 30, height: 20, sha256: 'a'.repeat(64),
    source: 'capture', created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z', aliases: [], capture: null,
}

const EditorStub = defineComponent({
    props: { platform: String },
    emits: ['capture', 'openValueEditor', 'extract-statements'],
    setup(_, { emit }) {
        return () => h('fieldset', { 'data-value-id': 'value_image' }, [
            h('button', {
                class: 'open-resource', 'data-parameter-action-id': 'choose-resource',
                onClick: () => emit('capture', {
                    document_id: 'document_main', base_revision: revisionA,
                    request: {
                        statement_id: 'statement_find', parameter_id: 'parameter_image', value_id: 'value_image',
                        action: chooseAction,
                    },
                }),
            }, '选择资源'),
            h('button', {
                class: 'open-value-editor',
                onClick: () => emit('openValueEditor', {
                    document_id: 'document_main', base_revision: revisionA,
                    request: { statement_id: 'statement_find', parameter_id: 'parameter_tasks', value_id: 'value_tasks' },
                }),
            }, '编辑列表'),
            h('button', {
                class: 'extract-statements',
                onClick: () => emit('extract-statements', ['statement_find']),
            }, '提取语句'),
        ])
    },
})

const ValueEditorStub = defineComponent({
    props: { value: { type: Object, required: true } },
    emits: ['save', 'cancel'],
    setup(props, { emit }) {
        return () => h('section', { class: 'value-editor-stub' }, [
            h('button', {
                class: 'save-value',
                onClick: () => emit('save', {
                    ...(props.value as ProgramValueNode),
                    items: [
                        { value_id: 'value_task_1', kind: 'literal', value_type: 'string', value: '日常任务' },
                        { value_id: 'value_task_2', kind: 'literal', value_type: 'string', value: '周常任务' },
                    ],
                }),
            }, '保存列表'),
            h('button', { class: 'cancel-value', onClick: () => emit('cancel') }, '取消'),
        ])
    },
})

const AsyncWorkspaceHostStub = defineComponent({
    inheritAttrs: false,
    props: { label: String, loader: Function },
    setup(props, { attrs }) {
        return () => {
            if (props.label === '资源') {
                return h('section', { class: 'resource-stub' }, [
                    h('button', { class: 'apply-resource', onClick: () => (attrs.onInsertReference as ((value: AssetDefinition) => void))?.(asset) }, '应用'),
                    h('button', { class: 'cancel-resource', onClick: () => (attrs.onCancelSelection as (() => void))?.() }, '取消'),
                    h('button', {
                        class: 'capture-resource',
                        onClick: (event: MouseEvent) => (attrs.onCaptureResource as ((category: string, trigger: EventTarget | null) => void))?.('page', event.currentTarget),
                    }, '视觉录入'),
                ])
            }
            if (props.label === '运行记录') {
                return h('section', { class: 'replay-stub' }, [
                    h('button', { class: 'open-history-frame', onClick: () => (attrs.onOpenHistoryFrame as ((sessionId: string, frame: number) => void))?.('session_1', 12) }, '打开历史帧'),
                ])
            }
            if (props.label === '计划与实例') return h('section', { class: 'schedule-stub' }, '计划中心')
            return h('section')
        }
    },
})

function mountIde() {
    return shallowMount(VNextIdeV6, {
        attachTo: document.body,
        global: { stubs: {
            ProgramEditorSurface: EditorStub,
            ProgramFunctionLibrary: true,
            ProgramRunConsole: true,
            ProgramStructuredValueEditor: ValueEditorStub,
            VNextAsyncWorkspaceHost: AsyncWorkspaceHostStub,
            VNextInlineNotice: false,
            VNextPaneHeader: false,
            VNextActivityRail: false,
        } },
    })
}

describe('VNextIdeV6 Program capture integration', () => {
    afterEach(() => { vi.unstubAllGlobals() })

    beforeEach(() => {
        setActivePinia(createPinia())
        Object.values(apiMocks).forEach((mock) => mock.mockReset())
        Object.values(captureMocks).forEach((mock) => mock.mockClear())
        captureMocks.disconnect.mockResolvedValue(undefined)
        captureMocks.captureResource.mockReset()
        scheduleMocks.hubStatus.mockReset()
        scheduleMocks.hubStatus.mockResolvedValue({ available: true, ready: true })
        apiMocks.listAvailableFunctions.mockResolvedValue([contract()])
        apiMocks.listPrograms.mockResolvedValue([summary])
        apiMocks.getProgram.mockResolvedValue(snapshot())
        apiMocks.getProjectVariables.mockResolvedValue({
            schema_version: 1, variables: [], revision: revisionA,
        })
        vi.spyOn(vnextApi, 'debugSettings').mockResolvedValue({ schema_version: 2, breakpoints: {} })
        vi.spyOn(vnextApi, 'saveDebugSettings').mockResolvedValue({ schema_version: 2, breakpoints: {} })
        vi.spyOn(vnextApi, 'activeRuns').mockResolvedValue({ runs: [] })
        window.sessionStorage.clear()
        const workspaceStore = useVNextStore()
        workspaceStore.workspace = {
            workspace_id: 'workspace_main', generation: 4, project_id: 'project_main', project_name: '测试项目',
            project_path: 'D:/Project', read_only: false,
        }
        workspaceStore.targets = [{
            target_id: 'target_main', name: '测试窗口', type: 'windows', window_title: '测试', window_match: 'contains',
            work_area: { mode: 'client' }, allow_physical_fallback: true,
        }]
        workspaceStore.defaultTargetId = 'target_main'
        workspaceStore.assets = [asset]
    })

    it('reattaches the active runtime session after a browser refresh', async () => {
        vi.mocked(vnextApi.activeRuns).mockResolvedValueOnce({ runs: [{
            execution_id: 'execution-refresh', status: 'paused',
            started_at: '2026-09-10T05:00:00+00:00', finished_at: '', error: '', events: [],
            current_instruction_id: 'statement_find',
            current_source: { function_id: 'function_main', statement_id: 'statement_find' },
            variables: {}, project_variables: {}, breakpoints: [],
            diagnostic_available: false, failure_frame_available: false,
        }] })

        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.find('.stop-button').exists()).toBe(true))

        expect(wrapper.text()).toContain('继续')
        expect(wrapper.text()).toContain('已暂停')
        expect(window.sessionStorage.getItem('easycode.ide.active-run:workspace_main:4')).toBe('execution-refresh')
        wrapper.unmount()
    })

    it('cancels resource selection without a Program command and returns focus to the opening action', async () => {
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.find('.open-resource').exists()).toBe(true))
        await wrapper.get('.open-resource').trigger('click')
        await flushPromises()
        expect(wrapper.find('.resource-stub').exists()).toBe(true)

        await wrapper.get('.cancel-resource').trigger('click')
        await flushPromises()
        expect(apiMocks.applyCommand).not.toHaveBeenCalled()
        expect(wrapper.find('.open-resource').exists()).toBe(true)
        expect(document.activeElement).toBe(wrapper.get('.open-resource').element)
        wrapper.unmount()
    })

    it('opens the replay workspace and routes a historical frame through the shared capture host', async () => {
        captureMocks.connect.mockResolvedValueOnce(undefined)
        captureMocks.openRecordingFrame.mockResolvedValueOnce(undefined)
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.find('[aria-label="运行记录"]').exists()).toBe(true))

        await wrapper.get('[aria-label="运行记录"]').trigger('click')
        await wrapper.get('.open-history-frame').trigger('click')
        await flushPromises()

        expect(captureMocks.connect).toHaveBeenCalledTimes(1)
        expect(captureMocks.openRecordingFrame).toHaveBeenCalledWith('session_1', 12)
        wrapper.unmount()
    })

    it('routes independent resource recording through the shared Capture Session and restores trigger focus on cancel', async () => {
        captureMocks.connect.mockResolvedValueOnce(undefined)
        captureMocks.captureResource.mockImplementationOnce(async (_category, _handler, options) => {
            await options.onCancel()
        })
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.find('[aria-label="资源"]').exists()).toBe(true))

        await wrapper.get('[aria-label="资源"]').trigger('click')
        const trigger = wrapper.get('.capture-resource')
        ;(trigger.element as HTMLElement).focus()
        await trigger.trigger('click')
        await flushPromises()

        expect(captureMocks.captureResource).toHaveBeenCalledWith(
            'page', expect.any(Function), expect.objectContaining({ title: '视觉录入 · 页面' }),
        )
        expect(wrapper.text()).toContain('已取消视觉录入')
        expect(document.activeElement).toBe(trigger.element)
        wrapper.unmount()
    })

    it('shows the schedule workspace only after the real Hub reports ready', async () => {
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.find('[aria-label="运行中心"]').exists()).toBe(true))

        await wrapper.get('[aria-label="运行中心"]').trigger('click')

        expect(wrapper.find('.schedule-stub').exists()).toBe(true)
        expect(scheduleMocks.hubStatus).toHaveBeenCalledTimes(1)
        wrapper.unmount()
    })

    it('does not expose a schedule entry when the Hub is unavailable', async () => {
        scheduleMocks.hubStatus.mockResolvedValueOnce({ available: false, ready: false })
        const wrapper = mountIde()
        await flushPromises()

        expect(wrapper.find('[aria-label="运行中心"]').exists()).toBe(false)
        wrapper.unmount()
    })

    it('checks and renders an empty target selection as explicit no_target instead of Windows', async () => {
        const workspaceStore = useVNextStore()
        workspaceStore.targets = []
        workspaceStore.defaultTargetId = null
        apiMocks.compile.mockResolvedValueOnce({
            valid: false,
            ecir: null,
            diagnostics: [{ code: 'PGM-PLATFORM-001', severity: 'error', message: '图像.查找不支持目标平台：no_target' }],
        })
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.findComponent(EditorStub).exists()).toBe(true))

        expect(wrapper.getComponent(EditorStub).props('platform')).toBe('no_target')
        const checkButton = wrapper.findAll('button').find((button) => button.text().includes('检查'))
        expect(checkButton).toBeDefined()
        await checkButton!.trigger('click')
        await flushPromises()

        expect(apiMocks.compile).toHaveBeenCalledWith(
            expect.objectContaining({ workspace_id: 'workspace_main', generation: 4 }),
            'function_main',
            'no_target',
        )
        expect(wrapper.text()).toContain('检查发现 1 个问题')
        wrapper.unmount()
    })

    it('confirms a selected resource through typed update_argument and returns to the inspector', async () => {
        apiMocks.applyCommand.mockResolvedValueOnce(snapshot(revisionB, true))
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.find('.open-resource').exists()).toBe(true))
        await wrapper.get('.open-resource').trigger('click')
        await wrapper.get('.apply-resource').trigger('click')
        await flushPromises()

        expect(apiMocks.applyCommand).toHaveBeenCalledWith(
            expect.objectContaining({ workspace_id: 'workspace_main', generation: 4 }),
            'function_main', revisionA,
            {
                kind: 'update_argument', statement_id: 'statement_find', parameter_id: 'parameter_image',
                value: { value_id: 'value_image', kind: 'asset_ref', asset_id: 'asset_login', asset_kind: 'image' },
            },
        )
        expect(wrapper.find('.open-resource').exists()).toBe(true)
        expect(document.activeElement).toBe(wrapper.get('.open-resource').element)
        wrapper.unmount()
    })

    it('does not overwrite on a revision conflict and keeps the explicit resource choice recoverable', async () => {
        apiMocks.applyCommand.mockRejectedValueOnce(new ProgramApiError('项目函数已被外部修改', {
            status: 409,
            code: 'program_revision_conflict',
            recoveryAction: 'reload_workspace',
            diagnostics: [{ function_id: 'function_main', expected_revision: revisionA, actual_revision: revisionB }],
        }))
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.find('.open-resource').exists()).toBe(true))
        await wrapper.get('.open-resource').trigger('click')
        await wrapper.get('.apply-resource').trigger('click')
        await flushPromises()

        expect(apiMocks.applyCommand).toHaveBeenCalledTimes(1)
        expect(wrapper.find('.resource-stub').exists()).toBe(true)
        expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)
        expect(wrapper.text()).toContain('项目函数已在外部修改')
        wrapper.unmount()
    })

    it('saves a focused list edit through the stable update_argument command', async () => {
        apiMocks.applyCommand.mockResolvedValueOnce(snapshot(revisionB))
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.find('.open-value-editor').exists()).toBe(true))

        ;(wrapper.get('.open-value-editor').element as HTMLElement).focus()
        await wrapper.get('.open-value-editor').trigger('click')
        await flushPromises()
        expect(wrapper.find('.value-editor-stub').exists()).toBe(true)

        await wrapper.get('.save-value').trigger('click')
        await flushPromises()

        expect(apiMocks.applyCommand).toHaveBeenCalledWith(
            expect.objectContaining({ workspace_id: 'workspace_main', generation: 4 }),
            'function_main', revisionA,
            {
                kind: 'update_argument',
                statement_id: 'statement_find',
                parameter_id: 'parameter_tasks',
                value: {
                    value_id: 'value_tasks',
                    kind: 'list',
                    item_type: 'string',
                    items: [
                        { value_id: 'value_task_1', kind: 'string', value: '日常任务' },
                        { value_id: 'value_task_2', kind: 'string', value: '周常任务' },
                    ],
                },
            },
        )
        expect(wrapper.find('.value-editor-stub').exists()).toBe(false)
        expect(document.activeElement).toBe(wrapper.get('.open-value-editor').element)
        wrapper.unmount()
    })

    it('refuses a focused value draft when the loaded Program revision changed locally', async () => {
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.find('.open-value-editor').exists()).toBe(true))
        await wrapper.get('.open-value-editor').trigger('click')
        await flushPromises()

        const programStore = useProgramStore()
        if (!programStore.serverSnapshot) throw new Error('expected the Program snapshot to be loaded')
        programStore.serverSnapshot.revision = revisionB
        await wrapper.get('.save-value').trigger('click')
        await flushPromises()

        expect(apiMocks.applyCommand).not.toHaveBeenCalled()
        expect(wrapper.find('.value-editor-stub').exists()).toBe(true)
        expect(wrapper.text()).toContain('编辑视图已过期')
        wrapper.unmount()
    })

    it('keeps the focused value draft recoverable when the backend reports a revision conflict', async () => {
        apiMocks.applyCommand.mockRejectedValueOnce(new ProgramApiError('项目函数已被外部修改', {
            status: 409,
            code: 'program_revision_conflict',
            recoveryAction: 'reload_workspace',
            diagnostics: [{ function_id: 'function_main', expected_revision: revisionA, actual_revision: revisionB }],
        }))
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.find('.open-value-editor').exists()).toBe(true))
        await wrapper.get('.open-value-editor').trigger('click')
        await wrapper.get('.save-value').trigger('click')
        await flushPromises()

        expect(apiMocks.applyCommand).toHaveBeenCalledTimes(1)
        expect(wrapper.find('.value-editor-stub').exists()).toBe(true)
        expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)
        expect(wrapper.text()).toContain('项目函数已在外部修改')
        wrapper.unmount()
    })

    it('uses the active workspace icon to open the narrow sidebar and restores focus on Escape', async () => {
        vi.stubGlobal('matchMedia', vi.fn(() => ({
            matches: true,
            addEventListener: vi.fn(),
            removeEventListener: vi.fn(),
        })))
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.find('[aria-label="展开函数库侧栏"]').exists()).toBe(true))

        const trigger = wrapper.get('[aria-label="展开函数库侧栏"]')
        await trigger.trigger('click')
        await flushPromises()

        const drawer = wrapper.get('.function-library-shell')
        expect(drawer.attributes('role')).toBe('dialog')
        expect(drawer.attributes('aria-modal')).toBe('true')
        expect(wrapper.get('.editor-pane').attributes()).toHaveProperty('inert')
        expect(document.activeElement).toBe(wrapper.get('[aria-label="关闭函数库"].function-library-drawer-close').element)

        await drawer.trigger('keydown', { key: 'Escape' })
        await flushPromises()

        expect(wrapper.find('.function-library-shell[role="dialog"]').exists()).toBe(false)
        expect(document.activeElement).toBe(trigger.element)
        wrapper.unmount()
    })

    it('keeps the two narrow side drawers mutually exclusive', async () => {
        vi.stubGlobal('matchMedia', vi.fn(() => ({
            matches: true,
            addEventListener: vi.fn(),
            removeEventListener: vi.fn(),
        })))
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.find('[aria-label="展开函数库侧栏"]').exists()).toBe(true))

        await wrapper.get('[aria-label="展开函数库侧栏"]').trigger('click')
        expect(wrapper.find('.function-library-shell[role="dialog"]').exists()).toBe(true)
        expect(wrapper.find('[aria-label="展开语句检查器"]').exists()).toBe(true)

        await wrapper.get('[aria-label="展开语句检查器"]').trigger('click')
        await flushPromises()
        expect(wrapper.find('.function-library-shell[role="dialog"]').exists()).toBe(false)
        expect(wrapper.find('[aria-label="展开函数库侧栏"]').exists()).toBe(true)
        expect(wrapper.find('[aria-label="收起语句检查器"]').exists()).toBe(true)
        wrapper.unmount()
    })

    it('keeps repeated context out of the titlebar and toggles both program side panels from their rails', async () => {
        vi.stubGlobal('matchMedia', vi.fn(() => ({
            matches: false,
            addEventListener: vi.fn(),
            removeEventListener: vi.fn(),
        })))
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.find('[aria-label="收起函数库侧栏"]').exists()).toBe(true))

        expect(wrapper.find('.breadcrumb').exists()).toBe(false)
        expect(wrapper.find('.vnext-activity-rail').exists()).toBe(true)
        await wrapper.get('[aria-label="收起函数库侧栏"]').trigger('click')
        expect(wrapper.get('.main-stage').classes()).toContain('sidebar-collapsed')
        expect(wrapper.find('[aria-label="展开函数库侧栏"]').exists()).toBe(true)

        await wrapper.get('[aria-label="收起语句检查器"]').trigger('click')
        expect(wrapper.find('[aria-label="展开语句检查器"]').exists()).toBe(true)
        wrapper.unmount()
    })

    it('chooses an existing variable before inserting a modify-variable statement', async () => {
        apiMocks.getProjectVariables.mockResolvedValueOnce({
            schema_version: 1,
            variables: [{
                variable_id: 'variable_energy', display_name: '当前体力', value_type: 'int64',
                default_value: { value_id: 'value_energy', kind: 'int64', value: 18 },
                description: '', constraints: {},
            }],
            revision: revisionA,
        })
        apiMocks.applyCommand.mockResolvedValueOnce(snapshot(revisionB))
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.findComponent(EditorStub).exists()).toBe(true))

        wrapper.getComponent({ name: 'ProgramFunctionLibrary' }).vm.$emit('insert', {
            source: 'structure', function_id: 'assignment.existing',
        })
        await flushPromises()

        expect(wrapper.get('[aria-labelledby="modify-variable-title"]').text()).toContain('当前体力')
        expect(document.activeElement).toBe(wrapper.get('[data-variable-option]').element)
        await wrapper.get('[data-variable-option]').trigger('click')
        await flushPromises()

        expect(apiMocks.applyCommand).toHaveBeenCalledWith(
            expect.objectContaining({ workspace_id: 'workspace_main', generation: 4 }),
            'function_main', revisionA,
            expect.objectContaining({
                kind: 'insert_assignment',
                target: expect.objectContaining({ kind: 'project_variable', variable_id: 'variable_energy' }),
                value: expect.objectContaining({ kind: 'int64', value: 0 }),
            }),
        )
        expect(wrapper.find('[aria-labelledby="modify-variable-title"]').exists()).toBe(false)
        wrapper.unmount()
    })

    it('keeps create, extract, and rename transactions on the same compact single-field form row', async () => {
        const wrapper = mountIde()
        await vi.waitFor(() => expect(wrapper.findComponent(EditorStub).exists()).toBe(true))
        const library = wrapper.getComponent({ name: 'ProgramFunctionLibrary' })

        library.vm.$emit('create-project')
        await flushPromises()
        const create = wrapper.get('[aria-labelledby="create-program-title"]')
        expect(create.get('.dialog-form-row').classes()).toContain('app-form-row')
        expect(create.get('input').classes()).toContain('app-form-control')
        expect(create.find('header p').exists()).toBe(false)
        await create.get('[label="关闭"]').trigger('click')

        await wrapper.get('.extract-statements').trigger('click')
        const extract = wrapper.get('[aria-labelledby="extract-program-title"]')
        expect(extract.get('.dialog-form-row').classes()).toContain('app-form-row')
        expect(extract.get('header p').text()).toContain('连续语句')
        await extract.get('[label="关闭"]').trigger('click')

        library.vm.$emit('rename-project', { function_id: 'function_main', display_name: '主程序' })
        await flushPromises()
        const rename = wrapper.get('[aria-labelledby="rename-program-title"]')
        expect(rename.get('.dialog-form-row').classes()).toContain('app-form-row')
        expect(rename.find('header p').exists()).toBe(false)
        expect(rename.get('input').element).toHaveProperty('value', '主程序')
        wrapper.unmount()
    })
})

