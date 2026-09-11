<template>
    <div class="ide-v6-shell">
        <a class="skip-to-workspace" href="#easycode-main-stage">跳到主要工作区</a>
        <header class="titlebar">
            <button type="button" class="brand" :aria-label="activityRailMode === 'labeled' ? '切换为紧凑导航' : '切换为文字导航'" :title="activityRailMode === 'labeled' ? '切换为紧凑导航' : '切换为文字导航'" @click="toggleActivityRailMode">
                <Braces :size="17" aria-hidden="true" /><strong>EasyCode</strong>
            </button>
            <VNextMenuBar
                :shortcuts="ideShortcuts"
                :enabled="isIdeCommandEnabled"
                :disabled-reason="ideCommandDisabledReason"
                @command="executeIdeCommand"
            />
            <span class="titlebar-spacer" aria-hidden="true"></span>
            <div class="title-actions">
                <button ref="commandPaletteButton" type="button" class="toolbar-button command-search-button" :title="`搜索并运行命令（${ideShortcuts['help.command_palette'] || 'Ctrl+Shift+P'}）`" @click="openCommandPalette">
                    <Search :size="14" aria-hidden="true" /><span class="action-label">搜索命令</span>
                </button>
                <button v-if="activeView === 'program'" type="button" class="toolbar-button" aria-label="检查项目" title="检查项目" :disabled="!programStore.document || programStore.busy" @click="checkProgram">
                    <ScanSearch :size="15" aria-hidden="true" /><span class="action-label">检查</span>
                </button>
                <button
                    v-if="activeView === 'program'"
                    type="button"
                    class="toolbar-button"
                    :class="{ 'is-recording': Boolean(operationRecording) }"
                    :aria-label="operationRecording ? '停止并审阅操作录制' : '录制操作骨架'"
                    :title="operationRecording ? '停止并审阅操作录制' : '录制操作骨架'"
                    :disabled="!programStore.document || programStore.busy || !activeTarget"
                    @click="toggleOperationRecording"
                >
                    <Square v-if="operationRecording" :size="13" aria-hidden="true" />
                    <Circle v-else :size="14" aria-hidden="true" />
                    <span class="action-label">{{ operationRecording ? '停止录制' : '录制' }}</span>
                </button>
                <button
                    v-if="activeView === 'program' && !runIsActive"
                    type="button"
                    class="toolbar-button run-button"
                    :title="`运行（${ideShortcuts['run.start_or_resume'] || 'F5'}）`"
                    :disabled="!programStore.document || programStore.busy"
                    @click="runProgram"
                >
                    <Play :size="15" aria-hidden="true" /><span class="action-label">运行</span>
                </button>
                <template v-else-if="activeView === 'program'">
                    <button v-if="runtimeSession?.status === 'paused'" type="button" class="toolbar-button" :title="`继续（${ideShortcuts['run.start_or_resume'] || 'F5'}）`" @click="resumeProgram">
                        <Play :size="14" aria-hidden="true" /><span class="action-label">继续</span>
                    </button>
                    <button v-if="runtimeSession?.status === 'paused'" type="button" class="toolbar-button" :title="`单步（${ideShortcuts['run.step'] || 'F10'}）`" @click="stepProgram">
                        <StepForward :size="14" aria-hidden="true" /><span class="action-label">单步</span>
                    </button>
                    <button v-else type="button" class="toolbar-button" :disabled="runtimeSession?.status === 'queued'" @click="pauseProgram">
                        <Pause :size="14" aria-hidden="true" /><span class="action-label">暂停</span>
                    </button>
                    <button type="button" class="toolbar-button stop-button" @click="stopProgram">
                        <Square :size="13" aria-hidden="true" /><span class="action-label">停止</span>
                    </button>
                </template>
            </div>
        </header>

        <div class="workbench">
            <VNextActivityRail :mode="activityRailMode" :items="activityRailItems" @activate="activateActivityItem" />

            <main
                id="easycode-main-stage"
                class="main-stage"
                tabindex="-1"
                :class="{ 'sidebar-collapsed': !libraryDrawerOpen, 'sidebar-overlay-open': libraryDrawerOpen && narrowWorkbench }"
                :style="{ '--workspace-sidebar-width': `${panelSizes.sidebar}px` }"
            >
                <button
                    v-if="libraryDrawerOpen && narrowWorkbench"
                    type="button"
                    class="workspace-sidebar-scrim"
                    aria-label="关闭左侧栏"
                    @click="closeLibraryDrawer"
                ></button>
                <div
                    v-if="activeView === 'program'"
                    class="program-workspace"
                    :style="{ '--program-library-width': `${panelSizes.sidebar}px` }"
                >
                    <div
                        ref="libraryDrawerElement"
                        class="function-library-shell"
                        :class="{ 'narrow-drawer-open': libraryDrawerOpen && narrowWorkbench }"
                        :role="libraryDrawerOpen && narrowWorkbench ? 'dialog' : undefined"
                        :aria-modal="libraryDrawerOpen && narrowWorkbench ? 'true' : undefined"
                        :aria-label="libraryDrawerOpen && narrowWorkbench ? '函数库' : undefined"
                        :tabindex="libraryDrawerOpen && narrowWorkbench ? -1 : undefined"
                        @keydown="handleLibraryDrawerKeydown"
                    >
                        <ProgramFunctionLibrary
                            ref="functionLibrary"
                            :official-functions="officialFunctions"
                            :project-functions="projectFunctions"
                            :extension-functions="extensionFunctions"
                            :selected="librarySelection"
                            :busy="programStore.busy"
                            @select="librarySelection = $event"
                            @insert="insertLibraryFunction"
                            @open-project="openProgram"
                            @create-project="openCreateProgram"
                            @rename-project="openRenameProgram"
                            @delete-project="openDeleteProgram"
                        />
                        <button
                            v-if="libraryDrawerOpen && narrowWorkbench"
                            ref="libraryDrawerClose"
                            type="button"
                            class="function-library-drawer-close icon-button"
                            aria-label="关闭函数库"
                            title="关闭函数库"
                            @click="closeLibraryDrawer"
                        >
                            <PanelLeftClose :size="15" aria-hidden="true" />
                        </button>
                    </div>

                    <VNextPaneResizer
                        v-if="libraryDrawerOpen"
                        v-model="panelSizes.sidebar"
                        class="program-sidebar-resizer"
                        orientation="vertical"
                        :min="240"
                        :max="460"
                        :default-value="260"
                        label="调整函数库宽度"
                        @commit="scheduleViewStateSave"
                    />

                    <section
                        class="editor-pane"
                        aria-label="项目函数编辑器"
                        :aria-hidden="libraryDrawerOpen && narrowWorkbench ? 'true' : undefined"
                        :inert="libraryDrawerOpen && narrowWorkbench ? true : undefined"
                    >
                        <ProgramEditorSurface
                            v-if="programStore.document"
                            :document="programStore.document"
                            :function-contracts="programStore.functionContracts"
                            :project-function-ids="programStore.programs.map((item) => item.function_id)"
                            :selected-statement-ids="programStore.selectedStatementIds"
                            :collapsed-statement-ids="programStore.collapsedStatementIds"
                            :insertion-target="programStore.insertionTarget"
                            :pending-cut-statement-ids="programStore.pendingCutStatementIds"
                            :can-paste="programStore.canPasteStatements"
                            :statement-states="statementStates"
                            :assets="workspaceStore.assets"
                            :load-asset-preview="workspaceStore.assetPreviewUrl"
                            :diagnostics-by-value-id="programStore.diagnosticsByValueId"
                            :diagnostics="programStore.effectiveDiagnostics"
                            :target-options="targetOptions"
                            :available-values="projectVariableStore.availableValues"
                            :platform="selectedStatementPlatform"
                            :target-context-label="selectedStatementTargetLabel"
                            :target-context-detail="selectedStatementTargetDetail"
                            :workspace="workspaceStore.workspace"
                            :target-id="selectedStatementTarget?.target_id || ''"
                            :inspector-width="panelSizes.inspector"
                            :inspector-open="programInspectorOpen"
                            :show-inspector-toggle="false"
                            :busy="programStore.busy || debugSettingsBusy || Boolean(pendingCapture)"
                            :quick-insert-candidates="quickInsertCandidates"
                            :recent-quick-insert-keys="recentQuickInsertKeys"
                            :insert-quick-function="insertQuickFunction"
                            :resolve-value-catalog="resolveInlineValueCatalog"
                            @update:selected-statement-ids="programStore.setSelectedStatementIds"
                            @update:collapsed-statement-ids="programStore.setCollapsedStatementIds"
                            @update:insertion-target="programStore.setInsertionTarget"
                            @command="applyProgramCommand"
                            @capture="handleCaptureRequest"
                            @open-value-editor="handleValueEditorRequest"
                            @locate-player="locateStatementInPlayer"
                            @request-function-library="focusFunctionLibrary"
                            @toggle-breakpoint="toggleBreakpoint"
                            @extract-statements="openExtractStatements"
                            @update:inspector-width="panelSizes.inspector = $event"
                            @update:inspector-open="setProgramInspectorOpen"
                            @commit-inspector-width="scheduleViewStateSave"
                        >
                            <template #header>
                                <VNextPaneHeader class="editor-header" role="workspace" :title="activeProgramName || '未选择函数'" :meta="`${statementCount} 条语句`">
                                    <template #actions><div v-if="findOpen" class="statement-find" role="search">
                                        <Search :size="13" aria-hidden="true" />
                                        <input
                                            ref="findInput"
                                            v-model="findQuery"
                                            aria-label="查找当前函数的语句"
                                            placeholder="查找语句、备注或 ID"
                                            @keydown.enter.prevent="jumpFind($event.shiftKey ? -1 : 1)"
                                            @keydown.esc="closeFind"
                                        />
                                        <span>{{ findStatus }}</span>
                                        <VNextIconButton label="上一个匹配" :disabled="!findMatches.length" @click="jumpFind(-1)"><ChevronUp /></VNextIconButton>
                                        <VNextIconButton label="下一个匹配" :disabled="!findMatches.length" @click="jumpFind(1)"><ChevronDown /></VNextIconButton>
                                        <VNextIconButton label="关闭查找" @click="closeFind"><X /></VNextIconButton>
                                    </div>
                                    <div v-else class="editor-header-actions">
                                        <VNextIconButton class="icon-button" label="设置函数参数与返回值" :disabled="programStore.busy || programStore.readOnly || !activeProgram" @click="openProgramSignature"><SlidersHorizontal aria-hidden="true" /></VNextIconButton>
                                        <VNextIconButton class="icon-button" label="查找当前函数" :title="`查找当前函数（${ideShortcuts['edit.find'] || 'Ctrl+F'}）`" @click="openFind"><Search aria-hidden="true" /></VNextIconButton>
                                    </div></template>
                                </VNextPaneHeader>
                            </template>
                        </ProgramEditorSurface>
                        <div v-else class="editor-empty">
                            <Braces :size="28" aria-hidden="true" />
                            <strong>还没有可编辑的项目函数</strong>
                            <p>新建函数后，从左侧目录插入已经验证可运行的能力。</p>
                            <button type="button" @click="openCreateProgram">新建项目函数</button>
                        </div>
                    </section>
                </div>

                <VNextAsyncWorkspaceHost
                    v-else-if="activeView === 'resources'"
                    label="资源"
                    :loader="workspaceLoaders.resources"
                    class="resource-workspace"
                    :selection-mode="Boolean(pendingResourceSelection)"
                    :selection-label="pendingResourceSelection ? `应用到“${pendingResourceSelection.parameter_display_name}”` : '使用此图片'"
                    :selection-busy="resourceSelectionBusy"
                    :capture-busy="resourceCaptureBusy"
                    :initial-category="resourceSelectionCategory"
                    :detail-open="workspaceDetailOpen.resources"
                    :detail-overlay="narrowWorkbench"
                    @update:detail-open="workspaceDetailOpen.resources = $event"
                    @insert-reference="applySelectedAsset"
                    @cancel-selection="cancelPendingCapture"
                    @open-reference="openAssetReference"
                    @capture-resource="startResourceCapture"
                />
                <VNextAsyncWorkspaceHost
                    v-else-if="activeView === 'variables'"
                    label="项目变量"
                    :loader="workspaceLoaders.variables"
                    class="variable-workspace"
                    :assets="workspaceStore.assets"
                    :read-only="Boolean(workspaceStore.workspace?.read_only)"
                    @open-reference="openProjectVariableReference"
                />
                <VNextAsyncWorkspaceHost
                    v-else-if="activeView === 'targets'"
                    label="运行目标"
                    :loader="workspaceLoaders.targets"
                    class="target-workspace-view"
                    :read-only="Boolean(workspaceStore.workspace?.read_only)"
                    :ensure-capture-session="ensureCaptureSessionConnected"
                    @open-reference="openTargetReference"
                />
                <VNextAsyncWorkspaceHost
                    v-else-if="activeView === 'replay'"
                    label="运行记录"
                    :loader="workspaceLoaders.replay"
                    class="replay-workspace-view"
                    :detail-open="workspaceDetailOpen.replay"
                    :detail-overlay="narrowWorkbench"
                    @update:detail-open="workspaceDetailOpen.replay = $event"
                    @open-history-frame="openReplayCapture"
                />
                <VNextAsyncWorkspaceHost
                    v-else-if="activeView === 'extensions'"
                    label="扩展"
                    :loader="workspaceLoaders.extensions"
                    class="extension-workspace-view"
                    :detail-open="workspaceDetailOpen.extensions"
                    :detail-overlay="narrowWorkbench"
                    @update:detail-open="workspaceDetailOpen.extensions = $event"
                />
                <VNextAsyncWorkspaceHost
                    v-else-if="activeView === 'schedules'"
                    label="计划与实例"
                    :loader="workspaceLoaders.schedules"
                    class="schedule-workspace-view"
                    :detail-open="workspaceDetailOpen.schedules"
                    :detail-overlay="narrowWorkbench"
                    @update:detail-open="workspaceDetailOpen.schedules = $event"
                />
                <VNextAsyncWorkspaceHost
                    v-else-if="activeView === 'player'"
                    label="Player 界面"
                    :loader="workspaceLoaders.player"
                    class="player-workspace-view"
                    :initial-statement-id="pendingPlayerStatementId"
                    :detail-open="workspaceDetailOpen.player"
                    :detail-overlay="narrowWorkbench"
                    @update:detail-open="workspaceDetailOpen.player = $event"
                    @initial-location-consumed="pendingPlayerStatementId = ''"
                    @runtime-session="acceptPlayerPreviewSession"
                />
                <VNextPaneResizer
                    v-if="activeView !== 'program' && libraryDrawerOpen"
                    v-model="panelSizes.sidebar"
                    class="workspace-sidebar-resizer"
                    orientation="vertical"
                    :min="200"
                    :max="460"
                    :default-value="260"
                    label="调整工作区左栏宽度"
                    @commit="scheduleViewStateSave"
                />
            </main>
            <aside v-if="hasRightPanel" class="context-activity-bar" aria-label="右侧面板">
                <button
                    ref="inspectorRailToggle"
                    type="button"
                    :class="{ active: activeRightPanelOpen }"
                    :aria-expanded="activeRightPanelOpen"
                    :aria-label="activeRightPanelOpen ? `收起${activeRightPanelLabel}` : `展开${activeRightPanelLabel}`"
                    :title="activeRightPanelOpen ? `收起${activeRightPanelLabel}` : `展开${activeRightPanelLabel}`"
                    @click="setActiveRightPanelOpen(!activeRightPanelOpen)"
                >
                    <PanelRightClose v-if="activeRightPanelOpen" :size="18" aria-hidden="true" />
                    <PanelRightOpen v-else :size="18" aria-hidden="true" />
                </button>
            </aside>
        </div>

        <ProgramStructuredValueEditor
            v-if="valueEditorState"
            :title="valueEditorState.title"
            :value="valueEditorState.value"
            :available-values="valueEditorState.availableValues"
            :allow-condition-builder="valueEditorState.allowConditionBuilder"
            :initial-source="valueEditorState.envelope.request.preferred_source"
            :constraints="valueEditorState.constraints"
            :workspace="workspaceStore.workspace"
            :function-id="programStore.document?.function.function_id || ''"
            :statement-id="valueEditorState.envelope.request.statement_id"
            :base-revision="valueEditorState.envelope.base_revision"
            :busy="programStore.busy"
            @save="saveFocusedValue"
            @cancel="closeValueEditor"
        />

        <VNextCreateProjectDialog
            :open="createProjectDialogOpen"
            @close="createProjectDialogOpen = false"
            @created="afterProjectSwitch"
        />

        <VNextShortcutSettingsDialog
            v-if="shortcutSettingsOpen"
            :shortcuts="ideShortcuts"
            :defaults="ideShortcutDefaults"
            :busy="shortcutSettingsBusy"
            @cancel="shortcutSettingsOpen = false"
            @save="saveShortcutSettings"
        />
        <VNextCommandPalette
            v-if="commandPaletteOpen"
            :shortcuts="ideShortcuts"
            :enabled="isIdeCommandEnabled"
            :disabled-reason="ideCommandDisabledReason"
            @cancel="closeCommandPalette"
            @command="runPaletteCommand"
        />
        <VNextGettingStartedDialog
            v-if="gettingStartedOpen"
            @close="gettingStartedOpen = false"
            @command="runGettingStartedCommand"
        />

        <div
            v-if="notice.message || bottomPanelOpen"
            class="bottom-stack"
            :class="{ 'has-panel': bottomPanelOpen, 'has-notice': bottomPanelOpen && Boolean(notice.message) }"
            :style="bottomPanelOpen ? { '--bottom-panel-height': `${panelSizes.bottom}px` } : undefined"
        >
            <VNextPaneResizer
                v-if="bottomPanelOpen"
                v-model="panelSizes.bottom"
                orientation="horizontal"
                :min="150"
                :max="560"
                :default-value="270"
                :reverse="true"
                label="调整底部面板高度"
                @commit="scheduleViewStateSave"
            />
            <VNextInlineNotice
                v-if="notice.message"
                class="notice-bar"
                :tone="notice.tone === 'error' ? 'error' : 'success'"
                :message="notice.message"
                dismissible
                @dismiss="notice.message = ''"
            />
            <div v-if="bottomPanelOpen" class="bottom-panel-content">
                <ProgramBottomFeedbackPanel
                    v-model:active-tab="bottomPanelTab"
                    :session="runtimeSession"
                    :diagnostics="programStore.effectiveDiagnostics"
                    :programs="programStore.programs"
                    @locate-statement="locateRuntimeStatement"
                    @open-problem="openProblem"
                    @close="bottomPanelOpen = false"
                />
            </div>
        </div>

        <footer class="statusbar">
            <div>
                <span :title="programStore.serverSnapshot ? `格式 6 · revision ${compactRevision}` : '项目状态'">
                    {{ workspaceStore.workspace?.read_only ? '只读项目' : saveStateLabel }}
                </span>
                <span v-if="runtimeStatusLabel" class="runtime-summary" :data-state="runtimeSession?.status">{{ runtimeStatusLabel }}</span>
            </div>
            <div>
                <span :title="`项目默认目标：${activeTargetLabel}`">默认目标 · {{ activeTargetLabel }}</span>
                <button type="button" :class="{ active: bottomPanelOpen && bottomPanelTab === 'problems' }" @click="toggleProblems">
                    <CircleAlert :size="12" aria-hidden="true" />{{ programStore.effectiveDiagnostics.length }} 个问题
                </button>
            </div>
        </footer>

        <div v-if="modifyVariablePickerOpen" class="dialog-backdrop" @mousedown.self="closeModifyVariablePicker()">
            <section
                ref="modifyVariablePicker"
                class="create-dialog variable-picker-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="modify-variable-title"
                @keydown="trapDialogFocus"
                @keydown.esc="closeModifyVariablePicker()"
            >
                <header>
                    <div>
                        <h2 id="modify-variable-title">修改变量</h2>
                        <p>选择已经存在的变量，再在语句详情中填写新值。</p>
                    </div>
                    <VNextIconButton label="关闭" @click="closeModifyVariablePicker()"><X /></VNextIconButton>
                </header>
                <div v-if="assignableVariables.length" class="variable-picker-list" role="listbox" aria-label="可修改的变量">
                    <button
                        v-for="variable in assignableVariables"
                        :key="`${variable.source}:${variable.id}`"
                        type="button"
                        role="option"
                        data-variable-option
                        :disabled="programStore.busy"
                        @click="insertVariableAssignment(variable)"
                    >
                        <span>
                            <strong>{{ variable.display_name }}</strong>
                            <small>{{ variable.source === 'project' ? '项目变量' : '局部变量' }}</small>
                        </span>
                        <small>{{ programTypeDisplayName(variable.value_type) }}</small>
                    </button>
                </div>
                <div v-else class="variable-picker-empty">
                    <p>当前位置还没有可修改的变量。</p>
                    <VNextButton @click="insertNewLocalFromPicker">新建局部变量</VNextButton>
                </div>
                <footer class="variable-picker-footer">
                    <VNextButton :disabled="programStore.busy" @click="closeModifyVariablePicker()">取消</VNextButton>
                </footer>
            </section>
        </div>

        <div v-if="createProgramOpen" class="dialog-backdrop" @mousedown.self="closeCreateProgram">
            <section class="create-dialog" role="dialog" aria-modal="true" aria-labelledby="create-program-title" @keydown="trapDialogFocus" @keydown.esc="closeCreateProgram">
                <header>
                    <div><h2 id="create-program-title">新建项目函数</h2></div>
                    <VNextIconButton label="关闭" @click="closeCreateProgram"><X /></VNextIconButton>
                </header>
                <form @submit.prevent="createProgram">
                    <div class="dialog-form-row app-form-row">
                        <label for="program-name" class="app-form-label">函数名称</label>
                        <input id="program-name" ref="createProgramInput" v-model="createProgramName" class="app-form-control" maxlength="80" autocomplete="off" placeholder="例如：领取每日奖励" :aria-invalid="createProgramError ? 'true' : undefined" :aria-describedby="createProgramError ? 'create-program-error' : undefined" />
                        <p v-if="createProgramError" id="create-program-error" class="form-error app-form-error" role="alert">{{ createProgramError }}</p>
                    </div>
                    <footer>
                        <VNextButton @click="closeCreateProgram">取消</VNextButton>
                        <VNextButton type="submit" tone="primary" appearance="solid" :loading="programStore.busy" :disabled="!createProgramName.trim()">创建</VNextButton>
                    </footer>
                </form>
            </section>
        </div>

        <div v-if="extractStatementIds.length" class="dialog-backdrop" @mousedown.self="closeExtractStatements">
            <section class="create-dialog" role="dialog" aria-modal="true" aria-labelledby="extract-program-title" @keydown="trapDialogFocus" @keydown.esc="closeExtractStatements">
                <header>
                    <div><h2 id="extract-program-title">提取为项目函数</h2><p>将 {{ extractStatementIds.length }} 条连续语句替换为一次函数调用；需要的局部值会自动变成参数。</p></div>
                    <VNextIconButton label="关闭" @click="closeExtractStatements"><X /></VNextIconButton>
                </header>
                <form @submit.prevent="extractStatements">
                    <div class="dialog-form-row app-form-row">
                        <label for="extract-program-name" class="app-form-label">函数名称</label>
                        <input id="extract-program-name" ref="extractProgramInput" v-model="extractProgramName" class="app-form-control" maxlength="80" autocomplete="off" placeholder="例如：检查体力并准备副本" :aria-invalid="extractProgramError ? 'true' : undefined" :aria-describedby="extractProgramError ? 'extract-program-error' : undefined" />
                        <p v-if="extractProgramError" id="extract-program-error" class="form-error app-form-error" role="alert">{{ extractProgramError }}</p>
                    </div>
                    <footer>
                        <VNextButton @click="closeExtractStatements">取消</VNextButton>
                        <VNextButton type="submit" tone="primary" appearance="solid" :loading="programStore.busy" :disabled="!extractProgramName.trim()">提取</VNextButton>
                    </footer>
                </form>
            </section>
        </div>

        <div v-if="renameCandidate" class="dialog-backdrop" @mousedown.self="closeRenameProgram">
            <section class="create-dialog" role="dialog" aria-modal="true" aria-labelledby="rename-program-title" @keydown="trapDialogFocus" @keydown.esc="closeRenameProgram">
                <header>
                    <div><h2 id="rename-program-title">重命名项目函数</h2></div>
                    <VNextIconButton label="关闭" @click="closeRenameProgram"><X /></VNextIconButton>
                </header>
                <form @submit.prevent="renameProgram">
                    <div class="dialog-form-row app-form-row">
                        <label for="rename-program-name" class="app-form-label">函数名称</label>
                        <input id="rename-program-name" ref="renameProgramInput" v-model="renameProgramName" class="app-form-control" maxlength="80" autocomplete="off" :aria-invalid="renameProgramError ? 'true' : undefined" :aria-describedby="renameProgramError ? 'rename-program-error' : undefined" />
                        <p v-if="renameProgramError" id="rename-program-error" class="form-error app-form-error" role="alert">{{ renameProgramError }}</p>
                    </div>
                    <footer>
                        <VNextButton @click="closeRenameProgram">取消</VNextButton>
                        <VNextButton type="submit" tone="primary" appearance="solid" :loading="programStore.busy" :disabled="!renameProgramName.trim()">保存名称</VNextButton>
                    </footer>
                </form>
            </section>
        </div>

        <div v-if="deleteCandidate" class="dialog-backdrop">
            <section class="delete-program-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-program-title" @keydown="trapDialogFocus">
                <header>
                    <div>
                        <h2 id="delete-program-title">{{ programStore.lifecycleBlocker ? '这个函数暂时不能删除' : '删除项目函数？' }}</h2>
                        <p v-if="programStore.lifecycleBlocker">{{ programStore.lifecycleBlocker.message }}</p>
                        <p v-else>将删除“{{ deleteCandidate.display_name }}”及其全部结构化语句。此操作不可撤销。</p>
                    </div>
                </header>
                <ul v-if="programStore.lifecycleBlocker?.references.length" class="lifecycle-reference-list">
                    <li v-for="(reference, index) in programStore.lifecycleBlocker.references" :key="`${String(reference.kind || 'reference')}:${index}`">
                        <button
                            v-if="typeof reference.function_id === 'string'"
                            type="button"
                            @click="openLifecycleReference(reference)"
                        >
                            <span>{{ String(reference.function_name || '项目函数') }}</span>
                            <small>{{ lifecycleReferenceLabel(reference) }}</small>
                        </button>
                        <div v-else><span>{{ lifecycleReferenceLabel(reference) }}</span></div>
                    </li>
                </ul>
                <footer>
                    <VNextButton @click="closeDeleteProgram">{{ programStore.lifecycleBlocker ? '关闭' : '取消' }}</VNextButton>
                    <VNextButton v-if="!programStore.lifecycleBlocker" tone="danger" appearance="solid" :loading="programStore.busy" @click="confirmDeleteProgram">删除函数</VNextButton>
                </footer>
            </section>
        </div>

        <ProgramFunctionSignatureDialog
            :open="programSignatureOpen"
            :program="activeProgram || null"
            :busy="programStore.busy"
            :error="programSignatureError"
            @close="closeProgramSignature"
            @save="saveProgramSignature"
        />

        <div v-if="programStore.conflict && !conflictDialogDismissed" class="dialog-backdrop">
            <section class="conflict-dialog" role="alertdialog" aria-modal="true" aria-labelledby="conflict-title" @keydown="trapDialogFocus">
                <header><CircleAlert :size="18" aria-hidden="true" /><h2 id="conflict-title">项目函数已在外部修改</h2></header>
                <p>当前操作没有执行，也没有覆盖磁盘。你可以先保留当前界面稍后处理，或重新加载磁盘版本后再次提交刚才的设置。</p>
                <dl class="conflict-revisions"><div><dt>当前界面的基线</dt><dd>{{ shortRevision(programStore.conflict.expected_revision) }}</dd></div><div><dt>磁盘上的版本</dt><dd>{{ shortRevision(programStore.conflict.actual_revision) }}</dd></div></dl>
                <div class="conflict-actions">
                    <VNextButton :disabled="programStore.busy" @click="conflictDialogDismissed = true">保留界面，稍后处理</VNextButton>
                    <VNextButton tone="primary" appearance="solid" :loading="programStore.busy" @click="reloadConflict">重新加载磁盘版本</VNextButton>
                </div>
            </section>
        </div>

        <div v-if="historyOpen" class="dialog-backdrop" @mousedown.self="closeHistory">
            <section class="history-dialog" role="dialog" aria-modal="true" aria-labelledby="history-title" @keydown="trapDialogFocus" @keydown.esc="closeHistory">
                <header>
                    <div><h2 id="history-title">历史版本</h2><p>每次修改前自动保留；恢复不会覆盖掉当前版本。</p></div>
                    <VNextIconButton label="关闭" @click="closeHistory"><X /></VNextIconButton>
                </header>
                <div class="history-body">
                    <p v-if="historyError" class="form-error" role="alert">{{ historyError }}</p>
                    <div v-else-if="historyLoading" class="history-empty">正在读取历史版本…</div>
                    <div v-else-if="!programStore.history?.items.length" class="history-empty">还没有历史版本。完成一次修改后，这里会保留修改前的内容。</div>
                    <ol v-else class="history-list">
                        <li v-for="item in programStore.history.items" :key="item.history_id">
                            <div><strong>{{ formatHistoryTime(item.created_at) }}</strong><span>{{ historyReason(item.reason) }} · {{ item.statement_count }} 条语句</span></div>
                            <button type="button" :disabled="programStore.busy" @click="restoreHistory(item.history_id)">恢复此版本</button>
                        </li>
                    </ol>
                </div>
            </section>
        </div>

        <VNextDialog
            :open="Boolean(operationReview)"
            title="审阅操作录制"
            description="删除噪声动作后一次插入；坐标动作会保留可替换为图片或 OCR 的建议。"
            size="large"
            :dismiss-on-backdrop="false"
            @close="cancelOperationRecording"
        >
            <div class="operation-review-list">
                <label v-for="event in operationReviewEvents" :key="String(event.event_id)">
                    <input v-model="event.enabled" type="checkbox" />
                    <span><strong>{{ operationEventLabel(event) }}</strong><small v-if="operationEventSuggestions(event)">{{ operationEventSuggestions(event) }}</small></span>
                </label>
            </div>
            <template #footer>
                <VNextButton :disabled="operationRecordingBusy" @click="cancelOperationRecording">放弃草稿</VNextButton>
                <VNextButton tone="primary" appearance="solid" :loading="operationRecordingBusy" :disabled="!operationReviewEvents.some(event => event.enabled)" @click="commitOperationRecording">插入 {{ operationReviewEvents.filter(event => event.enabled).length }} 个动作</VNextButton>
            </template>
        </VNextDialog>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
    Braces,
    CalendarClock,
    ChevronDown,
    ChevronUp,
    CircleAlert,
    Circle,
    Crosshair,
    Film,
    Images,
    LayoutTemplate,
    PanelLeftClose,
    PanelRightClose,
    PanelRightOpen,
    Pause,
    Play,
    Puzzle,
    ScanSearch,
    Search,
    SlidersHorizontal,
    Square,
    StepForward,
    TerminalSquare,
    Variable,
    X,
} from 'lucide-vue-next'
import { mergeRuntimeSession, vnextApi } from '../api'
import { FALLBACK_IDE_SHORTCUTS, IDE_COMMANDS, shortcutMatches } from '../ideCommands'
import { vnextCaptureSession } from '../captureSession'
import { scheduleApi } from '../scheduleApi'
import { useVNextStore } from '../store'
import { trapDialogFocus } from '../dialogFocus'
import { rememberProject } from '../projectHistory'
import type { AssetCategoryId, AssetDefinition, AssetReferenceDefinition, ExecutionPlatformId, RuntimeSession, TargetDefinition, TargetReferenceDefinition, WorkspaceIdentity } from '../types'
import {
    captureCommandEnvelope,
    captureDefaultCategory,
    createProgramCaptureDestination,
    focusProgramCaptureOrigin,
    ProgramEditorSurface,
    ProgramFunctionLibrary,
    ProgramBottomFeedbackPanel,
    ProgramStructuredValueEditor,
    ProgramFunctionSignatureDialog,
    programApi,
    availableValuesAtInsertion,
    availableValuesAtStatement,
    directProgramValue,
    findStatement,
    isConditionValueDestination,
    projectStatements,
    programValueEditorConstraints,
    programValueEditorTitle,
    programTypeDisplayName,
    replaceDirectProgramValue,
    programValueToDraft,
    resolveStatementTargetId,
    useProjectVariableStore,
    useProgramStore,
    validateProgramCaptureDestination,
    valueDraftForAsset,
    valueDraftForCaptureResult,
    visibleStatementRows,
} from '../program'
import type { BottomFeedbackTab } from '../program'
import type {
    FunctionLibrarySelection,
    ProgramCaptureContext,
    ProgramCaptureDestination,
    ProgramCaptureEnvelope,
    ProgramCommandEnvelope,
    ProgramValueEditorEnvelope,
    ProgramValueNode,
    AvailableProgramValue,
    ProgramStructureKind,
    ProgramDiagnosticDto,
    ProjectFunctionLibraryItem,
    LocalSymbolDefinition,
    ProgramValueCatalogDto,
    ProgramStatementState,
    ProgramStatement,
} from '../program'
import VNextAsyncWorkspaceHost from './VNextAsyncWorkspaceHost.vue'
import VNextPaneResizer from './VNextPaneResizer.vue'
import VNextMenuBar from './VNextMenuBar.vue'
import VNextShortcutSettingsDialog from './VNextShortcutSettingsDialog.vue'
import VNextCommandPalette from './VNextCommandPalette.vue'
import VNextGettingStartedDialog from './VNextGettingStartedDialog.vue'
import VNextCreateProjectDialog from './VNextCreateProjectDialog.vue'
import VNextPaneHeader from './ui/VNextPaneHeader.vue'
import VNextInlineNotice from './ui/VNextInlineNotice.vue'
import VNextActivityRail from './ui/VNextActivityRail.vue'
import VNextIconButton from './ui/VNextIconButton.vue'
import VNextButton from './ui/VNextButton.vue'
import VNextDialog from './ui/VNextDialog.vue'
import type { ActivityRailItem, ActivityRailMode } from './ui/VNextActivityRail.vue'
import type { ProjectVariableReferenceDto } from '../program/serverTypes'
import { buildFunctionCatalog } from '../program/functionCatalogSearch'

type WorkspaceView = 'program' | 'resources' | 'variables' | 'targets' | 'replay' | 'extensions' | 'schedules' | 'player'

const workspaceLoaders = {
    resources: () => import('./VNextResourceWorkspace.vue'),
    variables: () => import('./VNextProjectVariableWorkspace.vue'),
    targets: () => import('./VNextTargetWorkspace.vue'),
    replay: () => import('./VNextReplayWorkspace.vue'),
    extensions: () => import('./VNextExtensionWorkspace.vue'),
    schedules: () => import('./VNextScheduleWorkspace.vue'),
    player: () => import('./VNextPlayerWorkspace.vue'),
}

const workspaceStore = useVNextStore()
const programStore = useProgramStore()
const createProjectDialogOpen = ref(false)
const projectVariableStore = useProjectVariableStore()
const activeView = ref<WorkspaceView>('program')
const ACTIVITY_RAIL_MODE_KEY = 'easycode:vnext:activity-rail-mode'
const activityRailMode = ref<ActivityRailMode>(readActivityRailMode())
const librarySelection = ref<FunctionLibrarySelection | null>(null)
const functionLibrary = ref<InstanceType<typeof ProgramFunctionLibrary> | null>(null)
const QUICK_INSERT_RECENT_KEY = 'easycode:vnext:quick-insert-recent'
const recentQuickInsertKeys = ref<string[]>(readRecentQuickInsertKeys())
const libraryDrawerOpen = ref(true)
const narrowWorkbench = ref(false)
const programInspectorOpen = ref(true)
const workspaceDetailOpen = reactive({ resources: true, replay: true, extensions: true, schedules: true, player: true })
const modifyVariablePickerOpen = ref(false)
const modifyVariablePicker = ref<HTMLElement | null>(null)
const libraryDrawerElement = ref<HTMLElement | null>(null)
const libraryDrawerClose = ref<HTMLButtonElement | null>(null)
const inspectorRailToggle = ref<HTMLButtonElement | null>(null)
const createProgramOpen = ref(false)
const createProgramName = ref('')
const createProgramError = ref('')
const createProgramInput = ref<HTMLInputElement | null>(null)
const extractStatementIds = ref<string[]>([])
const extractProgramName = ref('')
const extractProgramError = ref('')
const extractProgramInput = ref<HTMLInputElement | null>(null)
const renameCandidate = ref<ProjectFunctionLibraryItem | null>(null)
const renameProgramName = ref('')
const renameProgramError = ref('')
const renameProgramInput = ref<HTMLInputElement | null>(null)
const deleteCandidate = ref<ProjectFunctionLibraryItem | null>(null)
const bottomPanelOpen = ref(false)
const bottomPanelTab = ref<BottomFeedbackTab>('output')
const logOpen = computed({
    get: () => bottomPanelOpen.value && bottomPanelTab.value !== 'problems',
    set: (value: boolean) => {
        if (value) {
            bottomPanelOpen.value = true
            if (bottomPanelTab.value === 'problems') bottomPanelTab.value = 'output'
        } else if (bottomPanelTab.value !== 'problems') bottomPanelOpen.value = false
    },
})
const problemsOpen = computed({
    get: () => bottomPanelOpen.value && bottomPanelTab.value === 'problems',
    set: (value: boolean) => {
        if (value) { bottomPanelTab.value = 'problems'; bottomPanelOpen.value = true }
        else if (bottomPanelTab.value === 'problems') bottomPanelOpen.value = false
    },
})
const historyOpen = ref(false)
const historyLoading = ref(false)
const historyError = ref('')
const conflictDialogDismissed = ref(false)
const collapsedByFunction = ref<Record<string, string[]>>({})
const scrollOffsets = ref<Record<string, number>>({})
const panelSizes = reactive({ sidebar: 260, inspector: 340, bottom: 270 })
const ideShortcuts = ref<Record<string, string>>({ ...FALLBACK_IDE_SHORTCUTS })
const ideShortcutDefaults = ref<Record<string, string>>({ ...FALLBACK_IDE_SHORTCUTS })
const shortcutSettingsOpen = ref(false)
const shortcutSettingsBusy = ref(false)
const commandPaletteOpen = ref(false)
const commandPaletteButton = ref<HTMLButtonElement | null>(null)
const gettingStartedOpen = ref(false)
let viewStateHydrating = false
let viewStateSaveTimer: number | null = null
const scheduleAvailable = ref(false)
const runtimeSession = ref<RuntimeSession | null>(null)
const operationRecording = ref<Record<string, unknown> | null>(null)
const operationReview = ref<Record<string, unknown> | null>(null)
const operationReviewEvents = ref<Array<Record<string, unknown> & { enabled: boolean }>>([])
const operationRecordingBusy = ref(false)
const activityRailItems = computed<ActivityRailItem[]>(() => [
    activityWorkspaceItem('program', '函数库', Braces),
    activityWorkspaceItem('resources', '资源', Images),
    activityWorkspaceItem('variables', '项目变量', Variable),
    activityWorkspaceItem('targets', '运行目标', Crosshair),
    activityWorkspaceItem('player', 'Player', LayoutTemplate),
    activityWorkspaceItem('replay', '运行记录', Film, true),
    ...(scheduleAvailable.value ? [activityWorkspaceItem('schedules', '运行中心', CalendarClock)] : []),
    activityWorkspaceItem('extensions', '扩展', Puzzle, true),
    {
        id: 'feedback-output', label: '运行与检查', icon: TerminalSquare, placement: 'bottom',
        active: bottomPanelOpen.value && bottomPanelTab.value !== 'problems',
        ariaLabel: bottomPanelOpen.value && bottomPanelTab.value !== 'problems' ? '收起运行与检查面板' : '展开运行与检查面板',
        badge: runtimeSession.value?.events.length ? Math.min(runtimeSession.value.events.length, 99) : undefined,
    },
])
const debugBreakpoints = ref<Record<string, string[]>>({})
const debugSettingsBusy = ref(false)
const findOpen = ref(false)
const findQuery = ref('')
const findIndex = ref(-1)
const findInput = ref<HTMLInputElement | null>(null)
const pendingCapture = ref<ProgramCaptureDestination | null>(null)
const pendingPlayerStatementId = ref('')
const inlineValueCatalogCache = new Map<string, Promise<ProgramValueCatalogDto>>()
const valueEditorState = ref<{
    envelope: ProgramValueEditorEnvelope
    title: string
    value: ProgramValueNode
    availableValues: AvailableProgramValue[]
    allowConditionBuilder: boolean
    constraints: Record<string, unknown>
} | null>(null)

const rightPanelLabels: Partial<Record<WorkspaceView, string>> = {
    program: '语句检查器',
    resources: '资源详情',
    replay: '运行记录检查器',
    extensions: '扩展状态',
    schedules: '计划检查器',
    player: '属性检查器',
}
const hasRightPanel = computed(() => Boolean(rightPanelLabels[activeView.value]))
const activeRightPanelLabel = computed(() => rightPanelLabels[activeView.value] || '右侧面板')
const activeRightPanelOpen = computed(() => {
    if (activeView.value === 'program') return programInspectorOpen.value
    if (activeView.value in workspaceDetailOpen) {
        return workspaceDetailOpen[activeView.value as keyof typeof workspaceDetailOpen]
    }
    return false
})
const resourceSelectionBusy = ref(false)
const resourceCaptureBusy = ref(false)
const programSignatureOpen = ref(false)
const programSignatureError = ref('')
const notice = reactive<{ tone: 'info' | 'success' | 'error'; message: string }>({ tone: 'info', message: '' })
let runPollToken = 0
let captureSessionWorkspaceKey = ''
let valueEditorOrigin: HTMLElement | null = null
let modifyVariablePickerOrigin: HTMLElement | null = null

const activeProgram = computed(() => programStore.programs.find((item) => item.function_id === programStore.activeFunctionId))
const activeProgramName = computed(() => programStore.document?.function.display_name || activeProgram.value?.display_name || '')

function openProgramSignature(): void {
    if (!activeProgram.value || programStore.busy || programStore.readOnly) return
    programSignatureError.value = ''
    programSignatureOpen.value = true
}
function closeProgramSignature(): void {
    if (programStore.busy) return
    programSignatureOpen.value = false
    programSignatureError.value = ''
}
async function saveProgramSignature(payload: {
    parameters: Array<{ parameter_id?: string | null; display_name: string; value_type: string; required: boolean; default_value: ProgramValueNode | null }>
    returnType: string
}): Promise<void> {
    if (!activeProgram.value) return
    programSignatureError.value = ''
    try {
        await programStore.updateProgramSignature(activeProgram.value.function_id, payload.parameters, payload.returnType)
        programSignatureOpen.value = false
    } catch (error) {
        programSignatureError.value = error instanceof Error ? error.message : '无法保存函数参数'
    }
}
const assignableVariables = computed<AvailableProgramValue[]>(() => {
    const documentModel = programStore.document
    const localValues = documentModel
        ? availableValuesAtInsertion(
            documentModel,
            programStore.selectedStatementIds.at(-1),
            programStore.insertionTarget,
        )
        : []
    const seen = new Set<string>()
    return [...localValues, ...projectVariableStore.availableValues].filter((item) => {
        const key = `${item.source}:${item.id}`
        if (seen.has(key)) return false
        seen.add(key)
        return true
    })
})
const statementCount = computed(() => programStore.document
    ? visibleStatementRows(projectStatements(programStore.document.function.statements)).length
    : 0)
const searchableStatementRows = computed(() => programStore.document
    ? visibleStatementRows(projectStatements(programStore.document.function.statements))
    : [])
const findMatches = computed(() => {
    const query = findQuery.value.trim().toLocaleLowerCase('zh-CN')
    if (!query) return []
    return searchableStatementRows.value.filter((row) => [
        row.summary,
        row.statement.step_label || '',
        row.statement.statement_id,
    ].some((value) => value.toLocaleLowerCase('zh-CN').includes(query)))
})
const findStatus = computed(() => !findQuery.value.trim()
    ? '输入关键词'
    : !findMatches.value.length
        ? '无结果'
        : `${Math.max(0, findIndex.value) + 1} / ${findMatches.value.length}`)
const projectFunctions = computed(() => programStore.programs.map((item) => ({
    ...item,
    insertable: item.function_id !== programStore.activeFunctionId,
    insert_disabled_reason: item.function_id === programStore.activeFunctionId ? '当前函数不能调用自身' : undefined,
})))
const officialFunctions = computed(() => programStore.availableFunctions.filter((item) => item.source !== 'extension'))
const extensionFunctions = computed(() => programStore.availableFunctions
    .filter((item) => item.source === 'extension')
    .map((item) => ({
        function_id: item.function_id,
        namespace: item.namespace,
        display_name: item.name,
        qualified_name: item.qualified_name,
        summary: item.summary,
        parameters: item.parameters.map((parameter) => ({ name: parameter.name, display_name: parameter.display_name })),
        description: item.summary,
        implementation_state: item.implementation_state,
        return_type: item.return_type,
    })))
const quickInsertCandidates = computed(() => buildFunctionCatalog({
    officialFunctions: officialFunctions.value,
    projectFunctions: projectFunctions.value,
    extensionFunctions: extensionFunctions.value,
    activeFunctionId: programStore.activeFunctionId || undefined,
}))
const runIsActive = computed(() => ['queued', 'running', 'paused'].includes(runtimeSession.value?.status || ''))
const runtimeStatusLabel = computed(() => {
    const status = runtimeSession.value?.status
    if (status === 'queued') return '等待运行'
    if (status === 'running') return '正在运行'
    if (status === 'paused') return '已暂停'
    if (status === 'completed') return '上次运行完成'
    if (status === 'failed') return '上次运行失败'
    if (status === 'cancelled') return '运行已停止'
    return ''
})
const statementStates = computed<Record<string, ProgramStatementState>>(() => {
    const merged: Record<string, ProgramStatementState> = Object.fromEntries(
        Object.entries(programStore.statementStates).map(([statementId, state]) => [statementId, { ...state }]),
    )
    const functionId = programStore.activeFunctionId
    for (const statementId of debugBreakpoints.value[functionId] || []) {
        merged[statementId] = { ...(merged[statementId] || {}), breakpoint: true }
    }
    const session = runtimeSession.value
    const current = session?.current_source?.statement_id || session?.current_instruction_id
    const belongsToActiveFunction = Boolean(
        current && programStore.document && findStatement(programStore.document.function.statements, current),
    )
    if (current && belongsToActiveFunction) {
        const status = session?.status
        const runtime = status === 'paused' ? 'paused' : status === 'failed' ? 'failed' : status === 'running' ? 'running' : undefined
        if (runtime) merged[current] = { ...(merged[current] || {}), runtime }
    }
    return merged
})
const saveStateLabel = computed(() => {
    if (programStore.busy) return '处理中'
    if (programStore.status === 'conflict') return '磁盘有变化'
    if (programStore.status === 'error') return '需要处理'
    return programStore.readOnly ? '只读' : '已保存'
})
const targetOptions = computed(() => workspaceStore.targets.map((item) => ({ label: item.name, value: item.target_id })))
const activeTarget = computed(() => workspaceStore.targets.find((item) => item.target_id === workspaceStore.defaultTargetId) || null)
const activePlatform = computed<ExecutionPlatformId>(() => activeTarget.value?.type || 'no_target')
const activeTargetLabel = computed(() => activeTarget.value?.name || '无操作目标')
const selectedStatementTarget = computed<TargetDefinition | null>(() => {
    const snapshot = programStore.serverSnapshot
    const statementId = programStore.selectedStatementIds.at(-1)
    if (!snapshot || !statementId) return activeTarget.value
    const targetId = resolveStatementTargetId(snapshot, statementId, activeTarget.value?.target_id || null)
    return workspaceStore.targets.find((item) => item.target_id === targetId) || null
})
const selectedStatementPlatform = computed<ExecutionPlatformId>(() => selectedStatementTarget.value?.type || 'no_target')
const selectedStatementTargetLabel = computed(() => selectedStatementTarget.value?.name || '未选择运行目标')
const selectedStatementTargetDetail = computed(() => {
    if (!programStore.selectedStatementIds.length) return ''
    if (!activeTarget.value) return selectedStatementTarget.value ? '此语句单独指定目标' : '项目尚未设置默认目标'
    if (selectedStatementTarget.value?.target_id === activeTarget.value.target_id) return '继承项目默认目标'
    return selectedStatementTarget.value
        ? `覆盖默认目标“${activeTarget.value.name}”`
        : `默认目标“${activeTarget.value.name}”在此处不可用`
})
const compactRevision = computed(() => (programStore.serverSnapshot?.revision || '').slice(0, 10))
const pendingResourceSelection = computed(() => (
    pendingCapture.value?.action.id === 'choose-resource' ? pendingCapture.value : null
))

function clampPanelSize(value: number, min: number, max: number): number {
    return Math.max(min, Math.min(max, Math.round(value)))
}

function acceptPlayerPreviewSession(session: RuntimeSession) {
    runtimeSession.value = session
    rememberRuntimeSession(session)
}

function runtimeSessionStorageKey(workspace: WorkspaceIdentity): string {
    return `easycode.ide.active-run:${workspace.workspace_id}:${workspace.generation}`
}

function rememberedRuntimeSessionId(workspace: WorkspaceIdentity): string {
    try {
        return window.sessionStorage.getItem(runtimeSessionStorageKey(workspace)) || ''
    } catch {
        return ''
    }
}

function forgetRuntimeSession(workspace: WorkspaceIdentity, executionId = ''): void {
    try {
        const key = runtimeSessionStorageKey(workspace)
        if (!executionId || window.sessionStorage.getItem(key) === executionId) {
            window.sessionStorage.removeItem(key)
        }
    } catch {
        // Runtime discovery still works when browser storage is unavailable.
    }
}

function rememberRuntimeSession(session: RuntimeSession): void {
    const workspace = workspaceStore.workspace
    if (!workspace) return
    if (!['queued', 'running', 'paused'].includes(session.status)) {
        forgetRuntimeSession(workspace, session.execution_id)
        return
    }
    try {
        window.sessionStorage.setItem(runtimeSessionStorageKey(workspace), session.execution_id)
    } catch {
        // The backend remains authoritative; session storage only disambiguates tabs.
    }
}

function restoreRuntimeSession(workspace: WorkspaceIdentity, runs: RuntimeSession[]): void {
    if (
        workspaceStore.workspace?.workspace_id !== workspace.workspace_id
        || workspaceStore.workspace?.generation !== workspace.generation
    ) return
    const rememberedId = rememberedRuntimeSessionId(workspace)
    const session = runs.find((item) => item.execution_id === rememberedId) || runs[0] || null
    if (!session) {
        forgetRuntimeSession(workspace)
        return
    }
    runtimeSession.value = session
    rememberRuntimeSession(session)
    logOpen.value = true
    notice.tone = 'success'
    notice.message = runs.length > 1 && !rememberedId
        ? `刷新后已接回最近一次运行；当前项目另有 ${runs.length - 1} 个活动运行。`
        : '刷新后已接回原来的运行，可继续暂停、单步或停止。'
    void pollRun(session.execution_id)
}

async function openReplayCapture(sessionId: string, frameIndex: number): Promise<void> {
    try {
        await ensureCaptureSessionConnected()
        await vnextCaptureSession.openRecordingFrame(sessionId, frameIndex)
    } catch (error) {
        showError(error, '无法在捕获器中打开历史帧')
    }
}

const resourceSelectionCategory = computed(() => (
    pendingResourceSelection.value ? captureDefaultCategory(pendingResourceSelection.value) : 'image'
))

async function probeScheduleAvailability(): Promise<void> {
    try {
        const status = await scheduleApi.hubStatus()
        scheduleAvailable.value = Boolean(status.available && status.ready)
        if (!scheduleAvailable.value && activeView.value === 'schedules') activeView.value = 'program'
    } catch {
        scheduleAvailable.value = false
        if (activeView.value === 'schedules') activeView.value = 'program'
    }
}

watch(() => workspaceStore.workspace, async (workspace) => {
    runPollToken += 1
    runtimeSession.value = null
    pendingCapture.value = null
    valueEditorState.value = null
    valueEditorOrigin = null
    resourceSelectionBusy.value = false
    resourceCaptureBusy.value = false
    captureSessionWorkspaceKey = ''
    closeFind()
    await vnextCaptureSession.disconnect().catch(() => undefined)
    if (!workspace) {
        scheduleAvailable.value = false
        programStore.reset()
        projectVariableStore.reset()
        debugBreakpoints.value = {}
        return
    }
    void probeScheduleAvailability()
    viewStateHydrating = true
    const viewResult = await vnextApi.viewState(workspace).catch(() => null)
    if (viewResult) {
        activeView.value = viewResult.active_view
        collapsedByFunction.value = viewResult.collapsed_statement_ids
        scrollOffsets.value = viewResult.scroll_offsets
        panelSizes.sidebar = clampPanelSize(viewResult.panel_sizes.sidebar || viewResult.panel_sizes.library || 260, 200, 460)
        panelSizes.inspector = viewResult.panel_sizes.inspector || 340
        panelSizes.bottom = viewResult.panel_sizes.bottom || 270
    }
    const [programResult, variableResult, debugResult, activeRunsResult] = await Promise.allSettled([
        programStore.connect(workspace, viewResult?.active_function_id || ''),
        projectVariableStore.connect(workspace),
        vnextApi.debugSettings(workspace),
        vnextApi.activeRuns(workspace),
    ])
    if (programResult.status === 'fulfilled' && programStore.activeFunctionId) {
        programStore.setCollapsedStatementIds(collapsedByFunction.value[programStore.activeFunctionId] || [])
    }
    viewStateHydrating = false
    if (programResult.status === 'rejected') showError(programResult.reason, '无法载入结构化程序')
    if (variableResult.status === 'rejected') showError(variableResult.reason, '无法载入项目变量')
    if (debugResult.status === 'fulfilled') debugBreakpoints.value = debugResult.value.breakpoints
    else showError(debugResult.reason, '无法载入断点设置')
    if (activeRunsResult.status === 'fulfilled') restoreRuntimeSession(workspace, activeRunsResult.value.runs)
    else showError(activeRunsResult.reason, '无法恢复刷新前的运行状态')
}, { immediate: true })

function scheduleViewStateSave(): void {
    const workspace = workspaceStore.workspace
    if (!workspace || viewStateHydrating) return
    const functionId = programStore.activeFunctionId
    if (functionId) collapsedByFunction.value = { ...collapsedByFunction.value, [functionId]: [...programStore.collapsedStatementIds] }
    if (viewStateSaveTimer !== null) window.clearTimeout(viewStateSaveTimer)
    viewStateSaveTimer = window.setTimeout(() => {
        viewStateSaveTimer = null
        void vnextApi.saveViewState(workspace, {
            active_view: activeView.value,
            active_function_id: programStore.activeFunctionId,
            collapsed_statement_ids: collapsedByFunction.value,
            scroll_offsets: scrollOffsets.value,
            panel_sizes: { ...panelSizes },
        }).catch(error => showError(error, '工作区视图状态未保存'))
    }, 400)
}

watch(() => [activeView.value, programStore.activeFunctionId, [...programStore.collapsedStatementIds]] as const, () => {
    scheduleViewStateSave()
}, { deep: true })

watch(() => programStore.activeFunctionId, (functionId) => {
    if (functionId) librarySelection.value = { source: 'project', function_id: functionId }
}, { immediate: true })

watch(() => projectVariableStore.availableValues, (values) => {
    programStore.setProjectVariableCatalog(values)
}, { deep: true, immediate: true })

watch(() => programStore.operationError, (message) => {
    if (message && !programStore.lifecycleBlocker && !programStore.conflict) notice.message = message
})

watch(() => programStore.conflict, (conflict) => {
    if (!conflict) return
    conflictDialogDismissed.value = false
    renameCandidate.value = null
    renameProgramError.value = ''
    deleteCandidate.value = null
    programStore.clearLifecycleBlocker()
})

watch(() => [activeTarget.value?.target_id, runtimeSession.value?.status] as const, () => {
    if (captureSessionWorkspaceKey) {
        vnextCaptureSession.update(activeTarget.value, runtimeSession.value?.status || 'idle')
    }
})

onBeforeUnmount(() => {
    runPollToken += 1
    pendingCapture.value = null
    if (viewStateSaveTimer !== null) window.clearTimeout(viewStateSaveTimer)
    window.removeEventListener('keydown', onWorkbenchKeydown)
    window.removeEventListener('resize', syncWorkbenchViewport)
    void vnextCaptureSession.disconnect()
})

onMounted(() => {
    window.addEventListener('keydown', onWorkbenchKeydown)
    syncWorkbenchViewport()
    window.addEventListener('resize', syncWorkbenchViewport)
    void loadShortcutSettings()
})

async function loadShortcutSettings(): Promise<void> {
    try {
        const settings = await vnextApi.ideSettings()
        // Merge bundled values so a still-running older backend cannot make a newly added command unreachable.
        ideShortcuts.value = { ...FALLBACK_IDE_SHORTCUTS, ...settings.shortcuts }
        ideShortcutDefaults.value = { ...FALLBACK_IDE_SHORTCUTS, ...settings.defaults }
    } catch {
        // Keep the bundled defaults available while an older local backend finishes restarting.
        ideShortcuts.value = { ...FALLBACK_IDE_SHORTCUTS }
        ideShortcutDefaults.value = { ...FALLBACK_IDE_SHORTCUTS }
    }
}

async function saveShortcutSettings(shortcuts: Record<string, string>): Promise<void> {
    if (shortcutSettingsBusy.value) return
    shortcutSettingsBusy.value = true
    try {
        const settings = await vnextApi.saveIdeSettings(shortcuts)
        ideShortcuts.value = { ...FALLBACK_IDE_SHORTCUTS, ...settings.shortcuts }
        ideShortcutDefaults.value = settings.defaults
        shortcutSettingsOpen.value = false
        notice.tone = 'success'
        notice.message = '键盘快捷键已保存'
    } catch (error) {
        showError(error, '快捷键没有保存')
    } finally {
        shortcutSettingsBusy.value = false
    }
}

function onWorkbenchKeydown(event: KeyboardEvent): void {
    if (event.defaultPrevented || commandPaletteOpen.value || gettingStartedOpen.value || shortcutSettingsOpen.value || createProgramOpen.value || extractStatementIds.value.length || renameCandidate.value || deleteCandidate.value || valueEditorState.value) return
    const element = event.target as HTMLElement | null
    const editing = Boolean(element?.closest('input, textarea, select, [contenteditable="true"]'))
    if (!editing && event.key === 'Escape' && programStore.pendingCutStatementIds.length && programStore.document) {
        event.preventDefault()
        void applyProgramCommand({
            document_id: programStore.document.document_id,
            base_revision: programStore.document.revision,
            command: { kind: 'cancel_statement_clipboard' },
        })
        return
    }
    for (const command of IDE_COMMANDS.filter(item => item.shortcut)) {
        const shortcut = ideShortcuts.value[command.id]
        if (!shortcutMatches(event, shortcut)) continue
        if (editing && !['edit.find', 'help.command_palette'].includes(command.id)) return
        if (!isIdeCommandEnabled(command.id)) return
        event.preventDefault()
        void executeIdeCommand(command.id)
        return
    }
}

function isIdeCommandEnabled(commandId: string): boolean {
    const hasDocument = Boolean(programStore.document)
    const hasSelection = Boolean(programStore.selectedStatementIds.length)
    const programContext = activeView.value === 'program'
    const busy = programStore.busy || debugSettingsBusy.value
    if (commandId === 'view.schedules') return scheduleAvailable.value
    if (commandId.startsWith('help.') || commandId.startsWith('view.')) return true
    if (commandId === 'project.new' || commandId === 'project.open') return !busy && !workspaceStore.busy && !runIsActive.value
    if (commandId === 'project.new_function') return !busy
    if (commandId === 'project.history') return programContext && hasDocument && !busy
    if (commandId === 'edit.undo') return programContext && programStore.canUndo && !busy
    if (commandId === 'edit.redo') return programContext && programStore.canRedo && !busy
    if (commandId === 'edit.find') return programContext && hasDocument && !busy
    if (commandId === 'run.check') return hasDocument && !busy
    if (['edit.copy_statements', 'edit.cut_statements', 'edit.duplicate_statement', 'edit.delete_statement', 'edit.extract_function', 'run.toggle_breakpoint'].includes(commandId)) return programContext && hasDocument && hasSelection && !busy
    if (commandId === 'edit.paste_statements') return programContext && hasDocument && programStore.canPasteStatements && !busy
    if (commandId === 'run.start_or_resume') return hasDocument && !busy && (!runIsActive.value || runtimeSession.value?.status === 'paused')
    if (commandId === 'run.pause') return runtimeSession.value?.status === 'running'
    if (commandId === 'run.step') return runtimeSession.value?.status === 'paused'
    if (commandId === 'run.stop') return runIsActive.value
    return false
}

function ideCommandDisabledReason(commandId: string): string {
    const programOnly = commandId === 'project.history'
        || commandId.startsWith('edit.')
        || commandId === 'run.toggle_breakpoint'
    if (programOnly && activeView.value !== 'program') return '请切换到函数库编辑流程'
    if (commandId === 'view.schedules') return '当前调度服务尚未就绪'
    if ((commandId === 'project.new' || commandId === 'project.open') && runIsActive.value) return '请先停止当前运行，再切换项目'
    if (programStore.busy || debugSettingsBusy.value) return '当前操作完成后可用'
    if (!programStore.document && !commandId.startsWith('view.')) return '请先打开项目函数'
    if (['edit.copy_statements', 'edit.cut_statements', 'edit.duplicate_statement', 'edit.delete_statement', 'edit.extract_function', 'run.toggle_breakpoint'].includes(commandId) && !programStore.selectedStatementIds.length) return '请先选择语句'
    if (commandId === 'edit.paste_statements') return '当前函数没有可粘贴的语句'
    if (commandId === 'edit.undo') return '没有可撤销的操作'
    if (commandId === 'edit.redo') return '没有可重做的操作'
    return '当前状态不可用'
}

function afterProjectSwitch(): void {
    createProjectDialogOpen.value = false
    activeView.value = 'program'
    notice.tone = 'success'
    notice.message = `已切换到“${workspaceStore.workspace?.project_name || '新项目'}”`
}

async function openProjectFromMenu(): Promise<void> {
    try {
        const path = await workspaceStore.chooseFolder()
        if (!path) return
        const result = await workspaceStore.openProject(path)
        if (!result.workspace) {
            const errors = Array.isArray(result.inspection?.errors) ? result.inspection.errors.join('；') : ''
            throw new Error(errors || '这不是可用的 EasyCode 项目')
        }
        rememberProject(result.workspace.project_name, result.workspace.project_path)
        afterProjectSwitch()
    } catch (error) {
        showError(error, '无法打开项目')
    }
}

async function executeIdeCommand(commandId: string): Promise<void> {
    if (!isIdeCommandEnabled(commandId)) return
    const documentModel = programStore.document
    const selected = [...programStore.selectedStatementIds]
    if (commandId === 'project.new') { createProjectDialogOpen.value = true; return }
    if (commandId === 'project.open') return void openProjectFromMenu()
    if (commandId === 'project.new_function') return openCreateProgram()
    if (commandId === 'project.history') return void openHistory()
    if (commandId === 'edit.undo') return void undo()
    if (commandId === 'edit.redo') return void redo()
    if (commandId === 'edit.find') return openFind()
    if (commandId === 'edit.extract_function') return openExtractStatements(selected)
    if (['edit.copy_statements', 'edit.cut_statements', 'edit.paste_statements', 'edit.duplicate_statement', 'edit.delete_statement'].includes(commandId)) {
        if (!documentModel) return
        const command = commandId === 'edit.copy_statements'
            ? { kind: 'copy_statements' as const, statement_ids: selected }
            : commandId === 'edit.cut_statements'
                ? { kind: 'cut_statements' as const, statement_ids: selected }
                : commandId === 'edit.paste_statements'
                    ? { kind: 'paste_statements' as const }
                    : commandId === 'edit.duplicate_statement'
                        ? { kind: 'duplicate_statements' as const, statement_ids: selected }
                        : { kind: 'delete_statements' as const, statement_ids: selected }
        await applyProgramCommand({
            document_id: documentModel.document_id,
            base_revision: documentModel.revision,
            command,
        })
        return
    }
    const targetView = commandId.startsWith('view.') ? commandId.slice(5) : ''
    if (['program', 'resources', 'variables', 'targets', 'player', 'replay', 'extensions', 'schedules'].includes(targetView)) return switchView(targetView as WorkspaceView)
    if (commandId === 'view.toggle_problems') return toggleProblems()
    if (commandId === 'view.toggle_log') return toggleLog()
    if (commandId === 'view.toggle_activity_labels') return toggleActivityRailMode()
    if (commandId === 'view.reset_layout') {
        Object.assign(panelSizes, { sidebar: 260, inspector: 340, bottom: 270 })
        libraryDrawerOpen.value = true
        programInspectorOpen.value = !narrowWorkbench.value
        for (const view of Object.keys(workspaceDetailOpen) as Array<keyof typeof workspaceDetailOpen>) {
            workspaceDetailOpen[view] = !narrowWorkbench.value
        }
        scheduleViewStateSave()
        notice.tone = 'success'
        notice.message = '面板布局已恢复默认'
        return
    }
    if (commandId === 'run.check') return void checkProgram()
    if (commandId === 'run.start_or_resume') return runtimeSession.value?.status === 'paused' ? void resumeProgram() : void runProgram()
    if (commandId === 'run.pause') return void pauseProgram()
    if (commandId === 'run.step') return void stepProgram()
    if (commandId === 'run.stop') return void stopProgram()
    if (commandId === 'run.toggle_breakpoint') return void toggleBreakpoint(selected.at(-1) || '')
    if (commandId === 'help.command_palette') return openCommandPalette()
    if (commandId === 'help.getting_started') { gettingStartedOpen.value = true; return }
    if (commandId === 'help.shortcuts') shortcutSettingsOpen.value = true
}

function openCommandPalette(): void { commandPaletteOpen.value = true }
function closeCommandPalette(): void { commandPaletteOpen.value = false; void nextTick(() => commandPaletteButton.value?.focus()) }
function runPaletteCommand(commandId: string): void { commandPaletteOpen.value = false; void nextTick(() => executeIdeCommand(commandId)) }
function runGettingStartedCommand(commandId: string): void { gettingStartedOpen.value = false; void nextTick(() => executeIdeCommand(commandId)) }

function openFind(): void {
    if (!programStore.document) return
    findOpen.value = true
    void nextTick(() => {
        findInput.value?.focus()
        findInput.value?.select()
    })
}

function closeFind(): void {
    findOpen.value = false
    findQuery.value = ''
    findIndex.value = -1
}

function statementAncestors(
    statements: ProgramStatement[],
    statementId: string,
    parents: string[] = [],
): string[] | null {
    for (const statement of statements) {
        if (statement.statement_id === statementId) return parents
        const children: ProgramStatement[][] = []
        if (statement.kind === 'if') children.push(
            statement.then_body,
            ...statement.additional_branches.map((branch) => branch.statements),
            statement.else_body,
        )
        else if (statement.kind === 'loop' || statement.kind === 'target_scope') children.push(statement.body)
        else if (statement.kind === 'try') children.push(
            statement.body,
            ...statement.catches.map((clause) => clause.statements),
            statement.finally_body,
        )
        for (const block of children) {
            const result = statementAncestors(block, statementId, [...parents, statement.statement_id])
            if (result) return result
        }
    }
    return null
}

function jumpFind(direction: 1 | -1): void {
    const matches = findMatches.value
    if (!matches.length || !programStore.document) return
    const current = findIndex.value
    findIndex.value = current < 0
        ? (direction > 0 ? 0 : matches.length - 1)
        : (current + direction + matches.length) % matches.length
    const statementId = matches[findIndex.value].statement.statement_id
    const ancestors = new Set(statementAncestors(
        programStore.document.function.statements,
        statementId,
    ) || [])
    programStore.setCollapsedStatementIds(
        programStore.collapsedStatementIds.filter((id) => !ancestors.has(id)),
    )
    programStore.setSelectedStatementIds([statementId])
    void nextTick(() => {
        const escaped = globalThis.CSS?.escape?.(statementId) || statementId.replace(/["\\]/g, '\\$&')
        document.querySelector<HTMLElement>(`[data-statement-id="${escaped}"]`)?.scrollIntoView({ block: 'center' })
    })
}

watch(findMatches, (matches) => {
    findIndex.value = -1
    if (matches.length) jumpFind(1)
})

async function openProgram(functionId: string): Promise<void> {
    if (narrowWorkbench.value) libraryDrawerOpen.value = false
    try {
        const previousId = programStore.activeFunctionId
        if (previousId) collapsedByFunction.value = { ...collapsedByFunction.value, [previousId]: [...programStore.collapsedStatementIds] }
        viewStateHydrating = true
        activeView.value = 'program'
        await programStore.loadProgram(functionId)
        programStore.setCollapsedStatementIds(collapsedByFunction.value[functionId] || [])
    } catch (error) {
        showError(error, '无法打开项目函数')
    } finally {
        viewStateHydrating = false
        scheduleViewStateSave()
    }
}

function resolveInlineValueCatalog(
    statementId: string,
    expectedType: string,
    scopeBindings: LocalSymbolDefinition[] = [],
): Promise<ProgramValueCatalogDto> {
    const workspace = workspaceStore.workspace
    const documentModel = programStore.document
    if (!workspace || !documentModel) return Promise.reject(new Error('请先打开项目函数。'))
    const key = JSON.stringify([
        documentModel.revision,
        statementId,
        expectedType,
        scopeBindings.map((item) => [item.symbol_id, item.value_type]),
    ])
    const cached = inlineValueCatalogCache.get(key)
    if (cached) return cached
    const request = programApi.getValueCatalog(
        workspace,
        documentModel.function.function_id,
        statementId,
        expectedType,
        scopeBindings,
    ).then((catalog) => {
        if (catalog.revision !== documentModel.revision) throw new Error('项目函数已变化，请重新选择当前语句。')
        return catalog
    }).catch((error) => {
        inlineValueCatalogCache.delete(key)
        throw error
    })
    inlineValueCatalogCache.set(key, request)
    return request
}

async function openAssetReference(reference: AssetReferenceDefinition): Promise<void> {
    if (pendingCapture.value) clearPendingCapture()
    if (!reference.function_id) {
        notice.tone = 'error'
        notice.message = '该引用没有可打开的项目函数位置。'
        return
    }
    try {
        activeView.value = 'program'
        if (programStore.activeFunctionId !== reference.function_id) {
            await programStore.loadProgram(reference.function_id)
        }
        if (reference.statement_id) programStore.setSelectedStatementIds([reference.statement_id])
    } catch (error) {
        showError(error, '无法打开资源引用')
    }
}

async function openProjectVariableReference(reference: ProjectVariableReferenceDto): Promise<void> {
    if (!reference.function_id) {
        notice.tone = 'error'
        notice.message = '该引用没有可打开的项目函数位置。'
        return
    }
    try {
        activeView.value = 'program'
        if (programStore.activeFunctionId !== reference.function_id) {
            await programStore.loadProgram(reference.function_id)
        }
        if (reference.statement_id) programStore.setSelectedStatementIds([reference.statement_id])
    } catch (error) {
        showError(error, '无法打开项目变量引用')
    }
}

async function openTargetReference(reference: TargetReferenceDefinition): Promise<void> {
    if (reference.function_id) {
        try {
            activeView.value = 'program'
            if (programStore.activeFunctionId !== reference.function_id) await programStore.loadProgram(reference.function_id)
            if (reference.statement_id) programStore.setSelectedStatementIds([reference.statement_id])
        } catch (error) { showError(error, '无法打开目标引用') }
        return
    }
    if (reference.variable_id) {
        activeView.value = 'variables'
        projectVariableStore.selectedVariableId = reference.variable_id
        return
    }
    notice.tone = 'info'
    notice.message = reference.path ? `该引用位于 ${reference.path}，当前没有更精确的可视化定位。` : '该引用当前没有可打开的可视化位置。'
}

async function performFunctionInsert(selection: FunctionLibrarySelection): Promise<'inserted' | 'delegated'> {
    if (selection.source === 'structure' && selection.function_id === 'assignment.existing') {
        openModifyVariablePicker()
        return 'delegated'
    }
    if (selection.source === 'structure') {
        const structureKind = selection.function_id === 'assignment.new'
            ? 'assignment'
            : selection.function_id as ProgramStructureKind
        await programStore.insertStructure(structureKind, {
            target_id: activeTarget.value?.target_id,
        })
    } else {
        if (selection.intent === 'call_and_if') await programStore.insertFunctionAndIf(selection.function_id)
        else if (selection.intent === 'execute_until') await programStore.insertExecuteUntil(selection.function_id)
        else await programStore.insertFunction(selection.function_id)
    }
    return 'inserted'
}

function markInsertSuccess(selection: FunctionLibrarySelection): void {
    notice.tone = 'success'
    notice.message = selection.source === 'structure' ? '控制结构已插入并保存' : '函数已插入并保存'
    if (narrowWorkbench.value) libraryDrawerOpen.value = false
}

async function insertLibraryFunction(selection: FunctionLibrarySelection): Promise<void> {
    try {
        const outcome = await performFunctionInsert(selection)
        if (outcome === 'inserted') markInsertSuccess(selection)
    } catch (error) {
        showError(error, '插入函数失败')
    }
}

async function insertQuickFunction(selection: FunctionLibrarySelection): Promise<void> {
    try {
        const outcome = await performFunctionInsert(selection)
        if (outcome === 'inserted') {
            rememberQuickInsert(selection)
            markInsertSuccess(selection)
        }
    } catch (error) {
        showError(error, '插入函数失败')
        throw error
    }
}

function openModifyVariablePicker(): void {
    modifyVariablePickerOrigin = document.activeElement instanceof HTMLElement ? document.activeElement : null
    modifyVariablePickerOpen.value = true
    void nextTick(() => {
        const firstOption = modifyVariablePicker.value?.querySelector<HTMLButtonElement>('[data-variable-option]:not(:disabled)')
        const fallback = modifyVariablePicker.value?.querySelector<HTMLButtonElement>('.variable-picker-empty button, header button')
        const focusTarget = firstOption || fallback
        focusTarget?.focus()
    })
}

function closeModifyVariablePicker(restoreFocus = true): void {
    if (programStore.busy) return
    modifyVariablePickerOpen.value = false
    if (restoreFocus) void nextTick(() => modifyVariablePickerOrigin?.focus())
    modifyVariablePickerOrigin = null
}

async function insertNewLocalFromPicker(): Promise<void> {
    closeModifyVariablePicker(false)
    await insertLibraryFunction({ source: 'structure', function_id: 'assignment.new' })
}

async function insertVariableAssignment(variable: AvailableProgramValue): Promise<void> {
    try {
        await programStore.insertStructure('assignment', {
            assignment_target: variable.source === 'project'
                ? {
                    kind: 'project_variable',
                    variable_id: variable.id,
                    display_name: variable.display_name,
                    value_type: variable.value_type,
                }
                : {
                    kind: 'local',
                    symbol_id: variable.id,
                    display_name: variable.display_name,
                    value_type: variable.value_type,
                    declare: false,
                },
        })
        closeModifyVariablePicker(false)
        notice.tone = 'success'
        notice.message = `已插入“修改 ${variable.display_name}”并保存`
        if (narrowWorkbench.value) libraryDrawerOpen.value = false
    } catch (error) {
        showError(error, '无法插入变量修改')
    }
}

async function applyProgramCommand(envelope: ProgramCommandEnvelope): Promise<void> {
    try {
        await programStore.applyUiCommand(envelope)
    } catch (error) {
        showError(error, '修改语句失败')
    }
}

function operationEventLabel(event: Record<string, unknown>): string {
    const labels: Record<string, string> = {
        click: '单击', double_click: '双击', right_click: '右键单击', text_input: '输入文本',
        key: '按键', shortcut: '快捷键', scroll: '滚动', drag: '拖动', wait: '等待',
        application_start: '启动应用', window_activate: '激活窗口',
    }
    const kind = String(event.kind || '')
    const detail = event.control_name || event.text || event.key
    return detail ? `${labels[kind] || kind} · ${String(detail)}` : labels[kind] || kind || '未识别动作'
}

function operationEventSuggestions(event: Record<string, unknown>): string {
    return Array.isArray(event.suggestions) ? event.suggestions.map(String).join('；') : ''
}

async function toggleOperationRecording(): Promise<void> {
    if (operationRecordingBusy.value || !workspaceStore.workspace || !programStore.serverSnapshot || !activeTarget.value) return
    operationRecordingBusy.value = true
    try {
        if (!operationRecording.value) {
            operationRecording.value = await programApi.startOperationRecording(workspaceStore.workspace, {
                function_id: programStore.activeFunctionId,
                expected_revision: programStore.serverSnapshot.revision,
                target_id: activeTarget.value.target_id,
                location: programStore.insertionTarget ? { ...programStore.insertionTarget } : { block: 'root' },
            })
            notice.tone = 'info'
            notice.message = '操作录制已开始；请在目标中完成基础操作，再点击“停止录制”。'
        } else {
            const sessionId = String(operationRecording.value.session_id || '')
            const review = await programApi.stopOperationRecording(workspaceStore.workspace, sessionId)
            operationReview.value = review
            operationReviewEvents.value = (Array.isArray(review.review_events) ? review.review_events : [])
                .map(event => ({ ...(event as Record<string, unknown>), enabled: (event as Record<string, unknown>).enabled !== false }))
            operationRecording.value = null
        }
    } catch (error) {
        showError(error, '操作录制失败')
    } finally {
        operationRecordingBusy.value = false
    }
}

async function cancelOperationRecording(): Promise<void> {
    if (operationRecordingBusy.value || !workspaceStore.workspace) return
    const sessionId = String(operationReview.value?.session_id || operationRecording.value?.session_id || '')
    operationRecordingBusy.value = true
    try {
        if (sessionId) await programApi.cancelOperationRecording(workspaceStore.workspace, sessionId)
        operationReview.value = null
        operationReviewEvents.value = []
        operationRecording.value = null
        notice.tone = 'info'
        notice.message = '已放弃操作录制草稿，项目函数没有变化。'
    } catch (error) {
        showError(error, '无法放弃操作录制')
    } finally {
        operationRecordingBusy.value = false
    }
}

async function commitOperationRecording(): Promise<void> {
    if (operationRecordingBusy.value || !workspaceStore.workspace || !operationReview.value) return
    operationRecordingBusy.value = true
    try {
        const result = await programApi.commitOperationRecording(
            workspaceStore.workspace,
            String(operationReview.value.session_id || ''),
            operationReviewEvents.value,
        )
        programStore.adoptSnapshot(result.program)
        operationReview.value = null
        operationReviewEvents.value = []
        notice.tone = 'success'
        notice.message = `已一次插入 ${result.inserted_command_count} 条录制语句，可整体撤销。`
    } catch (error) {
        showError(error, '无法插入录制结果')
    } finally {
        operationRecordingBusy.value = false
    }
}

function captureContext(statementId?: string): ProgramCaptureContext {
    const workspace = workspaceStore.workspace
    const snapshot = programStore.serverSnapshot
    if (!workspace || !snapshot) throw new Error('请先打开项目函数')
    const targetId = statementId
        ? resolveStatementTargetId(snapshot, statementId, activeTarget.value?.target_id || null)
        : activeTarget.value?.target_id || null
    const target = workspaceStore.targets.find((item) => item.target_id === targetId) || null
    if (!target) throw new Error(statementId
        ? '当前语句没有有效运行目标；请将它放入“切换目标并执行”结构，或设置项目默认目标'
        : '无操作目标不能使用取点、框选或视觉录入；请先选择运行目标')
    return {
        workspace,
        snapshot,
        functionContracts: programStore.functionContracts,
        platform: target.type,
        target,
    }
}

async function ensureCaptureSessionConnected(target: TargetDefinition | null = activeTarget.value): Promise<void> {
    const workspace = workspaceStore.workspace
    if (!workspace) throw new Error('请先打开项目')
    const key = `${workspace.workspace_id}:${workspace.generation}`
    if (captureSessionWorkspaceKey !== key) {
        await vnextCaptureSession.disconnect().catch(() => undefined)
        await vnextCaptureSession.connect(
            workspace,
            target,
            runtimeSession.value?.status || 'idle',
            (message) => {
                notice.tone = 'error'
                notice.message = message
            },
        )
        captureSessionWorkspaceKey = key
        return
    }
    vnextCaptureSession.update(target, runtimeSession.value?.status || 'idle')
}

function clearPendingCapture(destination: ProgramCaptureDestination | null = pendingCapture.value): void {
    if (!destination || pendingCapture.value?.request_id === destination.request_id) pendingCapture.value = null
    resourceSelectionBusy.value = false
}

async function restoreCaptureFocus(destination: ProgramCaptureDestination): Promise<void> {
    activeView.value = 'program'
    if (programStore.activeFunctionId === destination.function_id) {
        programStore.setSelectedStatementIds([destination.statement_id])
    }
    await nextTick()
    focusProgramCaptureOrigin(destination)
}

async function finishCapture(
    destination: ProgramCaptureDestination,
    message: string,
    tone: 'success' | 'info' = 'success',
): Promise<void> {
    clearPendingCapture(destination)
    notice.tone = tone
    notice.message = message
    await restoreCaptureFocus(destination)
}

async function failCapture(destination: ProgramCaptureDestination, error: unknown): Promise<void> {
    clearPendingCapture(destination)
    showError(error, '捕获结果没有应用')
    await restoreCaptureFocus(destination)
}

async function handleCaptureRequest(envelope: ProgramCaptureEnvelope): Promise<void> {
    if (pendingCapture.value) {
        notice.tone = 'error'
        notice.message = '请先完成或取消当前参数捕获。'
        return
    }
    let destination: ProgramCaptureDestination
    try {
        const context = captureContext(envelope.request.statement_id)
        destination = createProgramCaptureDestination(envelope, context)
        pendingCapture.value = destination
        if (destination.action.id === 'choose-resource') {
            activeView.value = 'resources'
            return
        }
        await ensureCaptureSessionConnected(context.target)
        await vnextCaptureSession.capture(destination.action, async (payload) => {
            try {
                validateProgramCaptureDestination(destination, captureContext(destination.statement_id))
                if (destination.action.capture_kind === 'image') {
                    const capturedAssets = Array.isArray(payload.captured_assets)
                        ? payload.captured_assets.filter((item): item is AssetDefinition => (
                            !!item && typeof item === 'object'
                            && typeof (item as AssetDefinition).asset_id === 'string'
                        ))
                        : []
                    if (capturedAssets.length) workspaceStore.upsertAssets(capturedAssets)
                    else await workspaceStore.refreshAssets()
                }
                const next = valueDraftForCaptureResult(destination, payload, workspaceStore.assets)
                await programStore.applyUiCommand(captureCommandEnvelope(destination, next))
                await finishCapture(destination, `${destination.parameter_display_name}已更新`)
                return { message: `${destination.parameter_display_name}已更新` }
            } catch (error) {
                await failCapture(destination, error)
                throw error
            }
        }, {
            category: captureDefaultCategory(destination),
            maxRects: destination.action.max_rects || 1,
            title: destination.action.title || `设置 ${destination.parameter_display_name}`,
            onCancel: () => finishCapture(destination, '已取消参数捕获', 'info'),
            onError: (message) => failCapture(destination, new Error(message)),
        })
    } catch (error) {
        if (pendingCapture.value) {
            const pending = pendingCapture.value
            await failCapture(pending, error)
        } else showError(error, '无法开始参数捕获')
    }
}

async function restoreResourceCaptureFocus(origin: HTMLElement): Promise<void> {
    await nextTick()
    if (origin.isConnected) origin.focus()
}

async function startResourceCapture(category: AssetCategoryId, origin: HTMLElement): Promise<void> {
    if (resourceCaptureBusy.value) return
    resourceCaptureBusy.value = true
    const categoryLabel = ({ image: '图像', ocr: 'OCR', page: '页面' } as const)[category]
    try {
        await ensureCaptureSessionConnected()
        await vnextCaptureSession.captureResource(category, async (payload) => {
            try {
                const capturedAssets = Array.isArray(payload.captured_assets)
                    ? payload.captured_assets.filter((item): item is AssetDefinition => (
                        !!item && typeof item === 'object'
                        && typeof (item as AssetDefinition).asset_id === 'string'
                    ))
                    : []
                if (capturedAssets.length) workspaceStore.upsertAssets(capturedAssets)
                else await workspaceStore.refreshAssets()
                const assetIds = (Array.isArray(payload.asset_refs) ? payload.asset_refs : [])
                    .map(value => String(value).replace(/^asset:\/\//, ''))
                    .filter(Boolean)
                const captured = workspaceStore.assets.filter(item => assetIds.includes(item.asset_id))
                notice.tone = 'success'
                notice.message = captured.length
                    ? `已录入 ${captured.length} 项资源：${captured.map(item => item.display_name).join('、')}`
                    : '资源已录入并刷新'
                return { message: notice.message }
            } finally {
                resourceCaptureBusy.value = false
                await restoreResourceCaptureFocus(origin)
            }
        }, {
            title: `视觉录入 · ${categoryLabel}`,
            onCancel: async () => {
                resourceCaptureBusy.value = false
                notice.tone = 'info'
                notice.message = '已取消视觉录入'
                await restoreResourceCaptureFocus(origin)
            },
            onError: async (message) => {
                resourceCaptureBusy.value = false
                showError(new Error(message), '视觉录入失败')
                await restoreResourceCaptureFocus(origin)
            },
        })
    } catch (error) {
        resourceCaptureBusy.value = false
        showError(error, '无法开始视觉录入')
        await restoreResourceCaptureFocus(origin)
    }
}

async function applySelectedAsset(asset: AssetDefinition): Promise<void> {
    const destination = pendingResourceSelection.value
    if (!destination || resourceSelectionBusy.value) return
    resourceSelectionBusy.value = true
    try {
        validateProgramCaptureDestination(destination, captureContext(destination.statement_id))
        const next = valueDraftForAsset(destination, asset)
        await programStore.applyUiCommand(captureCommandEnvelope(destination, next))
        await finishCapture(destination, `${destination.parameter_display_name}已使用图片“${asset.display_name}”`)
    } catch (error) {
        showError(error, '图片资源没有应用')
    } finally {
        resourceSelectionBusy.value = false
    }
}

async function cancelPendingCapture(): Promise<void> {
    const destination = pendingCapture.value
    if (!destination || resourceSelectionBusy.value) return
    await finishCapture(destination, '已取消资源选择', 'info')
}

function switchView(view: WorkspaceView): void {
    if (pendingResourceSelection.value && view !== 'resources') {
        void cancelPendingCapture()
        return
    }
    if (pendingCapture.value && view !== 'program') {
        notice.tone = 'error'
        notice.message = '请先在捕获窗口完成或取消当前操作。'
        return
    }
    if (resourceCaptureBusy.value && view !== 'resources') {
        notice.tone = 'error'
        notice.message = '请先在捕获窗口完成或取消当前视觉录入。'
        return
    }
    activeView.value = view
}

function workspaceActivityLabel(view: WorkspaceView, label: string): string {
    if (activeView.value !== view) return label
    return libraryDrawerOpen.value ? `收起${label}侧栏` : `展开${label}侧栏`
}

function readActivityRailMode(): ActivityRailMode {
    if (typeof window === 'undefined') return 'labeled'
    try { return window.localStorage.getItem(ACTIVITY_RAIL_MODE_KEY) === 'compact' ? 'compact' : 'labeled' }
    catch { return 'labeled' }
}

function readRecentQuickInsertKeys(): string[] {
    if (typeof window === 'undefined') return []
    try {
        const value = JSON.parse(window.localStorage.getItem(QUICK_INSERT_RECENT_KEY) || '[]')
        return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string').slice(0, 8) : []
    } catch { return [] }
}

function rememberQuickInsert(selection: FunctionLibrarySelection): void {
    const key = `${selection.source}:${selection.function_id}`
    recentQuickInsertKeys.value = [key, ...recentQuickInsertKeys.value.filter((item) => item !== key)].slice(0, 8)
    try { window.localStorage.setItem(QUICK_INSERT_RECENT_KEY, JSON.stringify(recentQuickInsertKeys.value)) } catch { /* storage may be unavailable */ }
}

function toggleActivityRailMode(): void {
    activityRailMode.value = activityRailMode.value === 'labeled' ? 'compact' : 'labeled'
    try { window.localStorage.setItem(ACTIVITY_RAIL_MODE_KEY, activityRailMode.value) } catch { /* storage may be unavailable */ }
}

function activityWorkspaceItem(view: WorkspaceView, label: string, icon: ActivityRailItem['icon'], dividerBefore = false): ActivityRailItem {
    return {
        id: view,
        label,
        icon,
        dividerBefore,
        active: activeView.value === view,
        current: activeView.value === view,
        expanded: activeView.value === view ? libraryDrawerOpen.value : undefined,
        ariaLabel: workspaceActivityLabel(view, label),
    }
}

function activateActivityItem(id: string): void {
    if (id === 'feedback-output') { toggleLog(); return }
    activateWorkspace(id as WorkspaceView)
}

function activateWorkspace(view: WorkspaceView): void {
    const previousView = activeView.value
    if (previousView === view) {
        libraryDrawerOpen.value = !libraryDrawerOpen.value
        if (libraryDrawerOpen.value && narrowWorkbench.value) {
            if (view === 'program') programInspectorOpen.value = false
            else if (view in workspaceDetailOpen) workspaceDetailOpen[view as keyof typeof workspaceDetailOpen] = false
            void focusOpenedSidebar()
        }
        return
    }
    switchView(view)
    if (activeView.value !== view) return
    libraryDrawerOpen.value = true
    if (narrowWorkbench.value) {
        if (view === 'program') programInspectorOpen.value = false
        else if (view in workspaceDetailOpen) workspaceDetailOpen[view as keyof typeof workspaceDetailOpen] = false
        void focusOpenedSidebar()
    }
}

function locateStatementInPlayer(statementId: string): void {
    pendingPlayerStatementId.value = statementId
    activeView.value = 'player'
}

function handleValueEditorRequest(envelope: ProgramValueEditorEnvelope): void {
    const documentModel = programStore.document
    if (!documentModel || envelope.document_id !== documentModel.document_id || envelope.base_revision !== documentModel.revision) {
        notice.tone = 'error'
        notice.message = '当前语句已经变化，请重新选择后再编辑。'
        return
    }
    const statement = findStatement(documentModel.function.statements, envelope.request.statement_id)
    const value = statement ? directProgramValue(statement, envelope.request.parameter_id, envelope.request.value_id) : null
    const batchIds = envelope.request.batch_statement_ids || []
    const batchStatements = batchIds.map((statementId) => findStatement(documentModel.function.statements, statementId))
    if (batchIds.length && (batchStatements.some((item) => !item || item.kind !== 'call') || !batchIds.includes(envelope.request.statement_id))) {
        notice.tone = 'error'
        notice.message = '批量选择已经变化，请重新选择后再编辑。'
        return
    }
    const allowConditionBuilder = Boolean(statement && isConditionValueDestination(statement, envelope.request.parameter_id))
    if (!statement || !value) {
        notice.tone = 'error'
        notice.message = '当前值没有可安全保存的结构化编辑入口。'
        return
    }
    const valueCatalogs = (batchIds.length ? batchIds : [statement.statement_id]).map((statementId) => {
        const seen = new Set<string>()
        return [...availableValuesAtStatement(documentModel, statementId), ...projectVariableStore.availableValues]
            .filter((item) => {
                const key = `${item.source}:${item.id}`
                if (seen.has(key)) return false
                seen.add(key)
                return true
            })
    })
    const availableValues = valueCatalogs[0].filter((item) => valueCatalogs.slice(1).every((catalog) => (
        catalog.some((candidate) => candidate.source === item.source && candidate.id === item.id)
    )))
    valueEditorOrigin = document.activeElement instanceof HTMLElement ? document.activeElement : null
    valueEditorState.value = {
        envelope,
        title: `${batchIds.length ? `批量修改 ${batchIds.length} 条 · ` : ''}${programValueEditorTitle(statement, envelope.request.parameter_id, programStore.functionContracts)}`,
        value,
        availableValues,
        allowConditionBuilder,
        constraints: programValueEditorConstraints(statement, envelope.request.parameter_id, programStore.functionContracts),
    }
}

async function closeValueEditor(): Promise<void> {
    valueEditorState.value = null
    await nextTick()
    valueEditorOrigin?.focus()
    valueEditorOrigin = null
}

async function saveFocusedValue(next: ProgramValueNode): Promise<void> {
    const editor = valueEditorState.value
    const documentModel = programStore.document
    if (!editor || !documentModel) return
    if (editor.envelope.document_id !== documentModel.document_id || editor.envelope.base_revision !== documentModel.revision) {
        notice.tone = 'error'
        notice.message = '项目函数已在编辑期间变化，旧草稿没有提交。'
        return
    }
    const statement = findStatement(documentModel.function.statements, editor.envelope.request.statement_id)
    const batchIds = editor.envelope.request.batch_statement_ids || []
    const command = batchIds.length ? {
        kind: 'batch_update_values' as const,
        statement_ids: batchIds,
        parameter_id: editor.envelope.request.parameter_id,
        next: programValueToDraft(next),
    } : statement ? replaceDirectProgramValue(
        statement,
        editor.envelope.request.parameter_id,
        editor.envelope.request.value_id,
        next,
    ) : null
    if (!command) {
        notice.tone = 'error'
        notice.message = '当前字段已经变化，复杂值草稿没有提交。'
        return
    }
    try {
        await programStore.applyUiCommand({
            document_id: editor.envelope.document_id,
            base_revision: editor.envelope.base_revision,
            command,
        })
        notice.tone = 'success'
        notice.message = `${editor.title}已保存`
        await closeValueEditor()
    } catch (error) {
        showError(error, '复杂值保存失败')
    }
}

function isNarrowProgramViewport(): boolean {
    return typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 1099px)').matches
}

function syncWorkbenchViewport(): void {
    const wasNarrow = narrowWorkbench.value
    narrowWorkbench.value = isNarrowProgramViewport()
    if (narrowWorkbench.value && !wasNarrow) {
        libraryDrawerOpen.value = false
        programInspectorOpen.value = false
        for (const view of Object.keys(workspaceDetailOpen) as Array<keyof typeof workspaceDetailOpen>) {
            workspaceDetailOpen[view] = false
        }
    }
}

async function focusOpenedSidebar(): Promise<void> {
    await nextTick()
    if (activeView.value === 'program') libraryDrawerClose.value?.focus()
    else document.querySelector<HTMLElement>('.main-stage aside button:not(:disabled), .main-stage aside input:not(:disabled)')?.focus()
}

async function closeLibraryDrawer(): Promise<void> {
    if (!libraryDrawerOpen.value) return
    libraryDrawerOpen.value = false
    await nextTick()
    document.querySelector<HTMLButtonElement>('.vnext-activity-rail button.active')?.focus()
}

function handleLibraryDrawerKeydown(event: KeyboardEvent): void {
    if (!libraryDrawerOpen.value || !narrowWorkbench.value) return
    if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        void closeLibraryDrawer()
        return
    }
    trapDialogFocus(event)
}

async function focusFunctionLibrary(query = ''): Promise<void> {
    libraryDrawerOpen.value = true
    if (narrowWorkbench.value) programInspectorOpen.value = false
    await nextTick()
    functionLibrary.value?.focusSearch(query)
}

async function setProgramInspectorOpen(open: boolean): Promise<void> {
    programInspectorOpen.value = open
    if (open && narrowWorkbench.value) libraryDrawerOpen.value = false
    await nextTick()
    if (!open) inspectorRailToggle.value?.focus()
}

async function setActiveRightPanelOpen(open: boolean): Promise<void> {
    if (activeView.value === 'program') {
        await setProgramInspectorOpen(open)
        return
    }
    if (activeView.value in workspaceDetailOpen) {
        workspaceDetailOpen[activeView.value as keyof typeof workspaceDetailOpen] = open
        if (open && narrowWorkbench.value) libraryDrawerOpen.value = false
        await nextTick()
        if (!open) inspectorRailToggle.value?.focus()
    }
}

async function undo(): Promise<void> {
    try { await programStore.undo() } catch (error) { showError(error, '撤销失败') }
}

async function redo(): Promise<void> {
    try { await programStore.redo() } catch (error) { showError(error, '重做失败') }
}

async function checkProgram(): Promise<boolean> {
    try {
        const result = await programStore.compile(activePlatform.value)
        if (!result.valid) {
            notice.tone = 'error'
            notice.message = `检查发现 ${result.diagnostics.length} 个问题，请在问题面板中逐项定位处理。`
            problemsOpen.value = true
            logOpen.value = false
            return false
        }
        notice.tone = 'success'
        notice.message = '检查通过，可以运行。'
        return true
    } catch (error) {
        showError(error, '检查失败')
        return false
    }
}

function toggleLog(): void {
    if (bottomPanelOpen.value && bottomPanelTab.value !== 'problems') {
        bottomPanelOpen.value = false
        return
    }
    bottomPanelTab.value = 'output'
    bottomPanelOpen.value = true
}

function toggleProblems(): void {
    if (bottomPanelOpen.value && bottomPanelTab.value === 'problems') {
        bottomPanelOpen.value = false
        return
    }
    bottomPanelTab.value = 'problems'
    bottomPanelOpen.value = true
}

async function openProblem(diagnostic: ProgramDiagnosticDto): Promise<void> {
    try {
        activeView.value = 'program'
        const functionId = diagnostic.function_id || programStore.activeFunctionId
        if (functionId && functionId !== programStore.activeFunctionId) await programStore.loadProgram(functionId)
        if (diagnostic.statement_id) programStore.setSelectedStatementIds([diagnostic.statement_id])
        await nextTick()
        if (diagnostic.value_id) {
            const escaped = globalThis.CSS?.escape?.(diagnostic.value_id) || diagnostic.value_id.replace(/["\\]/g, '\\$&')
            const field = document.querySelector<HTMLElement>(`[data-value-id="${escaped}"]`)
            field?.scrollIntoView({ block: 'center' })
            field?.querySelector<HTMLElement>('input, select, textarea, button')?.focus()
        }
    } catch (error) {
        showError(error, '无法定位问题')
    }
}

async function locateRuntimeStatement(statementId: string): Promise<void> {
    try {
        activeView.value = 'program'
        const functionId = runtimeSession.value?.current_source?.function_id
        const isCurrentLocation = runtimeSession.value?.current_instruction_id === statementId
        if (isCurrentLocation && functionId && functionId !== programStore.activeFunctionId) {
            await programStore.loadProgram(functionId)
        }
        if (!programStore.document || !findStatement(programStore.document.function.statements, statementId)) {
            notice.tone = 'info'
            notice.message = '这条日志来自其他项目函数；请先打开对应函数后再定位。'
            return
        }
        programStore.setSelectedStatementIds([statementId])
        await nextTick()
        document.querySelector<HTMLElement>(`[data-statement-id="${statementId}"]`)?.scrollIntoView({ block: 'center' })
    } catch (error) {
        showError(error, '无法定位运行语句')
    }
}

async function runProgram(): Promise<void> {
    if (!await checkProgram()) return
    try {
        const session = await programStore.run({
            target_platform: activePlatform.value,
            target_id: activeTarget.value?.target_id,
            debug: { breakpoints: debugBreakpoints.value[programStore.activeFunctionId] || [] },
        })
        runtimeSession.value = session
        rememberRuntimeSession(session)
        logOpen.value = true
        void pollRun(session.execution_id)
    } catch (error) {
        logOpen.value = true
        showError(error, '运行启动失败')
    }
}

async function toggleBreakpoint(statementId: string): Promise<void> {
    const workspace = workspaceStore.workspace
    const functionId = programStore.activeFunctionId
    if (!workspace || !functionId || debugSettingsBusy.value) return
    const before = debugBreakpoints.value
    const next = Object.fromEntries(Object.entries(before).map(([key, values]) => [key, [...values]]))
    const current = new Set(next[functionId] || [])
    if (current.has(statementId)) current.delete(statementId)
    else current.add(statementId)
    if (current.size) next[functionId] = [...current]
    else delete next[functionId]
    debugBreakpoints.value = next
    debugSettingsBusy.value = true
    try {
        debugBreakpoints.value = (await vnextApi.saveDebugSettings(workspace, next)).breakpoints
    } catch (error) {
        debugBreakpoints.value = before
        showError(error, '断点保存失败')
    } finally {
        debugSettingsBusy.value = false
    }
}

async function pauseProgram(): Promise<void> {
    const executionId = runtimeSession.value?.execution_id
    if (!executionId) return
    try {
        runtimeSession.value = mergeRuntimeSession(runtimeSession.value, await vnextApi.pauseRun(executionId))
    } catch (error) { showError(error, '暂停运行失败') }
}

async function resumeProgram(): Promise<void> {
    const executionId = runtimeSession.value?.execution_id
    if (!executionId) return
    try {
        runtimeSession.value = mergeRuntimeSession(runtimeSession.value, await vnextApi.resumeRun(executionId))
    } catch (error) { showError(error, '继续运行失败') }
}

async function stepProgram(): Promise<void> {
    const executionId = runtimeSession.value?.execution_id
    if (!executionId) return
    try {
        runtimeSession.value = mergeRuntimeSession(runtimeSession.value, await vnextApi.stepRun(executionId))
    } catch (error) { showError(error, '单步运行失败') }
}

async function pollRun(executionId: string): Promise<void> {
    const token = ++runPollToken
    while (token === runPollToken && runIsActive.value) {
        await new Promise((resolve) => window.setTimeout(resolve, 350))
        if (token !== runPollToken) return
        try {
            const cursor = runtimeSession.value?.event_cursor || runtimeSession.value?.events.at(-1)?.sequence || 0
            const snapshot = await vnextApi.runStatus(executionId, cursor)
            if (token !== runPollToken) return
            runtimeSession.value = mergeRuntimeSession(runtimeSession.value, snapshot)
            rememberRuntimeSession(snapshot)
        } catch (error) {
            if (token !== runPollToken) return
            if ((error as { status?: number } | null)?.status === 404) {
                const workspace = workspaceStore.workspace
                if (workspace) forgetRuntimeSession(workspace, executionId)
                runtimeSession.value = null
                notice.tone = 'info'
                notice.message = '原运行会话已结束或运行服务已重启，现在可以重新运行。'
                return
            }
            showError(error, '运行状态连接中断')
            return
        }
    }
}

async function stopProgram(): Promise<void> {
    const executionId = runtimeSession.value?.execution_id
    if (!executionId) return
    try {
        const snapshot = await vnextApi.cancelRun(executionId)
        runtimeSession.value = mergeRuntimeSession(runtimeSession.value, snapshot)
        rememberRuntimeSession(snapshot)
    } catch (error) {
        showError(error, '停止运行失败')
    }
}

function openCreateProgram(): void {
    createProgramName.value = ''
    createProgramError.value = ''
    createProgramOpen.value = true
    void nextTick(() => createProgramInput.value?.focus())
}

function closeCreateProgram(): void {
    if (programStore.busy) return
    createProgramOpen.value = false
}

function openExtractStatements(statementIds: string[]): void {
    extractStatementIds.value = [...statementIds]
    extractProgramName.value = ''
    extractProgramError.value = ''
    void nextTick(() => extractProgramInput.value?.focus())
}

function closeExtractStatements(): void {
    if (programStore.busy) return
    extractStatementIds.value = []
    extractProgramError.value = ''
}

async function extractStatements(): Promise<void> {
    extractProgramError.value = ''
    try {
        await programStore.extractStatements(extractStatementIds.value, extractProgramName.value)
        extractStatementIds.value = []
        notice.tone = 'success'
        notice.message = `已提取为“${extractProgramName.value.trim()}”`
    } catch (error) {
        extractProgramError.value = error instanceof Error ? error.message : '提取失败'
    }
}

async function createProgram(): Promise<void> {
    createProgramError.value = ''
    try {
        await programStore.createProgram(createProgramName.value)
        createProgramOpen.value = false
        activeView.value = 'program'
    } catch (error) {
        createProgramError.value = error instanceof Error ? error.message : '创建失败'
    }
}

function openRenameProgram(item: ProjectFunctionLibraryItem): void {
    renameCandidate.value = item
    renameProgramName.value = item.display_name
    renameProgramError.value = ''
    void nextTick(() => {
        renameProgramInput.value?.focus()
        renameProgramInput.value?.select()
    })
}

function closeRenameProgram(): void {
    if (programStore.busy) return
    renameCandidate.value = null
    renameProgramError.value = ''
}

async function renameProgram(): Promise<void> {
    const item = renameCandidate.value
    if (!item) return
    renameProgramError.value = ''
    try {
        await programStore.renameProgram(item.function_id, renameProgramName.value)
        renameCandidate.value = null
        notice.tone = 'success'
        notice.message = '函数名称已保存。'
    } catch (error) {
        renameProgramError.value = error instanceof Error ? error.message : '重命名失败'
    }
}

function openDeleteProgram(item: ProjectFunctionLibraryItem): void {
    programStore.clearLifecycleBlocker()
    deleteCandidate.value = item
}

function closeDeleteProgram(): void {
    if (programStore.busy) return
    deleteCandidate.value = null
    programStore.clearLifecycleBlocker()
}

async function confirmDeleteProgram(): Promise<void> {
    const item = deleteCandidate.value
    if (!item) return
    try {
        await programStore.deleteProgram(item.function_id)
        deleteCandidate.value = null
        notice.tone = 'success'
        notice.message = '项目函数已删除。'
    } catch (error) {
        if (!programStore.lifecycleBlocker) showError(error, '删除函数失败')
    }
}

async function openLifecycleReference(reference: Record<string, unknown>): Promise<void> {
    const functionId = typeof reference.function_id === 'string' ? reference.function_id : ''
    if (!functionId) return
    closeDeleteProgram()
    await openProgram(functionId)
    if (typeof reference.statement_id === 'string') {
        programStore.setSelectedStatementIds([reference.statement_id])
    }
}

function lifecycleReferenceLabel(reference: Record<string, unknown>): string {
    if (typeof reference.field === 'string') return reference.field
    if (typeof reference.kind === 'string' && reference.kind === 'listen_handler') return '监听处理函数'
    if (typeof reference.kind === 'string') return reference.kind
    return '函数引用'
}

async function reloadConflict(): Promise<void> {
    try {
        await programStore.reloadConflict()
        valueEditorState.value = null
        valueEditorOrigin = null
        notice.tone = 'success'
        notice.message = '已重新加载磁盘版本。'
    } catch (error) {
        showError(error, '重新加载失败')
    }
}

function shortRevision(value: string): string {
    return value ? value.replace(/^sha256:/, '').slice(0, 12) : '文件已不存在'
}

function formatHistoryTime(value: string): string {
    const parsed = new Date(value)
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('zh-CN', { hour12: false })
}

function historyReason(reason: string): string {
    return ({ before_edit: '修改前', before_delete: '删除前', before_restore: '恢复前' } as Record<string, string>)[reason] || '自动保存'
}

async function openHistory(): Promise<void> {
    historyOpen.value = true
    historyLoading.value = true
    historyError.value = ''
    try {
        await programStore.loadHistory()
    } catch (error) {
        historyError.value = error instanceof Error ? error.message : '历史版本读取失败'
    } finally {
        historyLoading.value = false
    }
}

function closeHistory(): void {
    if (programStore.busy) return
    historyOpen.value = false
    historyError.value = ''
}

async function restoreHistory(historyId: string): Promise<void> {
    historyError.value = ''
    try {
        await programStore.restoreHistory(historyId)
        historyOpen.value = false
        notice.tone = 'success'
        notice.message = '历史版本已恢复；刚才的当前版本也已自动保留。'
    } catch (error) {
        historyError.value = error instanceof Error ? error.message : '历史版本恢复失败'
    }
}

function showError(error: unknown, fallback: string): void {
    notice.tone = 'error'
    notice.message = error instanceof Error ? error.message : fallback
}
</script>

<style scoped>
.ide-v6-shell {
    width: 100vw;
    height: 100vh;
    display: grid;
    grid-template-rows: var(--app-height-app-header) minmax(0, 1fr) auto var(--app-height-status-bar);
    overflow: hidden;
    background: var(--app-bg-base);
    color: var(--app-text-regular);
}

.skip-to-workspace {
    position: fixed;
    z-index: 3000;
    top: 6px;
    left: 8px;
    padding: 6px 10px;
    transform: translateY(-160%);
    border: 1px solid var(--app-color-primary);
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-overlay);
    color: var(--app-text-primary);
    text-decoration: none;
}
.skip-to-workspace:focus { transform: translateY(0); box-shadow: var(--focus-ring); }

.titlebar,
.brand,
.title-actions,
.toolbar-button,
.editor-header,
.editor-title,
.compact-button,
.notice-bar,
.statusbar,
.statusbar > div { display: flex; align-items: center; }

.titlebar {
    display: grid;
    grid-template-columns: auto auto minmax(0, 1fr) auto;
    gap: 10px;
    padding: 0 10px;
    border-bottom: 1px solid var(--app-border-subtle);
    background: var(--app-bg-chrome);
    user-select: none;
}
.titlebar > * { min-width: 0; }
.brand { display: inline-flex; align-items: center; gap: 7px; padding: 0 2px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-primary); font: inherit; cursor: pointer; }
.brand:hover, .brand:focus-visible { outline: 0; background: var(--app-bg-hover); box-shadow: var(--focus-ring); }
.brand svg { color: var(--app-color-primary); }
.brand strong { font-size: var(--app-font-compact); }
.titlebar-spacer { min-width: 12px; }
.title-actions { gap: 5px; }
.command-search-button { min-width: 116px; justify-content: flex-start; color: var(--app-text-secondary); }
.toolbar-button.is-recording { border-color: color-mix(in srgb, var(--app-color-danger) 58%, var(--app-border-default)); color: var(--app-color-danger); }
.operation-review-list { display: grid; gap: var(--app-spacing-xs); }
.operation-review-list label { min-height: var(--app-control-touch); display: flex; align-items: center; gap: var(--app-spacing-sm); padding: 7px 9px; border: 1px solid var(--app-border-subtle); border-radius: var(--app-radius-sm); background: var(--app-bg-input); }
.operation-review-list input { flex: none; accent-color: var(--app-color-primary); }
.operation-review-list span { min-width: 0; display: flex; flex: 1; flex-direction: column; gap: 2px; }
.operation-review-list strong { color: var(--app-text-primary); font-size: var(--app-font-interface); font-weight: 550; line-height: var(--app-line-height-compact); }
.operation-review-list small { color: var(--app-text-secondary); font-size: var(--app-font-caption); line-height: var(--app-line-height-body); }

.icon-button,
.context-activity-bar button {
    position: relative;
    display: grid;
    place-items: center;
    padding: 0;
    border: 0;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
    cursor: pointer;
}
.icon-button { width: var(--app-control-compact); height: var(--app-control-compact); }
.icon-button:hover:not(:disabled), .icon-button:focus-visible, .context-activity-bar button:hover, .context-activity-bar button:focus-visible { background: var(--app-bg-hover); color: var(--app-text-primary); }
.icon-button:disabled { opacity: .35; cursor: default; }

.toolbar-button,
.compact-button {
    height: var(--app-control-compact);
    justify-content: center;
    gap: 6px;
    padding: 0 10px;
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-raised);
    color: var(--app-text-regular);
    font: inherit;
    cursor: pointer;
}
.toolbar-button:hover:not(:disabled), .compact-button:hover:not(:disabled) { border-color: var(--app-border-strong); background: var(--app-bg-hover); color: var(--app-text-primary); }
.toolbar-button:disabled, .compact-button:disabled { opacity: .4; cursor: default; }
.run-button { border-color: color-mix(in srgb, var(--app-color-primary-hover) 62%, var(--app-border-default)); color: var(--app-color-primary-hover); }
.stop-button { border-color: color-mix(in srgb, var(--app-color-danger) 48%, var(--app-border-default)); color: var(--app-color-danger); }

.workbench { min-height: 0; display: flex; overflow: hidden; }
.context-activity-bar {
    width: 38px;
    flex: 0 0 38px;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 6px;
    border-left: 1px solid var(--app-border-subtle);
    background: var(--app-bg-chrome);
}
.context-activity-bar button { width: 28px; height: var(--app-control-default); }
.context-activity-bar button.active { color: var(--app-color-primary-hover); }
.context-activity-bar button.active::after { content: ''; position: absolute; right: -5px; width: 1px; height: 18px; background: var(--app-color-primary-hover); }
.main-stage { position: relative; min-width: 0; min-height: 0; flex: 1; overflow: hidden; }
.program-workspace { position: relative; width: 100%; height: 100%; display: grid; grid-template-columns: var(--program-library-width, 260px) 5px minmax(0, 1fr); }
.main-stage.sidebar-collapsed .program-workspace { grid-template-columns: minmax(0, 1fr); }
.main-stage.sidebar-collapsed .function-library-shell,
.main-stage.sidebar-collapsed .program-sidebar-resizer { display: none; }
.function-library-shell { min-width: 0; min-height: 0; overflow: hidden; }
.function-library-shell > :deep(.function-library) { height: 100%; }
.function-library-drawer-close { display: none; }
.workspace-sidebar-scrim { display: none; }
.workspace-sidebar-resizer { position: absolute; z-index: 55; inset: 0 auto 0 calc(var(--workspace-sidebar-width, 260px) - 2px); }
.editor-pane { min-width: 0; min-height: 0; display: grid; grid-template-rows: minmax(0, 1fr); }
.editor-header { justify-content: space-between; gap: 12px; padding: 0 8px 0 13px; border-bottom: 1px solid var(--app-border-subtle); background: var(--app-bg-chrome); }
.editor-title { min-width: 0; gap: 7px; }
.editor-title > svg { color: var(--app-color-primary); }
.editor-title strong { overflow: hidden; color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.editor-title span { flex: none; color: var(--app-text-secondary); font-size: var(--app-font-xs); white-space: nowrap; }
.editor-header-actions, .statement-find { display: flex; align-items: center; gap: 4px; }
.statement-find { min-width: min(390px, 55%); height: var(--app-control-compact); padding-left: 8px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-input); color: var(--app-text-secondary); }
.statement-find:focus-within { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.statement-find input { min-width: 80px; flex: 1; height: var(--app-control-compact); padding: 0 4px; border: 0; outline: 0; background: transparent; color: var(--app-text-primary); font: inherit; }
.statement-find > span { flex: none; color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
.statement-find button { width: 25px; height: 25px; display: grid; place-items: center; padding: 0; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-secondary); cursor: pointer; }
.statement-find button:hover:not(:disabled) { background: var(--app-bg-hover); color: var(--app-text-primary); }
.statement-find button:disabled { opacity: .35; }
.compact-button { padding: 0 8px; background: transparent; font-size: var(--app-font-xs); }
.editor-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 7px; padding: 30px; color: var(--app-text-secondary); text-align: center; }
.editor-empty > svg { color: var(--app-text-placeholder); }
.editor-empty strong { color: var(--app-text-primary); font-size: var(--app-font-md); }
.editor-empty p { max-width: 340px; margin: 0; font-size: var(--app-font-sm); line-height: 1.6; }
.editor-empty button { min-height: var(--app-control-default); margin-top: 6px; padding: 0 12px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-raised); color: var(--app-text-primary); cursor: pointer; }
.resource-workspace { width: 100%; height: 100%; }
.variable-workspace { width: 100%; height: 100%; }
.target-workspace-view { width: 100%; height: 100%; }
.player-workspace-view { width: 100%; height: 100%; }
.main-stage.sidebar-collapsed .workspace-sidebar-resizer,
.main-stage.sidebar-collapsed :deep(.resource-tree),
.main-stage.sidebar-collapsed :deep(.variable-sidebar),
.main-stage.sidebar-collapsed :deep(.target-sidebar),
.main-stage.sidebar-collapsed :deep(.replay-sessions),
.main-stage.sidebar-collapsed :deep(.package-pane),
.main-stage.sidebar-collapsed :deep(.schedule-nav),
.main-stage.sidebar-collapsed :deep(.player-outline) { display: none !important; }
.main-stage.sidebar-collapsed :deep(.resource-workspace) { grid-template-columns: minmax(0, 1fr) 300px; }
.main-stage.sidebar-collapsed :deep(.variable-workspace),
.main-stage.sidebar-collapsed :deep(.target-workspace) { grid-template-columns: minmax(0, 1fr); }
.main-stage.sidebar-collapsed :deep(.replay-workspace) { grid-template-columns: minmax(0, 1fr) minmax(300px, 360px); }
.main-stage.sidebar-collapsed :deep(.extension-workspace) { grid-template-columns: minmax(420px, 1fr) 310px; }
.main-stage.sidebar-collapsed :deep(.schedule-workspace) { grid-template-columns: minmax(360px, 1fr) minmax(300px, 360px); }
.main-stage.sidebar-collapsed :deep(.player-workspace) { grid-template-columns: minmax(360px, 1fr) 300px; }
.main-stage.sidebar-collapsed :deep(.resource-workspace.detail-panel-collapsed),
.main-stage.sidebar-collapsed :deep(.replay-workspace.detail-panel-collapsed),
.main-stage.sidebar-collapsed :deep(.extension-workspace.detail-panel-collapsed),
.main-stage.sidebar-collapsed :deep(.schedule-workspace.detail-panel-collapsed),
.main-stage.sidebar-collapsed :deep(.player-workspace.detail-panel-collapsed) { grid-template-columns: minmax(0, 1fr); }
.bottom-stack { min-height: 0; display: flex; flex-direction: column; }
.bottom-stack.has-panel {
    height: min(var(--bottom-panel-height, 270px), calc(100vh - 96px));
    display: grid;
    grid-template-rows: 5px minmax(0, 1fr);
}
.bottom-stack.has-panel.has-notice { grid-template-rows: 5px auto minmax(0, 1fr); }
.bottom-panel-content { min-height: 0; overflow: hidden; }
.bottom-panel-content :deep(.run-console),
.bottom-panel-content :deep(.problems-panel) { min-height: 0; height: 100%; border-top: 0; }

.notice-bar { gap: 7px; min-height: var(--app-control-default); padding: 5px 10px 5px 12px; border-top: 1px solid var(--app-border-subtle); background: var(--app-bg-raised); color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.notice-bar[data-tone="success"] > svg { color: var(--app-color-success); }
.notice-bar[data-tone="error"] { color: var(--app-color-danger); }
.notice-bar span { min-width: 0; flex: 1; overflow-wrap: anywhere; }
.notice-bar button { width: 24px; height: 24px; display: grid; place-items: center; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: inherit; cursor: pointer; }
.notice-bar button:hover { background: var(--app-bg-hover); }
.statusbar { grid-row: 4; height: 24px; min-height: 24px; justify-content: space-between; padding: 0 8px; overflow: hidden; border-top: 1px solid var(--app-border-subtle); background: var(--app-bg-chrome); color: var(--app-text-secondary); font-size: var(--app-font-xs); user-select: none; }
.statusbar > div { gap: 12px; }
.statusbar button { min-height: 24px; display: inline-flex; align-items: center; gap: 5px; padding: 0 6px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: inherit; font: inherit; cursor: pointer; }
.statusbar button:hover, .statusbar button:focus-visible, .statusbar button.active { background: var(--app-bg-hover); color: var(--app-text-primary); outline: 0; }
.statusbar button:focus-visible { box-shadow: var(--focus-ring); }
.runtime-summary[data-state="running"], .runtime-summary[data-state="queued"] { color: var(--app-color-success); }
.runtime-summary[data-state="paused"] { color: var(--app-color-warning); }
.runtime-summary[data-state="failed"] { color: var(--app-color-danger); }

.dialog-backdrop { position: fixed; inset: 0; z-index: 2200; display: grid; place-items: center; padding: 20px; background: rgba(7, 7, 6, .72); }
.create-dialog,
.conflict-dialog,
.delete-program-dialog { width: min(460px, calc(100vw - 28px)); overflow: hidden; border: 1px solid var(--app-overlay-border); border-radius: var(--app-radius-lg); background: var(--app-bg-raised); box-shadow: var(--app-shadow-lg); }
.create-dialog > header { display: flex; align-items: flex-start; justify-content: space-between; padding: 15px 16px; border-bottom: 1px solid var(--app-border-subtle); }
.create-dialog h2, .conflict-dialog h2, .delete-program-dialog h2 { margin: 0; color: var(--app-text-primary); font-size: var(--app-font-md); font-weight: 600; }
.create-dialog header p { margin: 3px 0 0; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.create-dialog form { container-type: inline-size; padding: 16px; }
.create-dialog label { margin: 0; color: var(--app-text-regular); font-size: var(--app-font-sm); font-weight: 500; }
.create-dialog input { width: 100%; height: var(--app-control-default); padding: 0 10px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); outline: 0; background: var(--app-bg-input); color: var(--app-text-primary); }
.create-dialog input:focus { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.create-dialog input[aria-invalid='true'] { border-color: var(--app-color-danger); }
.dialog-form-row { --app-form-row-label-min: 84px; --app-form-row-label-max: 96px; }
.dialog-form-row > .form-error { grid-column: 2 / -1; margin: var(--app-spacing-xs) 0 0; }
.create-dialog form > footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
.variable-picker-dialog { max-height: min(620px, calc(100vh - 40px)); display: flex; flex-direction: column; }
.variable-picker-list { min-height: 0; overflow: auto; padding: 6px; }
.variable-picker-list > button { width: 100%; min-height: 48px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 7px 10px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-secondary); font: inherit; text-align: start; cursor: pointer; }
.variable-picker-list > button:hover, .variable-picker-list > button:focus-visible { outline: 0; background: var(--app-bg-hover); color: var(--app-text-primary); box-shadow: var(--focus-ring); }
.variable-picker-list > button > span { min-width: 0; display: flex; align-items: baseline; gap: 8px; }
.variable-picker-list strong { overflow: hidden; color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.variable-picker-list small { color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.variable-picker-empty { min-height: 132px; display: grid; place-items: center; align-content: center; gap: 12px; padding: 20px; color: var(--app-text-secondary); font-size: var(--app-font-sm); text-align: center; }
.variable-picker-empty p { margin: 0; }
.variable-picker-footer { display: flex; justify-content: flex-end; padding: 12px 16px; border-top: 1px solid var(--app-border-subtle); }
.form-error { margin: 7px 0 0; color: var(--app-color-danger); font-size: var(--app-font-xs); }
@container (max-width: 300px) {
    .dialog-form-row { grid-template-columns: minmax(0, 1fr); row-gap: var(--app-form-label-control-gap); }
    .dialog-form-row > .form-error { grid-column: 1; }
}
.primary-button, .secondary-button { height: var(--app-control-default); padding: 0 12px; border-radius: var(--app-radius-sm); font: inherit; cursor: pointer; }
.primary-button { border: 1px solid var(--app-color-primary); background: var(--app-color-primary); color: var(--app-color-on-primary); }
.secondary-button { border: 1px solid var(--app-border-default); background: transparent; color: var(--app-text-regular); }
.shortcut-dialog { width: min(780px, calc(100vw - 36px)); height: min(680px, calc(100vh - 48px)); display: grid; grid-template-rows: auto auto auto minmax(0, 1fr) auto; overflow: hidden; border: 1px solid var(--app-overlay-border); border-radius: var(--app-radius-lg); background: var(--app-bg-raised); box-shadow: var(--app-shadow-lg); }
.shortcut-dialog > header { display: flex; align-items: flex-start; justify-content: space-between; padding: 15px 18px; border-bottom: 1px solid var(--app-border-subtle); }
.shortcut-dialog h2 { margin: 0; color: var(--app-text-primary); font-size: var(--app-font-md); }
.shortcut-dialog header p { margin: 4px 0 0; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.shortcut-tools { display: flex; gap: 8px; padding: 12px 18px; }
.shortcut-tools input { min-width: 0; flex: 1; height: var(--app-control-default); padding: 0 10px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); outline: 0; background: var(--app-bg-input); color: var(--app-text-primary); }
.shortcut-tools input:focus { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.shortcut-dialog > .form-error { margin: 0 18px 8px; }
.shortcut-list { min-height: 0; overflow: auto; padding: 0 18px 16px; }
.shortcut-list h3 { margin: 14px 0 5px; color: var(--app-text-secondary); font-size: var(--app-font-xs); font-weight: 600; }
.shortcut-row { min-height: 48px; display: grid; grid-template-columns: minmax(0, 1fr) 180px 48px; align-items: center; gap: 8px; border-top: 1px solid var(--app-border-subtle); }
.shortcut-row > div { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.shortcut-row strong { color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 500; }
.shortcut-row span { overflow: hidden; color: var(--app-text-placeholder); font-size: var(--app-font-xs); text-overflow: ellipsis; white-space: nowrap; }
.shortcut-recorder { height: var(--app-control-compact); border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-input); color: var(--app-text-regular); font: inherit; cursor: pointer; }
.shortcut-recorder.recording { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); color: var(--app-color-primary); }
.shortcut-clear { border: 0; background: transparent; color: var(--app-text-secondary); font: inherit; font-size: var(--app-font-xs); cursor: pointer; }
.shortcut-dialog > footer { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 18px; border-top: 1px solid var(--app-border-subtle); }
.primary-button:disabled { opacity: .45; cursor: default; }
.conflict-dialog { padding: 18px; }
.conflict-dialog header { display: flex; align-items: center; gap: 9px; color: var(--app-color-warning); }
.conflict-dialog p { margin: 12px 0 18px; color: var(--app-text-secondary); font-size: var(--app-font-sm); line-height: 1.6; }
.conflict-actions { display: flex; justify-content: flex-end; gap: 8px; }
.conflict-revisions{display:grid;gap:5px;margin:0 0 16px;padding:9px 10px;border:1px solid var(--app-border-subtle);border-radius: var(--app-radius-md);background:var(--app-bg-input)}.conflict-revisions div{display:flex;align-items:center;justify-content:space-between;gap:16px}.conflict-revisions dt{color:var(--app-text-secondary);font-size: var(--app-font-interface)}.conflict-revisions dd{margin:0;color:var(--app-text-regular);font-family:var(--app-font-mono);font-size:var(--app-font-interface)}
.history-dialog{width:min(620px,calc(100vw - 32px));max-height:min(680px,calc(100vh - 32px));display:flex;flex-direction:column;overflow:hidden;border:1px solid var(--app-overlay-border);border-radius: var(--app-radius-lg);background:var(--app-bg-raised);box-shadow:var(--app-shadow-lg)}
.history-dialog>header{display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-bottom:1px solid var(--app-border-subtle)}
.history-dialog h2{margin:0;color:var(--app-text-primary);font-size: var(--app-font-page-title)}.history-dialog header p{margin:3px 0 0;color:var(--app-text-secondary);font-size: var(--app-font-caption)}
.history-body{min-height:160px;overflow:auto;padding:10px}.history-empty{display:grid;min-height:140px;place-items:center;padding:20px;color:var(--app-text-secondary);font-size: var(--app-font-compact);text-align:center}
.history-list{display:flex;flex-direction:column;gap:2px;margin:0;padding:0;list-style:none}.history-list li{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:52px;padding:8px 10px;border-radius: var(--app-radius-md)}.history-list li:hover{background:var(--app-bg-hover)}
.history-list li>div{min-width:0;display:flex;flex-direction:column;gap:3px}.history-list strong{color:var(--app-text-regular);font-size: var(--app-font-compact);font-weight:500}.history-list span{color:var(--app-text-muted);font-size: var(--app-font-caption)}.history-list button{height: var(--app-control-compact);flex:0 0 auto;padding:0 10px;border:1px solid var(--app-border-default);border-radius: var(--app-radius-sm);background:var(--app-bg-input);color:var(--app-text-regular);cursor:pointer}.history-list button:hover:not(:disabled){border-color:var(--app-color-primary);color:var(--app-text-primary)}
.delete-program-dialog > header { padding: 16px 18px; border-bottom: 1px solid var(--app-border-subtle); }
.delete-program-dialog header p { margin: 5px 0 0; color: var(--app-text-secondary); font-size: var(--app-font-sm); line-height: 1.55; }
.delete-program-dialog > footer { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 18px; border-top: 1px solid var(--app-border-subtle); }
.danger-confirm-button { height: var(--app-control-default); padding: 0 12px; border: 1px solid var(--app-color-danger); border-radius: var(--app-radius-sm); background: var(--app-color-danger); color: white; font: inherit; cursor: pointer; }
.danger-confirm-button:disabled { cursor: default; opacity: .45; }
.lifecycle-reference-list { max-height: min(320px, 44vh); margin: 0; padding: 8px; overflow: auto; list-style: none; }
.lifecycle-reference-list button, .lifecycle-reference-list li > div { width: 100%; min-height: 48px; display: flex; flex-direction: column; align-items: flex-start; justify-content: center; gap: 3px; padding: 7px 10px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-regular); font: inherit; text-align: start; }
.lifecycle-reference-list button { cursor: pointer; }
.lifecycle-reference-list button:hover, .lifecycle-reference-list button:focus-visible { background: var(--app-bg-hover); color: var(--app-text-primary); outline: 0; box-shadow: var(--focus-ring); }
.lifecycle-reference-list small { color: var(--app-text-secondary); font-size: var(--app-font-xs); }

@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 1099px) {
    .workspace-sidebar-resizer, .program-sidebar-resizer { display: none; }
    .program-workspace { grid-template-columns: minmax(0, 1fr); }
    .function-library-shell { display: none; }
    .function-library-shell.narrow-drawer-open {
        position: absolute;
        z-index: 62;
        inset: 0 auto 0 0;
        width: min(340px, calc(100% - 44px));
        display: block;
        border-inline-end: 1px solid var(--app-overlay-border);
        background: var(--app-bg-sidebar);
        box-shadow: var(--app-shadow-lg);
    }
    .workspace-sidebar-scrim {
        position: absolute;
        z-index: 60;
        inset: 0;
        display: block;
        width: 100%;
        height: 100%;
        padding: 0;
        border: 0;
        background: rgba(4, 4, 3, .62);
        cursor: default;
    }
    .function-library-drawer-close {
        position: absolute;
        z-index: 2;
        inset: 6px 6px auto auto;
        display: grid;
        background: var(--app-bg-sidebar);
    }
    .function-library-shell.narrow-drawer-open :deep(.vnext-pane-header) { padding-right: 42px; }
    .main-stage :deep(.resource-workspace),
    .main-stage :deep(.variable-workspace),
    .main-stage :deep(.target-workspace),
    .main-stage :deep(.replay-workspace),
    .main-stage :deep(.extension-workspace),
    .main-stage :deep(.schedule-workspace),
    .main-stage :deep(.player-workspace) { position: relative; grid-template-columns: minmax(0, 1fr) !important; }
    .main-stage.sidebar-overlay-open :deep(.resource-tree),
    .main-stage.sidebar-overlay-open :deep(.variable-sidebar),
    .main-stage.sidebar-overlay-open :deep(.target-sidebar),
    .main-stage.sidebar-overlay-open :deep(.replay-sessions),
    .main-stage.sidebar-overlay-open :deep(.package-pane),
    .main-stage.sidebar-overlay-open :deep(.schedule-nav),
    .main-stage.sidebar-overlay-open :deep(.player-outline) {
        position: absolute;
        z-index: 62;
        inset: 0 auto 0 0;
        width: min(340px, calc(100% - 44px));
        display: flex !important;
        flex-direction: column;
        border-inline-end: 1px solid var(--app-overlay-border);
        background: var(--app-bg-sidebar);
        box-shadow: var(--app-shadow-lg);
    }
}
@media (max-width: 960px) { .brand strong { display: none; } }
@media (max-width: 820px) {
    .titlebar { grid-template-columns: auto auto minmax(0, 1fr) auto; gap: 6px; padding-inline: 7px; }
    .title-actions { gap: 3px; }
}
@media (max-width: 620px) {
    .toolbar-button { width: var(--app-control-compact); padding: 0; }
    .command-search-button { min-width: var(--app-control-compact); }
    .toolbar-button .action-label { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
}
@media (max-width: 760px) {
    .title-actions > .toolbar-button[aria-label="检查项目"] { display: none; }
}
.variable-picker-list > button { min-height: var(--app-list-row-rich); padding-block: 5px; }
.shortcut-row { min-height: var(--app-list-row-rich); grid-template-columns: minmax(0, 1fr) 180px 44px; }
.history-list li { min-height: var(--app-list-row-rich); padding-block: 5px; }
.lifecycle-reference-list button,
.lifecycle-reference-list li > div { min-height: var(--app-list-row-rich); padding-block: 5px; }
</style>
