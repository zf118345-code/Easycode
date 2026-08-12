// frontend/src/api/blueprintApi.js
import client from './client'

export const blueprintApi = {
    getParams: () => client.get('/api/params'),
    verifyProject: (projectPath) => client.get('/api/projects/verify', { params: { project_path: projectPath } }),
    getBlueprint: (projectPath) => client.get('/api/blueprint', { params: { project_path: projectPath } }),
    saveBlueprint: (projectPath, blueprintData) => client.post('/api/blueprint/save', { project_path: projectPath, blueprint_data: blueprintData }),
    listTasks: (projectPath) => client.get('/api/tasks', { params: { project_path: projectPath } }),
    getTask: (taskId, projectPath) => client.get(`/api/tasks/${taskId}`, { params: { project_path: projectPath } }),
    saveTask: (taskId, projectPath, taskData) => client.put(`/api/tasks/${taskId}`, { project_path: projectPath, task_data: taskData }),
    createTask: (projectPath, taskData) => client.post('/api/tasks', { project_path: projectPath, task_data: taskData }),
    deleteTask: (taskId, projectPath) => client.delete(`/api/tasks/${taskId}`, { params: { project_path: projectPath } }),
    getTaskNodes: (taskId, projectPath) => client.get(`/api/tasks/${taskId}/nodes`, { params: { project_path: projectPath } }),
    saveTaskOrder: (projectPath, order) => client.post('/api/tasks/order', { project_path: projectPath, order }),
    runTask: (projectPath, taskId, startNodeId, blueprintData) => client.post('/api/run', { project_path: projectPath, task_id: taskId, start_node_id: startNodeId, blueprint_data: blueprintData }),
    getExecutionStatus: (executionId) => client.get(`/api/execution/${executionId}`)
}