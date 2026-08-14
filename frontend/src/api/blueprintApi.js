// frontend/src/api/blueprintApi.js
// 蓝图与任务管理 API
// 注: 执行相关接口 (status/stop/pause/resume/step/debug) 已统一收敛至 executionApi.js
import client from './client'

export const blueprintApi = {
    getParams: () => client.get('/api/params'),
    verifyProject: (projectPath) => client.get('/api/projects/verify', { params: { project_path: projectPath } }),
    // 项目元数据（project.json：project_name/variables/ui_state）
    getBlueprint: (projectPath) => client.get('/api/blueprint', { params: { project_path: projectPath } }),
    saveBlueprint: (projectPath, blueprintData) => client.post('/api/blueprint/save', { project_path: projectPath, blueprint_data: blueprintData }),
    // 流程画布（workflow.json：{tasks, edges}）
    getWorkflow: (projectPath) => client.get('/api/workflow', { params: { project_path: projectPath } }),
    saveWorkflow: (projectPath, workflowData) => client.post('/api/workflow/save', { project_path: projectPath, workflow_data: workflowData }),
    // 拓扑地图（topology.json：{tasks, edges}）
    getTopology: (projectPath) => client.get('/api/topology', { params: { project_path: projectPath } }),
    saveTopology: (projectPath, topologyData) => client.post('/api/topology/save', { project_path: projectPath, topology_data: topologyData }),
    // 任务 CRUD
    listTasks: (projectPath) => client.get('/api/tasks', { params: { project_path: projectPath } }),
    getTask: (taskId, projectPath) => client.get(`/api/tasks/${taskId}`, { params: { project_path: projectPath } }),
    saveTask: (taskId, projectPath, taskData) => client.put(`/api/tasks/${taskId}`, { project_path: projectPath, task_data: taskData }),
    createTask: (projectPath, taskData) => client.post('/api/tasks', { project_path: projectPath, task_data: taskData }),
    deleteTask: (taskId, projectPath) => client.delete(`/api/tasks/${taskId}`, { params: { project_path: projectPath } }),
    getTaskNodes: (taskId, projectPath) => client.get(`/api/tasks/${taskId}/nodes`, { params: { project_path: projectPath } }),
    runTask: (projectPath, taskId, startNodeId, blueprintData) => client.post('/api/run', { project_path: projectPath, task_id: taskId, start_node_id: startNodeId, blueprint_data: blueprintData })
}
