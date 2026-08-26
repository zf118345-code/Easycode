<template>
    <section class="capability-panel">
        <div class="panel-toolbar">
            <el-input v-model="query" clearable placeholder="搜索能力名称或 ID"><template #prefix><Search :size="14" /></template></el-input>
            <button type="button" class="tool-button" title="重新扫描" aria-label="重新扫描能力库" @click="load(true)"><RefreshCw /></button>
            <button type="button" class="tool-button primary" title="创建能力" aria-label="创建能力" @click="createVisible = true"><Plus /></button>
        </div>
        <div v-if="errors.length" class="catalog-errors">
            <TriangleAlert :size="15" />
            <span>{{ errors.length }} 个能力包未能加载</span>
            <el-tooltip :content="errors.map(item => item.message).join('\n')"><CircleHelp :size="14" /></el-tooltip>
        </div>
        <div class="catalog" v-loading="loading">
            <div v-for="group in groups" :key="group.key" class="catalog-group">
                <div class="group-title"><component :is="group.icon" /><span>{{ group.title }}</span><em>{{ group.items.length }}</em></div>
                <button v-for="item in group.items" :key="`${item.id}@${item.version}`" type="button" class="capability-row" :class="{ active: selected?.id === item.id }" @click="selected = item">
                    <div><strong>{{ item.name }}</strong><small>{{ item.id }}@{{ item.version }}</small></div>
                    <ChevronRight />
                </button>
                <div v-if="!group.items.length" class="empty-group">暂无{{ group.title }}</div>
            </div>
        </div>
        <div v-if="selected" class="detail-card">
            <div class="detail-heading"><div><strong>{{ selected.name }}</strong><small>{{ selected.id }}@{{ selected.version }}</small></div><button type="button" class="tool-button" title="复制能力 ID" aria-label="复制能力 ID" @click="copyId"><Copy /></button></div>
            <p>{{ selected.description || '暂无说明。能力的参数、权限和返回值由 capability.json 声明。' }}</p>
            <div class="detail-line"><span>来源</span><b>{{ sourceLabel(selected.source) }}</b></div>
            <div class="detail-line"><span>超时</span><b>{{ selected.timeout_ms }} ms</b></div>
            <div class="detail-line"><span>自动重试</span><b>{{ selected.idempotent ? '允许（幂等）' : '不允许' }}</b></div>
            <div class="chips"><span v-for="permission in selected.permissions" :key="permission">{{ permission }}</span><span v-if="!selected.permissions?.length">无需额外权限</span></div>
            <div class="contract"><strong>输入</strong><small v-for="item in selected.inputs" :key="item.name">{{ item.name }} · {{ item.type || 'any' }}{{ item.required ? ' · 必填' : '' }}</small><small v-if="!selected.inputs?.length">无</small></div>
            <div class="contract"><strong>输出</strong><small v-for="item in selected.outputs" :key="item.name">{{ item.name }} · {{ item.type || 'any' }}</small><small v-if="!selected.outputs?.length">无</small></div>
        </div>
        <div v-else class="detail-empty"><strong>选择一个能力查看契约</strong><span>这里会显示来源、权限、输入、输出与重试语义。</span></div>

        <el-dialog v-model="createVisible" title="创建能力函数" width="520px" append-to-body :close-on-click-modal="false">
            <el-form label-position="top">
                <el-form-item label="保存位置">
                    <el-radio-group v-model="draft.scope"><el-radio-button value="project">当前项目</el-radio-button><el-radio-button value="shared">公共能力库</el-radio-button></el-radio-group>
                    <div class="form-help">项目能力随当前脚本打包；公共能力可被所有子项目选择，发布时仍只收集实际引用项。</div>
                </el-form-item>
                <el-form-item label="能力包 ID"><el-input v-model="draft.package_id" placeholder="例如 inventory_tools" /></el-form-item>
                <el-form-item label="函数 ID"><el-input v-model="draft.function_name" placeholder="例如 collect_list"><template #prepend>{{ draft.package_id || 'package' }}.</template></el-input></el-form-item>
                <el-form-item label="显示名称"><el-input v-model="draft.display_name" placeholder="例如 采集结构化列表" /></el-form-item>
                <el-form-item label="说明"><el-input v-model="draft.description" type="textarea" :rows="3" /></el-form-item>
            </el-form>
            <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="creating" @click="createPackage">创建</el-button></template>
        </el-dialog>
    </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, toRef, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Boxes, ChevronRight, CircleHelp, Copy, FolderCode, Plus, RefreshCw, Search, Share2, TriangleAlert } from 'lucide-vue-next'
import { capabilityApi } from '@/api/capabilityApi'
import { useCapabilityCatalog } from '@/composables/useCapabilityCatalog'
import { useIdeStore } from '@/stores'

const store = useIdeStore()
const projectPath = toRef(store, 'currentProjectPath')
const { capabilities, errors, loading, load } = useCapabilityCatalog(projectPath)
const query = ref('')
const selected = ref(null)
const createVisible = ref(false)
const creating = ref(false)
const draft = reactive({ scope: 'project', package_id: '', function_name: 'run', display_name: '', description: '' })
const filtered = computed(() => {
    const needle = query.value.trim().toLowerCase()
    return capabilities.value.filter(item => !needle || `${item.name} ${item.id} ${item.description}`.toLowerCase().includes(needle))
})
const groups = computed(() => [
    { key: 'project', title: '项目能力', icon: FolderCode, items: filtered.value.filter(item => String(item.source).startsWith('project:')) },
    { key: 'shared', title: '公共能力', icon: Share2, items: filtered.value.filter(item => String(item.source).startsWith('shared:')) },
    { key: 'builtin', title: '平台内置', icon: Boxes, items: filtered.value.filter(item => item.source === 'builtin') }
])
const sourceLabel = source => source === 'builtin' ? 'EasyCode 平台内置' : (String(source).startsWith('shared:') ? '公共能力库' : '当前项目')
const copyId = async () => {
    try {
        await navigator.clipboard.writeText(selected.value.id)
        ElMessage.success('能力 ID 已复制')
    } catch {
        ElMessage.error('复制失败，请手动选择能力 ID')
    }
}
const createPackage = async () => {
    if (!draft.package_id.trim() || !draft.function_name.trim()) return ElMessage.warning('请填写能力包 ID 和函数 ID')
    creating.value = true
    try {
        const result = await capabilityApi.createPackage({ ...draft })
        ElMessage.success(`已创建 ${result.id}`)
        createVisible.value = false
        Object.assign(draft, { scope: 'project', package_id: '', function_name: 'run', display_name: '', description: '' })
        await load(true)
        selected.value = capabilities.value.find(item => item.id === result.id) || null
    } catch (error) {
        ElMessage.error(error.message || '能力创建失败')
    } finally { creating.value = false }
}
onMounted(() => load())
watch(projectPath, () => { selected.value = null; load(true) })
</script>

<style scoped>
.capability-panel { height:100%; display:grid; grid-template-columns:1fr; grid-template-rows:auto auto minmax(150px,45%) minmax(0,1fr); min-width:0; overflow:hidden; background:var(--app-sidebar-bg); }
.panel-toolbar { grid-column:1/-1; display:flex; gap:5px; padding:8px; border-bottom:1px solid var(--app-separator); }
.tool-button { width:30px; height:30px; flex:0 0 30px; display:grid; place-items:center; padding:0; border:0; border-radius:7px; background:transparent; color:var(--el-text-color-secondary); cursor:pointer; }
.tool-button:hover { background:var(--el-fill-color-light); color:var(--el-text-color-primary); }
.tool-button.primary { background:var(--el-color-primary); color:#07150f; }
.tool-button svg { width:15px; height:15px; }
.catalog-errors { grid-column:1/-1; margin:7px 8px 0; padding:7px 8px; display:flex; gap:6px; align-items:center; border-radius:7px; background:color-mix(in srgb,var(--el-color-warning) 12%,transparent); color:var(--el-color-warning); font-size:11px; }
.catalog-errors span { flex:1; }
.catalog { min-height:0; overflow:auto; padding:7px; border-bottom:1px solid var(--app-separator); }
.catalog-group { margin-bottom:10px; }
.group-title { height:28px; display:flex; align-items:center; gap:6px; padding:0 5px; color:var(--el-text-color-secondary); font-size:11px; font-weight:600; }
.group-title svg { width:14px; height:14px; }.group-title em { margin-left:auto; font-style:normal; opacity:.65; }
.capability-row { width:100%; display:flex; align-items:center; gap:5px; padding:7px 7px 7px 9px; border:0; border-radius:7px; background:transparent; color:inherit; text-align:left; cursor:pointer; }
.capability-row:hover,.capability-row.active { background:var(--el-fill-color-light); }.capability-row.active { box-shadow:inset 2px 0 var(--el-color-primary); }
.capability-row div { min-width:0; flex:1; display:flex; flex-direction:column; gap:2px; }.capability-row strong { font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }.capability-row small { color:var(--el-text-color-secondary); font-size:10px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }.capability-row>svg { width:13px; opacity:.45; }
.empty-group { padding:6px 10px; color:var(--el-text-color-placeholder); font-size:11px; }
.detail-card { min-height:0; overflow:auto; padding:18px; background:var(--el-bg-color); }
.detail-empty { display:flex; flex-direction:column; align-items:center; justify-content:center; gap:6px; padding:24px; color:var(--app-text-secondary); text-align:center; }
.detail-empty strong { color:var(--app-text-primary); font-size:13px; }.detail-empty span { font-size:11px; }
.detail-heading { display:flex; align-items:center; }.detail-heading>div { flex:1; min-width:0; display:flex; flex-direction:column; }.detail-heading strong { font-size:13px; }.detail-heading small,.detail-card p { color:var(--el-text-color-secondary); font-size:10.5px; overflow-wrap:anywhere; }.detail-card p { line-height:1.55; }
.detail-line { display:flex; justify-content:space-between; margin-top:5px; font-size:10.5px; }.detail-line span { color:var(--el-text-color-secondary); }.detail-line b { font-weight:500; }
.chips { display:flex; flex-wrap:wrap; gap:4px; margin-top:8px; }.chips span { padding:2px 5px; border-radius:5px; background:var(--el-fill-color-light); color:var(--el-text-color-secondary); font-size:10px; }
.contract { display:flex; flex-direction:column; gap:3px; margin-top:8px; }.contract strong { font-size:10.5px; }.contract small { color:var(--el-text-color-secondary); font-size:10px; }
.form-help { margin-top:6px; color:var(--el-text-color-secondary); font-size:11px; line-height:1.5; }
@media(max-width:720px){.capability-panel{grid-template-columns:1fr}.panel-toolbar,.catalog-errors{grid-column:1}.catalog{border-right:0}.detail-card,.detail-empty{display:none}}
</style>
