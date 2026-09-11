// frontend/src/config/panelsConfig.js
import { defineAsyncComponent } from 'vue'
import { FolderTree, Braces, Map, Images, Binary, ServerCog, Sliders, Terminal, Bug } from 'lucide-vue-next'

export const leftPanelsConfig = [
    {
        id: 'explorer',
        title: '主流程大纲',
        group: 'structure',
        icon: FolderTree,
        component: defineAsyncComponent(() => import('@/components/panels/ProjectExplorerPanel.vue'))
    },
    {
        id: 'functions',
        title: '函数库',
        group: 'structure',
        icon: Braces,
        component: defineAsyncComponent(() => import('@/components/panels/FunctionLibraryPanel.vue'))
    },
    {
        id: 'page-map',
        title: '页面地图',
        group: 'structure',
        icon: Map,
        component: defineAsyncComponent(() => import('@/components/panels/PageMapPanel.vue'))
    },
    {
        id: 'resources',
        title: '图片资源',
        group: 'assets',
        icon: Images,
        component: defineAsyncComponent(() => import('@/components/panels/ResourceLibraryPanel.vue'))
    },
    {
        id: 'variables',
        title: '变量与上下文',
        group: 'assets',
        icon: Binary,
        component: defineAsyncComponent(() => import('@/components/panels/GlobalVariablesPanel.vue'))
    },
    {
        id: 'runtime',
        title: '运行服务',
        group: 'runtime',
        icon: ServerCog,
        component: defineAsyncComponent(() => import('@/components/panels/RuntimeServicesPanel.vue'))
    }
]

export const rightPanelsConfig = [
    {
        id: 'inspector',
        title: '节点属性检查器',
        icon: Sliders,
        component: defineAsyncComponent(() => import('@/components/inspector/InspectorPanel.vue'))
    },
    {
        id: 'variable-inspector',
        title: '变量监控',
        icon: Bug,
        component: defineAsyncComponent(() => import('@/components/panels/VariableInspectorPanel.vue'))
    }
]

export const bottomPanelsConfig = [
    {
        id: 'console',
        title: '运行日志',
        icon: Terminal,
        component: defineAsyncComponent(() => import('@/components/canvas/CanvasLogPanel.vue'))
    }
]
