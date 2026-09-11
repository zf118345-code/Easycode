<template>
    <section :class="['schedule-workspace', { 'detail-panel-collapsed': !detailVisible }]" aria-label="计划与实例中心" data-testid="schedule-workspace">
        <VNextNavigationPane class="schedule-nav" aria-label="计划中心分类">
            <VNextPaneHeader title="运行中心" meta="当前用户" />
            <nav class="app-navigation-list">
                <VNextNavigationItem v-for="item in navigation" :key="item.id" :selected="section === item.id" @click="selectSection(item.id)">
                    <component :is="item.icon" :size="15" aria-hidden="true" />
                    <span>{{ item.label }}</span><em>{{ item.count }}</em>
                </VNextNavigationItem>
            </nav>
            <div class="agent-state" :class="{ blocked: !hub?.wake_agent.installed }">
                <span><Power :size="14" aria-hidden="true" />{{ hub?.wake_agent.installed ? '计划 Agent 已启用' : '计划 Agent 未启用' }}</span>
                <p>{{ hub?.wake_agent.installed ? 'IDE 和单项目 Player 关闭后仍可触发。' : '计划可以保存，但关闭应用后不会自动唤醒。' }}</p>
                <button v-if="hub?.wake_agent.available && !hub?.wake_agent.installed" type="button" :disabled="busy" @click="installAgent">启用自动唤醒</button>
            </div>
        </VNextNavigationPane>

        <main class="schedule-main">
            <VNextPaneHeader class="workspace-heading" role="workspace" :title="heading" :description="subheading" :heading-level="1">
                <template #actions><div class="heading-actions">
                    <VNextIconButton label="重新载入计划中心" title="重新载入" :disabled="busy" @click="loadAll"><RefreshCw /></VNextIconButton>
                    <VNextButton v-if="section === 'plans' && planView === 'plans'" class="primary" tone="primary" appearance="solid" size="compact" :disabled="busy || !batches.length" @click="newPlan"><template #icon><Plus /></template>新建计划</VNextButton>
                    <VNextButton v-else-if="section === 'batches'" class="primary" tone="primary" appearance="solid" size="compact" :disabled="busy || !instancesWithProfiles.length" @click="newBatch"><template #icon><Plus /></template>新建批次</VNextButton>
                    <VNextButton v-else-if="section === 'triggers'" class="primary" tone="primary" appearance="solid" size="compact" :disabled="busy" @click="newTrigger"><template #icon><Plus /></template>新建启动方式</VNextButton>
                    <template v-else-if="section === 'instances'">
                        <VNextIconButton :label="lan?.running ? '停止局域网监听' : '启动局域网监听'" :disabled="busy" @click="toggleLanListener"><Radio /></VNextIconButton>
                        <VNextButton class="primary" tone="primary" appearance="solid" size="compact" :disabled="busy" @click="openPairing('offer')"><template #icon><QrCode /></template>配对设备</VNextButton>
                    </template>
                </div></template>
            </VNextPaneHeader>

            <div v-if="section === 'plans'" class="view-switch" role="tablist" aria-label="计划视图">
                <button v-for="view in planViews" :key="view.id" type="button" role="tab" :aria-selected="planView === view.id" :class="{ active: planView === view.id }" @click="planView = view.id">
                    {{ view.label }}<span>{{ view.count }}</span>
                </button>
            </div>

            <VNextWorkspaceState v-if="loading" class="center-state" kind="loading" title="正在读取本机计划" description="正在验证安装记录和运行方案。"><template #icon><LoaderCircle class="spin" :size="20" /></template></VNextWorkspaceState>
            <VNextWorkspaceState v-else-if="error" class="center-state error" kind="error" title="计划中心暂时不可用" :description="error"><template #icon><CircleAlert :size="20" /></template><template #actions><VNextButton size="compact" @click="loadAll">重新载入</VNextButton></template></VNextWorkspaceState>

            <template v-else>
                <div v-if="section === 'plans' && planView === 'plans'" class="object-list" role="listbox" aria-label="运行计划">
                    <button v-for="plan in plans" :key="plan.schedule_id" type="button" role="option" :aria-selected="selectedPlanId === plan.schedule_id" :class="{ selected: selectedPlanId === plan.schedule_id }" @click="selectPlan(plan)">
                        <span class="object-icon"><CalendarClock :size="15" /></span>
                        <span class="object-copy"><strong>{{ plan.name }}</strong><small>{{ triggerSummary(plan) }}</small></span>
                        <span class="object-state" :class="plan.enabled ? 'ready' : 'muted'">{{ plan.enabled ? '启用' : '暂停' }}</span>
                        <time>{{ plan.next_due_at ? formatTime(plan.next_due_at) : '无下次运行' }}</time>
                    </button>
                    <VNextWorkspaceState v-if="!plans.length" class="list-empty" kind="empty" title="还没有运行计划" :description="batches.length ? '从一个批次创建单次、每日或固定间隔计划。' : '先创建批次，明确要运行的实例与方案。'"><template #icon><CalendarClock :size="24" /></template><template #actions><VNextButton v-if="batches.length" size="compact" @click="newPlan">新建计划</VNextButton><VNextButton v-else size="compact" @click="section = 'batches'">前往批次</VNextButton></template></VNextWorkspaceState>
                </div>

                <div v-else-if="section === 'plans' && planView === 'history'" class="object-list history-list" role="listbox" aria-label="计划运行历史">
                    <button v-for="item in occurrences" :key="item.occurrence_id" type="button" role="option" :aria-selected="selectedOccurrenceId === item.occurrence_id" :class="{ selected: selectedOccurrenceId === item.occurrence_id }" @click="selectOccurrence(item)">
                        <span class="object-icon"><History :size="15" /></span>
                        <span class="object-copy"><strong>{{ planName(item.schedule_id) }}</strong><small>{{ formatTime(item.scheduled_at) }} · {{ sourceLabel(item.trigger_source) }}</small></span>
                        <span class="object-state" :class="statusTone(item.status)">{{ statusLabel(item.status) }}</span>
                    </button>
                    <VNextWorkspaceState v-if="!occurrences.length" class="list-empty" kind="empty" title="还没有触发记录" description="计划到期或手动检查后，真实批次结果会出现在这里。"><template #icon><History :size="24" /></template></VNextWorkspaceState>
                </div>

                <div v-else-if="section === 'plans' && planView === 'diagnostics'" class="diagnostic-list" aria-label="计划诊断">
                    <article v-for="item in diagnostics" :key="item.sequence">
                        <span class="diagnostic-level" :class="item.level"><CircleAlert v-if="item.level === 'error'" :size="14" /><Info v-else :size="14" /></span>
                        <div><strong>{{ eventLabel(item.event_type) }}</strong><p>{{ diagnosticSummary(item) }}</p><small>{{ formatTime(item.recorded_at) }} · #{{ item.sequence }}</small></div>
                    </article>
                    <VNextWorkspaceState v-if="!diagnostics.length" class="list-empty" kind="empty" title="没有计划诊断" description="这里只显示真实调度事件，不生成占位日志。"><template #icon><FileCheck2 :size="24" /></template></VNextWorkspaceState>
                </div>

                <div v-else-if="section === 'batches'" class="object-list" role="listbox" aria-label="运行批次">
                    <button v-for="batch in batches" :key="batch.batch_id" type="button" role="option" :aria-selected="selectedBatchId === batch.batch_id" :class="{ selected: selectedBatchId === batch.batch_id }" @click="selectBatch(batch)">
                        <span class="object-icon"><Layers3 :size="15" /></span>
                        <span class="object-copy"><strong>{{ batch.name }}</strong><small>{{ batch.entries.length }} 个条目 · {{ batch.dispatch_mode === 'staggered' ? '确定性错峰' : '跨实例同时派发' }}</small></span>
                        <span class="object-state ready">rev {{ batch.revision }}</span>
                    </button>
                    <VNextWorkspaceState v-if="!batches.length" class="list-empty" kind="empty" title="还没有可复用批次" :description="instancesWithProfiles.length ? '把一个或多个实例与方案整理为批次，再交给计划使用。' : '先登记签名 Player，并在 Player 中保存至少一个运行方案。'"><template #icon><Layers3 :size="24" /></template><template #actions><VNextButton v-if="instancesWithProfiles.length" size="compact" @click="newBatch">新建批次</VNextButton><VNextButton v-else size="compact" @click="section = 'instances'">前往实例</VNextButton></template></VNextWorkspaceState>
                </div>

                <div v-else-if="section === 'instances'" class="instance-list" role="listbox" aria-label="Player 实例与局域网设备">
                    <VNextInlineNotice v-if="lanError" class="lan-inline-error" tone="error" :message="lanError"><template #actions><VNextButton appearance="ghost" size="compact" @click="refreshLan">重试</VNextButton></template></VNextInlineNotice>
                    <section class="instance-group">
                        <header><div><strong>本机实例</strong><small>{{ instances.length }} 个</small></div><span><ShieldCheck :size="12" />当前用户</span></header>
                        <template v-for="installation in installations" :key="installation.installation_id">
                            <div class="installation-label"><span>{{ installation.display_name }}</span><small>{{ installation.release_id }} · 签名已验证</small></div>
                            <button v-for="instance in installation.instances" :key="instance.instance_id" type="button" role="option" :aria-selected="selectedInstanceId === instance.instance_id" :class="{ selected: selectedInstanceId === instance.instance_id }" @click="selectInstance(instance)">
                                <span class="object-icon"><MonitorCog :size="15" /></span>
                                <span class="object-copy"><strong>{{ instance.display_name }}</strong><small>{{ instance.profiles?.length || 0 }} 套方案 · {{ compactPath(instance.data_root) }}</small></span>
                                <span class="object-state" :class="instance.status === 'ready' ? 'ready' : 'danger'">{{ instance.status === 'ready' ? '可调度' : '需检查' }}</span>
                            </button>
                        </template>
                        <div v-if="!installations.length" class="compact-empty"><PackageCheck :size="18" /><span>尚未登记签名 Player</span><button type="button" @click="openInstallForm">登记 Player</button></div>
                    </section>

                    <section class="instance-group">
                        <header><div><strong>已配对设备</strong><small>{{ lan?.paired_devices.length || 0 }} 台</small></div><span :class="lan?.running ? 'ready' : 'muted'"><component :is="lan?.running ? Wifi : WifiOff" :size="12" />{{ lan?.running ? `监听 ${lan.port}` : '监听已停止' }}</span></header>
                        <button v-for="peer in lan?.paired_devices || []" :key="peer.host_id" type="button" role="option" :aria-selected="selectedPeerId === peer.host_id" :class="{ selected: selectedPeerId === peer.host_id }" @click="selectPeer(peer)">
                            <span class="object-icon"><Wifi :size="15" /></span>
                            <span class="object-copy"><strong>{{ peer.device_name }}</strong><small>{{ peerInstanceCount(peer.host_id) }} 个已知实例 · {{ permissionSummary(peer.remote_permissions) }}</small></span>
                            <span class="object-state" :class="peer.connection_state === 'online' ? 'ready' : peer.connection_state === 'offline' ? 'danger' : 'muted'">{{ peer.connection_state === 'online' ? '在线' : peer.connection_state === 'offline' ? '离线' : '未探测' }}</span>
                        </button>
                        <div v-if="!lan?.paired_devices.length" class="compact-empty"><Link2 :size="18" /><span>还没有已配对电脑</span><button type="button" @click="openPairing('offer')">开始配对</button></div>
                    </section>

                    <section v-if="lan?.pairing_sessions.some(item => item.pending.length)" class="instance-group">
                        <header><div><strong>等待确认</strong><small>需要在本机核对指纹</small></div><span class="active">短期会话</span></header>
                        <button v-for="pending in lan.pairing_sessions.flatMap(item => item.pending)" :key="pending.pending_id" type="button" role="option" :aria-selected="selectedPendingId === pending.pending_id" :class="{ selected: selectedPendingId === pending.pending_id }" @click="selectPending(pending)">
                            <span class="object-icon"><ShieldCheck :size="15" /></span>
                            <span class="object-copy"><strong>{{ pending.device_name }}</strong><small>{{ pending.fingerprint }}</small></span>
                            <span class="object-state active">待确认</span>
                        </button>
                    </section>
                </div>

                <div v-else class="object-list" role="listbox" aria-label="项目启动方式">
                    <button v-for="trigger in triggers" :key="trigger.trigger_id" type="button" role="option" :aria-selected="triggerDraft?.trigger_id === trigger.trigger_id" :class="{ selected: triggerDraft?.trigger_id === trigger.trigger_id }" @click="selectTrigger(trigger)">
                        <span class="object-icon"><Zap :size="15" /></span>
                        <span class="object-copy"><strong>{{ trigger.display_name }}</strong><small>{{ triggerKindLabel(trigger) }} · {{ triggerEntryLabel(trigger) }}</small></span>
                        <span class="object-state" :class="trigger.enabled ? 'ready' : 'muted'">{{ trigger.enabled ? '启用' : '关闭' }}</span>
                    </button>
                    <VNextWorkspaceState v-if="!triggers.length" class="list-empty" kind="empty" title="还没有启动方式" description="为现有项目函数添加全局快捷键、应用、文件或系统事件；不会复制脚本。"><template #icon><Zap :size="24" /></template><template #actions><VNextButton size="compact" @click="newTrigger">新建启动方式</VNextButton></template></VNextWorkspaceState>
                </div>
            </template>
        </main>

        <div v-if="detailOverlayOpen" class="schedule-inspector-scrim" aria-hidden="true" @click="closeInspector"></div>
        <aside
            v-if="detailVisible"
            ref="scheduleInspectorElement"
            class="schedule-inspector app-inspector-form"
            :class="{ 'is-drawer': detailAsOverlay }"
            :role="detailAsOverlay ? 'dialog' : undefined"
            :aria-modal="detailAsOverlay ? 'true' : undefined"
            aria-label="计划中心检查器"
            tabindex="-1"
            @keydown="trapDialogFocus"
            @keydown.esc.stop="closeInspector"
        >
            <VNextPaneHeader role="inspector" title="检查器" :meta="inspectorTitle" />
            <VNextIconButton v-if="detailAsOverlay" class="inspector-close" label="关闭计划中心检查器" title="关闭检查器" @click="closeInspector"><X /></VNextIconButton>

            <form v-if="section === 'plans' && planView === 'plans' && planDraft" class="inspector-form" @submit.prevent="savePlan">
                <div class="form-scroll app-inspector-body">
                    <label class="field"><span>计划名称</span><input v-model.trim="planDraft.name" maxlength="160" autocomplete="off" /></label>
                    <fieldset class="choice-row"><legend>触发方式</legend><div class="choice-options"><label v-for="option in triggerOptions" :key="option.id" :class="{ active: triggerType === option.id }"><input v-model="triggerType" type="radio" :value="option.id" @change="resetTrigger" /><span>{{ option.label }}</span></label></div></fieldset>
                    <label v-if="triggerType === 'once'" class="field"><span>执行时间</span><input v-model="triggerValue" type="datetime-local" /></label>
                    <label v-else-if="triggerType === 'daily'" class="field"><span>每天时间</span><input v-model="triggerValue" type="time" step="1" /></label>
                    <template v-else><label class="field"><span>首次时间</span><input v-model="triggerAnchor" type="datetime-local" /></label><label class="field"><span>间隔（分）</span><input v-model.number="intervalMinutes" type="number" min="1" max="525600" /></label></template>
                    <label class="field"><span>时区</span><input v-model.trim="planDraft.timezone_id" maxlength="128" placeholder="例如：Asia/Shanghai" /></label>
                    <label class="field"><span>运行批次</span><select v-model="planBatchId"><option value="">{{ planDraft.schedule_id ? '保留当前条目快照' : '请选择批次' }}</option><option v-for="batch in batches" :key="batch.batch_id" :value="batch.batch_id">{{ batch.name }}（{{ batch.entries.length }} 项）</option></select><small>保存时复制批次条目；以后修改批次不会静默改写既有计划。</small></label>
                    <details><summary>错过与重叠策略</summary><label class="field"><span>错过触发</span><select v-model="planDraft.misfire_policy"><option value="skip">记录并跳过</option><option value="catch_up_once">窗口内合并补跑一次</option></select></label><label v-if="planDraft.misfire_policy === 'catch_up_once'" class="field"><span>最大迟到（分）</span><input v-model.number="latenessMinutes" type="number" min="1" max="525600" /></label><label class="field"><span>上次仍在运行</span><select v-model="planDraft.overlap_policy"><option value="skip">跳过本次</option><option value="queue_once">最多排队一次</option></select></label></details>
                    <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
                </div>
                <footer><button v-if="planDraft.schedule_id" type="button" :disabled="busy" @click="togglePlan">{{ planDraft.enabled ? '暂停计划' : '启用计划' }}</button><button v-if="planDraft.schedule_id" type="button" class="danger-text" :disabled="busy" @click="confirmDelete = 'plan'">删除</button><button type="submit" class="primary" :disabled="busy || !canSavePlan">{{ planDraft.schedule_id ? '保存修改' : '创建计划' }}</button></footer>
            </form>

            <div v-else-if="section === 'plans' && planView === 'history' && selectedOccurrence" class="inspector-detail">
                <dl><div><dt>计划</dt><dd>{{ planName(selectedOccurrence.schedule_id) }}</dd></div><div><dt>计划时间</dt><dd>{{ formatTime(selectedOccurrence.scheduled_at) }}</dd></div><div><dt>实际发现</dt><dd>{{ formatTime(selectedOccurrence.discovered_at) }}</dd></div><div><dt>批次状态</dt><dd>{{ statusLabel(selectedOccurrence.status) }}</dd></div></dl>
                <h2>条目结果</h2><ol class="dispatch-list"><li v-for="item in selectedDispatches" :key="item.dispatch_id"><span :class="statusTone(item.status)">{{ statusLabel(item.status) }}</span><div><strong>{{ instanceName(item.instance_id) }}</strong><small>{{ item.run_id || item.error_id || '等待接纳' }}</small><p v-if="item.error_message">{{ item.error_message }}</p></div></li></ol>
            </div>

            <VNextWorkspaceState v-else-if="section === 'plans' && planView === 'diagnostics'" class="inspector-empty" compact kind="selection" title="结构化调度诊断" description="选择一条诊断后查看关联状态与脱敏原因。"><template #icon><FileCheck2 :size="22" /></template></VNextWorkspaceState>

            <form v-else-if="section === 'batches' && batchDraft" class="inspector-form" @submit.prevent="saveBatch">
                <div class="form-scroll app-inspector-body"><label class="field"><span>批次名称</span><input v-model.trim="batchDraft.name" maxlength="160" /></label><label class="field"><span>跨实例派发</span><select v-model="batchDraft.dispatch_mode" @change="normalizeOffsets"><option value="simultaneous">同时派发</option><option value="staggered">按条目错峰</option></select></label><section class="entry-editor"><header><h2>批次条目</h2><button type="button" class="app-inline-action" :disabled="!instancesWithProfiles.length" @click="addBatchEntry"><Plus :size="13" aria-hidden="true" /><span>添加</span></button></header><article v-for="(entry, index) in batchDraft.entries" :key="entry.entry_id || index"><div class="entry-title"><strong>条目 {{ index + 1 }}</strong><button type="button" aria-label="删除条目" @click="batchDraft.entries.splice(index, 1)"><Trash2 :size="13" /></button></div><label class="field"><span>实例</span><select :value="entryTargetKey(entry)" @change="changeEntryInstance(entry, $event)"><option v-for="instance in instancesWithProfiles" :key="instance.key" :value="instance.key">{{ instance.remote ? '局域网 · ' : '本机 · ' }}{{ instance.display_name }}</option></select></label><label class="field"><span>运行方案</span><select v-model="entry.profile_id"><option v-for="profile in profilesFor(entry.host_id, entry.instance_id)" :key="profile.profile_id" :value="profile.profile_id">{{ profile.name }}</option></select></label><label v-if="batchDraft.dispatch_mode === 'staggered'" class="field"><span>启动偏移（秒）</span><input v-model.number="entry.start_offset_seconds" type="number" min="0" max="31536000" /></label></article></section><p v-if="formError" class="form-error" role="alert">{{ formError }}</p></div>
                <footer><button v-if="batchDraft.batch_id" type="button" class="danger-text" :disabled="busy" @click="confirmDelete = 'batch'">删除</button><button type="submit" class="primary" :disabled="busy || !batchDraft.name || !batchDraft.entries.length">{{ batchDraft.batch_id ? '保存批次' : '创建批次' }}</button></footer>
            </form>

            <form v-else-if="section === 'triggers' && triggerDraft" class="inspector-form" @submit.prevent="saveTrigger">
                <div class="form-scroll app-inspector-body">
                    <label class="field"><span>名称</span><input v-model.trim="triggerDraft.display_name" maxlength="160" /></label>
                    <label class="field"><span>触发事件</span><select v-model="triggerDraft.kind" @change="resetTriggerDraftConfig"><option value="global_hotkey">全局快捷键</option><option value="application">应用状态</option><option value="filesystem">文件或目录变化</option><option value="system">系统启动或登录</option></select></label>
                    <label v-if="triggerDraft.kind === 'global_hotkey'" class="field"><span>快捷键</span><input v-model.trim="triggerDraft.kind_config.shortcut" placeholder="例如：Ctrl+Alt+R" /></label>
                    <template v-else-if="triggerDraft.kind === 'application'"><label class="field"><span>进程名</span><input v-model.trim="triggerDraft.kind_config.process_name" placeholder="例如：notepad.exe" /></label><label class="field"><span>事件</span><select v-model="triggerDraft.kind_config.event"><option value="start">应用启动</option><option value="exit">应用退出</option><option value="focus">获得焦点</option></select></label></template>
                    <label v-else-if="triggerDraft.kind === 'filesystem'" class="field"><span>文件或目录</span><input v-model.trim="triggerDraft.kind_config.path" placeholder="完整路径" /></label>
                    <label v-else class="field"><span>系统事件</span><select v-model="triggerDraft.kind_config.event"><option value="system_start">系统启动</option><option value="user_login">用户登录</option></select></label>
                    <label class="field"><span>运行函数</span><select v-model="triggerDraft.entry_function_id"><option value="">请选择项目函数</option><option v-for="program in triggerPrograms" :key="program.function_id" :value="program.function_id">{{ program.display_name }}</option></select></label>
                    <label class="field"><span>运行目标</span><select v-model="triggerDraft.target_id"><option value="">无操作目标</option><option v-for="target in workspaceStore.targets" :key="target.target_id" :value="target.target_id">{{ target.name }}</option></select></label>
                    <label class="field"><span>并发处理</span><select v-model="triggerDraft.concurrency_policy"><option value="skip_if_running">运行中则跳过</option><option value="queue_one">最多排队一次</option><option value="parallel">允许并行</option></select></label>
                    <details><summary>防抖与冷却</summary><label class="field"><span>防抖（毫秒）</span><input v-model.number="triggerDraft.debounce_ms" type="number" min="0" /></label><label class="field"><span>冷却（毫秒）</span><input v-model.number="triggerDraft.cooldown_ms" type="number" min="0" /></label></details>
                    <label class="trigger-enabled"><input v-model="triggerDraft.enabled" type="checkbox" /><span>启用此启动方式</span></label>
                    <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
                </div>
                <footer><VNextButton v-if="triggerDraft.trigger_id" tone="danger" appearance="ghost" :disabled="busy" @click="deleteTrigger">删除</VNextButton><VNextButton tone="primary" appearance="solid" type="submit" :loading="busy" :disabled="!triggerDraft.display_name || !triggerDraft.entry_function_id">保存</VNextButton></footer>
            </form>

            <div v-else-if="section === 'instances' && selectedInstance" class="inspector-detail">
                <dl><div><dt>产品</dt><dd>{{ installationName(selectedInstance.product_id) }}</dd></div><div><dt>实例</dt><dd>{{ selectedInstance.display_name }}</dd></div><div><dt>运行方案</dt><dd>{{ selectedInstance.profiles?.length || 0 }} 套</dd></div><div><dt>数据目录</dt><dd class="path">{{ selectedInstance.data_root }}</dd></div></dl>
                <h2>可调度方案</h2><ul class="profile-list"><li v-for="profile in selectedInstance.profiles || []" :key="profile.profile_id"><div><strong>{{ profile.name }}</strong><small>{{ profile.target_id ? `目标 ${profile.target_id}` : '无操作目标' }}</small></div><span>rev {{ profile.revision }}</span></li></ul>
                <button type="button" class="app-inline-action open-player" :disabled="busy" @click="openInstancePlayer"><MonitorCog :size="14" aria-hidden="true" /><span>打开 Player 控制台</span></button>
                <section v-if="productReleases.length > 1" class="instance-action"><label class="field"><span>当前发布</span><select v-model="selectedReleaseId"><option v-for="release in productReleases" :key="release.installation_id" :value="release.installation_id">{{ release.release_id }}</option></select><small>可以切换同一作者签名产品的已验证发布，用于升级或回滚。</small></label><button type="button" class="app-inline-action" :disabled="busy || selectedReleaseId === selectedInstance.installation_id" @click="bindSelectedRelease"><RefreshCw :size="14" aria-hidden="true" /><span>切换发布</span></button></section>
                <section class="instance-action"><label class="field"><span>新实例名称</span><input v-model.trim="newInstanceName" maxlength="120" placeholder="例如：小号 2" /></label><button type="button" class="app-inline-action" :disabled="busy || !newInstanceName" @click="createSiblingInstance"><Plus :size="14" aria-hidden="true" /><span>创建隔离实例</span></button></section>
                <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
                <div v-if="selectedInstance.status !== 'ready'" class="inline-error" role="alert"><CircleAlert :size="15" /><span>{{ selectedInstance.error_message || '实例需要检查' }}</span></div>
                <section class="truth-box"><strong>本机可信实例</strong><p>同一用户下由 Player Hub 串行接纳。远程计划只会使用已配对设备单独授予的远程启动权限；普通消息始终不能启动任务。</p></section>
            </div>

            <div v-else-if="section === 'instances' && selectedPeer" class="inspector-detail device-inspector">
                <dl><div><dt>设备</dt><dd>{{ selectedPeer.device_name }} · {{ selectedPeer.platform }}</dd></div><div><dt>连接状态</dt><dd>{{ selectedPeer.connection_state === 'online' ? '在线' : selectedPeer.connection_state === 'offline' ? '离线' : '尚未探测' }}{{ selectedPeer.last_error_id ? ` · ${selectedPeer.last_error_id}` : '' }}</dd></div><div><dt>固定指纹</dt><dd class="path">{{ selectedPeer.fingerprint }}</dd></div><div><dt>局域网地址</dt><dd class="path">{{ selectedPeer.addresses.join(', ') }}:{{ selectedPeer.port }}</dd></div></dl>
                <h2>此设备可以对本机执行</h2>
                <div class="permission-list">
                    <label><input v-model="peerPermissions.messages" type="checkbox" /><span><MessageSquare :size="15" /><strong>普通消息</strong><small>只交付与已读，不代表业务完成。</small></span></label>
                    <label><input v-model="peerPermissions.status" type="checkbox" /><span><Eye :size="15" /><strong>查看状态</strong><small>读取实例目录与接纳状态。</small></span></label>
                    <label><input v-model="peerPermissions.remote_start" type="checkbox" /><span><Play :size="15" /><strong>远程启动</strong><small>独立特权命令；配对不会自动开启。</small></span></label>
                </div>
                <button type="button" class="primary full-action" :disabled="busy" @click="savePeerPermissions">保存本机授予</button>
                <h2>对方授予本机</h2><p class="permission-copy">{{ permissionSummary(selectedPeer.remote_permissions) }}</p>
                <div class="device-actions"><button type="button" :disabled="busy || !selectedPeer.remote_permissions.status" @click="refreshPeer"><RefreshCw :size="13" />刷新状态</button><button type="button" class="danger-text" :disabled="busy" @click="confirmRevokePeerId = selectedPeer.host_id"><Unplug :size="13" />撤销设备</button></div>
                <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
                <details class="network-diagnostics"><summary>最近网络诊断</summary><ol><li v-for="item in lanDiagnostics.filter(row => row.peer_host_id === selectedPeer?.host_id).slice(0, 8)" :key="item.sequence"><strong>{{ item.event_type }}</strong><small>{{ item.error_id || '完成' }} · {{ formatTime(item.recorded_at) }}</small></li></ol><p v-if="!lanDiagnostics.some(row => row.peer_host_id === selectedPeer?.host_id)">没有此设备的诊断事件。</p></details>
            </div>

            <form v-else-if="section === 'instances' && selectedPending" class="inspector-form" @submit.prevent="confirmPendingPairing">
                <div class="form-scroll app-inspector-body"><div class="pair-identity"><ShieldCheck :size="22" /><strong>{{ selectedPending.device_name }}</strong><p>请在两台电脑上核对同一稳定公钥指纹。</p><code>{{ selectedPending.fingerprint }}</code></div><h2>确认后授予</h2><div class="permission-list"><label><input v-model="peerPermissions.messages" type="checkbox" /><span><MessageSquare :size="15" /><strong>普通消息</strong><small>允许此设备发送结构化消息。</small></span></label><label><input v-model="peerPermissions.status" type="checkbox" /><span><Eye :size="15" /><strong>查看状态</strong><small>允许读取本机实例目录。</small></span></label><label><input v-model="peerPermissions.remote_start" type="checkbox" /><span><Play :size="15" /><strong>远程启动</strong><small>默认关闭，按需单独授予。</small></span></label></div><p v-if="formError" class="form-error" role="alert">{{ formError }}</p></div>
                <footer><button type="button" @click="selectedPendingId = ''">暂不确认</button><button type="submit" class="primary" :disabled="busy">核对无误并配对</button></footer>
            </form>

            <div v-else-if="section === 'instances' && showPairing" class="inspector-form pairing-panel">
                <div class="pair-tabs" role="tablist" aria-label="配对方式"><button type="button" role="tab" :aria-selected="pairMode === 'offer'" :class="{ active: pairMode === 'offer' }" @click="pairMode = 'offer'">让对方连接</button><button type="button" role="tab" :aria-selected="pairMode === 'join'" :class="{ active: pairMode === 'join' }" @click="pairMode = 'join'">连接另一台电脑</button></div>
                <div v-if="pairMode === 'offer'" class="form-scroll app-inspector-body">
                    <div v-if="pairingOffer" class="pair-offer"><img v-if="pairingQrUrl" :src="pairingQrUrl" :alt="`配对二维码，短期码 ${pairingOffer.code}`" /><span>短期配对码</span><button type="button" class="pair-code" title="复制配对码" @click="copyPairingCode"><code>{{ pairingOffer.code }}</code><Copy :size="14" /></button><small>有效至 {{ formatTime(pairingOffer.expires_at) }}</small><p>{{ pairingOffer.addresses.join(' / ') }}:{{ pairingOffer.port }}</p></div>
                    <div v-else class="compact-empty"><QrCode :size="20" /><span>创建 5 分钟短期码后，对方才能发起配对。</span><button type="button" :disabled="busy" @click="createPairingOffer">创建短期码</button></div>
                    <p class="pair-note">收到请求后会出现在中栏“等待确认”。必须核对指纹并逐项授予权限；远程启动默认关闭。</p>
                    <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
                </div>
                <div v-else class="form-scroll app-inspector-body">
                    <label class="field"><span>二维码内容</span><textarea v-model.trim="joinQrPayload" rows="4" placeholder="粘贴另一台电脑显示的二维码内容；也可在下方手工输入地址。" /></label>
                    <div class="pair-divider"><span>或使用手工地址</span></div>
                    <label class="field compound-address-field"><span>局域网地址</span><span class="compound-address-control"><input v-model.trim="joinAddress" aria-label="局域网地址" maxlength="255" placeholder="192.168.1.20" /><span aria-hidden="true">:</span><input v-model.number="joinPort" class="port-control" aria-label="端口" type="number" min="1" max="65535" /></span></label>
                    <label class="field"><span>会话 ID</span><input v-model.trim="joinSessionId" maxlength="128" /></label><label class="field"><span>短期码</span><input v-model.trim="joinCode" maxlength="32" placeholder="1234-5678" /></label>
                    <div class="discovery-row"><button type="button" class="app-inline-action" :disabled="busy" title="发现失败时仍可手工输入地址" @click="discoverLan"><Search :size="13" aria-hidden="true" /><span>发现同网段设备</span></button></div><button v-for="device in discoveredDevices" :key="String(device.host_id)" type="button" class="discovered-device" @click="chooseDiscovered(device)"><Wifi :size="13" /><span>{{ String(device.device_name || device.host_id) }}</span><small>{{ String(device.address) }}:{{ String(device.port) }}</small></button>
                    <h2>配对后允许对方</h2><div class="permission-list compact"><label><input v-model="pairGrantPermissions.messages" type="checkbox" /><span><MessageSquare :size="14" /><strong>普通消息</strong></span></label><label><input v-model="pairGrantPermissions.status" type="checkbox" /><span><Eye :size="14" /><strong>查看状态</strong></span></label><label><input v-model="pairGrantPermissions.remote_start" type="checkbox" /><span><Play :size="14" /><strong>远程启动</strong></span></label></div>
                    <div v-if="pendingPairing" class="pair-pending"><strong>等待对方确认</strong><p>核对指纹后，请让对方确认，再完成配对。</p><code>{{ pendingPairFingerprint }}</code><button type="button" class="primary" :disabled="busy" @click="completePairing">完成配对</button></div><button v-else type="button" class="primary full-action" :disabled="busy || (!joinQrPayload && (!joinAddress || !joinPort || !joinSessionId || !joinCode))" @click="beginPairing">发起配对</button>
                    <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
                </div>
            </div>

            <form v-else-if="section === 'instances' && showInstallForm" class="inspector-form" @submit.prevent="registerInstallation">
                <div class="form-scroll app-inspector-body"><label class="field"><span>Player_Bundle 目录</span><input v-model.trim="installPath" maxlength="2048" placeholder="D:\\发布目录\\Player_Bundle" /><small>目录内的签名包、固定信任根、清单和运行时都会重新验证。</small></label><label class="field"><span>默认实例名称</span><input v-model.trim="installInstanceName" maxlength="120" /></label><p v-if="formError" class="form-error" role="alert">{{ formError }}</p></div><footer><button type="button" @click="showInstallForm = false">取消</button><button type="submit" class="primary" :disabled="busy || !installPath || !installInstanceName">验证并登记</button></footer>
            </form>

            <VNextWorkspaceState v-else class="inspector-empty" compact kind="selection" title="选择一个对象" description="右侧只显示当前对象可修改的设置与真实运行结果。"><template #icon><MousePointer2 :size="22" /></template><template v-if="section === 'instances'" #actions><VNextButton size="compact" @click="openInstallForm">登记签名 Player</VNextButton><VNextButton size="compact" @click="openPairing('join')">连接另一台电脑</VNextButton></template></VNextWorkspaceState>
        </aside>

        <div v-if="confirmDelete" class="schedule-dialog-backdrop">
            <section ref="deleteDialogElement" class="schedule-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-schedule-object" tabindex="-1" @keydown="trapDialogFocus" @keydown.esc.stop="confirmDelete = ''">
                <header><h2 id="delete-schedule-object">删除{{ confirmDelete === 'plan' ? '计划' : '批次' }}？</h2><p>{{ confirmDelete === 'plan' ? '只阻止未来触发；已经接纳的普通任务会继续运行。' : '已有计划保存的是不可变条目快照，不会被改写。' }}</p></header>
                <footer><button type="button" data-dialog-initial-focus @click="confirmDelete = ''">取消</button><button type="button" class="danger" :disabled="busy" @click="deleteSelected">确认删除</button></footer>
            </section>
        </div>
        <div v-if="confirmRevokePeerId" class="schedule-dialog-backdrop">
            <section ref="revokeDialogElement" class="schedule-dialog" role="alertdialog" aria-modal="true" aria-labelledby="revoke-lan-device" tabindex="-1" @keydown="trapDialogFocus" @keydown.esc.stop="confirmRevokePeerId = ''">
                <header><h2 id="revoke-lan-device">撤销已配对设备？</h2><p>将立即删除固定公钥、三项权限、远端实例目录和重放记录。{{ affectedPlans(confirmRevokePeerId) }} 个现有计划引用会在下次校验或派发时失败；不会改由云端转发。</p></header>
                <footer><button type="button" data-dialog-initial-focus @click="confirmRevokePeerId = ''">取消</button><button type="button" class="danger" :disabled="busy" @click="revokePeer">撤销设备</button></footer>
            </section>
        </div>
    </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import QRCode from 'qrcode'
import { CalendarClock, CircleAlert, Copy, Eye, FileCheck2, History, Info, Layers3, Link2, LoaderCircle, MessageSquare, MonitorCog, MousePointer2, PackageCheck, Play, Plus, Power, QrCode, Radio, RefreshCw, Search, ShieldCheck, Trash2, Unplug, Wifi, WifiOff, X, Zap } from 'lucide-vue-next'
import { scheduleApi } from '../scheduleApi'
import { programApi } from '../program/api'
import type { ProgramSummaryDto } from '../program/serverTypes'
import { useVNextStore } from '../store'
import type { HubInstallation, HubInstance, HubProfile, HubStatus, LanDiagnostic, LanPairingOffer, LanPairingPending, LanPeer, LanPermissions, LanStatus, ScheduleBatch, ScheduleDiagnostic, ScheduleDispatch, ScheduleEntry, ScheduleOccurrence, SchedulePlan, TriggerType } from '../scheduleTypes'
import { trapDialogFocus, useDialogFocusReturn } from '../dialogFocus'
import VNextPaneHeader from './ui/VNextPaneHeader.vue'
import VNextNavigationPane from './ui/VNextNavigationPane.vue'
import VNextWorkspaceState from './ui/VNextWorkspaceState.vue'
import VNextInlineNotice from './ui/VNextInlineNotice.vue'
import VNextButton from './ui/VNextButton.vue'
import VNextIconButton from './ui/VNextIconButton.vue'
import VNextNavigationItem from './ui/VNextNavigationItem.vue'

type Section = 'plans' | 'batches' | 'instances' | 'triggers'
type PlanView = 'plans' | 'history' | 'diagnostics'
type PairMode = 'offer' | 'join'
interface ScheduleTarget {
    key: string
    host_id: string
    instance_id: string
    product_id: string
    display_name: string
    profiles: HubProfile[]
    remote: boolean
}
interface ProjectTrigger {
    schema_version?: number
    trigger_id?: string
    display_name: string
    enabled: boolean
    kind: 'global_hotkey' | 'application' | 'filesystem' | 'system'
    kind_config: Record<string, string>
    entry_function_id: string
    target_id: string
    debounce_ms: number
    cooldown_ms: number
    concurrency_policy: 'skip_if_running' | 'queue_one' | 'parallel'
    permission_requirements: string[]
}

const emptyPermissions = (): LanPermissions => ({ messages: false, status: false, remote_start: false, allowed_products: [], allowed_instances: [] })

const section = ref<Section>('plans')
const workspaceStore = useVNextStore()
const planView = ref<PlanView>('plans')
const loading = ref(true)
const busy = ref(false)
const deleteDialogElement = ref<HTMLElement | null>(null)
const revokeDialogElement = ref<HTMLElement | null>(null)
const scheduleInspectorElement = ref<HTMLElement | null>(null)
const error = ref('')
const formError = ref('')
const hub = ref<HubStatus | null>(null)
const plans = ref<SchedulePlan[]>([])
const batches = ref<ScheduleBatch[]>([])
const installations = ref<HubInstallation[]>([])
const occurrences = ref<ScheduleOccurrence[]>([])
const diagnostics = ref<ScheduleDiagnostic[]>([])
const triggers = ref<ProjectTrigger[]>([])
const triggerPrograms = ref<ProgramSummaryDto[]>([])
const triggerRevision = ref('')
const triggerDraft = ref<ProjectTrigger | null>(null)
const lan = ref<LanStatus | null>(null)
const lanDiagnostics = ref<LanDiagnostic[]>([])
const lanError = ref('')
const selectedDispatches = ref<ScheduleDispatch[]>([])
const selectedPlanId = ref('')
const selectedBatchId = ref('')
const selectedInstanceId = ref('')
const selectedPeerId = ref('')
const selectedPendingId = ref('')
const selectedOccurrenceId = ref('')
const planDraft = ref<SchedulePlan | null>(null)
const batchDraft = ref<ScheduleBatch | null>(null)
const planBatchId = ref('')
const triggerType = ref<TriggerType>('daily')
const triggerValue = ref('08:00:00')
const triggerAnchor = ref(localDateTime())
const intervalMinutes = ref(60)
const latenessMinutes = ref(30)
const showInstallForm = ref(false)
const installPath = ref('')
const installInstanceName = ref('实例 1')
const newInstanceName = ref('')
const selectedReleaseId = ref('')
const confirmDelete = ref<'plan' | 'batch' | ''>('')
const confirmRevokePeerId = ref('')
useDialogFocusReturn(() => Boolean(confirmDelete.value), deleteDialogElement)
useDialogFocusReturn(() => Boolean(confirmRevokePeerId.value), revokeDialogElement)
const showPairing = ref(false)
const pairMode = ref<PairMode>('offer')
const pairingOffer = ref<LanPairingOffer | null>(null)
const pairingQrUrl = ref('')
const pairGrantPermissions = ref<LanPermissions>(emptyPermissions())
const peerPermissions = ref<LanPermissions>(emptyPermissions())
const joinQrPayload = ref('')
const joinAddress = ref('')
const joinPort = ref<number | null>(null)
const joinCode = ref('')
const joinSessionId = ref('')
const pendingPairing = ref<Record<string, unknown> | null>(null)
const discoveredDevices = ref<Record<string, unknown>[]>([])
const props = withDefaults(defineProps<{ detailOpen?: boolean; detailOverlay?: boolean }>(), { detailOpen: undefined, detailOverlay: undefined })
const emit = defineEmits<{ 'update:detail-open': [open: boolean] }>()
const compactInspector = ref(false)
const inspectorDrawerOpen = ref(false)
const detailVisible = computed(() => props.detailOpen ?? (!compactInspector.value || inspectorDrawerOpen.value))
const detailAsOverlay = computed(() => props.detailOverlay ?? compactInspector.value)
const detailOverlayOpen = computed(() => detailVisible.value && detailAsOverlay.value)
useDialogFocusReturn(detailOverlayOpen, scheduleInspectorElement)
let compactInspectorMedia: MediaQueryList | null = null

function syncCompactInspector(event?: MediaQueryListEvent): void {
    compactInspector.value = event?.matches ?? compactInspectorMedia?.matches ?? false
    if (!compactInspector.value) inspectorDrawerOpen.value = false
}
function openInspector(): void {
    if (props.detailOpen !== undefined) emit('update:detail-open', true)
    else if (compactInspector.value) inspectorDrawerOpen.value = true
}
function closeInspector(): void {
    if (props.detailOpen !== undefined) emit('update:detail-open', false)
    else inspectorDrawerOpen.value = false
}
function openInstallForm(): void { showInstallForm.value = true; openInspector() }

const planViews = computed(() => [
    { id: 'plans' as const, label: '计划', count: plans.value.length },
    { id: 'history' as const, label: '运行历史', count: occurrences.value.length },
    { id: 'diagnostics' as const, label: '诊断', count: diagnostics.value.filter(item => item.level !== 'info').length },
])
const navigation = computed(() => [
    { id: 'plans' as const, label: '计划', icon: CalendarClock, count: plans.value.length },
    { id: 'batches' as const, label: '批次', icon: Layers3, count: batches.value.length },
    { id: 'instances' as const, label: '实例', icon: MonitorCog, count: instances.value.length + (lan.value?.paired_devices.length || 0) },
    { id: 'triggers' as const, label: '启动方式', icon: Zap, count: triggers.value.length },
])
const instances = computed(() => installations.value.flatMap(item => item.instances || []))
const scheduleTargets = computed<ScheduleTarget[]>(() => {
    const local = instances.value
        .filter(item => item.status === 'ready' && (item.profiles?.length || 0) > 0)
        .map(item => ({ key: `${hub.value?.host_id || ''}:${item.instance_id}`, host_id: hub.value?.host_id || '', instance_id: item.instance_id, product_id: item.product_id, display_name: item.display_name, profiles: item.profiles || [], remote: false }))
    const remote = (lan.value?.remote_instances || [])
        .filter(item => item.profiles.length > 0 && Boolean(lan.value?.paired_devices.find(peer => peer.host_id === item.host_id)?.remote_permissions.remote_start))
        .map(item => ({ key: `${item.host_id}:${item.instance_id}`, host_id: item.host_id, instance_id: item.instance_id, product_id: item.product_id, display_name: item.display_name, profiles: item.profiles, remote: true }))
    return [...local, ...remote]
})
const instancesWithProfiles = computed(() => scheduleTargets.value)
const selectedInstance = computed(() => instances.value.find(item => item.instance_id === selectedInstanceId.value) || null)
const selectedPeer = computed(() => lan.value?.paired_devices.find(item => item.host_id === selectedPeerId.value) || null)
const selectedPending = computed<LanPairingPending | null>(() => lan.value?.pairing_sessions.flatMap(item => item.pending).find(item => item.pending_id === selectedPendingId.value) || null)
const pendingPairFingerprint = computed(() => String((pendingPairing.value?.receiver as Record<string, unknown> | undefined)?.fingerprint || ''))
const productReleases = computed(() => installations.value.filter(item => item.product_id === selectedInstance.value?.product_id))
const selectedOccurrence = computed(() => occurrences.value.find(item => item.occurrence_id === selectedOccurrenceId.value) || null)
const heading = computed(() => section.value === 'plans' ? (planView.value === 'history' ? '运行历史' : planView.value === 'diagnostics' ? '计划诊断' : '运行计划') : section.value === 'batches' ? '运行批次' : section.value === 'instances' ? '实例与设备' : '启动方式')
const subheading = computed(() => section.value === 'plans' ? '决定何时创建普通任务；业务逻辑仍由项目函数负责。' : section.value === 'batches' ? '复用“实例 + 产品 + 方案”组合，不建立第二套工作流。' : section.value === 'instances' ? '本机实例与显式配对的局域网设备；不依赖账号或 EasyCode 云。' : '用快捷键、应用、文件或系统事件启动已有函数，不复制脚本。')
const inspectorTitle = computed(() => {
    if (planDraft.value?.name) return planDraft.value.name
    if (batchDraft.value?.name) return batchDraft.value.name
    if (selectedInstance.value?.display_name) return selectedInstance.value.display_name
    if (selectedPeer.value?.device_name) return selectedPeer.value.device_name
    if (selectedPending.value?.device_name) return `确认 ${selectedPending.value.device_name}`
    if (showPairing.value) return '局域网配对'
    if (selectedOccurrence.value) return '运行详情'
    if (showInstallForm.value) return '登记 Player'
    if (triggerDraft.value?.display_name) return triggerDraft.value.display_name
    return '未选择'
})
const canSavePlan = computed(() => Boolean(planDraft.value?.name && planDraft.value.timezone_id && (planDraft.value.schedule_id || planBatchId.value)))
const triggerOptions = [{ id: 'once', label: '单次' }, { id: 'daily', label: '每天' }, { id: 'interval', label: '固定间隔' }] as const

onMounted(() => {
    compactInspectorMedia = window.matchMedia?.('(max-width: 1099px)') || null
    syncCompactInspector()
    compactInspectorMedia?.addEventListener?.('change', syncCompactInspector)
    void loadAll()
})
onBeforeUnmount(() => compactInspectorMedia?.removeEventListener?.('change', syncCompactInspector))

async function loadAll() {
    loading.value = true; error.value = ''; lanError.value = ''
    try {
        const [status, planRows, batchRows, occurrenceRows, diagnosticRows, lanStatus, networkDiagnostics] = await Promise.all([
            scheduleApi.hubStatus(), scheduleApi.plans(), scheduleApi.batches(), scheduleApi.occurrences(), scheduleApi.diagnostics(),
            scheduleApi.lanStatus().catch(reason => { lanError.value = message(reason); return null }),
            scheduleApi.lanDiagnostics().catch(() => []),
        ])
        hub.value = status; plans.value = planRows; batches.value = batchRows; installations.value = status.installations || []; occurrences.value = occurrenceRows; diagnostics.value = diagnosticRows; lan.value = lanStatus; lanDiagnostics.value = networkDiagnostics
        if (workspaceStore.workspace) {
            const [configuration, programs] = await Promise.all([
                programApi.getTriggers(workspaceStore.workspace),
                programApi.listPrograms(workspaceStore.workspace),
            ])
            triggers.value = configuration.triggers as unknown as ProjectTrigger[]
            triggerRevision.value = configuration.revision
            triggerPrograms.value = programs
        }
        if (selectedPlanId.value) { const item = plans.value.find(row => row.schedule_id === selectedPlanId.value); if (item) selectPlan(item) }
    } catch (reason) { error.value = message(reason) } finally { loading.value = false }
}

function selectSection(value: Section) { section.value = value; formError.value = ''; inspectorDrawerOpen.value = false; if (value !== 'plans') planView.value = 'plans' }
function selectPlan(plan: SchedulePlan) { selectedPlanId.value = plan.schedule_id || ''; planDraft.value = structuredClone(plan); planBatchId.value = ''; readTrigger(plan); openInspector() }
function selectBatch(batch: ScheduleBatch) { selectedBatchId.value = batch.batch_id || ''; batchDraft.value = structuredClone(batch); openInspector() }
function selectInstance(instance: HubInstance) { selectedInstanceId.value = instance.instance_id; selectedPeerId.value = ''; selectedPendingId.value = ''; selectedReleaseId.value = instance.installation_id; newInstanceName.value = ''; showInstallForm.value = false; showPairing.value = false; openInspector() }
function selectPeer(peer: LanPeer) { selectedPeerId.value = peer.host_id; selectedInstanceId.value = ''; selectedPendingId.value = ''; showInstallForm.value = false; showPairing.value = false; peerPermissions.value = structuredClone(peer.permissions); openInspector() }
function selectPending(pending: LanPairingPending) { selectedPendingId.value = pending.pending_id; selectedPeerId.value = ''; selectedInstanceId.value = ''; showPairing.value = false; peerPermissions.value = emptyPermissions(); openInspector() }
async function selectOccurrence(item: ScheduleOccurrence) { selectedOccurrenceId.value = item.occurrence_id; selectedDispatches.value = await scheduleApi.dispatches(item.occurrence_id); openInspector() }

function newPlan() { const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai'; planDraft.value = { name: '', enabled: true, timezone_id: zone, trigger: { type: 'daily', local_time: '08:00:00' }, misfire_policy: 'skip', max_lateness_seconds: 0, overlap_policy: 'skip', dispatch_mode: 'simultaneous', entries: [] }; selectedPlanId.value = ''; planBatchId.value = batches.value[0]?.batch_id || ''; triggerType.value = 'daily'; triggerValue.value = '08:00:00'; openInspector() }
function newBatch() { batchDraft.value = { name: '', dispatch_mode: 'simultaneous', entries: [] }; selectedBatchId.value = ''; addBatchEntry(); openInspector() }
function emptyTrigger(): ProjectTrigger {
    return {
        display_name: '', enabled: false, kind: 'global_hotkey', kind_config: { shortcut: '' },
        entry_function_id: triggerPrograms.value[0]?.function_id || '', target_id: '',
        debounce_ms: 300, cooldown_ms: 1000, concurrency_policy: 'skip_if_running', permission_requirements: [],
    }
}
function newTrigger() { triggerDraft.value = emptyTrigger(); formError.value = ''; openInspector() }
function selectTrigger(trigger: ProjectTrigger) { triggerDraft.value = structuredClone(trigger); formError.value = ''; openInspector() }
function resetTriggerDraftConfig() {
    if (!triggerDraft.value) return
    triggerDraft.value.kind_config = triggerDraft.value.kind === 'global_hotkey' ? { shortcut: '' }
        : triggerDraft.value.kind === 'application' ? { process_name: '', event: 'start' }
            : triggerDraft.value.kind === 'filesystem' ? { path: '' }
                : { event: 'system_start' }
}
async function saveTrigger() {
    if (!workspaceStore.workspace || !triggerDraft.value) return
    busy.value = true; formError.value = ''
    try {
        const configuration = await programApi.saveTrigger(workspaceStore.workspace, triggerRevision.value, triggerDraft.value as unknown as Record<string, unknown>)
        triggers.value = configuration.triggers as unknown as ProjectTrigger[]
        triggerRevision.value = configuration.revision
        const saved = triggers.value.find(item => item.trigger_id === triggerDraft.value?.trigger_id)
            || triggers.value.find(item => item.display_name === triggerDraft.value?.display_name)
        if (saved) selectTrigger(saved)
    } catch (reason) { formError.value = message(reason) } finally { busy.value = false }
}
async function deleteTrigger() {
    if (!workspaceStore.workspace || !triggerDraft.value?.trigger_id) return
    busy.value = true; formError.value = ''
    try {
        const configuration = await programApi.deleteTrigger(workspaceStore.workspace, triggerDraft.value.trigger_id, triggerRevision.value)
        triggers.value = configuration.triggers as unknown as ProjectTrigger[]
        triggerRevision.value = configuration.revision
        triggerDraft.value = null
        closeInspector()
    } catch (reason) { formError.value = message(reason) } finally { busy.value = false }
}
function resetTrigger() { if (triggerType.value === 'once') triggerValue.value = localDateTime(); else if (triggerType.value === 'daily') triggerValue.value = '08:00:00'; else { triggerAnchor.value = localDateTime(); intervalMinutes.value = 60 } }
function readTrigger(plan: SchedulePlan) { triggerType.value = String(plan.trigger.type) as TriggerType; if (triggerType.value === 'once') triggerValue.value = String(plan.trigger.local_datetime || ''); else if (triggerType.value === 'daily') triggerValue.value = String(plan.trigger.local_time || '08:00:00'); else { triggerAnchor.value = String(plan.trigger.anchor_local_datetime || localDateTime()); intervalMinutes.value = Math.max(1, Number(plan.trigger.interval_seconds || 3600) / 60) } latenessMinutes.value = Math.max(1, Number(plan.max_lateness_seconds || 1800) / 60) }
function buildTrigger(): Record<string, string | number> { if (triggerType.value === 'once') return { type: 'once', local_datetime: triggerValue.value.length === 16 ? `${triggerValue.value}:00` : triggerValue.value }; if (triggerType.value === 'daily') return { type: 'daily', local_time: triggerValue.value }; return { type: 'interval', anchor_local_datetime: triggerAnchor.value.length === 16 ? `${triggerAnchor.value}:00` : triggerAnchor.value, interval_seconds: Math.round(intervalMinutes.value * 60) } }

async function savePlan() { if (!planDraft.value) return; busy.value = true; formError.value = ''; try { const draft = structuredClone(planDraft.value); const batch = batches.value.find(item => item.batch_id === planBatchId.value); if (batch) { draft.entries = structuredClone(batch.entries); draft.dispatch_mode = batch.dispatch_mode } draft.trigger = buildTrigger(); draft.max_lateness_seconds = draft.misfire_policy === 'catch_up_once' ? Math.round(latenessMinutes.value * 60) : 0; const saved = await scheduleApi.savePlan(draft); await loadAll(); selectPlan(saved) } catch (reason) { formError.value = message(reason) } finally { busy.value = false } }
async function togglePlan() { if (!planDraft.value) return; planDraft.value.enabled = !planDraft.value.enabled; await savePlan() }

function addBatchEntry() { const instance = instancesWithProfiles.value[0]; const profile = instance?.profiles?.[0]; if (!instance || !profile || !batchDraft.value) return; batchDraft.value.entries.push({ enabled: true, host_id: instance.host_id, instance_id: instance.instance_id, product_id: instance.product_id, profile_id: profile.profile_id, start_offset_seconds: batchDraft.value.dispatch_mode === 'staggered' ? batchDraft.value.entries.length * 10 : 0, start_deadline_seconds: null }) }
function entryTargetKey(entry: ScheduleEntry) { return `${entry.host_id}:${entry.instance_id}` }
function changeEntryInstance(entry: ScheduleEntry, event: Event) { const key = (event.target as HTMLSelectElement).value; const instance = scheduleTargets.value.find(item => item.key === key); if (!instance) return; entry.instance_id = instance.instance_id; entry.product_id = instance.product_id; entry.host_id = instance.host_id; entry.profile_id = instance.profiles[0]?.profile_id || '' }
function profilesFor(hostId: string, instanceId: string): HubProfile[] { return scheduleTargets.value.find(item => item.host_id === hostId && item.instance_id === instanceId)?.profiles || [] }
function normalizeOffsets() { if (batchDraft.value?.dispatch_mode === 'simultaneous') batchDraft.value.entries.forEach(item => { item.start_offset_seconds = 0 }) }
async function saveBatch() { if (!batchDraft.value) return; busy.value = true; formError.value = ''; try { const saved = await scheduleApi.saveBatch(batchDraft.value); await loadAll(); selectBatch(saved) } catch (reason) { formError.value = message(reason) } finally { busy.value = false } }

async function deleteSelected() { busy.value = true; try { if (confirmDelete.value === 'plan' && planDraft.value?.schedule_id && planDraft.value.revision) { await scheduleApi.deletePlan(planDraft.value.schedule_id, planDraft.value.revision); planDraft.value = null } else if (confirmDelete.value === 'batch' && batchDraft.value?.batch_id && batchDraft.value.revision) { await scheduleApi.deleteBatch(batchDraft.value.batch_id, batchDraft.value.revision); batchDraft.value = null } confirmDelete.value = ''; await loadAll() } catch (reason) { formError.value = message(reason); confirmDelete.value = '' } finally { busy.value = false } }
async function installAgent() { busy.value = true; try { await scheduleApi.installAgent(); await loadAll() } catch (reason) { error.value = message(reason) } finally { busy.value = false } }
async function openInstancePlayer() { if (!selectedInstance.value) return; busy.value = true; formError.value = ''; try { await scheduleApi.openConsole(selectedInstance.value.product_id) } catch (reason) { formError.value = message(reason) } finally { busy.value = false } }
async function createSiblingInstance() { if (!selectedInstance.value || !newInstanceName.value) return; busy.value = true; formError.value = ''; try { const created = await scheduleApi.createInstance(selectedInstance.value.installation_id, newInstanceName.value); await loadAll(); selectInstance(created) } catch (reason) { formError.value = message(reason) } finally { busy.value = false } }
async function bindSelectedRelease() { if (!selectedInstance.value || !selectedReleaseId.value) return; busy.value = true; formError.value = ''; try { const updated = await scheduleApi.bindRelease(selectedInstance.value.instance_id, selectedReleaseId.value, selectedInstance.value.revision); await loadAll(); selectInstance(updated) } catch (reason) { formError.value = message(reason) } finally { busy.value = false } }
async function registerInstallation() { busy.value = true; formError.value = ''; try { await scheduleApi.registerInstallation(installPath.value, installInstanceName.value); showInstallForm.value = false; installPath.value = ''; await loadAll() } catch (reason) { formError.value = message(reason) } finally { busy.value = false } }

async function toggleLanListener() { busy.value = true; lanError.value = ''; try { lan.value = lan.value?.running ? (await scheduleApi.stopLan(), await scheduleApi.lanStatus()) : await scheduleApi.startLan() } catch (reason) { lanError.value = message(reason) } finally { busy.value = false } }
async function openPairing(mode: PairMode) { showPairing.value = true; pairMode.value = mode; selectedInstanceId.value = ''; selectedPeerId.value = ''; selectedPendingId.value = ''; formError.value = ''; openInspector(); if (mode === 'offer' && !pairingOffer.value) await createPairingOffer() }
async function createPairingOffer() { busy.value = true; formError.value = ''; try { pairingOffer.value = await scheduleApi.createPairingSession(); pairingQrUrl.value = await QRCode.toDataURL(pairingOffer.value.qr_payload, { width: 196, margin: 1, errorCorrectionLevel: 'M' }); await refreshLan() } catch (reason) { formError.value = message(reason) } finally { busy.value = false } }
async function discoverLan() { busy.value = true; formError.value = ''; try { discoveredDevices.value = await scheduleApi.discoverLan(lan.value?.port || undefined) } catch (reason) { formError.value = message(reason) } finally { busy.value = false } }
function chooseDiscovered(item: Record<string, unknown>) { joinAddress.value = String(item.address || ''); joinPort.value = Number(item.port || 0) || null }
async function beginPairing() { busy.value = true; formError.value = ''; try { pendingPairing.value = await scheduleApi.beginPairing({ ...(joinQrPayload.value ? { qr_payload: joinQrPayload.value } : { address: joinAddress.value, port: joinPort.value || undefined, code: joinCode.value, session_id: joinSessionId.value }), permissions: pairGrantPermissions.value }); const receiver = pendingPairing.value.receiver as Record<string, unknown> | undefined; if (receiver?.fingerprint) formError.value = `请在另一台电脑确认指纹 ${String(receiver.fingerprint)}，确认后点击“完成配对”。` } catch (reason) { formError.value = message(reason) } finally { busy.value = false } }
async function completePairing() { if (!pendingPairing.value) return; busy.value = true; formError.value = ''; try { const receiver = pendingPairing.value.receiver as Record<string, unknown> | undefined; const result = await scheduleApi.completePairing(pendingPairing.value, String(receiver?.fingerprint || '')) as Record<string, unknown>; if (result.status === 'pending') { formError.value = '另一台电脑尚未确认，请核对指纹后再试。'; return } pendingPairing.value = null; showPairing.value = false; await refreshLan() } catch (reason) { formError.value = message(reason) } finally { busy.value = false } }
async function confirmPendingPairing() { if (!selectedPending.value) return; busy.value = true; formError.value = ''; try { await scheduleApi.confirmPairing(selectedPending.value.pending_id, peerPermissions.value); selectedPendingId.value = ''; await refreshLan() } catch (reason) { formError.value = message(reason) } finally { busy.value = false } }
async function savePeerPermissions() { if (!selectedPeer.value) return; busy.value = true; formError.value = ''; try { await scheduleApi.setLanPermissions(selectedPeer.value.host_id, peerPermissions.value); await refreshLan() } catch (reason) { formError.value = message(reason) } finally { busy.value = false } }
async function refreshPeer() { if (!selectedPeer.value) return; busy.value = true; formError.value = ''; try { await scheduleApi.refreshLanPeer(selectedPeer.value.host_id); await refreshLan() } catch (reason) { formError.value = message(reason) } finally { busy.value = false } }
async function revokePeer() { if (!confirmRevokePeerId.value) return; busy.value = true; formError.value = ''; try { await scheduleApi.revokeLanPeer(confirmRevokePeerId.value); confirmRevokePeerId.value = ''; selectedPeerId.value = ''; await refreshLan() } catch (reason) { formError.value = message(reason); confirmRevokePeerId.value = '' } finally { busy.value = false } }
async function refreshLan() { const [status, events] = await Promise.all([scheduleApi.lanStatus(), scheduleApi.lanDiagnostics().catch(() => [])]); lan.value = status; lanDiagnostics.value = events }
async function copyPairingCode() { if (pairingOffer.value) await navigator.clipboard.writeText(pairingOffer.value.code) }

function localDateTime() { const now = new Date(Date.now() + 5 * 60_000); const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000); return local.toISOString().slice(0, 16) }
function message(reason: unknown) { return reason instanceof Error ? reason.message : '操作失败，请重试。' }
function formatTime(value: string) { try { return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(value)) } catch { return value } }
function triggerSummary(plan: SchedulePlan) { const trigger = plan.trigger; if (trigger.type === 'once') return `单次 · ${trigger.local_datetime}`; if (trigger.type === 'daily') return `每天 ${trigger.local_time}`; return `每 ${Math.round(Number(trigger.interval_seconds) / 60)} 分钟` }
function triggerKindLabel(trigger: ProjectTrigger) {
    if (trigger.kind === 'global_hotkey') return trigger.kind_config.shortcut || '全局快捷键'
    if (trigger.kind === 'application') return `${trigger.kind_config.process_name || '应用'} · ${{ start: '启动', exit: '退出', focus: '获得焦点' }[trigger.kind_config.event || 'start'] || '状态变化'}`
    if (trigger.kind === 'filesystem') return `文件变化 · ${compactPath(trigger.kind_config.path || '')}`
    return trigger.kind_config.event === 'user_login' ? '用户登录' : '系统启动'
}
function triggerEntryLabel(trigger: ProjectTrigger) { return triggerPrograms.value.find(item => item.function_id === trigger.entry_function_id)?.display_name || trigger.entry_function_id }
function statusLabel(status: string) { return ({ pending: '等待派发', accepted: '已接纳', starting: '启动中', running: '运行中', paused: '已暂停', completed: '已完成', failed: '失败', partial_failed: '部分失败', stopped: '已停止', rejected: '已拒绝', skipped: '已跳过', expired: '已过期', queued_overlap: '排队一次' } as Record<string, string>)[status] || status }
function statusTone(status: string) { if (status === 'completed') return 'ready'; if (['failed', 'rejected', 'expired'].includes(status)) return 'danger'; if (['running', 'accepted', 'starting'].includes(status)) return 'active'; return 'muted' }
function sourceLabel(source: string) { return ({ timer: '正常触发', recovery: '恢复检查', recovery_catch_up: '合并补跑', manual: '手动运行' } as Record<string, string>)[source] || source }
function planName(id: string) { return plans.value.find(item => item.schedule_id === id)?.name || id }
function instanceName(id: string) { return scheduleTargets.value.find(item => item.instance_id === id)?.display_name || id }
function peerInstanceCount(hostId: string) { return lan.value?.remote_instances.filter(item => item.host_id === hostId).length || 0 }
function affectedPlans(hostId: string) { return plans.value.filter(plan => plan.entries.some(entry => entry.host_id === hostId)).length }
function permissionSummary(value: LanPermissions) { const labels = [value.messages && '消息', value.status && '状态', value.remote_start && '远程启动'].filter(Boolean); return labels.length ? labels.join('、') : '未授予动作权限' }
function installationName(productId: string) { return installations.value.find(item => item.product_id === productId)?.display_name || productId }
function compactPath(value: string) { return value.length > 42 ? `…${value.slice(-41)}` : value }
function eventLabel(value: string) { return ({ 'schedule.created': '计划已创建', 'schedule.updated': '计划已修改', 'occurrence.created': '生成触发批次', 'dispatch.accepted': '任务已接纳', 'dispatch.failed': '任务派发失败', 'run.completed': '任务已完成', 'run.failed': '任务运行失败' } as Record<string, string>)[value] || value }
function diagnosticSummary(item: ScheduleDiagnostic) { if (item.error_id) return item.error_id; const pairs = Object.entries(item.details || {}).slice(0, 3).map(([key, value]) => `${key}: ${String(value)}`); return pairs.join(' · ') || '状态已记录' }
</script>

<style scoped>
.schedule-workspace{position:relative;height:100%;min-width:0;display:grid;grid-template-columns:184px minmax(360px,1fr) minmax(300px,360px);background:var(--app-bg-base);color:var(--app-text-primary)}
.schedule-workspace.detail-panel-collapsed{grid-template-columns:184px minmax(0,1fr)}
.schedule-nav,.schedule-inspector{min-width:0;background:var(--app-bg-sidebar);border-color:var(--app-border-subtle);display:flex;flex-direction:column}.schedule-nav{border-right:1px solid var(--app-border-subtle);padding:14px 10px}.schedule-nav>header{display:flex;align-items:baseline;justify-content:space-between;padding:0 8px 12px}.schedule-nav>header strong{font-size: var(--app-font-body)}.schedule-nav>header small{color:var(--app-text-secondary);font-size: var(--app-font-caption)}.schedule-nav nav{display:grid;gap:2px}.schedule-nav nav button{width:100%;height: var(--app-control-default);display:grid;grid-template-columns:18px 1fr auto;align-items:center;gap:7px;border:0;border-radius:var(--app-radius-sm);padding:0 9px;background:transparent;color:var(--app-text-regular);text-align:left;cursor:pointer}.schedule-nav nav button:hover{background:var(--app-bg-hover)}.schedule-nav nav button.active{background:var(--app-bg-active);color:var(--app-text-primary)}.schedule-nav nav em{font-style:normal;font-size: var(--app-font-caption);color:var(--app-text-secondary);font-variant-numeric:tabular-nums}.agent-state{margin-top:auto;border-top:1px solid var(--app-border-subtle);padding:14px 8px 2px;color:var(--app-text-secondary)}.agent-state>span{display:flex;align-items:center;gap:6px;color:var(--app-text-regular);font-weight:600}.agent-state.blocked>span{color:var(--el-color-warning)}.agent-state p{margin:6px 0 10px;font-size: var(--app-font-caption);line-height:1.55}.agent-state button{width:100%}
.schedule-main{min-width:0;overflow:hidden;display:flex;flex-direction:column}.workspace-heading{height:var(--app-height-workspace-header-described);flex:none;border-bottom:1px solid var(--app-border-subtle);padding:12px 16px;display:flex;align-items:center;justify-content:space-between;gap:16px}.workspace-heading h1{font-size: var(--app-font-page-title);margin:0 0 3px}.workspace-heading p{font-size: var(--app-font-caption);color:var(--app-text-secondary);margin:0}.heading-actions{display:flex;gap:7px}.heading-actions button{height: var(--app-control-compact)}.heading-actions button:not(.primary){width:30px;padding:0}.view-switch{height:var(--app-height-pane-header);flex:none;border-bottom:1px solid var(--app-border-subtle);padding:6px 14px;display:flex;gap:4px}.view-switch button{height: var(--app-control-compact);border:0;background:transparent;color:var(--app-text-secondary);border-radius:var(--app-radius-sm);padding:0 10px}.view-switch button.active{background:var(--app-bg-raised);color:var(--app-text-primary)}.view-switch span{margin-left:6px;color:var(--app-text-placeholder);font-size: var(--app-font-caption)}
button:not(.app-inline-action){border:1px solid var(--app-border-default);background:var(--app-bg-raised);color:var(--app-text-regular);border-radius:var(--app-radius-sm);height: var(--app-control-compact);padding:0 10px;display:inline-flex;align-items:center;justify-content:center;gap:6px;cursor:pointer}button:not(.app-inline-action):hover:not(:disabled){background:var(--app-bg-hover);color:var(--app-text-primary)}button:not(.app-inline-action):disabled{opacity:.45;cursor:not-allowed}.primary{background:var(--el-color-primary);border-color:var(--el-color-primary);color:var(--app-color-on-primary);font-weight:600}.primary:hover:not(:disabled){background:var(--app-color-primary-hover)}.danger,.danger-text{color:var(--el-color-danger)}.danger{border-color:var(--el-color-danger)}.danger-text{background:transparent;border-color:transparent}
.object-list,.diagnostic-list,.instance-list{min-height:0;overflow:auto;padding:8px}.object-list>button,.instance-list section>button{width:100%;min-height:58px;border:0;border-bottom:1px solid var(--app-border-subtle);border-radius:var(--app-radius-sm);background:transparent;padding:8px 10px;display:grid;grid-template-columns:26px minmax(0,1fr) auto;grid-template-rows:auto auto;column-gap:8px;text-align:left}.object-list>button:hover,.instance-list section>button:hover{background:var(--app-bg-hover)}.object-list>button.selected,.instance-list section>button.selected{background:var(--app-bg-active)}.object-icon{grid-row:1/3;width:26px;height:26px;display:grid;place-items:center;color:var(--app-text-secondary)}.object-copy{min-width:0;display:flex;flex-direction:column;gap:2px}.object-copy strong{font-size: var(--app-font-compact);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.object-copy small{color:var(--app-text-secondary);font-size: var(--app-font-caption);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.object-state{align-self:start;border-radius:999px;padding:2px 7px;font-size: var(--app-font-caption);background:var(--app-bg-raised);color:var(--app-text-secondary)}.object-state.ready,.ready{color:var(--el-color-success)}.object-state.active,.active{color:var(--el-color-primary)}.object-state.danger,.danger{color:var(--el-color-danger)}.object-state.muted,.muted{color:var(--app-text-secondary)}.object-list time{grid-column:3;font-size: var(--app-font-caption);color:var(--app-text-placeholder);font-variant-numeric:tabular-nums}.instance-list section{margin-bottom:14px}.instance-list section>header{height: var(--app-control-default);padding:0 8px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--app-border-default)}.instance-list section>header div{display:flex;align-items:baseline;gap:8px}.instance-list section>header small{color:var(--app-text-secondary)}.instance-list section>header>span{color:var(--el-color-success);font-size: var(--app-font-caption)}.list-empty,.center-state{min-height:260px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:var(--app-text-secondary);padding:32px}.list-empty strong,.center-state strong{color:var(--app-text-primary);margin-top:10px}.list-empty p,.center-state span{max-width:42ch;margin:5px 0 12px;font-size: var(--app-font-caption)}.center-state.error svg{color:var(--el-color-danger)}.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
.diagnostic-list article{display:grid;grid-template-columns:26px minmax(0,1fr);gap:8px;border-bottom:1px solid var(--app-border-subtle);padding:10px}.diagnostic-level{width:24px;height:24px;display:grid;place-items:center;color:var(--app-text-secondary)}.diagnostic-level.error{color:var(--el-color-danger)}.diagnostic-list strong{font-size: var(--app-font-compact)}.diagnostic-list p{margin:3px 0;color:var(--app-text-regular);font-size: var(--app-font-caption)}.diagnostic-list small{color:var(--app-text-placeholder);font-size: var(--app-font-caption)}
.schedule-inspector{position:relative;border-left:1px solid var(--app-border-subtle);overflow:hidden}.schedule-inspector>header{height:52px;flex:none;padding:9px 42px 9px 14px;border-bottom:1px solid var(--app-border-subtle);display:flex;flex-direction:column;justify-content:center}.schedule-inspector>header span{font-size: var(--app-font-caption);color:var(--app-text-secondary)}.schedule-inspector>header strong{font-size: var(--app-font-compact);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.inspector-close{position:absolute;z-index:2;top:11px;right:10px;width:30px;padding:0}.schedule-inspector-scrim{position:absolute;z-index:19;inset:0 0 0 164px;background:rgba(0,0,0,.34)}.inspector-form{min-height:0;flex:1;display:flex;flex-direction:column}.form-scroll,.inspector-detail{min-height:0;overflow:auto;padding:14px}.field{display:grid;gap:6px;margin-bottom:14px}.field>span,.choice-row legend{font-size: var(--app-font-caption);color:var(--app-text-secondary)}.field small{font-size: var(--app-font-caption);color:var(--app-text-placeholder);line-height:1.5}input,select{width:100%;height: var(--app-control-default);border:1px solid var(--app-border-default);border-radius:var(--app-radius-sm);background:var(--app-bg-input);color:var(--app-text-primary);padding:0 9px;outline:0}input:focus,select:focus{border-color:var(--el-color-primary);box-shadow:var(--focus-ring)}.choice-row{border:0;padding:0;margin:0 0 14px}.choice-row legend{margin-bottom:6px}.choice-row{display:flex;flex-wrap:wrap;gap:5px}.choice-row label{position:relative}.choice-row input{position:absolute;opacity:0;pointer-events:none}.choice-row label span{display:flex;height: var(--app-control-compact);align-items:center;padding:0 9px;border:1px solid var(--app-border-default);border-radius:var(--app-radius-sm);color:var(--app-text-secondary)}.choice-row label.active span{border-color:var(--el-color-primary);background:var(--app-color-primary-dim);color:var(--app-text-primary)}details{margin:6px 0 14px;border-top:1px solid var(--app-border-subtle);padding-top:10px}summary{cursor:pointer;color:var(--app-text-regular);font-weight:600;margin-bottom:12px}.inspector-form>footer,.schedule-dialog footer{min-height:52px;flex:none;border-top:1px solid var(--app-border-subtle);padding:10px 12px;display:flex;justify-content:flex-end;gap:7px}.form-error,.inline-error{color:var(--el-color-danger);font-size: var(--app-font-caption);line-height:1.5}.entry-editor>header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}.entry-editor h2,.inspector-detail h2{font-size: var(--app-font-compact);margin:18px 0 8px}.entry-editor article{border-top:1px solid var(--app-border-default);padding:10px 0}.entry-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.entry-title button{width:28px;padding:0;border:0;background:transparent}.inspector-empty{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:var(--app-text-secondary);padding:28px}.inspector-empty strong{color:var(--app-text-primary);margin-top:10px}.inspector-empty p{max-width:34ch;font-size: var(--app-font-caption);line-height:1.6;margin:6px 0 12px}.inspector-detail dl{margin:0}.inspector-detail dl div{padding:9px 0;border-bottom:1px solid var(--app-border-subtle)}.inspector-detail dt{font-size: var(--app-font-caption);color:var(--app-text-secondary)}.inspector-detail dd{margin:3px 0 0;font-size: var(--app-font-caption);overflow-wrap:anywhere}.inspector-detail dd.path{font-family:var(--app-font-mono)}.dispatch-list,.profile-list{list-style:none;margin:0;padding:0}.dispatch-list li,.profile-list li{display:flex;gap:8px;align-items:flex-start;padding:9px 0;border-bottom:1px solid var(--app-border-subtle)}.dispatch-list li>span{flex:none;font-size: var(--app-font-caption);margin-top:2px}.dispatch-list li div,.profile-list li div{min-width:0;display:flex;flex-direction:column}.dispatch-list small,.profile-list small{font-size: var(--app-font-caption);color:var(--app-text-secondary);overflow-wrap:anywhere}.dispatch-list p{font-size: var(--app-font-caption);color:var(--el-color-danger);margin:4px 0}.profile-list li{justify-content:space-between}.profile-list li>span{font-size: var(--app-font-caption);color:var(--app-text-placeholder)}.truth-box{margin-top:16px;border-top:1px solid var(--app-border-default);padding-top:12px}.truth-box p{font-size: var(--app-font-caption);color:var(--app-text-secondary);line-height:1.55;margin:5px 0}
.schedule-dialog-backdrop{position:fixed;inset:0;z-index:5000;background:rgba(7,7,6,.74);display:grid;place-items:center}.schedule-dialog{width:min(420px,calc(100vw - 32px));background:var(--app-overlay-bg);border:1px solid var(--app-overlay-border);border-radius:var(--app-radius-lg);box-shadow:var(--el-box-shadow);overflow:hidden}.schedule-dialog header{padding:18px}.schedule-dialog h2{font-size: var(--app-font-page-title);margin:0 0 6px}.schedule-dialog p{margin:0;color:var(--app-text-secondary);font-size: var(--app-font-caption);line-height:1.6}
.open-player{width:100%;margin-top:12px}
.instance-action{margin-top:14px;padding-top:12px;border-top:1px solid var(--app-border-subtle)}.instance-action button{width:100%}
.instance-group{margin-bottom:16px}.instance-list .instance-group>header{min-height: var(--app-control-default);height:auto;padding-block:8px}.instance-list .instance-group>header>span{display:flex;align-items:center;gap:5px}.installation-label{padding:7px 10px 3px;display:flex;align-items:baseline;justify-content:space-between;gap:10px;color:var(--app-text-regular)}.installation-label span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size: var(--app-font-caption);font-weight:600}.installation-label small{flex:none;color:var(--app-text-placeholder);font-size: var(--app-font-caption)}.compact-empty{min-height:72px;padding:12px;display:flex;align-items:center;gap:9px;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.compact-empty span{min-width:0;flex:1}.compact-empty button{flex:none}.lan-inline-error{margin:4px 4px 10px;padding:9px;display:grid;grid-template-columns:18px minmax(0,1fr) auto;align-items:center;gap:7px;border:1px solid var(--el-color-danger);border-radius:var(--app-radius-sm);color:var(--el-color-danger);font-size: var(--app-font-caption)}.lan-inline-error button{height:26px}
.permission-list{display:grid;gap:6px;margin-bottom:12px}.permission-list label{position:relative;display:block}.permission-list input{position:absolute;inset-inline-start:10px;top:12px;width:16px;height:16px;accent-color:var(--el-color-primary)}.permission-list label>span{min-height:48px;padding:8px 9px 8px 36px;border:1px solid var(--app-border-default);border-radius:var(--app-radius-sm);display:grid;grid-template-columns:18px minmax(0,1fr);grid-template-rows:auto auto;align-items:center;column-gap:6px;background:var(--app-bg-input)}.permission-list label:has(input:checked)>span{border-color:var(--el-color-primary);background:var(--app-color-primary-dim)}.permission-list svg{grid-row:1/3;color:var(--app-text-secondary)}.permission-list strong{font-size: var(--app-font-caption)}.permission-list small{font-size: var(--app-font-caption);color:var(--app-text-secondary);line-height:1.4}.permission-list.compact{grid-template-columns:repeat(3,minmax(0,1fr))}.permission-list.compact label>span{min-height:42px;padding-inline-end:6px}.permission-list.compact small{display:none}.full-action{width:100%}.permission-copy{margin:0 0 12px;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.device-actions{display:flex;gap:7px}.device-actions button{flex:1}.network-diagnostics ol{list-style:none;padding:0;margin:0}.network-diagnostics li{display:flex;justify-content:space-between;gap:8px;padding:7px 0;border-bottom:1px solid var(--app-border-subtle)}.network-diagnostics li strong{font-size: var(--app-font-caption)}.network-diagnostics li small{font-size: var(--app-font-caption);color:var(--app-text-secondary);text-align:end}.network-diagnostics p{font-size: var(--app-font-caption);color:var(--app-text-secondary)}
.pair-identity{text-align:center;padding:14px 0 20px}.pair-identity svg{color:var(--el-color-primary)}.pair-identity strong{display:block;margin-top:7px}.pair-identity p,.pair-note{font-size: var(--app-font-caption);line-height:1.55;color:var(--app-text-secondary)}.pair-identity code,.pair-pending code{display:block;margin-top:9px;padding:8px;background:var(--app-bg-input);border-radius:var(--app-radius-sm);font-family:var(--app-font-mono);font-size: var(--app-font-caption);overflow-wrap:anywhere}.pair-tabs{height:42px;display:grid;grid-template-columns:1fr 1fr;gap:4px;padding:6px 10px;border-bottom:1px solid var(--app-border-subtle)}.pair-tabs button{border:0;background:transparent}.pair-tabs button.active{background:var(--app-bg-active);color:var(--app-text-primary)}.pair-offer{text-align:center;padding-top:4px}.pair-offer img{width:196px;height:196px;max-width:100%;image-rendering:pixelated;background:#fff;padding:5px;border-radius:var(--app-radius-sm)}.pair-offer>span{display:block;margin-top:10px;font-size: var(--app-font-caption);color:var(--app-text-secondary)}.pair-code{margin:5px auto;height:38px;padding-inline:14px}.pair-code code{font-family:var(--app-font-mono);font-size:18px;letter-spacing:.08em}.pair-offer small,.pair-offer p{display:block;margin:4px 0;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.pair-note{margin-top:16px;border-top:1px solid var(--app-border-subtle);padding-top:12px}.pairing-panel textarea{width:100%;resize:vertical;min-height:72px;border:1px solid var(--app-border-default);border-radius:var(--app-radius-sm);background:var(--app-bg-input);color:var(--app-text-primary);padding:8px 9px;font:inherit;line-height:1.45;outline:0}.pairing-panel textarea:focus{border-color:var(--el-color-primary);box-shadow:var(--focus-ring)}.pair-divider{position:relative;text-align:center;margin:16px 0;border-top:1px solid var(--app-border-subtle)}.pair-divider span{position:relative;top:-8px;padding:0 8px;background:var(--app-bg-sidebar);color:var(--app-text-placeholder);font-size: var(--app-font-caption)}.address-grid{display:grid;grid-template-columns:minmax(0,1fr) 92px;gap:8px}.discovery-row{display:flex;align-items:center;gap:8px;margin-bottom:8px}.discovery-row small{font-size: var(--app-font-caption);color:var(--app-text-secondary)}.discovered-device{width:100%;justify-content:flex-start;margin-bottom:4px}.discovered-device span{min-width:0;overflow:hidden;text-overflow:ellipsis}.discovered-device small{margin-inline-start:auto;color:var(--app-text-secondary);font-size: var(--app-font-caption)}.pair-pending{padding:12px;border-top:1px solid var(--app-border-default);text-align:center}.pair-pending p{font-size: var(--app-font-caption);color:var(--app-text-secondary)}.pair-pending button{width:100%;margin-top:10px}.empty-actions{display:flex;flex-wrap:wrap;justify-content:center;gap:7px}
@media(max-width:1099px){.schedule-workspace{grid-template-columns:164px minmax(0,1fr)}.schedule-inspector{position:absolute;right:0;top:0;bottom:0;width:min(360px,calc(100vw - 180px));z-index:20;box-shadow:-18px 0 42px rgba(0,0,0,.32)}}
@media(max-width:819px){.schedule-workspace{grid-template-columns:132px minmax(0,1fr)}.schedule-nav{padding-inline:6px}.schedule-inspector{width:calc(100vw - 132px)}.schedule-inspector-scrim{left:132px}.workspace-heading p{display:none}}
@media(prefers-reduced-motion:reduce){.spin{animation:none}}
@media(min-width:701px){.schedule-workspace{grid-template-columns:var(--workspace-sidebar-width,260px) minmax(360px,1fr) minmax(300px,360px)}}
@media(min-width:701px){.schedule-workspace.detail-panel-collapsed{grid-template-columns:var(--workspace-sidebar-width,260px) minmax(0,1fr)}}
@media(min-width:701px) and (max-width:1099px){.schedule-workspace{grid-template-columns:var(--workspace-sidebar-width,260px) minmax(0,1fr)}}
.object-list > button,
.instance-list section > button { min-height: var(--app-list-row-rich); padding-block: 5px; }
.field { gap: var(--app-form-label-control-gap); margin-bottom: var(--app-form-field-gap); }
.form-scroll > .field:last-child { margin-bottom: 0; }
.schedule-inspector > .vnext-pane-header { height: auto; min-height: var(--app-height-pane-header); padding: 0 var(--app-pane-inline-padding); flex-direction: row; }
.schedule-inspector > .vnext-pane-header span { font-size: var(--app-font-caption); }
.schedule-inspector > .vnext-pane-header strong { font-size: var(--app-font-pane-title); }
.inspector-close { top: 6px; }
.permission-list label > span { min-height: var(--app-list-row-rich); padding-block: 5px; }
.permission-list.compact label > span { min-height: var(--app-list-row-default); }
.inspector-form details { margin: 0 0 var(--app-form-field-gap); padding: 0; }
.inspector-form details > summary { min-height: var(--app-form-disclosure-height); display: flex; align-items: center; margin: 0; }
.inspector-form details[open] > summary { margin-bottom: var(--app-form-heading-field-gap); }

/* Inspector form grammar: one compact row until the available width genuinely cannot hold it. */
.schedule-inspector { container-type: inline-size; }
.form-scroll { --schedule-field-label: minmax(84px, 96px); }
.field {
    min-width: 0;
    min-height: var(--app-control-default);
    display: grid;
    grid-template-columns: var(--schedule-field-label) minmax(0, 1fr);
    align-items: center;
    gap: var(--app-spacing-xs);
    margin-bottom: var(--app-spacing-xs);
}
.field > span:first-child {
    min-width: 0;
    overflow: hidden;
    color: var(--app-text-secondary);
    font-size: var(--app-font-caption);
    text-overflow: ellipsis;
    white-space: nowrap;
}
.field > input,
.field > select,
.field > textarea,
.field > .compound-address-control { grid-column: 2; min-width: 0; }
.field > small {
    grid-column: 2;
    margin-top: calc(-1 * var(--app-spacing-2xs, 2px));
}
.choice-row {
    min-height: var(--app-control-default);
    display: grid;
    grid-template-columns: var(--schedule-field-label) minmax(0, 1fr);
    align-items: center;
    gap: var(--app-spacing-xs);
    margin: 0 0 var(--app-spacing-xs);
}
.choice-row legend { grid-column: 1; margin: 0; padding: 0; }
.choice-options { grid-column: 2; min-width: 0; display: flex; gap: var(--app-spacing-xs); }
.choice-options label { min-width: 0; flex: 1; }
.choice-row .choice-options label span {
    height: var(--app-control-default);
    justify-content: center;
    padding-inline: var(--app-spacing-xs);
    white-space: nowrap;
}
.compound-address-control {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto 72px;
    align-items: center;
    gap: var(--app-spacing-xs);
}
.compound-address-control > span { color: var(--app-text-placeholder); }
.compound-address-control .port-control { min-width: 0; }
.instance-action {
    display: grid;
    grid-template-columns: minmax(84px, 96px) minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--app-spacing-xs);
}
.instance-action .field { display: contents; }
.instance-action .field > span:first-child { grid-column: 1; }
.instance-action .field > input,
.instance-action .field > select { grid-column: 2; }
.instance-action .field > small { grid-column: 2 / -1; }
.instance-action .app-inline-action {
    grid-column: 3;
    grid-row: 1;
    width: auto;
    min-height: var(--app-control-default);
    white-space: nowrap;
}
.form-error { margin: var(--app-form-feedback-gap) 0 0 calc(96px + var(--app-spacing-xs)); }
.trigger-enabled { min-height: var(--app-control-default); display:flex; align-items:center; gap:var(--app-spacing-xs); margin:0 0 var(--app-spacing-xs) calc(96px + var(--app-spacing-xs)); color:var(--app-text-regular); }
.trigger-enabled input { width:16px; height:16px; padding:0; accent-color:var(--el-color-primary); }

@container (max-width: 278px) {
    .field,
    .choice-row {
        grid-template-columns: minmax(0, 1fr);
        align-items: stretch;
    }
    .field > input,
    .field > select,
    .field > textarea,
    .field > .compound-address-control,
    .field > small,
    .choice-row legend,
    .choice-options { grid-column: 1; }
    .choice-options { flex-wrap: wrap; }
    .instance-action {
        grid-template-columns: minmax(0, 1fr) auto;
    }
    .instance-action .field > span:first-child { grid-column: 1 / -1; }
    .instance-action .field > input,
    .instance-action .field > select { grid-column: 1; }
    .instance-action .field > small { grid-column: 1 / -1; }
    .instance-action .app-inline-action { grid-column: 2; grid-row: 2; }
    .form-error { margin-inline-start: 0; }
    .trigger-enabled { margin-inline-start: 0; }
}
</style>
