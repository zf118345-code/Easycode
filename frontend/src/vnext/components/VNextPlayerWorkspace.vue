<template>
    <section :class="['player-workspace', { 'detail-panel-collapsed': !detailVisible }]" aria-label="Player 界面配置">
        <VNextNavigationPane :class="['player-outline', { 'is-open': outlineOpen }]" @keydown.esc.stop="closeOutline">
            <VNextPaneHeader title="Player" :meta="dirty ? '有未保存修改' : saveMessage || '已保存'">
                <template #actions><div class="header-actions">
                    <VNextIconButton v-if="compactLayout" class="outline-close" label="关闭页面与控件列表" @click="closeOutline"><PanelLeftClose /></VNextIconButton>
                    <VNextIconButton label="新增页面" @click="addPage()"><Plus /></VNextIconButton>
                    <VNextIconButton label="添加已绑定控件" :disabled="!selectedPage" @click="openSourcePicker()"><PanelTopOpen /></VNextIconButton>
                </div></template>
            </VNextPaneHeader>
            <div class="outline-content app-navigation-list">
                <VNextNavigationItem class="page-row application-row" :selected="applicationSelected" @click="selectApplication">
                    <VNextAssetThumbnail v-if="applicationIconAsset" :asset="applicationIconAsset" :load-preview="store.assetPreviewUrl" :size="14" eager :show-popover="false" />
                    <Settings2 v-else :size="14" /><span>应用设置</span><small>{{ draft.icon_asset_id ? '已设图标' : '默认图标' }}</small>
                </VNextNavigationItem>
                <template v-for="page in draft.pages" :key="page.page_id">
                    <VNextNavigationItem class="page-row" :selected="!applicationSelected && page.page_id === selectedPageId && !selectedControlId" @click="selectPage(page.page_id)">
                        <PanelTop :size="14" /><span>{{ page.title }}</span><small>{{ page.controls.length }}</small>
                    </VNextNavigationItem>
                    <VNextNavigationItem v-for="control in page.controls" :key="control.control_id" class="control-row" child :selected="control.control_id === selectedControlId" @click="selectControl(page.page_id, control.control_id)">
                        <component :is="controlIcon(control.type)" :size="13" /><span>{{ control.label }}</span>
                    </VNextNavigationItem>
                </template>
                <button v-if="!draft.pages.length" type="button" class="empty-create" @click="addPage()"><Plus :size="15" />创建第一个页面</button>
            </div>
            <footer>
                <button type="button" class="secondary" :disabled="!dirty || saving" @click="resetDraft">放弃修改</button>
                <button type="button" class="primary" :disabled="!dirty || saving || !draft.pages.length" @click="save"><Save :size="14" />{{ saving ? '保存中' : '保存表单' }}</button>
            </footer>
        </VNextNavigationPane>

        <main class="player-preview-area">
            <VNextPaneHeader role="workspace" title="Player 预览">
                <template #actions><div class="preview-actions">
                    <span v-if="previewError" class="preview-error" role="alert">{{ previewError }}</span>
                    <span v-else-if="previewExecution" class="preview-status">{{ previewStatus }}</span>
                    <VNextIconButton v-if="!previewIsActive" label="预览运行 Player" title="使用默认运行目标真实执行已保存表单" :disabled="dirty || saving || !draft.pages.length" @click="startPreview()"><Play /></VNextIconButton>
                    <VNextIconButton v-else label="停止 Player 预览" title="停止预览" @click="stopPreview"><Square /></VNextIconButton>
                    <VNextIconButton v-if="compactLayout" ref="outlineToggleButton" class="outline-toggle" label="打开页面与控件列表" @click="outlineOpen = true"><PanelLeftOpen /></VNextIconButton>
                    <VNextIconButton v-if="compactLayout && props.detailOpen === undefined" ref="inspectorToggleButton" label="打开属性检查器" :disabled="!selectedPage && !applicationSelected" @click="openInspector"><PanelRightOpen /></VNextIconButton>
                    <div class="device-switch" aria-label="预览宽度">
                        <VNextIconButton label="桌面宽度预览" :pressed="previewWidth === 'wide'" @click="previewWidth = 'wide'"><Monitor /></VNextIconButton>
                        <VNextIconButton label="窄屏预览" :pressed="previewWidth === 'narrow'" @click="previewWidth = 'narrow'"><Smartphone /></VNextIconButton>
                    </div>
                    <VNextIconButton class="publish-button" label="检查并发布 Player" :disabled="dirty || saving || previewIsActive || !draft.pages.length" @click="publishOpen = true"><PackageCheck /></VNextIconButton>
                </div></template>
            </VNextPaneHeader>
            <div class="preview-canvas">
                <section :class="['player-card', previewWidth]">
                    <header><div><VNextAssetThumbnail v-if="applicationIconAsset" :asset="applicationIconAsset" :load-preview="store.assetPreviewUrl" :size="20" eager :show-popover="false" /><Braces v-else :size="18" /><strong>{{ draft.title }}</strong></div><span>{{ store.workspace?.project_name }}</span></header>
                    <VNextOverflowTabs v-if="draft.pages.length > 1" v-model="previewPageId" :items="draft.pages.map((page) => ({ id: page.page_id, label: page.title }))" label="Player 页面" />
                    <div v-if="previewPage" class="preview-form">
                        <label v-for="control in previewPage.controls" :key="control.control_id" :data-preview-control-id="control.control_id" :class="['preview-control', `span-${control.layout.span}`, { selected: control.control_id === selectedControlId, 'is-inline-field': playerControlUsesInlineLayout(control) }]" @click="selectControl(previewPage.page_id, control.control_id)">
                            <span v-if="control.type !== 'button'">{{ control.label }}<b v-if="control.required">*</b></span>
                            <VNextPlayerValueControl v-if="control.type !== 'button'" v-model="previewValues[control.control_id]" :control="control" :assets="store.assets" :platform="previewPlatform(control)" />
                            <button v-else type="button" class="action-button" :disabled="dirty || saving || previewIsActive" @click.stop="startPreview(control.control_id)"><Play :size="14" />{{ control.label }}</button>
                            <small v-if="control.help">{{ control.help }}</small>
                        </label>
                        <VNextWorkspaceState v-if="!previewPage.controls.length" class="preview-empty" compact kind="empty" title="这个页面还没有控件" description="添加一个真实绑定后，预览会立即出现。"><template #icon><LayoutTemplate :size="25" /></template><template #actions><VNextButton size="compact" @click="openSourcePicker()">添加已绑定控件</VNextButton></template></VNextWorkspaceState>
                    </div>
                </section>
            </div>
        </main>

        <button v-if="detailOverlayOpen || (compactLayout && outlineOpen)" type="button" class="player-panel-scrim" :aria-label="detailOverlayOpen ? '关闭属性检查器' : '关闭页面与控件列表'" @click="detailOverlayOpen ? closeInspector() : closeOutline()" />
        <aside v-if="detailVisible" :class="['player-inspector', { 'is-compact': detailAsOverlay }]" @keydown.esc.stop="closeInspector">
            <VNextPaneHeader role="inspector" title="属性"><template #actions><VNextIconButton v-if="detailAsOverlay" label="关闭属性检查器" @click="closeInspector"><PanelRightClose /></VNextIconButton></template></VNextPaneHeader>
            <div v-if="applicationSelected" class="properties app-inspector-body app-inspector-form">
                <div class="property-title"><VNextAssetThumbnail v-if="applicationIconAsset" :asset="applicationIconAsset" :load-preview="store.assetPreviewUrl" :size="28" eager :show-popover="false" /><Settings2 v-else :size="18" /><div><strong>{{ draft.title }}</strong><span>窗口名称与图标</span></div></div>
                <section><h3>应用外观</h3><label class="property-field">名称<input v-model.trim="draft.title" maxlength="80" placeholder="例如：超能世界助手" @input="markDirty" /></label><label class="property-field">图标<select v-model="draft.icon_asset_id" @change="markDirty"><option value="">使用 EasyCode 默认图标</option><option v-for="asset in applicationIconOptions" :key="asset.asset_id" :value="asset.asset_id">{{ asset.display_name }}</option></select></label><p>名称会显示在 Player 标题栏；图标会用于标题栏、任务栏和原生窗口。请先在资源库导入 PNG、JPG 或 BMP 图片。</p></section>
                <section><h3>可选能力</h3><label class="check-row"><input v-model="recordingFeaturePublished" type="checkbox" /><span>发布运行录制</span></label><p>仅在需要复盘长流程或排查偶发问题时开启。关闭后 Player 不显示录制入口，也不会订阅画面、写入录像或申请相关运行能力。</p></section>
            </div>
            <div v-else-if="selectedControl" class="properties app-inspector-body app-inspector-form">
                <div class="property-title"><component :is="controlIcon(selectedControl.type)" :size="17" /><div><strong>{{ selectedControl.label }}</strong><span>{{ controlTypeLabel(selectedControl.type) }}</span></div></div>
                <section><h3>外观</h3><label class="property-field">标签<input v-model.trim="selectedControl.label" maxlength="80" @input="markDirty" /></label><label class="property-field">辅助说明<input v-model.trim="selectedControl.help" maxlength="240" placeholder="仅在用户确实需要时说明" @input="markDirty" /></label><label class="property-field">宽度<select v-model.number="selectedControl.layout.span" @change="markDirty"><option :value="12">整行</option><option :value="6">半行</option><option :value="4">三分之一</option></select></label><label v-if="selectedControl.type !== 'button'" class="check-row" :title="selectedControlSource?.required ? '函数契约要求此值必填' : ''"><input v-model="selectedControl.required" type="checkbox" :disabled="selectedControlSource?.required" @change="markDirty" />必填</label></section>
                <section v-if="selectedControl.type !== 'button'"><h3>默认值</h3><VNextPlayerValueControl :model-value="selectedControl.default" :control="selectedControl" :assets="store.assets" :platform="previewPlatform(selectedControl)" @update:model-value="updateSelectedDefault" /></section>
                <section v-if="selectedBooleanMapOptions.length" class="fixed-option-section">
                    <h3>选项权限</h3>
                    <p>普通选项交给用户决定；固定项会在 Player 中锁定，并在运行前再次强制。</p>
                    <label v-for="option in selectedBooleanMapOptions" :key="String(option.value)" class="fixed-option-row">
                        <span>{{ option.label }}</span>
                        <select :value="fixedOptionMode(option)" @change="setFixedOptionMode(option, ($event.target as HTMLSelectElement).value)">
                            <option value="editable">用户可选</option>
                            <option value="on">固定必选</option>
                            <option value="off">固定不可选</option>
                        </select>
                    </label>
                </section>
                <section v-if="selectedControl.type !== 'button'" class="terminal-action-section">
                    <details>
                        <summary><span>允许终端用户操作</span><small>{{ selectedControl.terminal_actions?.length ? `已开放 ${selectedControl.terminal_actions.length} 项` : '默认关闭' }}</small></summary>
                        <p>仅在独立 Player、已保存方案和真实宿主均可用时显示。这里的响应式预览不会启动采集。</p>
                        <div v-if="selectedParameterActions.length" class="terminal-action-list">
                            <fieldset v-for="action in selectedParameterActions" :key="action.id">
                                <legend>{{ terminalActionLabel(action.id) }}</legend>
                                <label v-for="option in terminalPlatformOptions(action)" :key="option.platform" class="check-row" :title="option.reason">
                                    <input type="checkbox" :checked="terminalActionEnabled(action.id, option.platform)" :disabled="!option.available" @change="toggleTerminalAction(action.id, option.platform, ($event.target as HTMLInputElement).checked)" />
                                    <span>{{ platformLabel(option.platform) }}</span>
                                    <small v-if="!option.available">{{ option.reason }}</small>
                                </label>
                            </fieldset>
                        </div>
                        <p v-else>这个字段的 Control 契约没有可发布的终端动作。</p>
                    </details>
                </section>
                <section><h3>数据来源</h3><p>{{ bindingSummary(selectedControl) }}</p><button type="button" class="app-inline-action change-binding" @click="openSourcePicker()"><RefreshCw :size="14" aria-hidden="true" /><span>更换绑定</span></button></section>
                <button type="button" class="delete-control" @click="removeControl"><Trash2 :size="14" />删除控件</button>
            </div>
            <div v-else-if="selectedPage" class="properties app-inspector-body app-inspector-form"><div class="property-title"><PanelTop :size="17" /><div><strong>{{ selectedPage.title }}</strong><span>{{ selectedPage.controls.length }} 个控件</span></div></div><section><h3>页面</h3><label class="property-field">名称<input ref="pageNameInput" v-model.trim="selectedPage.title" maxlength="80" @input="markDirty" /></label></section><button v-if="draft.pages.length > 1" type="button" class="delete-control" @click="removePage"><Trash2 :size="14" />删除页面</button></div>
            <VNextWorkspaceState v-else class="player-empty" compact kind="selection" title="选择页面或控件" description="右侧只展示当前对象的必要配置。"><template #icon><MousePointer2 :size="21" /></template></VNextWorkspaceState>
        </aside>

        <div v-if="sourcePickerOpen" class="picker-backdrop" @mousedown.self="closeSourcePicker">
            <section class="source-picker" role="dialog" aria-modal="true" aria-labelledby="player-source-title" @keydown="trapDialogFocus" @keydown.esc="closeSourcePicker">
                <header><div><h2 id="player-source-title">选择要交给用户的内容</h2><p>选择一项添加到当前页面。</p></div><button type="button" aria-label="关闭绑定选择" @click="closeSourcePicker"><X :size="15" /></button></header>
                <div class="picker-filter">
                    <div class="picker-search"><Search :size="14" /><input ref="sourceSearchInput" v-model.trim="sourceQuery" placeholder="搜索名称、路径，或粘贴语句 ID" /></div>
                    <p v-if="locatedStatement" class="located-statement" role="status">
                        已定位到语句 {{ shortStatementId(locatedStatement.statementId) }}，共 {{ locatedStatement.sourceCount }} 个可发布参数
                    </p>
                </div>
                <VNextWorkspaceState v-if="sourceLoading" class="picker-state" compact kind="loading" title="正在读取可发布内容"><template #icon><LoaderCircle :size="18" /></template></VNextWorkspaceState>
                <VNextWorkspaceState v-else-if="sourceError" class="picker-state error" compact kind="error" title="读取失败" :description="sourceError"><template #icon><CircleAlert :size="18" /></template><template #actions><VNextButton size="compact" @click="loadBindingSources">重试</VNextButton></template></VNextWorkspaceState>
                <VNextWorkspaceState v-else-if="!filteredSourceGroups.length" class="picker-state" compact :kind="sourceQuery ? 'filtered' : 'empty'" title="没有可发布内容" :description="sourceQuery ? '换一个关键词，或清空搜索。' : '先在项目函数或变量中创建可交给用户配置的内容。'"><template #icon><Link2Off :size="18" /></template></VNextWorkspaceState>
                <div v-else class="source-groups">
                    <section v-for="group in filteredSourceGroups" :key="group.name">
                        <h3>{{ group.name }}</h3>
                        <div
                            v-for="source in group.items"
                            :key="source.source_id"
                            class="source-row"
                            role="option"
                            tabindex="0"
                            :aria-selected="selectedSourceId === source.source_id"
                            @dblclick="applyBindingSource(source)"
                            @click="selectedSourceId = source.source_id"
                            @keydown.enter.prevent="applyBindingSource(source)"
                        >
                            <VNextAssetThumbnail
                                v-if="sourceAsset(source)"
                                :asset="sourceAsset(source)"
                                :load-preview="store.assetPreviewUrl"
                                :size="18"
                            />
                            <component v-else :is="controlIcon(source.recommended_control)" :size="15" aria-hidden="true" />
                            <span><strong>{{ sourceDisplayLabel(source) }}</strong><small>{{ sourceContextLabel(source) }}</small></span>
                            <button type="button" class="app-inline-action insert-source" :aria-label="`使用 ${sourceDisplayLabel(source)}`" @click.stop="applyBindingSource(source)"><Check v-if="replacingControl" :size="14" aria-hidden="true" /><Plus v-else :size="14" aria-hidden="true" /><span>{{ replacingControl ? '应用' : '添加' }}</span></button>
                        </div>
                    </section>
                </div>
            </section>
        </div>
        <VNextPublishDialog v-if="publishOpen && store.workspace" :workspace="store.workspace" @close="publishOpen = false" />
    </section>
</template>

<script setup lang="ts">
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, reactive, ref, toRaw } from 'vue'
import { Braces, Check, CircleAlert, File, Folder, FormInput, Image as ImageIcon, LayoutTemplate, Link2Off, ListFilter, LoaderCircle, Monitor, MousePointer2, PackageCheck, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, PanelTop, PanelTopOpen, Play, Plus, RefreshCw, Save, Search, Settings2, Smartphone, Square, SquareMousePointer, ToggleLeft, Trash2, Type, X } from 'lucide-vue-next'
import { mergeRuntimeSession, vnextApi } from '../api'
import { trapDialogFocus } from '../dialogFocus'
import { useVNextStore } from '../store'
import VNextPlayerValueControl from './VNextPlayerValueControl.vue'
import VNextPublishDialog from './VNextPublishDialog.vue'
import VNextAssetThumbnail from './VNextAssetThumbnail.vue'
import VNextPaneHeader from './ui/VNextPaneHeader.vue'
import VNextNavigationPane from './ui/VNextNavigationPane.vue'
import VNextWorkspaceState from './ui/VNextWorkspaceState.vue'
import VNextButton from './ui/VNextButton.vue'
import VNextIconButton from './ui/VNextIconButton.vue'
import VNextNavigationItem from './ui/VNextNavigationItem.vue'
import VNextOverflowTabs from './ui/VNextOverflowTabs.vue'
import type { AssetDefinition, ParameterControlType, ParameterUiAction, ParameterUiContract, PlatformId, PlayerBinding, PlayerBindingSourceDefinition, PlayerControlDefinition, PlayerControlOption, PlayerControlType, PlayerFormDefinition, RuntimeSession } from '../types'

const store = useVNextStore()
const props = withDefaults(defineProps<{ initialStatementId?: string; detailOpen?: boolean; detailOverlay?: boolean }>(), { initialStatementId: '', detailOpen: undefined, detailOverlay: undefined })
const emit = defineEmits<{
    'runtime-session': [session: RuntimeSession]
    'initial-location-consumed': []
    'update:detail-open': [open: boolean]
}>()
const clone = <T,>(value: T): T => structuredClone(toRaw(value))
const blankForm = (): PlayerFormDefinition => ({ schema_version: 3, title: '脚本运行器', icon_asset_id: '', features: { recording: false }, pages: [] })
const normalizeTerminalActions = (form: PlayerFormDefinition): PlayerFormDefinition => {
    const normalized = clone(form)
    normalized.icon_asset_id = String(normalized.icon_asset_id || '')
    normalized.features = { recording: Boolean(normalized.features?.recording) }
    normalized.pages.flatMap((page) => page.controls).forEach((control) => {
        if (control.type !== 'button') control.terminal_actions = clone(control.terminal_actions || [])
        else delete control.terminal_actions
    })
    return normalized
}
const draft = reactive<PlayerFormDefinition>(normalizeTerminalActions(store.playerForm || blankForm()))
const recordingFeaturePublished = computed({
    get: () => Boolean(draft.features?.recording),
    set: (value: boolean) => {
        draft.features = { recording: value }
        markDirty()
    },
})
const selectedPageId = ref(draft.pages[0]?.page_id || '')
const selectedControlId = ref('')
const applicationSelected = ref(false)
const pageNameInput = ref<HTMLInputElement | null>(null)
const previewPageId = ref(selectedPageId.value)
const previewWidth = ref<'wide' | 'narrow'>('wide')
const previewValues = reactive<Record<string, unknown>>({})
const compactLayout = ref(false)
const inspectorOpen = ref(false)
const detailVisible = computed(() => props.detailOpen ?? (!compactLayout.value || inspectorOpen.value))
const detailAsOverlay = computed(() => props.detailOverlay ?? compactLayout.value)
const detailOverlayOpen = computed(() => detailVisible.value && detailAsOverlay.value)
const outlineOpen = ref(false)
const inspectorToggleButton = ref<InstanceType<typeof VNextIconButton> | null>(null)
const outlineToggleButton = ref<InstanceType<typeof VNextIconButton> | null>(null)
const dirty = ref(false)
const saving = ref(false)
const saveMessage = ref('')
const sourcePickerOpen = ref(false)
const sourceLoading = ref(false)
const sourceError = ref('')
const sourceQuery = ref('')
const selectedSourceId = ref('')
const bindingSources = ref<PlayerBindingSourceDefinition[]>([])
const replacingControl = ref(false)
const sourceSearchInput = ref<HTMLInputElement | null>(null)
const previewExecution = ref<RuntimeSession | null>(null)
const previewError = ref('')
const publishOpen = ref(false)
let previewPollToken = 0
let disposed = false
let compactMedia: MediaQueryList | null = null
let sourcePickerOrigin: HTMLElement | null = null

const icons: Record<string, unknown> = { text: markRaw(Type), number: markRaw(FormInput), toggle: markRaw(ToggleLeft), select: markRaw(ListFilter), 'slider-number': markRaw(FormInput), duration: markRaw(FormInput), time: markRaw(FormInput), color: markRaw(Square), coordinate: markRaw(SquareMousePointer), region: markRaw(SquareMousePointer), resource: markRaw(ImageIcon), file: markRaw(File), directory: markRaw(Folder), 'control-selector': markRaw(SquareMousePointer), 'gesture-path': markRaw(SquareMousePointer), list: markRaw(ListFilter), 'key-value': markRaw(ListFilter), expression: markRaw(FormInput), button: markRaw(SquareMousePointer) }
const selectedPage = computed(() => draft.pages.find((item) => item.page_id === selectedPageId.value) || null)
const selectedControl = computed(() => selectedPage.value?.controls.find((item) => item.control_id === selectedControlId.value) || null)
const previewPage = computed(() => draft.pages.find((item) => item.page_id === previewPageId.value) || draft.pages[0] || null)
const selectedBindingSource = computed(() => bindingSources.value.find((item) => item.source_id === selectedSourceId.value) || null)
const selectedControlSource = computed(() => selectedControl.value
    ? bindingSources.value.find((item) => stableBinding(item.binding) === stableBinding(selectedControl.value!.binding)) || null
    : null)
const selectedParameterActions = computed(() => selectedControl.value?.parameter_ui?.actions || [])
const selectedBooleanMapOptions = computed(() => selectedControl.value?.type === 'key-value' && selectedControl.value.source_type === 'map<string,bool>'
    ? selectedControl.value.options
    : [])
const stackedPlayerControlTypes = new Set<PlayerControlType>([
    'button',
    'coordinate',
    'region',
    'gesture-path',
    'json',
    'list',
    'key-value',
    'expression',
])
const playerControlUsesInlineLayout = (control: PlayerControlDefinition) =>
    !stackedPlayerControlTypes.has(control.type)
const assetById = computed(() => new Map(store.assets.map((asset) => [asset.asset_id, asset])))
const applicationIconOptions = computed(() => store.assets.filter((asset) =>
    asset.category === 'image' && ['.png', '.jpg', '.jpeg', '.bmp'].includes(asset.extension.toLocaleLowerCase()),
))
const applicationIconAsset = computed(() => assetById.value.get(String(draft.icon_asset_id || '')) || null)
const statementIdForSource = (source: PlayerBindingSourceDefinition) => source.binding.kind === 'statement_parameter' ? source.binding.statement_id : ''
const normalizedStatementId = (statementId: string) => statementId.replace(/^(statement|stmt)[_-]/i, '')
const shortStatementId = (statementId: string) => statementId ? `#${normalizedStatementId(statementId).slice(0, 8)}` : ''
const normalizedIdQuery = (query: string) => query.trim().replace(/^#/, '').toLocaleLowerCase('zh-CN')
const statementLabelForSource = (source: PlayerBindingSourceDefinition) => {
    const marker = source.path.findIndex((item) => item.id === 'statement_parameters')
    return marker >= 0 ? source.path[marker + 1]?.label || '' : ''
}
const parameterLabelForSource = (source: PlayerBindingSourceDefinition) => source.label.split(' · ').at(-1) || source.label
const sourceAsset = (source: PlayerBindingSourceDefinition): AssetDefinition | null => {
    const value = source.default
    if (!value || typeof value !== 'object' || Array.isArray(value)) return null
    const assetId = 'asset_id' in value && typeof value.asset_id === 'string' ? value.asset_id : ''
    return assetId ? assetById.value.get(assetId) || null : null
}
const sourceDisplayLabel = (source: PlayerBindingSourceDefinition) => {
    const asset = sourceAsset(source)
    const statementLabel = statementLabelForSource(source)
    return asset && statementLabel ? `${statementLabel} · ${asset.display_name}` : source.label
}
const sourceContextLabel = (source: PlayerBindingSourceDefinition) => {
    const parts = [sourceAsset(source) ? parameterLabelForSource(source) : sourceKindLabel(source.kind)]
    const statementId = statementIdForSource(source)
    if (statementId) parts.push(shortStatementId(statementId))
    return parts.join(' · ')
}
const sourceGroup = (source: PlayerBindingSourceDefinition) => {
    const labels = source.path.map((item) => item.label).filter(Boolean)
    return source.kind === 'statement_parameter' && labels.length > 1 ? `${labels[0]} · ${labels[1]}` : labels[0] || '其他'
}
const sourceSearchText = (source: PlayerBindingSourceDefinition) => {
    const statementId = statementIdForSource(source)
    return [
        source.path.map((item) => item.label).join(' '), source.label, sourceDisplayLabel(source),
        statementId, normalizedStatementId(statementId), shortStatementId(statementId), source.source_id,
    ].filter(Boolean).join(' ')
}
const filteredSourceGroups = computed(() => {
    const query = normalizedIdQuery(sourceQuery.value)
    const candidates = bindingSources.value.filter((source) => !query || sourceSearchText(source).toLocaleLowerCase('zh-CN').includes(query))
    return [...new Set(candidates.map(sourceGroup))].map((name) => ({ name, items: candidates.filter((item) => sourceGroup(item) === name) }))
})
const locatedStatement = computed(() => {
    const query = normalizedIdQuery(sourceQuery.value)
    if (!query) return null
    const matches = [...new Set(bindingSources.value.map(statementIdForSource).filter(Boolean))].filter((statementId) => {
        const normalized = normalizedStatementId(statementId).toLocaleLowerCase('zh-CN')
        return query === statementId.toLocaleLowerCase('zh-CN') || query === normalized || query === normalized.slice(0, 8)
    })
    if (matches.length !== 1) return null
    const statementId = matches[0]
    return { statementId, sourceCount: bindingSources.value.filter((source) => statementIdForSource(source) === statementId).length }
})
const previewIsActive = computed(() => ['queued', 'running', 'paused'].includes(previewExecution.value?.status || ''))
const previewStatus = computed(() => ({ queued: '等待运行', running: '运行中', paused: '已暂停', completed: '已完成', failed: '运行失败', cancelled: '已停止' } as Record<string, string>)[previewExecution.value?.status || ''] || '')

function uuid(prefix: string) { return `${prefix}_${crypto.randomUUID().replaceAll('-', '')}` }
function controlIcon(type: PlayerControlType) { return icons[type] || FormInput }
function controlTypeLabel(type: PlayerControlType) { return ({ text: '文本', number: '数值', toggle: '开关', select: '选项', 'slider-number': '数值滑块', duration: '持续时间', time: '时间', color: '颜色', coordinate: '坐标', region: '区域', resource: '资源', 'control-selector': '控件', 'gesture-path': '手势路径', file: '文件', directory: '目录', list: '列表', 'key-value': '键值', expression: '表达式', button: '操作按钮' } as Record<PlayerControlType, string>)[type] || '字段' }
function markDirty() { dirty.value = true; saveMessage.value = '' }
function selectApplication() { applicationSelected.value = true; selectedControlId.value = ''; outlineOpen.value = false; if (compactLayout.value) inspectorOpen.value = true }
function selectPage(pageId: string) { applicationSelected.value = false; selectedPageId.value = pageId; selectedControlId.value = ''; previewPageId.value = pageId; outlineOpen.value = false; if (compactLayout.value) inspectorOpen.value = true }
function selectControl(pageId: string, controlId: string) { applicationSelected.value = false; selectedPageId.value = pageId; selectedControlId.value = controlId; previewPageId.value = pageId; outlineOpen.value = false; if (compactLayout.value) inspectorOpen.value = true }
function openInspector() { if (props.detailOpen !== undefined) emit('update:detail-open', true); else inspectorOpen.value = true }
function closeInspector() { if (props.detailOpen !== undefined) emit('update:detail-open', false); else inspectorOpen.value = false; void nextTick(() => inspectorToggleButton.value?.focus()) }
function closeOutline() { outlineOpen.value = false; void nextTick(() => outlineToggleButton.value?.focus()) }
function addPage(focusName = true) { const page = { page_id: uuid('page'), title: `页面 ${draft.pages.length + 1}`, controls: [] }; draft.pages.push(page); selectPage(page.page_id); markDirty(); if (focusName) void nextTick(() => pageNameInput.value?.focus()) }
function removePage() { const index = draft.pages.findIndex((item) => item.page_id === selectedPageId.value); if (index < 0) return; draft.pages.splice(index, 1); const next = draft.pages[Math.min(index, draft.pages.length - 1)]; selectedPageId.value = next?.page_id || ''; previewPageId.value = selectedPageId.value; selectedControlId.value = ''; markDirty() }
function removeControl() { if (!selectedPage.value || !selectedControl.value) return; selectedPage.value.controls = selectedPage.value.controls.filter((item) => item.control_id !== selectedControl.value?.control_id); selectedControlId.value = ''; markDirty() }
function updateSelectedDefault(value: unknown) { if (!selectedControl.value) return; selectedControl.value.default = value; previewValues[selectedControl.value.control_id] = clone(value); markDirty() }
function fixedOptionMode(option: PlayerControlOption): 'editable' | 'on' | 'off' { return option.fixed_value === true ? 'on' : option.fixed_value === false ? 'off' : 'editable' }
function setFixedOptionMode(option: PlayerControlOption, mode: string) {
    const control = selectedControl.value
    if (!control || control.type !== 'key-value' || control.source_type !== 'map<string,bool>') return
    if (mode === 'editable') {
        delete option.fixed_value
        delete option.fixed_reason
    } else {
        option.fixed_value = mode === 'on'
        option.fixed_reason = option.fixed_value ? '此选项由开发者固定为必选' : '此选项由开发者固定为不可选'
        const current = control.default && typeof control.default === 'object' && !Array.isArray(control.default)
            ? clone(control.default as Record<string, unknown>)
            : {}
        current[String(option.value)] = option.fixed_value
        control.default = current
        previewValues[control.control_id] = clone(current)
    }
    markDirty()
}
function previewPlatform(control: PlayerControlDefinition): PlatformId { if (control.binding.kind === 'setting') { const targetId = control.binding.target_id; return store.targets.find((item) => item.target_id === targetId)?.type || 'windows' } return control.platforms?.[0] || 'windows' }
function sourceKindLabel(kind: PlayerBindingSourceDefinition['kind']) { return ({ project_variable: '项目变量', function_parameter: '函数参数', statement_parameter: '语句参数', function_action: '执行函数', setting: '运行设置' } as const)[kind] }
function stableBinding(binding: PlayerBinding) { return JSON.stringify(Object.fromEntries(Object.entries(binding).sort(([a], [b]) => a.localeCompare(b)))) }
function bindingSummary(control: PlayerControlDefinition) { const source = bindingSources.value.find((item) => stableBinding(item.binding) === stableBinding(control.binding)); return source ? sourceDisplayLabel(source) : sourceKindLabel(control.binding.kind) }
const terminalActionPlatforms: Record<string, PlatformId[]> = {
    'pick-point': ['windows', 'android_adb', 'android_local'],
    'pick-region': ['windows', 'android_adb', 'android_local'],
    'pick-color': ['windows', 'android_adb', 'android_local'],
    'capture-image': ['windows', 'android_adb', 'android_local'],
    'choose-resource': ['windows', 'android_adb', 'android_local'],
    'capture-control': ['windows', 'android_adb', 'android_local'],
    'capture-window': ['windows'],
    'capture-path': ['windows', 'android_adb', 'android_local'],
    'choose-file-read': ['windows', 'android_adb', 'android_local'],
    'choose-file-save': ['windows', 'android_adb', 'android_local'],
    'choose-directory': ['windows', 'android_adb', 'android_local'],
}
function terminalActionLabel(actionId: string) { return ({ 'pick-point': '拾取坐标', 'pick-region': '框选区域', 'pick-color': '从目标画面取色', 'capture-image': '截取图片', 'choose-resource': '选择图片', 'capture-control': '捕获控件', 'capture-window': '捕获目标窗口', 'capture-path': '绘制手势路径', 'choose-file-read': '选择读取文件', 'choose-file-save': '选择保存位置', 'choose-directory': '选择文件夹' } as Record<string, string>)[actionId] || actionId }
function platformLabel(platform: PlatformId) { return ({ windows: 'Windows', android_adb: 'Android（ADB）', android_local: 'Android 本机' } as Record<PlatformId, string>)[platform] }
function terminalPlatformOptions(action: ParameterUiAction) {
    const sourcePlatforms = selectedControlSource.value?.platforms || selectedControl.value?.platforms || []
    const controlPlatforms = selectedControl.value?.platforms?.length ? selectedControl.value.platforms : sourcePlatforms
    const declared = action.platforms || []
    return declared.filter((platform) => !sourcePlatforms.length || sourcePlatforms.includes(platform)).filter((platform) => !controlPlatforms.length || controlPlatforms.includes(platform)).map((platform) => {
        const available = Boolean(terminalActionPlatforms[action.id]?.includes(platform))
        return { platform, available, reason: available ? '' : '当前独立 Player 没有真实宿主适配器' }
    })
}
function terminalActionEnabled(actionId: string, platform: PlatformId) { return Boolean(selectedControl.value?.terminal_actions?.find((item) => item.action_id === actionId)?.platforms.includes(platform)) }
function recommendedTerminalActions(source: PlayerBindingSourceDefinition) {
    const sourcePlatforms = source.platforms || []
    return (source.parameter_ui?.actions || []).flatMap((action) => {
        const hostPlatforms = terminalActionPlatforms[action.id] || []
        const platforms = (action.platforms || []).filter((platform) =>
            hostPlatforms.includes(platform) && (!sourcePlatforms.length || sourcePlatforms.includes(platform)),
        )
        return platforms.length ? [{ action_id: action.id, platforms: [...new Set(platforms)].sort() }] : []
    }).sort((a, b) => a.action_id.localeCompare(b.action_id))
}
function toggleTerminalAction(actionId: string, platform: PlatformId, enabled: boolean) {
    const control = selectedControl.value
    if (!control || control.type === 'button') return
    const actions = control.terminal_actions || (control.terminal_actions = [])
    const existing = actions.find((item) => item.action_id === actionId)
    if (enabled) {
        if (existing && !existing.platforms.includes(platform)) existing.platforms.push(platform)
        else if (!existing) actions.push({ action_id: actionId, platforms: [platform] })
    } else if (existing) {
        existing.platforms = existing.platforms.filter((item) => item !== platform)
        if (!existing.platforms.length) control.terminal_actions = actions.filter((item) => item.action_id !== actionId)
    }
    control.terminal_actions?.forEach((item) => item.platforms.sort())
    control.terminal_actions?.sort((a, b) => a.action_id.localeCompare(b.action_id))
    markDirty()
}

async function loadBindingSources() { if (!store.workspace) return; sourceLoading.value = true; sourceError.value = ''; try { const result = await vnextApi.playerBindingSources(store.workspace); bindingSources.value = result.sources; if (!result.available) sourceError.value = result.unavailable_reason } catch (error) { sourceError.value = error instanceof Error ? error.message : '无法读取可发布内容' } finally { sourceLoading.value = false } }
async function openSourcePicker(initialQuery = '') { sourcePickerOrigin = document.activeElement instanceof HTMLElement ? document.activeElement : null; replacingControl.value = Boolean(selectedControl.value); sourcePickerOpen.value = true; sourceQuery.value = initialQuery; selectedSourceId.value = ''; if (!bindingSources.value.length) await loadBindingSources(); await nextTick(); sourceSearchInput.value?.focus() }
function closeSourcePicker() { sourcePickerOpen.value = false; selectedSourceId.value = ''; void nextTick(() => sourcePickerOrigin?.focus()) }
function controlFromSource(source: PlayerBindingSourceDefinition, existing?: PlayerControlDefinition): PlayerControlDefinition {
    const isButton = source.recommended_control === 'button'
    const fallbackControl: ParameterControlType = isButton
        ? 'expression'
        : source.recommended_control as ParameterControlType
    const fallbackUi: ParameterUiContract = { control: fallbackControl, player_supported: true }
    const options = clone(source.options || [])
    if (!options.length && source.value_type === 'map<string,bool>' && source.default && typeof source.default === 'object' && !Array.isArray(source.default)) {
        Object.keys(source.default as Record<string, unknown>).forEach((key) => options.push({ label: key, value: key }))
    }
    const base: PlayerControlDefinition = {
        control_id: existing?.control_id || uuid('control'),
        type: source.recommended_control,
        label: existing?.label || sourceDisplayLabel(source),
        // Keep author-facing guidance from the binding catalog. Complex
        // runtime values (for example a captured window binding) otherwise
        // arrive in Player as an unexplained empty field even though the
        // shared parameter contract already describes the intended action.
        help: existing?.help || source.parameter_ui?.help || '',
        options,
        required: isButton ? false : Boolean(source.required || existing?.required),
        binding: clone(source.binding),
        layout: clone(existing?.layout || { span: 12 }),
        parameter_ui: clone(source.parameter_ui || fallbackUi),
        constraints: clone(source.constraints || {}),
        platforms: clone(source.platforms || []),
    }
    if (!isButton) {
        base.source_type = source.value_type
        base.type_fingerprint = source.type_fingerprint
        // A required runtime reference legitimately has no value until the
        // terminal user grants it.  Omitting default preserves that state;
        // serialising null would violate the strong FileReference type.
        if (existing && Object.hasOwn(existing, 'default')) base.default = clone(existing.default)
        else if (Object.hasOwn(source, 'default')) base.default = clone(source.default)
        const sameBinding = existing && stableBinding(existing.binding) === stableBinding(source.binding)
        base.terminal_actions = sameBinding
            ? clone(existing.terminal_actions || [])
            : recommendedTerminalActions(source)
    }
    return base
}
function applyBindingSource(source = selectedBindingSource.value) { if (!source) return; if (!selectedPage.value) addPage(false); if (!selectedPage.value) return; const existing = selectedControl.value; const next = controlFromSource(source, existing || undefined); if (existing) { const index = selectedPage.value.controls.findIndex((item) => item.control_id === existing.control_id); selectedPage.value.controls.splice(index, 1, next) } else selectedPage.value.controls.push(next); selectedControlId.value = next.control_id; previewValues[next.control_id] = clone(next.default); markDirty(); closeSourcePicker() }
function adoptForm(form: PlayerFormDefinition) { Object.assign(draft, normalizeTerminalActions(form)); applicationSelected.value = false; selectedPageId.value = draft.pages[0]?.page_id || ''; selectedControlId.value = ''; previewPageId.value = selectedPageId.value; Object.keys(previewValues).forEach((key) => delete previewValues[key]); draft.pages.flatMap((page) => page.controls).forEach((control) => { if (control.type !== 'button') previewValues[control.control_id] = clone(control.default) }); dirty.value = false }
function resetDraft() { adoptForm(store.playerForm) }
async function save() { saving.value = true; saveMessage.value = ''; try { const saved = await store.savePlayerForm(clone(draft)); if (saved) adoptForm(saved); saveMessage.value = '已保存' } catch (error) { saveMessage.value = error instanceof Error ? error.message : '保存失败' } finally { saving.value = false } }
function previewOverrides(): Record<string, unknown> { const result: Record<string, unknown> = {}; for (const control of draft.pages.flatMap((page) => page.controls)) { if (control.type === 'button') continue; const value = previewValues[control.control_id]; if (JSON.stringify(value) !== JSON.stringify(control.default)) result[control.control_id] = clone(value) } return result }
async function followPreview(initial: RuntimeSession) { const token = ++previewPollToken; previewExecution.value = initial; emit('runtime-session', initial); while (!disposed && token === previewPollToken && previewIsActive.value) { await new Promise((resolve) => setTimeout(resolve, 250)); if (disposed || token !== previewPollToken || !previewExecution.value) return; const next = await vnextApi.runStatus(previewExecution.value.execution_id, previewExecution.value.event_cursor || previewExecution.value.events.at(-1)?.sequence || 0); previewExecution.value = mergeRuntimeSession(previewExecution.value, next); emit('runtime-session', previewExecution.value) } }
async function startPreview(actionControlId = '') { if (!store.workspace || dirty.value || saving.value || previewIsActive.value) return; previewError.value = ''; try { await followPreview(await vnextApi.playerPreviewRun(store.workspace, { target_id: store.defaultTargetId, player_values: previewOverrides(), action_control_id: actionControlId })) } catch (error) { previewError.value = error instanceof Error ? error.message : 'Player 预览启动失败' } }
async function stopPreview() { if (!previewExecution.value) return; const executionId = previewExecution.value.execution_id; previewPollToken += 1; try { previewExecution.value = await vnextApi.cancelRun(executionId); emit('runtime-session', previewExecution.value) } catch (error) { previewError.value = error instanceof Error ? error.message : '停止预览失败' } }
function syncCompactLayout() { compactLayout.value = Boolean(compactMedia?.matches); if (!compactLayout.value) { inspectorOpen.value = false; outlineOpen.value = false } }
onMounted(async () => {
    compactMedia = window.matchMedia?.('(max-width: 899px)') || null
    syncCompactLayout()
    compactMedia?.addEventListener?.('change', syncCompactLayout)
    if (store.workspace) {
        await Promise.allSettled([store.refreshPlayerForm(), loadBindingSources()])
        adoptForm(store.playerForm)
    }
    if (props.initialStatementId) {
        await openSourcePicker(props.initialStatementId)
        emit('initial-location-consumed')
    }
})
onBeforeUnmount(() => { disposed = true; previewPollToken += 1; compactMedia?.removeEventListener?.('change', syncCompactLayout) })
</script>

<style scoped>
.player-workspace{position:relative;height:100%;min-width:0;min-height:0;display:grid;grid-template-columns:250px minmax(360px,1fr) 300px;overflow:hidden;background:var(--app-bg-base);color:var(--app-text-regular)}.player-outline,.player-inspector{min-width:0;min-height:0;background:var(--app-bg-panel);border-right:1px solid var(--app-border-subtle);display:flex;flex-direction:column}.player-inspector{border-right:0;border-left:1px solid var(--app-border-subtle)}.player-outline>header,.player-inspector>header,.player-preview-area>header{height:var(--app-height-pane-header);display:flex;align-items:center;justify-content:space-between;padding:0 var(--app-pane-inline-padding);border-bottom:1px solid var(--app-border-subtle)}.player-outline>header>div:first-child,.player-preview-area>header>div:first-child{display:flex;flex-direction:column;gap:2px}.player-outline header span,.player-preview-area header span{font-size: var(--app-font-caption);color:var(--app-text-muted)}.header-actions,.preview-actions,.device-switch{display:flex;gap:4px}.header-actions button,.preview-actions button,.player-inspector>header button{width:28px;height: var(--app-control-compact);border:0;border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-muted);display:grid;place-items:center}.header-actions button:hover,.preview-actions button:hover{background:var(--app-bg-hover);color:var(--app-text-primary)}.outline-close,.outline-toggle{display:none!important}.player-panel-scrim{position:absolute;z-index:19;inset:0;padding:0;border:0;background:rgba(7,7,6,.62);cursor:default}
.player-workspace.detail-panel-collapsed{grid-template-columns:250px minmax(0,1fr)}
.player-inspector.is-compact{position:absolute;right:0;top:0;bottom:0;width:min(340px,calc(100% - 48px));z-index:20;box-shadow:-16px 0 40px rgba(0,0,0,.28)}
.preview-actions{align-items:center}.preview-actions .preview-error{max-width:220px;color:var(--app-color-danger);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.preview-actions .preview-status{color:var(--app-text-regular)}
.outline-content{flex:1;min-height:0;overflow:auto;padding:8px}.page-row,.control-row,.empty-create{width:100%;height: var(--app-control-default);border:0;border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-regular);display:grid;grid-template-columns:16px minmax(0,1fr) auto;align-items:center;gap:7px;padding:0 8px;text-align:left}.control-row{padding-left:26px}.page-row span,.control-row span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.page-row small{color:var(--app-text-muted)}.page-row:hover,.control-row:hover,.page-row.active,.control-row.active{background:var(--app-bg-hover);color:var(--app-text-primary)}.page-row.active,.control-row.active{box-shadow:inset 2px 0 var(--app-color-primary)}.empty-create{grid-template-columns:16px 1fr;color:var(--app-text-muted)}.player-outline>footer{display:flex;gap:8px;padding:10px;border-top:1px solid var(--app-border-subtle)}button.primary,button.secondary{height: var(--app-control-default);border-radius: var(--app-radius-md);padding:0 11px}.primary{border:1px solid var(--app-color-primary);background:var(--app-color-primary);color:white}.secondary{border:1px solid var(--app-border-strong);background:transparent;color:var(--app-text-regular)}button:disabled{opacity:.45;cursor:not-allowed}.player-outline>footer button{flex:1}
.player-preview-area{min-width:0;min-height:0;display:grid;grid-template-rows:var(--app-height-workspace-header) minmax(0,1fr)}.device-switch{padding:2px;border:1px solid var(--app-border-subtle);border-radius: var(--app-radius-md)}.device-switch button.active{background:var(--app-bg-selected);color:var(--app-text-primary)}.preview-canvas{min-height:0;overflow:auto;display:grid;place-items:start center;padding:28px;background:var(--app-bg-base);overscroll-behavior:contain}.player-card{width:min(100%,720px);min-height:360px;border:1px solid var(--app-border-subtle);border-radius: var(--app-radius-lg);background:var(--app-bg-panel);box-shadow:0 14px 36px rgba(0,0,0,.16);overflow:hidden}.player-card.narrow{width:min(100%,390px)}.player-card>header{height:48px;display:flex;align-items:center;justify-content:space-between;padding:0 16px;border-bottom:1px solid var(--app-border-subtle)}.player-card>header div{display:flex;align-items:center;gap:8px}.player-card>header span{font-size: var(--app-font-caption);color:var(--app-text-muted)}
.preview-form{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px;padding:20px}.preview-control{grid-column:span 12;min-width:0;display:flex;flex-direction:column;gap:7px;padding:9px;border:1px solid transparent;border-radius: var(--app-radius-md)}.preview-control.is-inline-field{display:grid;grid-template-columns:minmax(88px,116px) minmax(0,1fr);align-items:center;column-gap:10px;row-gap:var(--app-form-label-control-gap)}.preview-control.is-inline-field>small{grid-column:2}.preview-control.span-6{grid-column:span 6}.preview-control.span-4{grid-column:span 4}.player-card.narrow .preview-control{grid-column:span 12}.player-card.narrow .preview-control.is-inline-field{grid-template-columns:minmax(0,1fr);align-items:stretch;row-gap:8px}.player-card.narrow .preview-control.is-inline-field>small{grid-column:1}.player-card.narrow .preview-control :deep(input:not([type='checkbox'])),.player-card.narrow .preview-control :deep(select),.player-card.narrow .preview-control :deep(textarea),.player-card.narrow .preview-control :deep(button),.player-card.narrow .action-button{min-height:var(--app-control-android-touch)}.preview-control.selected{border-color:color-mix(in srgb,var(--app-color-primary) 52%,var(--app-border-subtle));background:var(--app-bg-hover)}.preview-control>span{font-size: var(--app-font-compact);color:var(--app-text-primary)}.preview-control b{color:var(--app-color-danger);margin-left:2px}.preview-control small{font-size: var(--app-font-caption);color:var(--app-text-muted)}.action-button{height: var(--app-control-default);border:0;border-radius: var(--app-radius-md);background:var(--app-color-primary);color:white;display:flex;align-items:center;justify-content:center;gap:6px}.preview-empty{grid-column:1/-1;min-height:210px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:7px;color:var(--app-text-muted)}.preview-empty button{margin-top:6px;border:1px solid var(--app-border-strong);border-radius: var(--app-radius-md);background:transparent;color:var(--app-text-regular);padding:7px 10px}
.properties{min-height:0;overflow:auto;padding:12px;container-type:inline-size}.property-title{display:flex;gap:9px;align-items:center;padding:6px 4px 14px}.property-title>div{display:flex;min-width:0;flex-direction:column;gap:2px}.property-title span{font-size: var(--app-font-caption);color:var(--app-text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.properties section{padding:13px 3px;border-top:1px solid var(--app-border-subtle)}.properties h3{margin:0 0 11px;font-size: var(--app-font-caption);color:var(--app-text-muted)}.properties label{min-width:0;margin:0 0 10px;font-size: var(--app-font-caption);color:var(--app-text-muted)}.properties .property-field{display:grid;grid-template-columns:minmax(58px,72px) minmax(0,1fr);align-items:center;gap:8px;color:var(--app-text-regular)}.properties input,.properties select{width:100%;height: var(--app-control-default);border:1px solid var(--app-border-strong);border-radius: var(--app-radius-sm);background:var(--app-bg-base);color:var(--app-text-primary);padding:0 9px}.properties .check-row{min-height:var(--app-control-default);display:flex;flex-direction:row;align-items:center;gap:7px;color:var(--app-text-regular)}.check-row input{width:auto;height:auto}.properties p{margin:0;color:var(--app-text-muted);font-size: var(--app-font-compact);line-height:1.55}.change-binding{margin-top:9px}.delete-control{width:100%;height:var(--app-control-default);border:1px solid color-mix(in srgb,var(--app-color-danger) 45%,var(--app-border-subtle));border-radius:var(--app-radius-md);background:transparent;color:var(--app-color-danger);display:flex;align-items:center;justify-content:center;gap:6px}.player-empty{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;color:var(--app-text-muted);text-align:center}.player-empty span{font-size: var(--app-font-compact)}
.fixed-option-section>p{margin-bottom:10px}.properties .fixed-option-row{display:grid;grid-template-columns:minmax(0,1fr) 104px;align-items:center;gap:8px}.fixed-option-row>span{overflow:hidden;color:var(--app-text-regular);text-overflow:ellipsis;white-space:nowrap}
.terminal-action-section details>summary{display:flex;align-items:center;justify-content:space-between;gap:8px;cursor:pointer;color:var(--app-text-primary);font-size: var(--app-font-compact);list-style-position:inside}.terminal-action-section details>summary small{color:var(--app-text-muted);font-size: var(--app-font-caption)}.terminal-action-section details>p{margin:10px 0}.terminal-action-list{display:flex;flex-direction:column;gap:10px}.terminal-action-list fieldset{margin:0;padding:9px;border:1px solid var(--app-border-subtle);border-radius: var(--app-radius-md)}.terminal-action-list legend{padding:0 5px;color:var(--app-text-regular);font-size: var(--app-font-caption)}.terminal-action-list .check-row{display:grid;grid-template-columns:14px minmax(0,1fr);gap:6px;margin:5px 0;color:var(--app-text-regular)}.terminal-action-list .check-row small{grid-column:2;color:var(--app-text-muted);line-height:1.35}
.picker-backdrop{position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.48);display:grid;place-items:center;padding:24px}.source-picker{width:min(680px,100%);max-height:min(720px,90vh);display:grid;grid-template-rows:auto auto minmax(0,1fr);border:1px solid var(--app-border-strong);border-radius: var(--app-radius-lg);background:var(--app-bg-panel);box-shadow:0 24px 80px rgba(0,0,0,.42);overflow:hidden}.source-picker>header{display:flex;justify-content:space-between;gap:18px;padding:17px 18px;border-bottom:1px solid var(--app-border-subtle)}.source-picker h2{margin:0;font-size: var(--app-font-page-title);color:var(--app-text-primary)}.source-picker header p{margin:5px 0 0;font-size: var(--app-font-compact);color:var(--app-text-muted)}.source-picker header button{width:28px;height: var(--app-control-compact);border:0;border-radius: var(--app-radius-sm);background:transparent;color:var(--app-text-muted)}.picker-filter{border-bottom:1px solid var(--app-border-subtle)}.picker-search{height:46px;display:flex;align-items:center;gap:8px;padding:0 16px}.picker-search input{flex:1;border:0;outline:0;background:transparent;color:var(--app-text-primary)}.located-statement{margin:0;padding:0 16px 10px;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.source-groups{overflow:auto;padding:10px}.source-groups h3{margin:10px 8px 5px;font-size: var(--app-font-caption);color:var(--app-text-muted)}.source-row{width:100%;min-height:45px;border:0;border-radius: var(--app-radius-md);background:transparent;color:var(--app-text-regular);display:grid;grid-template-columns:18px minmax(0,1fr) auto;align-items:center;gap:9px;padding:6px 8px;text-align:left}.source-row:hover,.source-row:focus-visible,.source-row[aria-selected=true]{background:var(--app-bg-hover);outline:0}.source-row>span{display:flex;min-width:0;flex-direction:column;gap:2px}.source-row strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.source-groups small{font-size: var(--app-font-caption);color:var(--app-text-muted)}.insert-source{justify-self:end}.picker-state{min-height:220px;display:flex;align-items:center;justify-content:center;gap:8px;color:var(--app-text-muted)}.picker-state.error{color:var(--app-color-danger)}.picker-state button{border:1px solid var(--app-border-strong);border-radius: var(--app-radius-sm);background:transparent;color:inherit;padding:5px 8px}
@media(max-width:899px){.player-workspace{grid-template-columns:220px minmax(0,1fr)}.player-inspector.is-compact{position:absolute;right:0;top:0;bottom:0;width:min(340px,calc(100% - 48px));z-index:20;box-shadow:-16px 0 40px rgba(0,0,0,.28)}.preview-canvas{padding:18px}}@media(max-width:640px){.player-workspace{grid-template-columns:1fr}.player-outline{display:none}.player-outline.is-open{position:absolute;z-index:20;inset:0 auto 0 0;width:min(300px,calc(100% - 48px));display:flex;box-shadow:16px 0 40px rgba(0,0,0,.28)}.outline-close,.outline-toggle{display:grid!important}.preview-canvas{padding:10px}.picker-backdrop{padding:10px}}
@media(min-width:701px){.player-workspace{grid-template-columns:var(--workspace-sidebar-width,260px) minmax(360px,1fr) 300px}}
@media(min-width:701px){.player-workspace.detail-panel-collapsed{grid-template-columns:var(--workspace-sidebar-width,260px) minmax(0,1fr)}}
@media(pointer:coarse){.preview-control{grid-column:span 12!important}.preview-control.is-inline-field{grid-template-columns:minmax(0,1fr);align-items:stretch;row-gap:8px}.preview-control.is-inline-field>small{grid-column:1}.preview-control :deep(input:not([type='checkbox'])),.preview-control :deep(select),.preview-control :deep(button),.action-button{min-height:var(--app-control-android-touch)}}
@media(min-width:701px) and (max-width:899px){.player-workspace{grid-template-columns:var(--workspace-sidebar-width,260px) minmax(0,1fr)}}
.page-row,
.control-row,
.empty-create { height: var(--app-list-row-compact); }
.player-card > header { height: var(--app-height-pane-header); }
.properties section { padding-block: var(--app-form-section-padding); }
.properties h3 { margin-bottom: var(--app-form-heading-field-gap); color: var(--app-text-primary); font-size: var(--app-font-sm); }
.properties label { gap: var(--app-form-label-control-gap); margin-bottom: var(--app-form-field-gap); color: var(--app-text-regular); font-size: var(--app-font-compact); }
.properties section > label:last-child { margin-bottom: 0; }
.picker-search { height: var(--app-height-pane-header); }
.source-row { min-height: var(--app-list-row-rich); padding-block: 5px; }
.terminal-action-section details > summary { min-height: var(--app-form-disclosure-height); font-size: var(--app-font-sm); }
@container(max-width:240px){.properties .property-field{grid-template-columns:minmax(0,1fr);align-items:stretch;gap:var(--app-form-label-control-gap)}}
</style>
