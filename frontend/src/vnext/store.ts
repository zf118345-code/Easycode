import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { setWorkspaceIdentity } from '@/api/workspaceIdentity'
import { VNextApiError, vnextApi } from './api'
import type {
    AssetCategory,
    AssetDefinition,
    FunctionDefinition,
    PlayerFormDefinition,
    TargetDefinition,
    TargetReferenceDefinition,
    WindowsWorkArea,
    WorkspaceIdentity,
} from './types'

export interface TargetRevisionConflict {
    expectedRevision: string
    actualRevision: string
    message: string
}

export interface NewTargetSetup {
    name?: string
    window_title?: string
    window_match?: 'contains' | 'exact' | 'regex'
    work_area?: WindowsWorkArea
    allow_physical_fallback?: boolean
    device_serial?: string
}

const emptyPlayerForm = (): PlayerFormDefinition => ({ schema_version: 3, title: '脚本运行器', features: { recording: false }, pages: [] })

function sameWorkspace(left: WorkspaceIdentity | null, right: WorkspaceIdentity): boolean {
    return left?.workspace_id === right.workspace_id && left.generation === right.generation
}

function fileAsBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onerror = () => reject(new Error('读取文件失败'))
        reader.onload = () => resolve(String(reader.result || '').split(',').pop() || '')
        reader.readAsDataURL(file)
    })
}

export const useVNextStore = defineStore('vnext-workspace', () => {
    const workspace = ref<WorkspaceIdentity | null>(null)
    const functions = ref<FunctionDefinition[]>([])
    const busy = ref(false)
    const operationError = ref('')
    const targets = ref<TargetDefinition[]>([])
    const defaultTargetId = ref<string | null>(null)
    const targetRevision = ref('')
    const targetConflict = ref<TargetRevisionConflict | null>(null)
    const targetError = ref('')
    const targetBlockedReferences = ref<TargetReferenceDefinition[]>([])
    const targetPendingCount = ref(0)
    const assets = ref<AssetDefinition[]>([])
    const assetCategories = ref<AssetCategory[]>([])
    const playerForm = ref<PlayerFormDefinition>(emptyPlayerForm())
    let targetMutationTail: Promise<void> = Promise.resolve()

    const targetBusy = computed(() => targetPendingCount.value > 0)

    function clearWorkspaceSurfaces(): void {
        targets.value = []
        defaultTargetId.value = null
        targetRevision.value = ''
        targetConflict.value = null
        targetError.value = ''
        targetBlockedReferences.value = []
        assets.value = []
        assetCategories.value = []
        playerForm.value = emptyPlayerForm()
        operationError.value = ''
    }

    function adoptTargetConfiguration(result: {
        targets?: TargetDefinition[]
        default_target_id?: string | null
        revision?: string
    }): void {
        targets.value = result.targets || []
        defaultTargetId.value = result.default_target_id || null
        targetRevision.value = result.revision || ''
        targetConflict.value = null
        targetError.value = ''
        targetBlockedReferences.value = []
    }

    async function refreshWorkspaceSurfaces(): Promise<void> {
        const results = await Promise.allSettled([refreshAssets(), refreshPlayerForm()])
        const failed = results.find((item): item is PromiseRejectedResult => item.status === 'rejected')
        operationError.value = failed
            ? failed.reason instanceof Error ? failed.reason.message : '部分项目内容加载失败'
            : ''
    }

    async function bootstrap(): Promise<void> {
        const [catalog, active] = await Promise.all([vnextApi.functions(), vnextApi.active()])
        functions.value = catalog.functions
        clearWorkspaceSurfaces()
        if (!active.workspace) {
            workspace.value = null
            return
        }
        workspace.value = active.workspace
        setWorkspaceIdentity(active.workspace)
        adoptTargetConfiguration(active)
        await refreshWorkspaceSurfaces()
    }

    async function chooseFolder(): Promise<string> {
        return (await vnextApi.chooseFolder()).path
    }

    async function chooseFile(title = '选择文件', extensions: string[] = []): Promise<string> {
        return (await vnextApi.chooseFile(title, extensions)).path
    }

    async function openProject(path: string, options: { initialize?: boolean; projectName?: string } = {}) {
        busy.value = true
        operationError.value = ''
        try {
            const result = await vnextApi.open(path, options)
            if (!result.workspace) return result
            workspace.value = result.workspace
            setWorkspaceIdentity(result.workspace)
            clearWorkspaceSurfaces()
            adoptTargetConfiguration(result)
            await refreshWorkspaceSurfaces()
            return result
        } finally {
            busy.value = false
        }
    }

    async function refreshFunctions(): Promise<void> {
        functions.value = (await vnextApi.functions()).functions
    }

    async function refreshTargets() {
        if (!workspace.value) {
            adoptTargetConfiguration({})
            return null
        }
        const workspaceAtStart = workspace.value
        targetPendingCount.value += 1
        try {
            const result = await vnextApi.targets(workspaceAtStart)
            if (!sameWorkspace(workspace.value, workspaceAtStart)) throw new Error('项目已经切换，旧目标配置未应用')
            adoptTargetConfiguration(result)
            return result
        } finally {
            targetPendingCount.value = Math.max(0, targetPendingCount.value - 1)
        }
    }

    async function targetReferences(targetId: string): Promise<TargetReferenceDefinition[]> {
        if (!workspace.value) throw new Error('请先打开项目')
        const workspaceAtStart = workspace.value
        targetPendingCount.value += 1
        targetError.value = ''
        targetBlockedReferences.value = []
        try {
            const result = await vnextApi.targetReferences(workspaceAtStart, targetId)
            if (!sameWorkspace(workspace.value, workspaceAtStart)) throw new Error('项目已经切换，旧目标引用结果未应用')
            targetBlockedReferences.value = result.references
            return result.references
        } catch (error) {
            targetError.value = error instanceof Error ? error.message : '目标引用检查失败'
            throw error
        } finally {
            targetPendingCount.value = Math.max(0, targetPendingCount.value - 1)
        }
    }

    function saveTargets(nextTargets: TargetDefinition[], nextDefaultTargetId: string | null): Promise<void> {
        const workspaceAtRequest = workspace.value
        if (!workspaceAtRequest) return Promise.reject(new Error('请先打开项目'))
        let resolveResult: () => void = () => undefined
        let rejectResult: (error: unknown) => void = () => undefined
        const result = new Promise<void>((resolve, reject) => { resolveResult = resolve; rejectResult = reject })
        targetMutationTail = targetMutationTail.catch(() => undefined).then(async () => {
            targetPendingCount.value += 1
            try {
                if (!sameWorkspace(workspace.value, workspaceAtRequest)) throw new Error('项目已经切换，旧目标操作未执行')
                if (!targetRevision.value) await refreshTargets()
                if (!sameWorkspace(workspace.value, workspaceAtRequest)) throw new Error('项目已经切换，旧目标操作未执行')
                if (!targetRevision.value) throw new Error('运行目标尚未载入')
                const saved = await vnextApi.saveTargets(workspaceAtRequest, targetRevision.value, nextTargets, nextDefaultTargetId)
                if (!sameWorkspace(workspace.value, workspaceAtRequest)) throw new Error('项目已经切换，旧目标保存结果未应用')
                adoptTargetConfiguration(saved)
                resolveResult()
            } catch (error) {
                targetError.value = error instanceof Error ? error.message : '运行目标保存失败'
                if (error instanceof VNextApiError && error.code === 'target_revision_conflict') {
                    const details = error.diagnostics[0] || {}
                    targetConflict.value = {
                        expectedRevision: String(details.expected_revision || targetRevision.value),
                        actualRevision: String(details.actual_revision || ''),
                        message: error.message,
                    }
                }
                if (error instanceof VNextApiError && error.code === 'target_referenced') {
                    targetBlockedReferences.value = error.diagnostics.flatMap((item) => (
                        typeof item.kind === 'string' ? [{ ...item, kind: item.kind } as TargetReferenceDefinition] : []
                    ))
                }
                rejectResult(error)
            } finally {
                targetPendingCount.value = Math.max(0, targetPendingCount.value - 1)
            }
        })
        return result
    }

    async function addTarget(type: TargetDefinition['type'], setup: NewTargetSetup = {}) {
        const targetId = `target_${crypto.randomUUID().replaceAll('-', '')}`
        let target: TargetDefinition
        if (type === 'windows') {
            const workArea = setup.work_area || (setup.window_title ? { mode: 'client' } : { mode: 'desktop' })
            target = {
                target_id: targetId,
                name: setup.name?.trim() || (workArea.mode === 'desktop' ? '全屏幕' : 'Windows 窗口'),
                type,
                window_title: setup.window_title?.trim() || '',
                window_match: setup.window_match || 'contains',
                work_area: workArea,
                allow_physical_fallback: workArea.mode === 'desktop' ? true : setup.allow_physical_fallback ?? true,
            }
        } else if (type === 'android_adb') {
            const serial = setup.device_serial?.trim() || ''
            if (!serial) throw new Error('请先填写明确的 ADB 设备序列号；EasyCode 不会自动猜测设备')
            target = { target_id: targetId, name: setup.name?.trim() || 'Android 模拟器', type, device_serial: serial }
        } else {
            target = { target_id: targetId, name: setup.name?.trim() || '当前手机', type }
        }
        await saveTargets([...targets.value, target], defaultTargetId.value || target.target_id)
        return target
    }

    async function updateTarget(target: TargetDefinition): Promise<void> {
        await saveTargets(targets.value.map((item) => item.target_id === target.target_id ? target : item), defaultTargetId.value)
    }

    async function refreshAssets(): Promise<void> {
        if (!workspace.value) { assets.value = []; assetCategories.value = []; return }
        const workspaceAtStart = workspace.value
        const result = await vnextApi.assets(workspaceAtStart)
        if (!sameWorkspace(workspace.value, workspaceAtStart)) return
        assets.value = result.assets
        assetCategories.value = result.categories
    }

    function upsertAssets(incoming: AssetDefinition[]): void {
        const valid = incoming.filter((item) => item && typeof item.asset_id === 'string' && item.asset_id)
        if (!valid.length) return
        const replacements = new Map(valid.map((item) => [item.asset_id, item]))
        assets.value = [
            ...assets.value.map((item) => replacements.get(item.asset_id) || item),
            ...valid.filter((item) => !assets.value.some((existing) => existing.asset_id === item.asset_id)),
        ]
        for (const asset of valid) {
            const category = assetCategories.value.find((item) => item.id === asset.category)
            if (category && asset.folder && !category.folders.includes(asset.folder)) {
                category.folders = [...category.folders, asset.folder]
                    .sort((left, right) => left.localeCompare(right, 'zh-CN'))
            }
        }
    }

    async function importAsset(file: File, category: AssetDefinition['category'], folder = '', displayName = '', capture?: Record<string, unknown>) {
        if (!workspace.value) return null
        const result = await vnextApi.importAsset(workspace.value, {
            category, folder, file_name: file.name, display_name: displayName,
            content_base64: await fileAsBase64(file), capture,
        })
        await refreshAssets()
        return result
    }

    async function updateAsset(assetId: string, payload: Partial<Pick<AssetDefinition, 'display_name' | 'category' | 'folder'>>) {
        if (!workspace.value) return undefined
        const result = await vnextApi.updateAsset(workspace.value, assetId, payload)
        await refreshAssets()
        return result.asset
    }

    async function replaceAsset(assetId: string, file: File) {
        if (!workspace.value) return undefined
        const result = await vnextApi.replaceAsset(workspace.value, assetId, { file_name: file.name, content_base64: await fileAsBase64(file) })
        assets.value = assets.value.map((item) => item.asset_id === assetId ? result.asset : item)
        return result.asset
    }

    async function deleteAsset(assetId: string, force = false, replacementAssetId = '') {
        if (!workspace.value) return null
        const result = await vnextApi.deleteAsset(workspace.value, assetId, force, replacementAssetId)
        if (result.deleted) await refreshAssets()
        return result
    }

    async function assetPreviewUrl(assetId: string): Promise<string> {
        if (!workspace.value) return ''
        return URL.createObjectURL(await vnextApi.assetContent(workspace.value, assetId))
    }

    async function refreshPlayerForm(): Promise<PlayerFormDefinition> {
        if (!workspace.value) { playerForm.value = emptyPlayerForm(); return playerForm.value }
        const workspaceAtStart = workspace.value
        const result = await vnextApi.playerForm(workspaceAtStart)
        if (sameWorkspace(workspace.value, workspaceAtStart)) playerForm.value = result
        return result
    }

    async function savePlayerForm(form: PlayerFormDefinition): Promise<PlayerFormDefinition> {
        if (!workspace.value) throw new Error('请先打开项目')
        playerForm.value = await vnextApi.savePlayerForm(workspace.value, form)
        return playerForm.value
    }

    return {
        workspace, functions, busy, operationError,
        targets, defaultTargetId, targetRevision, targetConflict, targetError, targetBlockedReferences, targetBusy,
        assets, assetCategories, playerForm,
        bootstrap, chooseFolder, chooseFile, openProject, refreshFunctions,
        refreshTargets, targetReferences, saveTargets, addTarget, updateTarget,
        refreshAssets, upsertAssets, importAsset, updateAsset, replaceAsset, deleteAsset, assetPreviewUrl,
        refreshPlayerForm, savePlayerForm,
    }
})
