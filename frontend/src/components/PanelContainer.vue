<template>
    <Splitpanes class="panel-container" :dbl-click-splitter="false">
        <!-- 左侧：垂直分割（任务列表 + 节点列表） -->
        <Pane size="25" min-size="15" max-size="40">
            <Splitpanes horizontal class="left-sub" :dbl-click-splitter="false">
                <Pane size="40" min-size="20" max-size="60">
                    <TaskListPanel />
                </Pane>
                <Pane size="60" min-size="20" max-size="80">
                    <NodeListPanel />
                </Pane>
            </Splitpanes>
        </Pane>

        <!-- 右侧：垂直分割（节点详情 + 执行日志） -->
        <Pane size="75">
            <Splitpanes horizontal class="right-sub" :dbl-click-splitter="false">
                <Pane size="65" min-size="20" max-size="80">
                    <div class="pane-content">
                        <PanelHeader title="节点详情" :actions="getActions('nodeEditor')" @action="handleAction" />
                        <NodeEditorPanel />
                    </div>
                </Pane>

                <!-- ⭐ 替换占位为真实的 LogPanel 面板 -->
                <Pane size="35" min-size="20" max-size="80">
                    <div class="pane-content">
                        <PanelHeader title="执行日志" :actions="[]" />
                        <LogPanel />
                    </div>
                </Pane>
            </Splitpanes>
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
    import LogPanel from './panels/LogPanel.vue'  // ⭐ 引入 LogPanel
    import { panelConfigs } from '@/config/panels.js'

    export default {
        components: {
            Splitpanes,
            Pane,
            PanelHeader,
            TaskListPanel,
            NodeListPanel,
            NodeEditorPanel,
            LogPanel
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
        background: #1a1a2e;
    }

    .left-sub, .right-sub {
        height: 100%;
    }

    .pane-content {
        display: flex;
        flex-direction: column;
        height: 100%;
        padding: 4px;
        background: #282a3a;
        border-radius: 4px;
        overflow: hidden;
    }
</style>