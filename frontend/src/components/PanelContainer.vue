<template>
    <Splitpanes class="panel-container" :dbl-click-splitter="false">
        <!-- 左侧：垂直分割（任务列表 + 节点列表/视图） -->
        <Pane size="30" min-size="20" max-size="45">
            <Splitpanes horizontal class="left-sub" :dbl-click-splitter="false">
                <Pane size="35" min-size="15" max-size="50">
                    <TaskListPanel />
                </Pane>

                <!-- 如果是列表模式，展示原生的节点列表面板 -->
                <Pane v-if="store.viewMode === 'list'" size="65" min-size="20" max-size="85">
                    <NodeListPanel />
                </Pane>
            </Splitpanes>
        </Pane>

        <!-- 右侧：中间流程图画布或节点详情 + 执行日志 -->
        <Pane size="70">
            <!-- 如果处于 [🔀 流程图画布] 模式，中间展现全屏可视化流程图 -->
            <template v-if="store.viewMode === 'flow'">
                <Splitpanes horizontal class="right-sub" :dbl-click-splitter="false">
                    <Pane size="65" min-size="30" max-size="85">
                        <div class="pane-content">
                            <PanelHeader title="可视化流程图 (拖拽/连线/节点感知)" :actions="[]" />
                            <WorkflowCanvas />
                        </div>
                    </Pane>
                    <Pane size="35" min-size="15" max-size="70">
                        <div class="pane-content">
                            <PanelHeader title="执行日志" :actions="[]" />
                            <LogPanel />
                        </div>
                    </Pane>
                </Splitpanes>
            </template>

            <!-- 如果处于 [📊 列表] 模式，展现经典三栏布局 -->
            <template v-else>
                <Splitpanes horizontal class="right-sub" :dbl-click-splitter="false">
                    <Pane size="65" min-size="20" max-size="80">
                        <div class="pane-content">
                            <PanelHeader title="节点详情" :actions="getActions('nodeEditor')" @action="handleAction" />
                            <NodeEditorPanel />
                        </div>
                    </Pane>
                    <Pane size="35" min-size="20" max-size="80">
                        <div class="pane-content">
                            <PanelHeader title="执行日志" :actions="[]" />
                            <LogPanel />
                        </div>
                    </Pane>
                </Splitpanes>
            </template>
        </Pane>
    </Splitpanes>
</template>

<script>
    import { Splitpanes, Pane } from 'splitpanes'
    import 'splitpanes/dist/splitpanes.css'

    import PanelHeader from './PanelHeader.vue'
    import TaskListPanel from './panels/TaskListPanel.vue'
    import NodeListPanel from './panels/NodeListPanel.vue'
    import NodeEditorPanel from './panels/NodeEditorPanel.vue'
    import LogPanel from './panels/LogPanel.vue'
    import WorkflowCanvas from './WorkflowCanvas.vue' // ⭐ 引入流程图画布组件
    import { panelConfigs } from '@/config/panels.js'
    import { useMainStore } from '@/stores'

    export default {
        components: {
            Splitpanes,
            Pane,
            PanelHeader,
            TaskListPanel,
            NodeListPanel,
            NodeEditorPanel,
            LogPanel,
            WorkflowCanvas
        },
        setup() {
            const store = useMainStore()
            return { store }
        },
        methods: {
            getActions(panelId) {
                return panelConfigs[panelId]?.actions || []
            },
            handleAction({ panelId, method }) {
                console.log(`面板 ${panelId} 触发操作: ${method}`)
            }
        }
    }
</script>

<style scoped>
    .panel-container {
        width: 100%;
        height: 100%;
        background: var(--el-bg-color-page);
    }

    .left-sub, .right-sub {
        height: 100%;
    }

    .pane-content {
        display: flex;
        flex-direction: column;
        height: 100%;
        padding: 4px;
        background: var(--el-bg-color);
        border-radius: 6px;
        overflow: hidden;
    }
</style>