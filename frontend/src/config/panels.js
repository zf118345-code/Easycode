// src/config/panels.js
export const panelConfigs = {
  nodeList: {
    id: 'nodeList',
    title: '节点列表',
    component: 'NodeListPanel',
    defaultWidth: 300,
    defaultHeight: 400,
    minWidth: 150,
    minHeight: 100,
    actions: []
  },
  nodeEditor: {
    id: 'nodeEditor',
    title: '节点详情',
    component: 'NodeEditorPanel',
    defaultWidth: 500,
    defaultHeight: 400,
    minWidth: 200,
    minHeight: 150,
    actions: []
  },
  logPanel: {
    id: 'logPanel',
    title: '执行日志',
    component: 'LogPanel',
    defaultWidth: 400,
    defaultHeight: 200,
    minWidth: 150,
    minHeight: 100,
    actions: []
  }
}