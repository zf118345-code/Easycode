// frontend/src/api/blueprintApi.js
// 项目蓝图、主流程、函数与页面地图 API
// 注: 执行相关接口 (status/stop/pause/resume/step/debug) 已统一收敛至 executionApi.js
import client from './client'

export const blueprintApi = {
    getParams: () => client.get('/api/params'),
    // 项目元数据（project.json：project_name/variables/ui_state）
    getBlueprint: (projectPath) => client.get('/api/blueprint', { params: { project_path: projectPath } }),
    saveBlueprint: (projectPath, blueprintData, workspaceIdentity) => client.post('/api/blueprint/save', { project_path: projectPath, blueprint_data: blueprintData }, { workspaceIdentity }),
    // 流程画布（workflow.json：{main_graph, functions, function_folders}）
    getWorkflow: (projectPath) => client.get('/api/workflow', { params: { project_path: projectPath } }),
    saveWorkflow: (projectPath, workflowData, workspaceIdentity) => client.post('/api/workflow/save', { project_path: projectPath, workflow_data: workflowData }, { workspaceIdentity }),
    // 页面地图（topology.json：{nodes, edges}）
    getTopology: (projectPath) => client.get('/api/topology', { params: { project_path: projectPath } }),
    saveTopology: (projectPath, topologyData, workspaceIdentity) => client.post('/api/topology/save', { project_path: projectPath, topology_data: topologyData }, { workspaceIdentity }),
    listFunctions: projectPath => client.get('/api/functions', { params: { project_path: projectPath } }),
    getFunction: (functionId, projectPath) => client.get(`/api/functions/${functionId}`, { params: { project_path: projectPath } }),
    saveFunction: (functionId, projectPath, functionData) => client.put(`/api/functions/${functionId}`, { project_path: projectPath, function_data: functionData }),
    createFunction: (projectPath, name = '新建函数', folderId = null) => client.post('/api/functions', { project_path: projectPath, name, folder_id: folderId }),
    deleteFunction: (functionId, projectPath) => client.delete(`/api/functions/${functionId}`, { params: { project_path: projectPath } }),
    duplicateFunction: (functionId, projectPath) => client.post(`/api/functions/${functionId}/duplicate`, null, { params: { project_path: projectPath } }),
    exportFunction: (functionId, projectPath) => client.get(`/api/functions/${encodeURIComponent(functionId)}/export`, {
        params: { project_path: projectPath },
        responseType: 'blob',
    }),
    importFunction: (projectPath, packagePath) => client.post('/api/functions/import', null, {
        params: { project_path: projectPath, package_path: packagePath },
    }),
    runTask: (projectPath, taskId, startNodeId, blueprintData) => client.post('/api/run', { project_path: projectPath, task_id: taskId, start_node_id: startNodeId, blueprint_data: blueprintData })
}
