<template>
    <el-dialog v-model="visible" title="版本历史" width="680px" append-to-body @open="loadHistory">
        <el-table :data="snapshots" height="440" v-loading="loading">
            <el-table-column label="时间" width="190"><template #default="scope">{{ formatTime(scope?.row?.created_at) }}</template></el-table-column>
            <el-table-column prop="reason" label="原因" width="150" />
            <el-table-column prop="hash" label="内容哈希"><template #default="scope"><code>{{ scope?.row?.hash?.slice(0, 12) }}</code></template></el-table-column>
            <el-table-column label="操作" width="90"><template #default="scope"><el-button v-if="scope?.row" link type="primary" :loading="restoringId === scope.row.snapshot_id" :disabled="Boolean(restoringId)" @click="restore(scope.row)">恢复</el-button></template></el-table-column>
        </el-table>
        <template #footer><span class="history-note">自动去重，最多保留 100 份</span><el-button :disabled="Boolean(restoringId)" @click="visible = false">关闭</el-button></template>
    </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '@/api/client'
import { useProjectStore } from '@/stores'

const visible = defineModel({ type: Boolean, default: false })
const projectStore = useProjectStore()
const snapshots = ref([])
const loading = ref(false)
const restoringId = ref('')
const formatTime = (value) => value ? new Date(value).toLocaleString() : ''
const loadHistory = async () => {
    if (!projectStore.currentProjectPath) return
    loading.value = true
    try {
        snapshots.value = (await client.get('/api/history', { params: { project_path: projectStore.currentProjectPath } })).snapshots || []
    } catch (error) {
        ElMessage.error(error?.message || '读取版本历史失败')
    } finally { loading.value = false }
}
const restore = async (row) => {
    if (restoringId.value) return
    try {
        await ElMessageBox.confirm('恢复会替换当前蓝图；系统会先自动保存当前版本，是否继续？', '恢复版本', { type: 'warning' })
        restoringId.value = row.snapshot_id
        await projectStore.flushPendingSaves()
        await client.post(`/api/history/${encodeURIComponent(row.snapshot_id)}/restore`, null, { params: { project_path: projectStore.currentProjectPath } })
        await projectStore.loadProjectData()
        ElMessage.success('版本已恢复；恢复前状态也已保留')
        await loadHistory()
    } catch (error) {
        const action = String(error?.action || error || '').toLowerCase()
        if (!['cancel', 'close'].includes(action)) ElMessage.error(error?.message || '版本恢复失败')
    } finally {
        restoringId.value = ''
    }
}
</script>

<style scoped>.history-note{float:left;color:var(--el-text-color-secondary);font-size:12px}</style>
