import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import VNextPlayerWorkspace from '../components/VNextPlayerWorkspace.vue'
import playerWorkspaceSource from '../components/VNextPlayerWorkspace.vue?raw'
import { useVNextStore } from '../store'

const api = vi.hoisted(() => ({
    playerForm: vi.fn(), savePlayerForm: vi.fn(), playerBindingSources: vi.fn(),
    playerPreviewRun: vi.fn(), runStatus: vi.fn(), cancelRun: vi.fn(),
}))
vi.mock('../api', () => ({
    mergeRuntimeSession: (_current: unknown, next: unknown) => next,
    vnextApi: api,
}))

const workspace = { workspace_id: 'w', generation: 1, project_id: 'p', project_name: '演示项目', project_path: 'D:/Demo', read_only: false }
const emptyForm = { schema_version: 3 as const, title: '脚本运行器', pages: [{ page_id: 'page_main', title: '运行配置', controls: [] }] }
const sourceCatalog = {
    schema_version: 3 as const,
    available: true,
    unavailable_reason: '',
    diagnostics: [],
    sources: [{
        source_id: 'project-variable:count', kind: 'project_variable' as const, label: '运行次数',
        path: [{ id: 'project-variable', label: '项目变量' }],
        binding: { kind: 'project_variable' as const, variable_id: 'variable-count' },
        required: false,
        recommended_control: 'number' as const, platforms: ['windows' as const], value_type: 'int64',
        type_fingerprint: 'sha256:fingerprint', constraints: { min: 1, max: 99 }, options: [], default: 1,
    }, {
        source_id: 'project-variable:point', kind: 'project_variable' as const, label: '点击坐标',
        path: [{ id: 'project-variable', label: '项目变量' }],
        binding: { kind: 'project_variable' as const, variable_id: 'variable-point' },
        required: false,
        recommended_control: 'coordinate' as const,
        platforms: ['windows' as const, 'android_local' as const], value_type: 'point',
        type_fingerprint: 'sha256:point', constraints: {}, options: [], default: { x: 1, y: 2 },
        parameter_ui: {
            control: 'coordinate' as const,
            help: '运行前可在终端重新取点',
            actions: [{ id: 'pick-point', capture_kind: 'point' as const, platforms: ['windows' as const, 'android_local' as const] }],
        },
    }],
}

function installComponentStyles(source: string) {
    const element = document.createElement('style')
    element.dataset.playerLayoutTest = 'true'
    element.textContent = source.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] || ''
    document.head.append(element)
}

describe('VNextPlayerWorkspace schema3 authoring', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        vi.clearAllMocks()
        vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
        api.playerForm.mockResolvedValue(emptyForm)
        api.savePlayerForm.mockImplementation(async (_workspace, form) => form)
        api.playerBindingSources.mockResolvedValue(sourceCatalog)
        api.playerPreviewRun.mockResolvedValue({ execution_id: 'preview_1', status: 'completed', events: [] })
    })
    afterEach(() => {
        vi.unstubAllGlobals()
        document.querySelectorAll('[data-player-layout-test]').forEach((element) => element.remove())
    })

    function setup() {
        const store = useVNextStore()
        store.workspace = workspace
        store.playerForm = structuredClone(emptyForm)
        return { store, wrapper: mount(VNextPlayerWorkspace) }
    }

    it('从 Pinia 响应式 schema3 表单建立本地草稿，不触发 DataCloneError', async () => {
        const { wrapper } = setup()
        await flushPromises()
        expect(wrapper.text()).toContain('脚本运行器')
        expect(wrapper.text()).toContain('运行配置')
        wrapper.unmount()
    })

    it('应用设置统一保存 Player 名称与原生窗口图标', async () => {
        const { store, wrapper } = setup()
        store.assets = [{
            asset_id: 'asset_app_icon', display_name: '超能世界图标', category: 'image', folder: '',
            path: 'assets/image/asset_app_icon.png', extension: '.png', mime_type: 'image/png',
            size_bytes: 12, width: 64, height: 64, sha256: 'a'.repeat(64), source: 'import',
            created_at: '', updated_at: '', aliases: [], capture: null,
        }]
        await flushPromises()

        await wrapper.get('.application-row').trigger('click')
        await wrapper.get('.player-inspector input').setValue('超能世界助手')
        await wrapper.get('.player-inspector select').setValue('asset_app_icon')
        await wrapper.get('.player-outline footer .primary').trigger('click')
        await flushPromises()

        expect(api.savePlayerForm.mock.calls[0][1]).toMatchObject({
            title: '超能世界助手', icon_asset_id: 'asset_app_icon',
        })
        wrapper.unmount()
    })

    it('窄窗口仍可通过抽屉编辑页面属性', async () => {
        vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
        const { wrapper } = setup()
        await flushPromises()
        expect(wrapper.find('.player-inspector').exists()).toBe(false)
        await wrapper.get('[aria-label="打开页面与控件列表"]').trigger('click')
        expect(wrapper.get('.player-outline').classes()).toContain('is-open')
        await wrapper.get('[aria-label="关闭页面与控件列表"]').trigger('click')
        expect(wrapper.get('.player-outline').classes()).not.toContain('is-open')
        await wrapper.get('.page-row').trigger('click')
        expect(wrapper.get('.player-inspector').classes()).toContain('is-compact')
        expect(wrapper.find('.player-panel-scrim').exists()).toBe(true)
        await wrapper.get('.player-inspector').trigger('keydown', { key: 'Escape' })
        expect(wrapper.find('.player-inspector').exists()).toBe(false)
        wrapper.unmount()
    })

    it('创建第一个页面后直接进入名称输入，避免用户重新寻找下一步', async () => {
        const store = useVNextStore()
        store.workspace = workspace
        store.playerForm = { schema_version: 3, title: '脚本运行器', pages: [] }
        api.playerForm.mockResolvedValue(store.playerForm)
        const wrapper = mount(VNextPlayerWorkspace, { attachTo: globalThis.document.body })
        await flushPromises()

        await wrapper.get('.empty-create').trigger('click')
        await wrapper.vm.$nextTick()

        expect((wrapper.get('.player-inspector input').element as HTMLInputElement).value).toBe('页面 1')
        expect(globalThis.document.activeElement).toBe(wrapper.get('.player-inspector input').element)
        wrapper.unmount()
    })

    it('布尔字典选项可在设计器中设为固定必选或固定不可选', async () => {
        const form = {
            schema_version: 3 as const,
            title: '任务脚本',
            pages: [{
                page_id: 'page_main',
                title: '任务',
                controls: [{
                    control_id: 'daily_tasks',
                    type: 'key-value' as const,
                    label: '日常任务',
                    help: '',
                    default: { '开放任务': true, '暂未开放': false },
                    options: [
                        { label: '开放任务', value: '开放任务' },
                        { label: '暂未开放', value: '暂未开放' },
                    ],
                    required: false,
                    binding: { kind: 'project_variable' as const, variable_id: 'daily_tasks' },
                    layout: { span: 12 },
                    parameter_ui: { control: 'key-value' as const, player_supported: true },
                    constraints: {},
                    platforms: ['windows' as const],
                    source_type: 'map<string,bool>',
                    type_fingerprint: 'sha256:tasks',
                    terminal_actions: [],
                }],
            }],
        }
        const store = useVNextStore()
        store.workspace = workspace
        store.playerForm = structuredClone(form)
        api.playerForm.mockResolvedValue(form)
        const wrapper = mount(VNextPlayerWorkspace)
        await flushPromises()

        await wrapper.get('.control-row').trigger('click')
        const optionModes = wrapper.findAll<HTMLSelectElement>('.fixed-option-row select')
        expect(optionModes).toHaveLength(2)
        await optionModes[1].setValue('off')

        const locked = (wrapper.vm as unknown as { selectedControl: { options: Array<Record<string, unknown>>; default: Record<string, boolean> } }).selectedControl
        expect(locked.options[1]).toMatchObject({ fixed_value: false })
        expect(locked.default['暂未开放']).toBe(false)
        expect(wrapper.get('[data-preview-control-id="daily_tasks"]').text()).toContain('不可选')
        wrapper.unmount()
    })

    it('只从后端可发布目录创建带稳定绑定和类型指纹的控件', async () => {
        const { wrapper } = setup()
        await flushPromises()

        await wrapper.get('[aria-label="添加已绑定控件"]').trigger('click')
        await flushPromises()
        await wrapper.get('[aria-label="使用 运行次数"]').trigger('click')

        expect(wrapper.get('.control-row').text()).toContain('运行次数')
        expect(wrapper.find('.preview-control').exists()).toBe(true)
        await wrapper.get('.player-outline footer .primary').trigger('click')
        await flushPromises()

        const saved = api.savePlayerForm.mock.calls[0][1]
        expect(saved.schema_version).toBe(3)
        expect(saved).not.toHaveProperty('bindings')
        expect(saved.pages[0].controls[0]).toMatchObject({
            source_type: 'int64', type_fingerprint: 'sha256:fingerprint',
            binding: { kind: 'project_variable', variable_id: 'variable-count' },
        })
        wrapper.unmount()
    })

    it('新增复杂绑定时继承共享参数契约中的帮助说明', async () => {
        const { wrapper } = setup()
        await flushPromises()

        await wrapper.get('[aria-label="添加已绑定控件"]').trigger('click')
        await flushPromises()
        await wrapper.get('[aria-label="使用 点击坐标"]').trigger('click')

        await wrapper.get('.player-outline footer .primary').trigger('click')
        await flushPromises()

        expect(api.savePlayerForm.mock.calls[0][1].pages[0].controls[0].help)
            .toBe('运行前可在终端重新取点')
        wrapper.unmount()
    })

    it('桌面预览让简单字段同行，窄屏预览恢复单列且不压缩复杂字段', async () => {
        const layoutForm = {
            schema_version: 3 as const,
            title: '布局预览',
            pages: [{ page_id: 'main', title: '运行', controls: [{
                control_id: 'count', type: 'number' as const, label: '运行次数', help: '最多运行十次', default: 1,
                options: [], required: false,
                binding: { kind: 'project_variable' as const, variable_id: 'variable-count' },
                layout: { span: 12 }, parameter_ui: { control: 'number' as const }, constraints: { min: 1 },
            }, {
                control_id: 'region', type: 'region' as const, label: '识别区域', help: '', default: { x: 0, y: 0, width: 10, height: 10 },
                options: [], required: false,
                binding: { kind: 'project_variable' as const, variable_id: 'variable-region' },
                layout: { span: 12 }, parameter_ui: { control: 'region' as const }, constraints: {},
            }] }],
        }
        api.playerForm.mockResolvedValue(layoutForm)
        const store = useVNextStore()
        store.workspace = workspace
        store.playerForm = structuredClone(layoutForm)
        installComponentStyles(playerWorkspaceSource)
        const wrapper = mount(VNextPlayerWorkspace, { attachTo: document.body })
        await flushPromises()

        const count = wrapper.get('[data-preview-control-id="count"]')
        const region = wrapper.get('[data-preview-control-id="region"]')
        expect(count.classes()).toContain('is-inline-field')
        expect(region.classes()).not.toContain('is-inline-field')
        expect(getComputedStyle(count.element).display).toBe('grid')
        expect(getComputedStyle(count.element).gridTemplateColumns).toContain('minmax')

        await count.trigger('click')
        const propertyFields = wrapper.findAll('.properties .property-field')
        expect(propertyFields).toHaveLength(3)
        expect(propertyFields.every((field) => getComputedStyle(field.element).display === 'grid')).toBe(true)
        expect(propertyFields.every((field) => getComputedStyle(field.element).gridTemplateColumns.includes('minmax'))).toBe(true)
        expect(getComputedStyle(wrapper.get('.properties .check-row').element).display).toBe('flex')
        expect(playerWorkspaceSource).toContain('@container(max-width:240px)')

        await wrapper.get('[aria-label="窄屏预览"]').trigger('click')
        expect(wrapper.get('.player-card').classes()).toContain('narrow')
        expect(getComputedStyle(count.element).gridTemplateColumns.replaceAll(' ', '')).toBe('minmax(0,1fr)')
        expect(getComputedStyle(count.element).alignItems).toBe('stretch')
        wrapper.unmount()
    })

    it('长表单受工作区高度约束并由预览画布持续滚动', () => {
        expect(playerWorkspaceSource).toMatch(/\.player-workspace\{[^}]*min-height:0[^}]*overflow:hidden/)
        expect(playerWorkspaceSource).toMatch(/\.player-outline,\.player-inspector\{[^}]*min-height:0/)
        expect(playerWorkspaceSource).toMatch(/\.player-preview-area\{[^}]*min-height:0[^}]*grid-template-rows:[^}]*minmax\(0,1fr\)/)
        expect(playerWorkspaceSource).toMatch(/\.preview-canvas\{[^}]*min-height:0[^}]*overflow:auto[^}]*overscroll-behavior:contain/)
    })

    it('用所属函数、资源名和粘贴的稳定 ID 精确区分同名语句', async () => {
        const duplicateSources = [
            { statementId: 'statement_image_login_12345678', assetId: 'asset_login', assetName: '登录按钮' },
            { statementId: 'statement_image_reward_87654321', assetId: 'asset_reward', assetName: '奖励按钮' },
        ].map(({ statementId, assetId }) => ({
            source_id: `statement_parameter:function_main:${statementId}:image`,
            kind: 'statement_parameter' as const,
            label: '图像.等待出现 · 图片',
            path: [
                { id: 'project_functions', label: '项目函数' },
                { id: 'function_main', label: '主程序' },
                { id: 'statement_parameters', label: '语句参数' },
                { id: statementId, label: '图像.等待出现' },
            ],
            binding: { kind: 'statement_parameter' as const, function_id: 'function_main', statement_id: statementId, parameter_id: 'image' },
            required: true,
            recommended_control: 'resource' as const,
            platforms: ['windows' as const], value_type: 'image_resource', type_fingerprint: `sha256:${statementId}`,
            constraints: {}, options: [], default: { asset_id: assetId, asset_kind: 'image' },
        }))
        api.playerBindingSources.mockResolvedValue({ ...sourceCatalog, sources: [...sourceCatalog.sources, ...duplicateSources] })
        const { store, wrapper } = setup()
        store.assets = [
            { asset_id: 'asset_login', display_name: '登录按钮', category: 'image', folder: '', path: 'images/login.png', extension: '.png', mime_type: 'image/png', size_bytes: 10, width: 24, height: 24, sha256: 'login', source: 'capture', created_at: '', updated_at: '', aliases: [], capture: null },
            { asset_id: 'asset_reward', display_name: '奖励按钮', category: 'image', folder: '', path: 'images/reward.png', extension: '.png', mime_type: 'image/png', size_bytes: 10, width: 24, height: 24, sha256: 'reward', source: 'capture', created_at: '', updated_at: '', aliases: [], capture: null },
        ]
        await flushPromises()
        await wrapper.get('[aria-label="添加已绑定控件"]').trigger('click')
        await flushPromises()

        await wrapper.get('.picker-search input').setValue('statement_image_login_12345678')

        expect(wrapper.get('.located-statement').text()).toContain('#image_lo')
        expect(wrapper.get('.located-statement').text()).toContain('1 个可发布参数')
        expect(wrapper.findAll('.source-row')).toHaveLength(1)
        expect(wrapper.get('.source-row strong').text()).toBe('图像.等待出现 · 登录按钮')
        expect(wrapper.get('.source-row small').text()).toContain('#image_lo')
        expect(wrapper.get('.source-groups h3').text()).toBe('项目函数 · 主程序')
        wrapper.unmount()
    })

    it('从语句直达 Player 时只筛选后端目录，不默认创建控件', async () => {
        const statementId = 'statement_direct_player_12345678'
        api.playerBindingSources.mockResolvedValue({
            ...sourceCatalog,
            sources: [...sourceCatalog.sources, {
                source_id: `statement_parameter:function_main:${statementId}:timeout`,
                kind: 'statement_parameter', label: '图像.等待出现 · 超时',
                path: [
                    { id: 'project_functions', label: '项目函数' },
                    { id: 'function_main', label: '主程序' },
                    { id: 'statement_parameters', label: '语句参数' },
                    { id: statementId, label: '图像.等待出现' },
                ],
                binding: { kind: 'statement_parameter', function_id: 'function_main', statement_id: statementId, parameter_id: 'timeout' },
                required: false, recommended_control: 'duration', platforms: ['windows'], value_type: 'duration',
                type_fingerprint: 'sha256:duration', constraints: {}, options: [], default: 3000,
            }],
        })
        const store = useVNextStore()
        store.workspace = workspace
        store.playerForm = { schema_version: 3, title: '脚本运行器', pages: [] }
        api.playerForm.mockResolvedValue(store.playerForm)
        const wrapper = mount(VNextPlayerWorkspace, { props: { initialStatementId: statementId } })
        await flushPromises()

        expect(wrapper.find('.source-picker').exists()).toBe(true)
        expect((wrapper.get('.picker-search input').element as HTMLInputElement).value).toBe(statementId)
        expect(wrapper.findAll('.source-row')).toHaveLength(1)
        expect(wrapper.find('.control-row').exists()).toBe(false)
        expect(wrapper.text()).not.toContain('有未保存修改')
        expect(wrapper.emitted('initial-location-consumed')).toHaveLength(1)
        wrapper.unmount()
    })

    it('目录请求失败时不展示可伪造的空控件入口', async () => {
        api.playerBindingSources.mockRejectedValue(new Error('目录暂不可用'))
        const { wrapper } = setup()
        await flushPromises()
        await wrapper.get('[aria-label="添加已绑定控件"]').trigger('click')
        await flushPromises()

        expect(wrapper.text()).toContain('目录暂不可用')
        expect(wrapper.find('.control-row').exists()).toBe(false)
        wrapper.unmount()
    })

    it('项目草稿未通过检查时用正常不可用状态解释绑定来源', async () => {
        api.playerBindingSources.mockResolvedValue({
            schema_version: 3,
            available: false,
            unavailable_reason: '先修复项目问题后才能选择 Player 绑定：必填值尚未配置',
            diagnostics: [{ severity: 'error', message: '必填值尚未配置' }],
            sources: [],
        })
        const { wrapper } = setup()
        await flushPromises()
        await wrapper.get('[aria-label="添加已绑定控件"]').trigger('click')
        await flushPromises()

        expect(wrapper.get('.picker-state.error').text()).toContain('必填值尚未配置')
        expect(wrapper.find('.control-row').exists()).toBe(false)
        wrapper.unmount()
    })

    it('新增字段预选共享契约推荐动作，作者仍可逐平台关闭', async () => {
        const { wrapper } = setup()
        await flushPromises()
        await wrapper.get('[aria-label="添加已绑定控件"]').trigger('click')
        await flushPromises()
        await wrapper.get('[aria-label="使用 点击坐标"]').trigger('click')

        expect(wrapper.get('.terminal-action-section').text()).toContain('已开放 1 项')
        const options = wrapper.findAll('.terminal-action-list input')
        expect(options).toHaveLength(2)
        expect((options[0].element as HTMLInputElement).checked).toBe(true)
        expect((options[1].element as HTMLInputElement).checked).toBe(true)
        expect(options[1].attributes('disabled')).toBeUndefined()
        expect(wrapper.text()).not.toContain('Android 本机原生步骤流尚未实现')
        await options[1].setValue(false)
        await wrapper.get('.player-outline footer .primary').trigger('click')
        await flushPromises()

        const saved = api.savePlayerForm.mock.calls[0][1]
        expect(saved.pages[0].controls[0].terminal_actions).toEqual([{
            action_id: 'pick-point', platforms: ['windows'],
        }])
        expect(wrapper.find('.preview-control .value-vector > button').exists()).toBe(false)
        wrapper.unmount()
    })

    it('必填文件引用在终端授权前不伪造 null 默认值', async () => {
        api.playerBindingSources.mockResolvedValue({
            ...sourceCatalog,
            sources: [{
                source_id: 'project-variable:input-file', kind: 'project_variable', label: '输入文件',
                path: [{ id: 'project-variable', label: '项目变量' }],
                binding: { kind: 'project_variable', variable_id: 'variable-input-file' },
                required: true,
                recommended_control: 'file',
                platforms: ['windows', 'android_adb', 'android_local'], value_type: 'file_ref<read>',
                type_fingerprint: 'sha256:file-read', constraints: { extensions: ['.json'] }, options: [],
                parameter_ui: {
                    control: 'file', player_supported: true,
                    actions: [{ id: 'choose-file-read', platforms: ['windows', 'android_adb', 'android_local'] }],
                },
            }],
        })
        const { wrapper } = setup()
        await flushPromises()
        await wrapper.get('[aria-label="添加已绑定控件"]').trigger('click')
        await flushPromises()
        await wrapper.get('[aria-label="使用 输入文件"]').trigger('click')
        await wrapper.get('.player-outline footer .primary').trigger('click')
        await flushPromises()

        const saved = api.savePlayerForm.mock.calls[0][1]
        expect(saved.pages[0].controls[0].type).toBe('file')
        expect(saved.pages[0].controls[0]).not.toHaveProperty('default')
        expect(wrapper.get('.reference-summary').text()).toContain('尚未选择文件')
        wrapper.unmount()
    })

    it('只通过真实 preview-run 执行已保存表单并回传运行会话', async () => {
        const { wrapper } = setup()
        await flushPromises()

        await wrapper.get('[aria-label="预览运行 Player"]').trigger('click')
        await flushPromises()

        expect(api.playerPreviewRun).toHaveBeenCalledWith(workspace, {
            target_id: null,
            player_values: {},
            action_control_id: '',
        })
        expect(wrapper.emitted('runtime-session')?.[0]?.[0]).toMatchObject({
            execution_id: 'preview_1',
            status: 'completed',
        })
        wrapper.unmount()
    })
})
