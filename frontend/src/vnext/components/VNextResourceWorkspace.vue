<template>
    <section :class="['resource-workspace', { 'detail-panel-collapsed': !detailVisible }]" aria-label="项目资源">
        <VNextNavigationPane class="resource-tree">
            <VNextPaneHeader title="资源" :meta="store.assets.length"><template #actions><span class="tree-actions"><VNextIconButton label="新建资源文件夹" :disabled="mutationBusy" @click="openFolderDialog('create')"><FolderPlus /></VNextIconButton><VNextIconButton label="导入图片" :disabled="mutationBusy" @click="chooseImport"><Plus /></VNextIconButton></span></template></VNextPaneHeader>
            <VNextListSearch v-model="query" placeholder="搜索资源" aria-label="搜索资源" />
            <nav class="app-navigation-list">
                <template v-for="category in categoryOptions" :key="category.id">
                    <VNextNavigationItem :selected="selectedCategory === category.id && selectedFolder === ''" @click="selectFolder(category.id, '')">
                        <component :is="categoryIcon(category.id)" :size="15" /><span>{{ category.label }}</span><small>{{ countFor(category.id, '') }}</small>
                    </VNextNavigationItem>
                    <VNextNavigationItem v-for="folder in category.folders" :key="`${category.id}:${folder}`" as="div" class="folder-row" child :selected="selectedCategory === category.id && selectedFolder === folder" @contextmenu.prevent="openFolderDialog('rename', category.id, folder)">
                        <button type="button" class="folder-select" :title="folder" @click="selectFolder(category.id, folder)"><Folder :size="14" /><span>{{ folderLabel(folder) }}</span><small>{{ countFor(category.id, folder) }}</small></button>
                        <button type="button" class="folder-more" :aria-label="`管理文件夹 ${folder}`" title="文件夹操作" @click="openFolderDialog('rename', category.id, folder)"><MoreHorizontal :size="13" /></button>
                    </VNextNavigationItem>
                </template>
            </nav>
        </VNextNavigationPane>

        <main class="resource-gallery">
            <VNextPaneHeader class="gallery-header" role="workspace" :title="selectedFolder ? `${categoryLabel} / ${selectedFolder}` : categoryLabel" :meta="`${filteredAssets.length} 项`"><template #actions><span class="gallery-actions"><VNextIconButton v-if="compactLayout && props.detailOpen === undefined" label="打开资源检查器" :disabled="!selectedAsset" @click="openInspector"><PanelRightOpen /></VNextIconButton><VNextButton v-if="selectionMode" class="selection-cancel" appearance="ghost" size="compact" :disabled="selectionBusy || mutationBusy" @click="emit('cancel-selection')">取消选择</VNextButton><VNextButton v-if="selectionMode" class="selection-action" tone="primary" appearance="solid" size="compact" :disabled="!selectedAsset || selectionBusy || mutationBusy" @click="confirmSelection"><template #icon><Check /></template>{{ selectionBusy ? '正在应用' : selectionLabel }}</VNextButton><VNextButton class="capture-action" tone="primary" appearance="solid" size="compact" :loading="captureBusy" :disabled="mutationBusy || store.workspace?.read_only" @click="requestCapture"><template #icon><Camera /></template>{{ captureBusy ? '正在录入' : '视觉录入' }}</VNextButton><VNextButton ref="galleryImportButton" class="primary-action" tone="primary" appearance="solid" size="compact" :loading="importBusy" :disabled="mutationBusy || store.workspace?.read_only" @click="chooseImport"><template #icon><Upload /></template>{{ importBusy ? '正在导入' : '导入图片' }}</VNextButton></span></template></VNextPaneHeader>
            <VNextWorkspaceState v-if="workspaceError" class="resource-state is-error" kind="error" title="资源目录加载失败" :description="workspaceError"><template #icon><CircleAlert :size="22" /></template><template #actions><VNextButton size="compact" :disabled="workspaceLoading" @click="refreshWorkspace"><template #icon><RefreshCw :class="{ spin: workspaceLoading }" /></template>重试</VNextButton></template></VNextWorkspaceState>
            <VNextWorkspaceState v-else-if="workspaceLoading" class="resource-state" kind="loading" title="正在读取资源目录" description="图片、文字识别和页面资源都会显示在这里。"><template #icon><RefreshCw :size="22" class="spin" /></template></VNextWorkspaceState>
            <div v-else-if="filteredAssets.length" ref="assetGrid" class="asset-grid" @scroll.passive="syncAssetViewport">
                <div class="asset-virtual-content" :style="assetVirtualContentStyle">
                    <div class="asset-window" :style="assetWindowStyle">
                        <button v-for="asset in visibleAssets" :key="asset.asset_id" :ref="element => setAssetCardRef(asset.asset_id, element)" :data-asset-id="asset.asset_id" type="button" :class="['asset-card', { active: selectedAssetId === asset.asset_id }]" :aria-pressed="selectedAssetId === asset.asset_id" :title="asset.display_name" @click="selectAsset(asset)" @dblclick="selectionMode && confirmSelection()">
                            <div :class="['asset-preview', { 'has-error': previewErrors[asset.asset_id] }]" :title="previewErrors[asset.asset_id] ? '资源预览加载失败，可在检查器中重试' : ''"><img v-if="previewUrls[asset.asset_id]" :src="previewUrls[asset.asset_id]" :alt="asset.display_name" /><CircleAlert v-else-if="previewErrors[asset.asset_id]" :size="22" /><ImageIcon v-else :size="22" /></div>
                            <div class="asset-caption"><strong>{{ asset.display_name }}</strong><span>{{ dimensionText(asset) }}</span></div>
                        </button>
                    </div>
                </div>
                <div v-if="showVisibleRangeStatus" class="asset-range-status" role="status">{{ visibleRangeLabel }}</div>
            </div>
            <VNextWorkspaceState v-else class="resource-empty" kind="empty" title="这里还没有资源" description="导入图片，或从目标画面录入。"><template #icon><Images :size="28" /></template><template #actions><VNextButton size="compact" :disabled="mutationBusy" @click="chooseImport"><template #icon><Upload /></template>选择图片</VNextButton></template></VNextWorkspaceState>
        </main>

        <button v-if="detailAsOverlay && detailVisible" type="button" class="asset-inspector-scrim" aria-label="关闭资源检查器" @click="closeInspector" />
        <aside v-if="detailVisible" :class="['asset-inspector', { 'is-compact': detailAsOverlay }]" @keydown.esc="closeInspector">
            <VNextPaneHeader role="inspector" title="资源详情"><template #actions><VNextIconButton v-if="detailAsOverlay" ref="inspectorCloseButton" label="关闭资源详情" @click="closeInspector"><PanelRightClose /></VNextIconButton></template></VNextPaneHeader>
            <div v-if="selectedAsset" class="asset-details app-inspector-body app-inspector-form">
                <div class="detail-preview"><img v-if="previewUrls[selectedAsset.asset_id]" :src="previewUrls[selectedAsset.asset_id]" :alt="selectedAsset.display_name" /></div>
                <label class="asset-field app-form-row"><span class="app-form-label">显示名称</span><input v-model="assetDraft.display_name" class="app-form-control" :aria-busy="metadataBusy" @keydown.enter.prevent="saveMetadata" @blur="saveMetadata" /></label>
                <label class="asset-field app-form-row"><span class="app-form-label">用途</span><select v-model="assetDraft.category" class="app-form-control" :aria-busy="metadataBusy" @change="saveMetadata"><option value="image">图像</option><option value="ocr">OCR</option><option value="page">页面</option></select></label>
                <label class="asset-field app-form-row"><span class="app-form-label">子目录</span><input v-model="assetDraft.folder" class="app-form-control" :aria-busy="metadataBusy" placeholder="可留空；例如 登录/按钮" @keydown.enter.prevent="saveMetadata" @blur="saveMetadata" /></label>
                <dl class="essential-details">
                    <div><dt>尺寸</dt><dd>{{ dimensionText(selectedAsset) }}</dd></div>
                    <div><dt>文件大小</dt><dd>{{ sizeText(selectedAsset.size_bytes) }}</dd></div>
                    <div><dt>引用</dt><dd>{{ references.length }} 处</dd></div>
                </dl>
                <details class="technical-details app-inspector-disclosure">
                    <summary>技术信息</summary>
                    <dl>
                        <div><dt>资源 ID</dt><dd><code>{{ selectedAsset.asset_id }}</code><button type="button" aria-label="复制资源 ID" @click="copyText(selectedAsset.asset_id)"><Copy :size="13" /></button></dd></div>
                        <div><dt>格式</dt><dd>{{ selectedAsset.extension.slice(1).toUpperCase() }}</dd></div>
                        <div><dt>文件</dt><dd><code>{{ selectedAsset.path }}</code></dd></div>
                        <div><dt>摘要</dt><dd><code>{{ selectedAsset.sha256.slice(0, 16) }}…</code></dd></div>
                        <div><dt>来源</dt><dd>{{ sourceLabel(selectedAsset.source) }}</dd></div>
                        <div v-if="captureRegion"><dt>捕获选区</dt><dd><code>{{ captureRegion }}</code></dd></div>
                        <div v-if="captureWorkArea"><dt>来源工作区</dt><dd><code>{{ captureWorkArea }}</code><small>仅溯源</small></dd></div>
                        <div v-if="captureReferenceSize"><dt>参考尺寸</dt><dd>{{ captureReferenceSize }}</dd></div>
                        <div v-if="captureTarget"><dt>录制目标</dt><dd><code>{{ captureTarget }}</code></dd></div>
                        <div v-if="capturePlatform"><dt>来源平台</dt><dd>{{ capturePlatform }}</dd></div>
                        <div v-if="captureHost"><dt>捕获宿主</dt><dd>{{ captureHost }}</dd></div>
                        <div v-if="captureTime"><dt>捕获时间</dt><dd>{{ captureTime }}</dd></div>
                        <div><dt>创建时间</dt><dd>{{ localTime(selectedAsset.created_at) }}</dd></div>
                        <div><dt>修改时间</dt><dd>{{ localTime(selectedAsset.updated_at) }}</dd></div>
                    </dl>
                </details>
                <div v-if="references.length" class="reference-list"><button v-for="item in references.slice(0, 5)" :key="referenceKey(item)" type="button" @click="openReference(item)"><span>{{ referenceTitle(item) }}</span><small>{{ referenceDetail(item) }}</small></button></div>
                <VNextInlineNotice v-if="message" class="asset-message" :tone="messageError ? 'error' : 'success'" :message="message" compact />
                <div class="asset-actions">
                    <button v-if="selectionMode" type="button" :disabled="selectionBusy || mutationBusy" @click="confirmSelection"><Check :size="14" />{{ selectionLabel }}</button>
                    <button v-if="previewErrors[selectedAsset.asset_id]" type="button" :disabled="mutationBusy" @click="retryPreview(selectedAsset)"><RefreshCw :size="14" />重试预览</button>
                    <button type="button" :disabled="mutationBusy" @click="chooseReplace"><RefreshCw :size="14" />{{ replaceBusy ? '正在替换' : '替换文件' }}</button>
                    <button v-if="!deletePending" type="button" class="danger" :disabled="mutationBusy" @click="requestDelete"><Trash2 :size="14" />删除</button>
                    <template v-else><button type="button" :disabled="deleteBusy" @click="deletePending = false">取消</button><button type="button" class="danger solid" :disabled="deleteBusy" @click="confirmDelete">{{ deleteBusy ? '正在删除' : '确认删除' }}</button></template>
                </div>
            </div>
            <VNextWorkspaceState v-else class="resource-empty compact" compact kind="selection" title="选择一项资源" description="查看预览、使用位置和相关操作。"><template #icon><MousePointer2 :size="22" /></template></VNextWorkspaceState>
        </aside>

        <input ref="importInput" type="file" accept="image/png,image/jpeg,image/bmp,image/webp" multiple hidden @change="importFiles" />
        <input ref="replaceInput" type="file" accept="image/png,image/jpeg,image/bmp,image/webp" hidden @change="replaceFile" />
        <dialog ref="folderDialog" class="folder-dialog" @cancel.prevent="closeFolderDialog">
            <form @submit.prevent="submitFolderDialog">
                <header><strong>{{ folderDialogMode === 'create' ? '新建资源文件夹' : '管理资源文件夹' }}</strong><button type="button" aria-label="关闭" @click="closeFolderDialog"><X :size="15" /></button></header>
                <label v-if="folderDialogMode!=='delete'" class="folder-field app-form-row">
                    <span class="app-form-label">{{ folderDialogMode === 'create' ? '文件夹名称' : '新名称' }}</span>
                    <input ref="folderNameInput" v-model="folderName" class="app-form-control" placeholder="例如 登录/按钮" :aria-invalid="folderDeleteMessage ? 'true' : undefined" :aria-describedby="folderDeleteMessage || folderDialogMode === 'create' ? 'folder-dialog-feedback' : undefined" />
                    <small v-if="folderDeleteMessage || folderDialogMode === 'create'" id="folder-dialog-feedback" :class="folderDeleteMessage ? 'app-form-error' : 'app-form-help'" :role="folderDeleteMessage ? 'alert' : undefined">
                        <template v-if="folderDeleteMessage">{{ folderDeleteMessage }}</template>
                        <template v-else>位置：/assets/{{ folderCategory }}/{{ selectedFolder || '' }}</template>
                    </small>
                </label>
                <p v-else class="danger-text">{{ folderDeleteMessage || '文件夹内的未引用资源会一并删除；存在引用时操作将被阻止。' }}</p>
                <footer><button type="button" :disabled="folderBusy" @click="closeFolderDialog">取消</button><button v-if="folderDialogMode==='rename'" type="button" class="danger" :disabled="folderBusy" @click="folderDialogMode='delete'">删除</button><button type="submit" :class="{danger:folderDialogMode==='delete'}" :disabled="folderBusy || (folderDialogMode !== 'delete' && !folderName.trim())">{{ folderBusy?'正在处理':folderDialogMode==='create'?'创建':folderDialogMode==='rename'?'保存':'确认删除' }}</button></footer>
            </form>
        </dialog>
    </section>
</template>

<script setup lang="ts">
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Camera, Check, CircleAlert, Copy, FileText, Folder, FolderPlus, Image as ImageIcon, Images, MoreHorizontal, MousePointer2, PanelRightClose, PanelRightOpen, Plus, RefreshCw, ScanText, Trash2, Upload, X } from 'lucide-vue-next'
import { useVNextStore } from '../store'
import { vnextApi } from '../api'
import type { AssetCategory, AssetCategoryId, AssetDefinition, AssetReferenceDefinition } from '../types'
import VNextPaneHeader from './ui/VNextPaneHeader.vue'
import VNextListSearch from './ui/VNextListSearch.vue'
import VNextNavigationPane from './ui/VNextNavigationPane.vue'
import VNextNavigationItem from './ui/VNextNavigationItem.vue'
import VNextWorkspaceState from './ui/VNextWorkspaceState.vue'
import VNextInlineNotice from './ui/VNextInlineNotice.vue'
import VNextButton from './ui/VNextButton.vue'
import VNextIconButton from './ui/VNextIconButton.vue'

const props = withDefaults(defineProps<{ selectionMode?: boolean; selectionLabel?: string; selectionBusy?: boolean; captureBusy?: boolean; initialCategory?: AssetCategoryId; detailOpen?: boolean; detailOverlay?: boolean }>(), {
    selectionMode: false,
    selectionLabel: '使用此图片',
    selectionBusy: false,
    captureBusy: false,
    initialCategory: 'image',
    detailOpen: undefined,
    detailOverlay: undefined,
})
const emit = defineEmits<{
    (_event: 'insert-reference', _asset: AssetDefinition): void
    (_event: 'cancel-selection'): void
    (_event: 'open-reference', _reference: AssetReferenceDefinition): void
    (_event: 'open-source', _reference: AssetReferenceDefinition): void
    (_event: 'capture-resource', _category: AssetCategoryId, _origin: HTMLElement): void
    (_event: 'update:detail-open', _open: boolean): void
}>()
const store = useVNextStore()
const selectedCategory = ref<AssetCategoryId>(props.initialCategory)
const selectedFolder = ref('')
const selectedAssetId = ref('')
const compactLayout = ref(false)
const inspectorOpen = ref(false)
const detailVisible = computed(() => props.detailOpen ?? (!compactLayout.value || inspectorOpen.value))
const detailAsOverlay = computed(() => props.detailOverlay ?? compactLayout.value)
const query = ref('')
const importInput = ref<HTMLInputElement | null>(null)
const replaceInput = ref<HTMLInputElement | null>(null)
const galleryImportButton = ref<InstanceType<typeof VNextButton> | null>(null)
const inspectorCloseButton = ref<InstanceType<typeof VNextIconButton> | null>(null)
const assetGrid = ref<HTMLElement | null>(null)
const folderDialog = ref<HTMLDialogElement | null>(null)
const folderNameInput = ref<HTMLInputElement | null>(null)
const folderDialogMode = ref<'create'|'rename'|'delete'>('create')
const folderCategory = ref<AssetCategoryId>('image')
const folderPath = ref('')
const folderName = ref('')
const folderDeleteForce = ref(false)
const folderDeleteMessage = ref('')
const previewUrls = reactive<Record<string, string>>({})
const previewErrors = reactive<Record<string, boolean>>({})
const previewLoading = new Set<string>()
const assetCardElements = new Map<string, HTMLElement>()
let disposed = false
let compactMedia: MediaQueryList | null = null
let previewObserver: IntersectionObserver | null = null
let assetResizeObserver: ResizeObserver | null = null
let dialogReturnFocus: HTMLElement | null = null
let metadataSaveTail: Promise<void> = Promise.resolve()
let referenceLoadGeneration = 0
const references = ref<AssetReferenceDefinition[]>([])
const message = ref('')
const messageError = ref(false)
const deletePending = ref(false)
const workspaceLoading = ref(false)
const workspaceError = ref('')
const metadataPendingCount = ref(0)
const importBusy = ref(false)
const replaceBusy = ref(false)
const deleteBusy = ref(false)
const folderBusy = ref(false)
// Grid virtualization keeps the DOM bounded even after a user traverses all
// 10,000 resources.  Cards use a measured fixed row stride; image loading is a
// separate IntersectionObserver concern.
const ASSET_MIN_WIDTH = 136
const ASSET_GAP = 10
const ASSET_PADDING = 12
const ASSET_ROW_OVERSCAN = 3
const assetScrollTop = ref(0)
const assetViewportWidth = ref(760)
const assetViewportHeight = ref(720)
const assetDraft = reactive({ display_name: '', category: 'image' as AssetCategoryId, folder: '' })
const selectedAsset = computed(() => store.assets.find(item => item.asset_id === selectedAssetId.value) || null)
const selectionMode = computed(() => props.selectionMode)
const selectionLabel = computed(() => props.selectionLabel)
const selectionBusy = computed(() => props.selectionBusy)
const captureBusy = computed(() => props.captureBusy)
const metadataBusy = computed(() => metadataPendingCount.value > 0)
const mutationBusy = computed(() => metadataBusy.value || importBusy.value || replaceBusy.value || deleteBusy.value || folderBusy.value)
const categoryOptions = computed<AssetCategory[]>(() => {
    const defaults: AssetCategory[] = [
        { id: 'image', label: '图像', folders: [] },
        { id: 'ocr', label: 'OCR', folders: [] },
        { id: 'page', label: '页面', folders: [] },
    ]
    return defaults.map((fallback) => {
        const remote = store.assetCategories.find(item => item.id === fallback.id)
        const inferred = store.assets.filter(item => item.category === fallback.id && item.folder).map(item => item.folder)
        return { ...fallback, ...remote, folders: [...new Set([...(remote?.folders || []), ...inferred])].sort((left, right) => left.localeCompare(right)) }
    })
})
const captureRegion = computed(() => {
    const value=selectedAsset.value?.capture?.selection_rect
    return Array.isArray(value)&&value.length===4?value.map(Number).join(', '):''
})
const captureWorkArea = computed(() => {
    const value=selectedAsset.value?.capture?.work_area
    return Array.isArray(value)&&value.length===4?value.map(Number).join(', '):''
})
const captureReferenceSize = computed(() => {
    const value=selectedAsset.value?.capture?.reference_size
    return Array.isArray(value)&&value.length===2?`${Number(value[0])} × ${Number(value[1])}`:''
})
const captureTarget = computed(() => String(selectedAsset.value?.capture?.target_id||''))
const capturePlatform = computed(() => String(selectedAsset.value?.capture?.platform||''))
const captureHost = computed(() => String(selectedAsset.value?.capture?.host||''))
const captureTime = computed(() => {
    const value=String(selectedAsset.value?.capture?.captured_at||'')
    return value?localTime(value):''
})
const categoryLabel = computed(() => categoryOptions.value.find(item => item.id === selectedCategory.value)?.label || '资源')
const filteredAssets = computed(() => {
    const text = query.value.trim().toLocaleLowerCase()
    return store.assets.filter(item => item.category === selectedCategory.value && (!selectedFolder.value || item.folder === selectedFolder.value) && (!text || `${item.display_name} ${item.folder} ${item.asset_id}`.toLocaleLowerCase().includes(text)))
})
const assetColumns = computed(() => Math.max(1, Math.floor(
    (Math.max(ASSET_MIN_WIDTH, assetViewportWidth.value - ASSET_PADDING * 2) + ASSET_GAP)
    / (ASSET_MIN_WIDTH + ASSET_GAP),
)))
const assetCardWidth = computed(() => Math.max(
    ASSET_MIN_WIDTH,
    (assetViewportWidth.value - ASSET_PADDING * 2 - (assetColumns.value - 1) * ASSET_GAP) / assetColumns.value,
))
const assetCardHeight = computed(() => Math.ceil((assetCardWidth.value - 10) * .75 + 36))
const assetRowHeight = computed(() => assetCardHeight.value + ASSET_GAP)
const assetRowCount = computed(() => Math.ceil(filteredAssets.value.length / assetColumns.value))
const assetStartRow = computed(() => Math.max(0, Math.floor(
    Math.max(0, assetScrollTop.value - ASSET_PADDING) / assetRowHeight.value,
) - ASSET_ROW_OVERSCAN))
const assetEndRow = computed(() => Math.min(
    assetRowCount.value,
    Math.ceil((assetScrollTop.value + assetViewportHeight.value) / assetRowHeight.value) + ASSET_ROW_OVERSCAN,
))
const assetStartIndex = computed(() => assetStartRow.value * assetColumns.value)
const assetEndIndex = computed(() => Math.min(filteredAssets.value.length, assetEndRow.value * assetColumns.value))
const visibleAssets = computed(() => filteredAssets.value.slice(assetStartIndex.value, assetEndIndex.value))
const showVisibleRangeStatus = computed(() => visibleAssets.value.length < filteredAssets.value.length)
const assetVirtualContentStyle = computed(() => ({ height: `${ASSET_PADDING * 2 + assetRowCount.value * assetRowHeight.value}px` }))
const assetWindowStyle = computed(() => ({
    top: `${ASSET_PADDING + assetStartRow.value * assetRowHeight.value}px`,
    gridTemplateColumns: `repeat(${assetColumns.value}, minmax(0, 1fr))`,
    gap: `${ASSET_GAP}px`,
    paddingInline: `${ASSET_PADDING}px`,
    '--asset-card-height': `${assetCardHeight.value}px`,
}))
const visibleRangeLabel = computed(() => `显示 ${assetStartIndex.value + 1}–${assetEndIndex.value} / ${filteredAssets.value.length}`)

function categoryIcon(category: AssetCategoryId) { return markRaw(category === 'ocr' ? ScanText : category === 'page' ? FileText : ImageIcon) }
function folderLabel(folder: string) { return folder.split('/').filter(Boolean).at(-1) || folder }
function countFor(category: AssetCategoryId, folder: string) { return store.assets.filter(item => item.category === category && (!folder || item.folder === folder)).length }
function selectFolder(category: AssetCategoryId, folder: string) {
    selectedCategory.value = category
    selectedFolder.value = folder
    const asset = selectedAsset.value
    if (asset && (asset.category !== category || (!!folder && asset.folder !== folder))) {
        selectedAssetId.value = ''
        references.value = []
        inspectorOpen.value = false
    }
}
function confirmSelection() { if (selectedAsset.value && !selectionBusy.value) emit('insert-reference', selectedAsset.value) }
function requestCapture(event: MouseEvent) {
    if (captureBusy.value || mutationBusy.value || store.workspace?.read_only) return
    const origin = event.currentTarget
    if (origin instanceof HTMLElement) emit('capture-resource', selectedCategory.value, origin)
}
function dimensionText(asset: AssetDefinition) { return asset.width && asset.height ? `${asset.width} × ${asset.height}` : '尺寸未知' }
function sizeText(value: number) { return value < 1024 ? `${value} B` : value < 1024 * 1024 ? `${(value / 1024).toFixed(1)} KB` : `${(value / 1024 / 1024).toFixed(1)} MB` }
function localTime(value: string) { return value ? new Date(value).toLocaleString() : '—' }
function referenceKey(item: AssetReferenceDefinition) { return [item.path, item.statement_id, item.parameter_id, item.value_id, item.field_path].join(':') }
function referenceTitle(item: AssetReferenceDefinition) {
    // `item.function_id` is the containing project function. The called contract is
    // identified by the globally stable parameter id carried by the reference.
    const definition = store.functions.find(candidate => candidate.parameters.some(parameter => parameter.parameter_id === item.parameter_id))
    const parameter = definition?.parameters.find(candidate => candidate.parameter_id === item.parameter_id)
    if (definition) return parameter ? `${definition.qualified_name} · ${parameter.display_name || parameter.name}` : definition.qualified_name
    if (item.preview && (!item.parameter_id || !item.preview.includes(item.parameter_id))) return item.preview
    return '项目流程中的资源'
}
function referenceDetail(item: AssetReferenceDefinition) {
    return item.statement_id ? '流程语句 · 点击定位' : '项目引用 · 点击定位'
}
function openReference(item: AssetReferenceDefinition) { emit('open-reference', item); emit('open-source', item) }
function revokePreviewUrl(value: string) { if (typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(value) }
function setMessage(value: string, error = false) { message.value = value; messageError.value = error }
function sourceLabel(value: string) { return ({ import: '本地导入', capture: 'Capture Session', record: '视觉录入', replace: '文件替换' } as Record<string, string>)[value] || value || '未知' }
function setAssetCardRef(assetId: string, element: unknown) {
    const previous = assetCardElements.get(assetId)
    if (previous && previous !== element) previewObserver?.unobserve(previous)
    if (element instanceof HTMLElement) {
        assetCardElements.set(assetId, element)
        previewObserver?.observe(element)
    } else assetCardElements.delete(assetId)
}
async function focusAssetCard(assetId = selectedAssetId.value) {
    await nextTick()
    ;(assetCardElements.get(assetId) || galleryImportButton.value)?.focus({ preventScroll: true })
}
function closeInspector() { inspectorOpen.value = false; emit('update:detail-open', false); void focusAssetCard() }
function chooseImport() { if (!mutationBusy.value) importInput.value?.click() }
function chooseReplace() { if (!mutationBusy.value) replaceInput.value?.click() }
function openFolderDialog(mode:'create'|'rename', category:AssetCategoryId=selectedCategory.value, folder=''){
    if (mutationBusy.value) return
    dialogReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    folderDialogMode.value=mode;folderCategory.value=category;folderPath.value=folder;folderName.value=mode==='rename'?folder.split('/').pop()||'':'';folderDeleteForce.value=false;folderDeleteMessage.value=''
    folderDialog.value?.showModal();queueMicrotask(()=>folderNameInput.value?.focus())
}
function closeFolderDialog(){
    if (folderBusy.value) return
    folderDialog.value?.close();folderDeleteMessage.value='';folderDeleteForce.value=false
    const returnTarget = dialogReturnFocus; dialogReturnFocus = null
    queueMicrotask(() => returnTarget?.focus())
}
async function submitFolderDialog(){
    if(!store.workspace)return
    folderBusy.value=true
    let shouldClose=false
    try{
        if(folderDialogMode.value==='create'){
            const name=folderName.value.trim();if(!name)return
            await vnextApi.createAssetFolder(store.workspace,folderCategory.value,[selectedFolder.value,name].filter(Boolean).join('/'))
        }else if(folderDialogMode.value==='rename'){
            const name=folderName.value.trim();if(!name)return
            const parts=folderPath.value.split('/');parts.pop();const parent=[folderCategory.value,...parts].join('/')
            const result=await vnextApi.moveAssetFolder(store.workspace,`${folderCategory.value}/${folderPath.value}`,parent,name)
            selectedFolder.value=result.new_path.split('/').slice(1).join('/')
        }else{
            const result=await vnextApi.deleteAssetFolder(store.workspace,`${folderCategory.value}/${folderPath.value}`,folderDeleteForce.value)
            if(result.blocked){folderDeleteForce.value=false;folderDeleteMessage.value=`文件夹中的资源仍有 ${(result.references as unknown[]|undefined)?.length||0} 处引用；请先替换或清除引用。`;return}
            if(result.requires_confirmation){folderDeleteForce.value=true;folderDeleteMessage.value=`文件夹包含 ${result.asset_count||0} 项资源；再次确认将删除这些未被引用的资源。`;return}
            if(selectedCategory.value===folderCategory.value&&(selectedFolder.value===folderPath.value||selectedFolder.value.startsWith(folderPath.value+'/')))selectedFolder.value=''
        }
        await store.refreshAssets();shouldClose=true
    }catch(error){folderDeleteMessage.value=error instanceof Error?error.message:'文件夹操作失败'}
    finally{folderBusy.value=false;if(shouldClose)closeFolderDialog()}
}
async function copyText(value: string) { try { await navigator.clipboard?.writeText(value); setMessage('已复制资源 ID') } catch { setMessage('无法访问剪贴板，请手动复制资源 ID', true) } }
async function loadPreviews(assets: AssetDefinition[] = visibleAssets.value) {
    const pending = assets.filter(asset => !previewUrls[asset.asset_id] && !previewLoading.has(asset.asset_id))
    pending.forEach(asset => previewLoading.add(asset.asset_id))
    for (let offset = 0; offset < pending.length; offset += 8) {
        await Promise.all(pending.slice(offset, offset + 8).map(async asset => {
            try {
                const url = await store.assetPreviewUrl(asset.asset_id)
                if (disposed || !store.assets.some(item => item.asset_id === asset.asset_id)) revokePreviewUrl(url)
                else { previewUrls[asset.asset_id] = url; delete previewErrors[asset.asset_id] }
            } catch { previewErrors[asset.asset_id] = true }
            finally { previewLoading.delete(asset.asset_id) }
        }))
    }
}
async function retryPreview(asset: AssetDefinition) {
    delete previewErrors[asset.asset_id]
    if (previewUrls[asset.asset_id]) revokePreviewUrl(previewUrls[asset.asset_id])
    delete previewUrls[asset.asset_id]
    await loadPreviews([asset])
    if (selectedAssetId.value !== asset.asset_id) return
    if (previewErrors[asset.asset_id]) setMessage('资源预览仍无法加载；请检查文件是否丢失或被外部修改。', true)
    else setMessage('资源预览已恢复')
}
function syncAssetViewport(event?: Event) {
    const element = (event?.currentTarget as HTMLElement | null) || assetGrid.value
    if (!element) return
    assetScrollTop.value = element.scrollTop
    assetViewportWidth.value = Math.max(1, element.clientWidth || assetViewportWidth.value)
    assetViewportHeight.value = Math.max(1, element.clientHeight || assetViewportHeight.value)
}
async function revealAsset(assetId: string) {
    const index = filteredAssets.value.findIndex(item => item.asset_id === assetId)
    if (index < 0) return
    await nextTick()
    syncAssetViewport()
    const row = Math.floor(index / assetColumns.value)
    const top = ASSET_PADDING + row * assetRowHeight.value
    const bottom = top + assetCardHeight.value
    const viewport = assetGrid.value
    if (!viewport) return
    if (top < viewport.scrollTop || bottom > viewport.scrollTop + viewport.clientHeight) {
        viewport.scrollTop = Math.max(0, top - Math.floor(viewport.clientHeight / 3))
        syncAssetViewport()
        await nextTick()
    }
}
async function selectAsset(asset: AssetDefinition) {
    const generation = ++referenceLoadGeneration
    selectedAssetId.value = asset.asset_id
    assetDraft.display_name = asset.display_name
    assetDraft.category = asset.category
    assetDraft.folder = asset.folder
    deletePending.value = false
    references.value = []
    setMessage('')
    void loadPreviews([asset])
    if (compactLayout.value) await openInspector()
    try {
        const loaded = store.workspace ? (await vnextApi.assetReferences(store.workspace, asset.asset_id)).references : []
        if (generation === referenceLoadGeneration && selectedAssetId.value === asset.asset_id) references.value = loaded
    } catch (error) {
        if (generation === referenceLoadGeneration && selectedAssetId.value === asset.asset_id) {
            references.value = []
            setMessage(error instanceof Error ? error.message : '无法读取资源引用', true)
        }
    }
}
async function openInspector(): Promise<void> { inspectorOpen.value = true; emit('update:detail-open', true); await nextTick(); inspectorCloseButton.value?.focus() }
function saveMetadata(): Promise<void> {
    const assetId = selectedAsset.value?.asset_id
    if (!assetId) return Promise.resolve()
    const payload = { ...assetDraft }
    metadataPendingCount.value += 1
    const run = async () => {
        try {
            const live = store.assets.find(item => item.asset_id === assetId)
            const unchanged = live && live.display_name === payload.display_name && live.category === payload.category && live.folder === payload.folder
            const updated = unchanged ? live : await store.updateAsset(assetId, payload)
            if (updated && selectedAssetId.value === assetId) {
                const draftUnchanged = assetDraft.display_name === payload.display_name && assetDraft.category === payload.category && assetDraft.folder === payload.folder
                if (draftUnchanged) Object.assign(assetDraft, { display_name: updated.display_name, category: updated.category, folder: updated.folder })
                // Keep the edited asset in view after moving it to another category or folder.
                // Otherwise the gallery and inspector describe two different navigation contexts.
                selectedCategory.value = updated.category
                selectedFolder.value = updated.folder
            }
            if (selectedAssetId.value === assetId) setMessage('已保存')
        } catch (error) {
            if (selectedAssetId.value === assetId) setMessage(error instanceof Error ? error.message : '保存失败', true)
        }
        finally { metadataPendingCount.value -= 1 }
    }
    metadataSaveTail = metadataSaveTail.catch(() => undefined).then(run)
    return metadataSaveTail
}
async function importFiles(event: Event) {
    const input = event.target as HTMLInputElement
    const files = [...(input.files || [])]
    input.value = ''
    if (!files.length) return
    const category = selectedCategory.value
    const folder = selectedFolder.value
    importBusy.value = true
    setMessage('')
    let lastAsset: AssetDefinition | null = null
    let importedCount = 0
    const duplicates: string[] = []
    let failure = ''
    try {
        for (const file of files) {
            const imported = await store.importAsset(file, category, folder)
            if (imported?.asset) { lastAsset = imported.asset; importedCount += 1 }
            if (imported?.duplicate_of?.display_name) duplicates.push(String(imported.duplicate_of.display_name))
        }
    } catch (error) {
        failure = error instanceof Error ? error.message : '图片导入失败'
    } finally {
        importBusy.value = false
    }
    if (lastAsset) await loadPreviews([lastAsset])
    const current = lastAsset ? store.assets.find(item => item.asset_id === lastAsset!.asset_id) : null
    if (current) {
        selectedCategory.value = current.category
        selectedFolder.value = current.folder
        await revealAsset(current.asset_id)
        await selectAsset(current)
    }
    if (failure) setMessage(importedCount ? `已导入 ${importedCount} 项，后续文件失败：${failure}` : failure, true)
    else if (duplicates.length) setMessage(`已导入 ${importedCount} 项；其中内容与“${[...new Set(duplicates)].join('、')}”相同，已按独立资源保留。`)
    else setMessage(`已导入 ${importedCount} 项到 ${category}${folder ? `/${folder}` : ''}`)
}
async function replaceFile(event: Event) {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    input.value = ''
    if (!file || !selectedAsset.value) return
    replaceBusy.value = true
    const assetId = selectedAsset.value.asset_id
    try {
        await store.replaceAsset(assetId, file)
        if (previewUrls[assetId]) revokePreviewUrl(previewUrls[assetId])
        delete previewUrls[assetId]
        delete previewErrors[assetId]
        const updated = store.assets.find(item => item.asset_id === assetId)
        if (updated) await loadPreviews([updated])
        if (selectedAssetId.value === assetId) setMessage('图片已替换，资源 ID 与引用保持不变')
    } catch (error) {
        if (selectedAssetId.value === assetId) setMessage(error instanceof Error ? error.message : '替换失败', true)
    }
    finally { replaceBusy.value = false }
}
async function requestDelete() {
    if (!selectedAsset.value) return
    const assetId = selectedAsset.value.asset_id
    deleteBusy.value = true
    try {
        const loadedReferences = store.workspace
            ? (await vnextApi.assetReferences(store.workspace, assetId)).references
            : []
        if (selectedAssetId.value !== assetId) return
        references.value = loadedReferences
        if (references.value.length) {
            deletePending.value = false
            setMessage(`该资源仍有 ${references.value.length} 处引用，请先在对应语句中替换或清除；系统不会生成无效脚本。`, true)
            return
        }
        deletePending.value = true
        setMessage('删除后无法从项目内恢复。')
    } catch (error) { setMessage(error instanceof Error ? error.message : '无法检查资源删除影响', true) }
    finally { deleteBusy.value = false }
}
async function confirmDelete() {
    if (!selectedAsset.value) return
    const id = selectedAsset.value.asset_id
    const visibleBeforeDelete = [...visibleAssets.value]
    const deletedIndex = visibleBeforeDelete.findIndex(item => item.asset_id === id)
    const focusCandidateId = visibleBeforeDelete[deletedIndex + 1]?.asset_id || visibleBeforeDelete[deletedIndex - 1]?.asset_id || ''
    deleteBusy.value = true
    try {
        const result = await store.deleteAsset(id)
        if (!result?.deleted) {
            references.value = result?.references || []
            deletePending.value = false
            setMessage(result?.message || '资源仍有引用，删除已取消。', true)
            return
        }
        if (previewUrls[id]) revokePreviewUrl(previewUrls[id])
        delete previewUrls[id]
        delete previewErrors[id]
        deletePending.value = false
        const nextAsset = store.assets.find(item => item.asset_id === focusCandidateId)
        if (nextAsset) await selectAsset(nextAsset)
        else { selectedAssetId.value = ''; references.value = []; inspectorOpen.value = false; setMessage('') }
        if (compactLayout.value) inspectorOpen.value = false
        await focusAssetCard(nextAsset?.asset_id || '')
    } catch (error) { setMessage(error instanceof Error ? error.message : '资源删除失败', true) }
    finally { deleteBusy.value = false }
}
async function refreshWorkspace() {
    // Keep an already usable gallery visible while refreshing in the
    // background.  Blocking an existing list creates a visible flash and can
    // strand large libraries behind a spinner while thumbnails hydrate.
    workspaceLoading.value = store.assets.length === 0
    workspaceError.value = ''
    try {
        await store.refreshAssets()
        // The resource list is useful before thumbnails finish. A real
        // IntersectionObserver hydrates only cards near the viewport.
        workspaceLoading.value = false
        if (!previewObserver) void loadPreviews()
    }
    catch (error) { workspaceError.value = error instanceof Error ? error.message : '无法读取资源目录' }
    finally { workspaceLoading.value = false }
}
function syncCompactLayout(event?: MediaQueryListEvent) {
    compactLayout.value = event?.matches ?? compactMedia?.matches ?? false
    if (!compactLayout.value) inspectorOpen.value = false
}
onMounted(async () => {
    compactMedia = window.matchMedia?.('(max-width: 1099px)') || null
    syncCompactLayout()
    compactMedia?.addEventListener?.('change', syncCompactLayout)
    await refreshWorkspace()
    await nextTick()
    syncAssetViewport()
    if (typeof ResizeObserver !== 'undefined' && assetGrid.value) {
        assetResizeObserver = new ResizeObserver(() => syncAssetViewport())
        assetResizeObserver.observe(assetGrid.value)
    }
    if (typeof IntersectionObserver !== 'undefined') {
        previewObserver = new IntersectionObserver((entries) => {
            const requested = entries
                .filter(entry => entry.isIntersecting)
                .map(entry => store.assets.find(asset => asset.asset_id === (entry.target as HTMLElement).dataset.assetId))
                .filter((asset): asset is AssetDefinition => Boolean(asset))
            for (const entry of entries) {
                if (entry.isIntersecting) previewObserver?.unobserve(entry.target)
            }
            if (requested.length) void loadPreviews(requested)
        }, { root: assetGrid.value, rootMargin: '180px 0px' })
        assetCardElements.forEach(element => previewObserver?.observe(element))
    }
})
watch([selectedCategory, selectedFolder, query], async () => {
    assetScrollTop.value = 0
    if (assetGrid.value) assetGrid.value.scrollTop = 0
    await nextTick()
    if (selectedAssetId.value && filteredAssets.value.some(item => item.asset_id === selectedAssetId.value)) {
        await revealAsset(selectedAssetId.value)
    }
})
watch(() => props.initialCategory, category => { selectedCategory.value = category; selectedFolder.value = '' })
watch(() => store.assets.map(item => item.asset_id).join('|'), () => {
    const liveIds = new Set(store.assets.map(item => item.asset_id))
    for (const assetId of Object.keys(previewUrls)) {
        if (liveIds.has(assetId)) continue
        revokePreviewUrl(previewUrls[assetId])
        delete previewUrls[assetId]
        delete previewErrors[assetId]
    }
    for (const assetId of Object.keys(previewErrors)) {
        if (!liveIds.has(assetId)) delete previewErrors[assetId]
    }
})
onBeforeUnmount(() => { disposed = true; previewObserver?.disconnect(); assetResizeObserver?.disconnect(); compactMedia?.removeEventListener?.('change', syncCompactLayout); Object.values(previewUrls).forEach(revokePreviewUrl) })
</script>

<style scoped>
.resource-workspace.detail-panel-collapsed { grid-template-columns: 220px minmax(320px, 1fr); }
.resource-workspace{min-width:0;min-height:0;flex:1;display:grid;grid-template-columns:220px minmax(320px,1fr) 300px;background:var(--app-bg-base);color:var(--app-text-regular)}.resource-tree,.asset-inspector{min-width:0;background:var(--app-bg-sidebar)}.resource-tree{border-right:1px solid var(--app-border-subtle)}.asset-inspector{border-left:1px solid var(--app-border-subtle)}.resource-tree>header,.asset-inspector>header,.gallery-header{height:40px;display:flex;align-items:center;justify-content:space-between;padding:0 10px 0 12px;border-bottom:1px solid var(--app-border-subtle)}.resource-tree>header>div,.gallery-header>div{min-width:0;display:flex;align-items:center;gap:6px}.resource-tree strong,.asset-inspector strong,.gallery-header strong{font-size: var(--app-font-compact);color:var(--app-text-primary)}.resource-tree header span,.gallery-header span,.gallery-header small{color:var(--app-text-secondary);font-size: var(--app-font-caption)}.resource-tree header button{width:28px;height: var(--app-control-compact);display:grid;place-items:center;border:0;border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-secondary);cursor:pointer}.resource-tree header button:hover{background:var(--app-bg-hover);color:var(--app-text-primary)}.resource-search{height: var(--app-control-compact);display:flex;align-items:center;gap:6px;margin:8px;padding:0 8px;border:1px solid var(--app-border-default);border-radius: var(--app-radius-sm);background:var(--app-bg-input);color:var(--app-text-secondary)}.resource-search:focus-within{border-color:var(--app-color-primary);box-shadow:var(--focus-ring)}.resource-search input{min-width:0;flex:1;border:0;outline:0;background:transparent;color:var(--app-text-primary);font-size: var(--app-font-caption)}.resource-tree nav{height:calc(100% - 87px);overflow:auto;padding:0 6px 10px}.resource-tree nav button{width:100%;height: var(--app-control-compact);display:grid;grid-template-columns:18px minmax(0,1fr) auto;align-items:center;gap:6px;padding:0 8px;border:0;border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-regular);font-size: var(--app-font-caption);text-align:left;cursor:pointer}.resource-tree nav button:hover{background:var(--app-bg-hover)}.resource-tree nav button.active{background:var(--app-color-primary-dim);color:var(--app-text-primary)}.resource-tree nav small{color:var(--app-text-placeholder);font-size: var(--app-font-caption)}.resource-tree .folder-row{padding-left:25px;color:var(--app-text-secondary)}.resource-gallery{min-width:0;display:grid;grid-template-rows:40px minmax(0,1fr);overflow:hidden}.primary-action,.resource-empty button,.asset-actions button{height: var(--app-control-compact);display:flex;align-items:center;justify-content:center;gap:5px;padding:0 9px;border:1px solid var(--app-border-default);border-radius: var(--app-radius-sm);background:var(--app-bg-raised);color:var(--app-text-regular);font-size: var(--app-font-caption);cursor:pointer}.primary-action:hover,.resource-empty button:hover,.asset-actions button:hover{background:var(--app-bg-hover);color:var(--app-text-primary)}.asset-grid{position:relative;overflow:auto;contain:strict}.asset-virtual-content{position:relative;min-width:0}.asset-window{position:absolute;left:0;right:0;display:grid;align-content:start}.asset-card{height:var(--asset-card-height);min-width:0;padding:0;border:1px solid transparent;border-radius: var(--app-radius-md);background:transparent;color:inherit;text-align:left;cursor:pointer}.asset-card:hover{background:var(--app-bg-hover)}.asset-card.active{border-color:var(--app-color-primary);background:var(--app-color-primary-dim)}.asset-preview{height:calc(var(--asset-card-height) - 36px);display:grid;place-items:center;overflow:hidden;margin:5px;border-radius: var(--app-radius-sm);background:var(--app-bg-input);color:var(--app-text-placeholder)}.asset-preview img{width:100%;height:100%;object-fit:contain}.asset-caption{display:flex;align-items:center;gap:6px;padding:3px 7px 8px}.asset-caption strong{min-width:0;flex:1;overflow:hidden;color:var(--app-text-primary);font-size: var(--app-font-caption);font-weight:500;text-overflow:ellipsis;white-space:nowrap}.asset-caption span{color:var(--app-text-placeholder);font-size: var(--app-font-caption)}.resource-empty{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;padding:24px;color:var(--app-text-secondary);text-align:center}.resource-empty strong{color:var(--app-text-regular);font-size: var(--app-font-compact)}.resource-empty span{max-width:270px;font-size: var(--app-font-caption);line-height:16px}.resource-empty.compact{height:calc(100% - 40px)}.asset-details{container-type:inline-size;height:calc(100% - 40px);overflow:auto;padding:12px}.detail-preview{aspect-ratio:16/10;display:grid;place-items:center;overflow:hidden;margin-bottom:14px;border:1px solid var(--app-border-subtle);border-radius: var(--app-radius-md);background:var(--app-bg-input)}.detail-preview img{width:100%;height:100%;object-fit:contain}.asset-field{--app-form-row-label-min:72px;--app-form-row-label-max:84px;margin-bottom:10px;color:var(--app-text-secondary);font-size:var(--app-font-caption)}.asset-details input,.asset-details select{width:100%;height:var(--app-control-default);padding:0 8px;border:1px solid var(--app-border-default);border-radius:var(--app-radius-sm);outline:0;background:var(--app-bg-input);color:var(--app-text-primary);font-size:var(--app-font-caption)}.asset-details input:focus,.asset-details select:focus{border-color:var(--app-color-primary);box-shadow:var(--focus-ring)}.asset-details dl{margin:16px 0;border-top:1px solid var(--app-border-subtle)}.asset-details dl>div{min-height: var(--app-control-default);display:grid;grid-template-columns:72px minmax(0,1fr);align-items:center;border-bottom:1px solid var(--app-border-subtle);font-size: var(--app-font-caption)}.asset-details dt{color:var(--app-text-secondary)}.asset-details dd{min-width:0;display:flex;align-items:center;gap:4px;margin:0;color:var(--app-text-regular)}.asset-details dd code{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.asset-details dd button{width:24px;height:24px;display:grid;place-items:center;border:0;border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-secondary);cursor:pointer}.reference-list{display:flex;flex-direction:column;gap:2px;margin-bottom:10px}.reference-list button{display:flex;flex-direction:column;gap:2px;padding:6px 7px;border:0;border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-regular);text-align:left;cursor:pointer}.reference-list button:hover{background:var(--app-bg-hover)}.reference-list span{font-size: var(--app-font-caption)}.reference-list small{overflow:hidden;color:var(--app-text-secondary);font-size: var(--app-font-caption);text-overflow:ellipsis;white-space:nowrap}.asset-message{padding:8px;border-radius: var(--app-radius-sm);background:var(--app-color-primary-dim);color:var(--app-text-regular);font-size: var(--app-font-caption);line-height:15px}.asset-message.danger{background:color-mix(in srgb,var(--app-color-danger) 12%,transparent);color:var(--app-color-danger)}.asset-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.asset-actions .danger{color:var(--app-color-danger)}.asset-actions .solid{border-color:var(--app-color-danger);background:var(--app-color-danger);color:var(--app-color-on-primary)}.asset-range-status{position:sticky;left:50%;bottom:6px;z-index:2;width:max-content;max-width:calc(100% - 16px);padding:3px 8px;transform:translateX(-50%);border:1px solid var(--app-border-subtle);border-radius:999px;background:var(--app-bg-raised);color:var(--app-text-placeholder);font-size: var(--app-font-caption);pointer-events:none;box-shadow:var(--app-shadow-sm)}@media(max-width:1050px){.resource-workspace{grid-template-columns:190px minmax(280px,1fr) 260px}}@media(max-width:820px){.resource-workspace{grid-template-columns:180px minmax(280px,1fr)}.asset-inspector{display:none}}
.technical-details{margin:6px 0 14px;border-bottom:1px solid var(--app-border-subtle)}.technical-details>summary{padding:9px 0;color:var(--app-text-secondary);font-size:var(--app-font-xs);cursor:pointer}.technical-details>summary:hover{color:var(--app-text-primary)}.technical-details dl{margin:0;border-top:1px solid var(--app-border-subtle)}
.tree-actions{display:flex;align-items:center;gap:2px}.folder-row{grid-template-columns:18px minmax(0,1fr) auto 18px!important}.folder-more{display:grid;place-items:center;width:18px;height:18px;border-radius: var(--app-radius-sm);opacity:0;color:var(--app-text-secondary)}.folder-row:hover .folder-more,.folder-row.active .folder-more,.folder-more:focus{opacity:1;background:var(--app-bg-hover)}.folder-dialog{container-type:inline-size;width:min(420px,calc(100vw - 32px));padding:0;border:1px solid var(--app-border-default);border-radius: var(--app-radius-lg);background:var(--app-bg-raised);color:var(--app-text-regular);box-shadow:0 18px 60px rgba(0,0,0,.45)}.folder-dialog::backdrop{background:rgba(0,0,0,.55)}.folder-dialog form>header{height:42px;display:flex;align-items:center;justify-content:space-between;padding:0 13px;border-bottom:1px solid var(--app-border-subtle)}.folder-dialog form>header button{width:26px;height:26px;border:0;border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-secondary);cursor:pointer}.folder-field{--app-form-row-label-min:86px;--app-form-row-label-max:96px;margin:16px;font-size:var(--app-font-caption)}.folder-dialog input{width:100%;height:var(--app-control-default);padding:0 9px;border:1px solid var(--app-border-default);border-radius:var(--app-radius-sm);outline:0;background:var(--app-bg-input);color:var(--app-text-primary)}.folder-dialog input:focus{border-color:var(--app-color-primary);box-shadow:var(--focus-ring)}.folder-dialog input[aria-invalid='true']{border-color:var(--app-color-danger)}.folder-dialog p{margin:10px 16px 16px;color:var(--app-text-secondary);font-size:var(--app-font-caption);line-height:16px}.folder-dialog .danger-text{color:var(--app-color-danger)}.folder-dialog footer{display:flex;justify-content:flex-end;gap:6px;padding:12px 16px;border-top:1px solid var(--app-border-subtle)}.folder-dialog footer button{height:var(--app-control-default);padding:0 10px;border:1px solid var(--app-border-default);border-radius:var(--app-radius-sm);background:var(--app-bg-input);color:var(--app-text-regular);cursor:pointer}.folder-dialog footer .danger{border-color:var(--app-color-danger);color:var(--app-color-danger)}
.resource-tree nav .folder-row{width:100%;display:grid;grid-template-columns:minmax(0,1fr) 24px!important;align-items:center;padding-left:17px;border-radius: var(--app-radius-sm);color:var(--app-text-secondary)}.resource-tree nav .folder-row:hover,.resource-tree nav .folder-row.active{background:var(--app-bg-hover)}.resource-tree nav .folder-select{height: var(--app-control-compact);grid-template-columns:18px minmax(0,1fr) auto;padding:0 2px 0 8px}.resource-tree nav .folder-more{width:22px;height:22px;display:grid;place-items:center;padding:0;border:0;border-radius: var(--app-radius-sm);opacity:0;background:transparent;color:var(--app-text-secondary)}.folder-row:hover .folder-more,.folder-row.active .folder-more,.folder-more:focus-visible{opacity:1}.resource-tree nav .folder-more:hover,.resource-tree nav .folder-more:focus-visible{background:var(--app-bg-active);color:var(--app-text-primary)}
.resource-tree nav button>span,.gallery-header>div>span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.resource-workspace{position:relative}.gallery-actions{display:flex;align-items:center;gap:6px}.icon-action,.asset-inspector>header button{width:28px;height: var(--app-control-compact);display:grid;place-items:center;padding:0;border:0;border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-secondary);cursor:pointer}.icon-action:hover:not(:disabled),.asset-inspector>header button:hover{background:var(--app-bg-hover);color:var(--app-text-primary)}.icon-action:disabled{opacity:.35;cursor:not-allowed}.asset-inspector-scrim{position:absolute;z-index:29;inset:0;padding:0;border:0;background:#05050588;cursor:default}.asset-inspector.is-compact{position:absolute;z-index:30;top:0;right:0;bottom:0;display:block;width:min(320px,calc(100% - 44px));box-shadow:var(--app-shadow-lg)}
@media(max-width:820px){.asset-inspector{display:block}.asset-inspector:not(.is-compact){display:none}}
.resource-workspace button:focus-visible{outline:2px solid var(--app-color-primary);outline-offset:2px}.resource-workspace button:disabled,.resource-workspace input:disabled,.resource-workspace select:disabled{opacity:.48;cursor:not-allowed}.resource-state{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;padding:24px;color:var(--app-text-secondary);text-align:center}.resource-state strong{color:var(--app-text-primary);font-size: var(--app-font-compact)}.resource-state span{max-width:360px;font-size: var(--app-font-caption);line-height:16px;overflow-wrap:anywhere}.resource-state button{height: var(--app-control-compact);display:flex;align-items:center;gap:5px;padding:0 10px;border:1px solid var(--app-border-default);border-radius: var(--app-radius-sm);background:var(--app-bg-raised);color:var(--app-text-primary);cursor:pointer}.resource-state.is-error svg,.resource-state.is-error strong{color:var(--app-color-danger)}.asset-details dd small{color:var(--app-text-secondary);font-size: var(--app-font-caption)}.asset-actions .solid{color:var(--app-color-on-primary)}.spin{animation:resource-spin .8s linear infinite}@keyframes resource-spin{to{transform:rotate(360deg)}}
@media(max-width:1099px){.resource-workspace{grid-template-columns:200px minmax(0,1fr)}.asset-inspector{display:block}.asset-inspector:not(.is-compact){display:none}}
@media(max-width:700px){.resource-workspace{grid-template-columns:150px minmax(0,1fr)}.resource-gallery{grid-template-rows:minmax(40px,auto) minmax(0,1fr)}.gallery-header{height:auto;min-height:40px;align-items:flex-start;gap:6px;padding-top:6px;padding-bottom:6px}.gallery-actions{justify-content:flex-end;flex-wrap:wrap}.resource-tree .folder-row{padding-left:12px}}
.asset-preview.has-error{color:var(--app-color-danger)}
.folder-field > .app-form-help { color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.folder-field > .app-form-error { color: var(--app-color-danger); font-size: var(--app-font-xs); }
@container (max-width:260px){.asset-field,.folder-field{grid-template-columns:minmax(0,1fr);row-gap:var(--app-form-label-control-gap)}.asset-field>.app-form-help,.asset-field>.app-form-error,.folder-field>.app-form-help,.folder-field>.app-form-error{grid-column:1}}
.resource-workspace button,
.resource-workspace input,
.resource-workspace select,
.resource-workspace label,
.resource-workspace small,
.resource-workspace dt,
.resource-workspace dd,
.resource-workspace .asset-caption strong,
.resource-workspace .asset-caption span,
.resource-workspace .asset-message,
.resource-workspace .asset-range-status,
.resource-workspace .resource-empty span,
.resource-workspace .resource-state span { font-size: var(--app-font-xs); }
@media(min-width:701px){.resource-workspace{grid-template-columns:var(--workspace-sidebar-width,260px) minmax(0,1fr) 300px}}
@media(min-width:701px) and (max-width:1099px){.resource-workspace{grid-template-columns:var(--workspace-sidebar-width,260px) minmax(0,1fr)}}
@media(min-width:701px){.resource-workspace.detail-panel-collapsed{grid-template-columns:var(--workspace-sidebar-width,260px) minmax(0,1fr)}}
</style>
