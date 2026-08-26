<template>
    <div class="capture-file-manager-view">
        <div v-if="loading" class="capture-manager-state">
            <LoaderCircle :size="20" class="spin" /> 正在读取项目资源…
        </div>

        <FileBrowser
            v-else-if="snapshot"
            :key="contextVersion"
            :project-path="snapshot.project_path"
            mode="capture-save"
            :initial-path="category"
            :allow-empty-name="true"
            :save-button-text="saveButtonText"
            :save-busy="saving"
            :fill-height="true"
            @save="handleSave"
            @close="cancel" />

        <div v-else-if="errorMessage" class="capture-manager-state is-error">
            <CircleAlert :size="20" />
            <span>{{ errorMessage }}</span>
            <el-button @click="cancel">关闭</el-button>
        </div>

        <div v-else class="capture-manager-state">
            等待捕获内容…
        </div>

        <el-dialog
            v-model="conflictVisible"
            title="同名文件已存在"
            width="460px"
            append-to-body
            :close-on-click-modal="false">
            <div class="conflict-copy">
                当前名称已存在。你可以返回修改名称、覆盖原文件，或保留原文件并自动添加序号。
            </div>
            <template #footer>
                <el-button @click="conflictVisible = false">返回改名</el-button>
                <el-button @click="resolveConflict('sequence')">序号保存</el-button>
                <el-button type="danger" @click="resolveConflict('overwrite')">覆盖保存</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
    import { computed, onMounted, onUnmounted, ref } from 'vue'
    import { ElMessage, ElMessageBox } from 'element-plus'
    import { CircleAlert, LoaderCircle } from 'lucide-vue-next'
    import FileBrowser from '@/components/FileBrowser.vue'
    import { captureApi } from '@/api/captureApi'
    import { setWorkspaceIdentity } from '@/api/workspaceIdentity'

    const parseJson = (value, fallback) => {
        try {
            return value ? JSON.parse(value) : fallback
        } catch {
            return fallback
        }
    }

    const snapshotId = ref('')
    const kind = ref('record')
    const explicitCategory = ref('')
    const fieldRequestId = ref('')
    const chainId = ref('')
    const operationId = ref('')
    const rects = ref([])
    const port = ref(null)
    const snapshot = ref(null)
    const loading = ref(false)
    const saving = ref(false)
    const errorMessage = ref('')
    const conflictVisible = ref(false)
    const pendingSave = ref(null)
    const conflictResult = ref(null)
    const contextVersion = ref(0)

    const category = computed(() => explicitCategory.value || (kind.value === 'record' ? 'image' : kind.value))
    const saveButtonText = computed(() => {
        if (saving.value) return '正在保存…'
        if (kind.value === 'field_confirm') return rects.value.length > 1 ? `保存并回填（${rects.value.length}）` : '保存并回填'
        if (kind.value === 'record') return rects.value.length > 1 ? `录入 ${rects.value.length} 张图片` : '录入图片'
        return rects.value.length > 1 ? `保存并生成（${rects.value.length}）` : '保存并生成节点'
    })

    const postHost = payload => {
        if (window.chrome?.webview?.postMessage) {
            window.chrome.webview.postMessage(payload)
            return true
        }
        return false
    }

    const cancel = () => {
        if (!postHost({ event: 'capture-save-cancel' })) window.close()
    }

    const hasReferences = result => (result?.conflicts || [])
        .some(item => Array.isArray(item.references) && item.references.length > 0)

    const categoryForPath = relativePath => {
        const root = String(relativePath || '').replace(/\\/g, '/').split('/').filter(Boolean)[0]?.toLowerCase()
        return ['image', 'ocr', 'page'].includes(root) ? root : category.value
    }

    const commitSavedAssets = async saved => {
        let actionCommitted = false
        try {
            const result = await captureApi.requestAction({
                session_id: snapshot.value.session_id,
                snapshot_id: snapshotId.value,
                capture_chain_id: chainId.value,
                capture_context: snapshot.value.capture_context || {},
                reference_size: [snapshot.value.width, snapshot.value.height],
                port: port.value,
                operation_id: operationId.value,
                kind: kind.value,
                rects: saved.rects,
                template_keys: saved.template_keys,
                asset_refs: saved.asset_refs,
                asset_transaction: saved.transaction_id,
                field_request_id: fieldRequestId.value
            })
            actionCommitted = true
            postHost({
                event: 'capture-save-complete',
                result,
                file_count: saved.files?.length || 0
            })
        } finally {
            if (!actionCommitted && saved.transaction_id) {
                await captureApi.undoAssets(saved.transaction_id).catch(() => {})
            }
        }
    }

    const saveAssets = async (collision = 'ask', overwriteConfirmed = false) => {
        if (!pendingSave.value || saving.value) return
        saving.value = true
        try {
            const relativeDir = pendingSave.value.relativePath || category.value
            const saved = await captureApi.saveAssets({
                snapshot_id: snapshotId.value,
                category: categoryForPath(relativeDir),
                relative_dir: relativeDir,
                prefix: pendingSave.value.fileName || '',
                rects: rects.value,
                collision,
                overwrite_confirmed: overwriteConfirmed
            })
            if (saved.conflict) {
                conflictResult.value = saved
                conflictVisible.value = true
                return
            }
            await commitSavedAssets(saved)
        } catch (error) {
            ElMessage.error(error?.message || '捕获资源保存失败')
        } finally {
            saving.value = false
        }
    }

    const handleSave = payload => {
        pendingSave.value = payload
        saveAssets()
    }

    const resolveConflict = async choice => {
        conflictVisible.value = false
        if (choice === 'sequence') {
            await saveAssets('sequence', false)
            return
        }
        const referenced = hasReferences(conflictResult.value)
        if (referenced) {
            try {
                await ElMessageBox.confirm(
                    '该图片已被流程引用，覆盖会改变所有引用位置。仍要继续吗？',
                    '二次确认覆盖',
                    { type: 'error', confirmButtonText: '继续覆盖', cancelButtonText: '返回' }
                )
            } catch {
                return
            }
        }
        await saveAssets('overwrite', referenced)
    }

    const applyContext = async rawContext => {
        const next = rawContext || {}
        const nextVersion = contextVersion.value + 1
        contextVersion.value = nextVersion
        snapshotId.value = String(next.snapshot_id || '')
        kind.value = String(next.kind || 'record')
        explicitCategory.value = String(next.category || '')
        fieldRequestId.value = String(next.field_request_id || '')
        chainId.value = String(next.chain_id || snapshotId.value)
        operationId.value = String(next.operation_id || `capture_web_${Date.now()}`)
        rects.value = Array.isArray(next.rects) ? next.rects : []
        port.value = next.port || null
        snapshot.value = null
        setWorkspaceIdentity(null)
        errorMessage.value = ''
        pendingSave.value = null
        conflictResult.value = null
        conflictVisible.value = false
        saving.value = false
        loading.value = true
        try {
            if (!snapshotId.value) throw new Error('缺少冻结帧标识')
            if (!['image', 'ocr', 'page', 'record', 'field_confirm'].includes(kind.value)) throw new Error('捕获资源类型无效')
            if (!['image', 'ocr', 'page'].includes(category.value)) throw new Error('捕获资源分类无效')
            if (kind.value === 'field_confirm' && !fieldRequestId.value) throw new Error('属性捕获请求已失效')
            if (!rects.value.length) throw new Error('没有可保存的框选范围')
            const loaded = await captureApi.getSnapshot(snapshotId.value)
            if (!loaded?.workspace_id || loaded?.workspace_generation === undefined) {
                throw new Error('冻结帧缺少工作区身份，请退出捕获并重新进入')
            }
            if (contextVersion.value === nextVersion) {
                setWorkspaceIdentity({
                    workspace_id: loaded.workspace_id,
                    generation: loaded.workspace_generation
                })
                // 身份必须先写入请求客户端，再挂载 FileBrowser；否则它的首个
                // 目录请求会以无工作区身份发出并得到 409。
                snapshot.value = loaded
            }
        } catch (error) {
            if (contextVersion.value === nextVersion) errorMessage.value = error?.message || String(error)
        } finally {
            if (contextVersion.value === nextVersion) loading.value = false
        }
    }

    const onHostMessage = event => {
        const message = event?.data || {}
        if (message.event === 'capture-save-context' && message.version === 1) {
            applyContext(message.context)
        }
    }

    onMounted(() => {
        window.chrome?.webview?.addEventListener?.('message', onHostMessage)
        postHost({ event: 'capture-file-manager-ready', version: 1 })

        // Query fallback keeps browser diagnostics and older hosts usable.
        const query = new URLSearchParams(window.location.search)
        if (query.get('snapshot_id')) {
            applyContext({
                snapshot_id: query.get('snapshot_id'),
                kind: query.get('kind') || 'record',
                chain_id: query.get('chain_id') || query.get('snapshot_id'),
                operation_id: query.get('operation_id') || `capture_web_${Date.now()}`,
                category: query.get('category') || '',
                field_request_id: query.get('field_request_id') || '',
                rects: parseJson(query.get('rects'), []),
                port: parseJson(query.get('port'), null)
            })
        }
    })

    onUnmounted(() => {
        setWorkspaceIdentity(null)
        window.chrome?.webview?.removeEventListener?.('message', onHostMessage)
    })
</script>

<style scoped>
    .capture-file-manager-view {
        width: 100%;
        height: 100vh;
        overflow: hidden;
        background: var(--el-bg-color-page);
    }

    .capture-manager-state {
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        color: var(--el-text-color-secondary);
        font-size: 13px;
    }

    .capture-manager-state.is-error {
        color: var(--el-color-danger);
        flex-direction: column;
    }

    .conflict-copy {
        color: var(--el-text-color-regular);
        line-height: 1.7;
    }

    .spin {
        animation: spin 0.9s linear infinite;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }
</style>
