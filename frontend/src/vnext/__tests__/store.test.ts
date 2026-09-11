import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useVNextStore } from '../store'

const api = vi.hoisted(() => ({
    functions: vi.fn(), active: vi.fn(), chooseFolder: vi.fn(), open: vi.fn(),
    targets: vi.fn(), targetReferences: vi.fn(), saveTargets: vi.fn(),
    assets: vi.fn(), playerForm: vi.fn(), savePlayerForm: vi.fn(),
    importAsset: vi.fn(), updateAsset: vi.fn(), replaceAsset: vi.fn(),
    deleteAsset: vi.fn(), assetContent: vi.fn(),
}))

vi.mock('../api', () => ({
    VNextApiError: class VNextApiError extends Error {
        status: number
        code: string
        diagnostics: Array<Record<string, unknown>>
        constructor(message: string, status = 0, _errorId = '', code = '', _retryable = false, _recoveryAction = '', diagnostics: Array<Record<string, unknown>> = []) {
            super(message); this.status = status; this.code = code; this.diagnostics = diagnostics
        }
    },
    vnextApi: api,
}))

const workspace = {
    workspace_id: 'workspace_1', generation: 1, project_id: 'project_1',
    project_name: '测试项目', project_path: 'D:/Projects/Test', read_only: false,
}

describe('vNext format-6 workspace store', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        vi.clearAllMocks()
        api.functions.mockResolvedValue({ functions: [] })
        api.active.mockResolvedValue({ workspace: null, targets: [], default_target_id: null, revision: '' })
        api.assets.mockResolvedValue({ categories: [], assets: [] })
        api.playerForm.mockResolvedValue({ schema_version: 3, title: '脚本运行器', pages: [] })
        api.savePlayerForm.mockImplementation(async (_workspace, form) => form)
        api.targets.mockResolvedValue({ schema_version: 1, targets: [], default_target_id: null, revision: 'sha256:initial' })
        api.saveTargets.mockImplementation(async (_workspace, _expectedRevision, targets, defaultTargetId) => ({
            schema_version: 1,
            targets,
            default_target_id: defaultTargetId,
            revision: `sha256:saved-${api.saveTargets.mock.calls.length}`,
        }))
    })

    it('打开格式6项目只加载领域工作区，不请求源码', async () => {
        api.open.mockResolvedValue({ workspace, inspection: { status: 'valid' }, targets: [], default_target_id: null, revision: 'sha256:targets' })
        const store = useVNextStore()
        await store.openProject('D:/Projects/Test')

        expect(store.workspace?.project_id).toBe('project_1')
        expect(api.assets).toHaveBeenCalledWith(workspace)
        expect(api.playerForm).toHaveBeenCalledWith(workspace)
        expect(store.playerForm.schema_version).toBe(3)
    })

    it('按严格判别联合创建 Windows、ADB 和 Android 本机目标', async () => {
        const store = useVNextStore()
        store.workspace = workspace
        await store.refreshTargets()

        const windowsTarget = await store.addTarget('windows')
        const adbTarget = await store.addTarget('android_adb', { device_serial: 'emulator-5554' })
        const localTarget = await store.addTarget('android_local')

        expect(windowsTarget).toMatchObject({ type: 'windows', work_area: { mode: 'desktop' }, allow_physical_fallback: true })
        expect(adbTarget).toEqual(expect.objectContaining({ type: 'android_adb', device_serial: 'emulator-5554' }))
        expect(adbTarget).not.toHaveProperty('window_title')
        expect(localTarget).toEqual(expect.objectContaining({ type: 'android_local' }))
        expect(localTarget).not.toHaveProperty('work_area')
        expect(api.saveTargets.mock.calls[1]?.[1]).toBe('sha256:saved-1')
    })

    it('拒绝猜测 ADB 序列号，并允许显式使用无目标模式', async () => {
        const store = useVNextStore()
        store.workspace = workspace
        await store.refreshTargets()

        await expect(store.addTarget('android_adb')).rejects.toThrow('不会自动猜测设备')
        await store.saveTargets([], null)

        expect(api.saveTargets).toHaveBeenCalledWith(workspace, 'sha256:initial', [], null)
        expect(store.targets).toEqual([])
        expect(store.defaultTargetId).toBeNull()
    })

    it('revision 冲突不覆盖已经确认的目标快照，也不自动重试', async () => {
        const { VNextApiError } = await import('../api')
        const store = useVNextStore()
        store.workspace = workspace
        await store.refreshTargets()
        await store.addTarget('windows')
        const confirmedTargets = [...store.targets]
        api.saveTargets.mockRejectedValueOnce(new VNextApiError(
            '目标已被其他窗口修改', 409, '', 'target_revision_conflict', false, 'reload_workspace',
            [{ expected_revision: 'sha256:saved-1', actual_revision: 'sha256:external' }],
        ))

        await expect(store.saveTargets([], null)).rejects.toThrow('目标已被其他窗口修改')
        expect(store.targets).toEqual(confirmedTargets)
        expect(store.targetConflict).toEqual({
            expectedRevision: 'sha256:saved-1', actualRevision: 'sha256:external', message: '目标已被其他窗口修改',
        })
        expect(api.saveTargets).toHaveBeenCalledTimes(2)
    })

    it('Player 表单只接受 schema3 并原样保存稳定绑定', async () => {
        const store = useVNextStore()
        store.workspace = workspace
        const form = {
            schema_version: 3 as const,
            title: '每日任务',
            pages: [{
                page_id: 'page-main', title: '运行配置', controls: [{
                    control_id: 'control-count', type: 'number' as const, label: '次数', help: '', default: 1,
                    options: [], required: true, binding: { kind: 'project_variable' as const, variable_id: 'variable-count' },
                    layout: { span: 12 }, source_type: 'int64', type_fingerprint: 'sha256:fingerprint',
                }],
            }],
        }

        await store.savePlayerForm(form)
        expect(api.savePlayerForm).toHaveBeenCalledWith(workspace, form)
        expect(store.playerForm.pages[0].controls[0].binding).toEqual({ kind: 'project_variable', variable_id: 'variable-count' })
    })

    it('捕获保存后增量合并资源与目录，不再全量刷新资源清单', () => {
        const store = useVNextStore()
        store.assets = [{
            asset_id: 'asset_old', display_name: '旧图', category: 'image', folder: '',
            path: 'assets/image/asset_old.png', extension: '.png', mime_type: 'image/png',
            size_bytes: 3, width: 1, height: 1, sha256: '0'.repeat(64), source: 'import',
            created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z', aliases: [], capture: null,
        }]
        store.assetCategories = [{ id: 'image', label: '图像', folders: [] }]
        store.upsertAssets([{
            asset_id: 'asset_new', display_name: '新图', category: 'image', folder: '任务',
            path: 'assets/image/任务/asset_new.png', extension: '.png', mime_type: 'image/png',
            size_bytes: 4, width: 2, height: 2, sha256: '1'.repeat(64), source: 'capture',
            created_at: '2026-09-11T00:00:00Z', updated_at: '2026-09-11T00:00:00Z', aliases: [], capture: null,
        }])

        expect(store.assets.map(item => item.asset_id)).toEqual(['asset_old', 'asset_new'])
        expect(store.assetCategories[0].folders).toEqual(['任务'])
        expect(api.assets).not.toHaveBeenCalled()
    })
})
