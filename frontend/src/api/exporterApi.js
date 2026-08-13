// frontend/src/api/exporterApi.js
import client from './client'

export const exporterApi = {
    /**
     * 获取当前项目绑定的客户表单 Schema 定义
     */
    getFormSchema: (projectPath) => client.get('/api/exporter/schema', { params: { project_path: projectPath } }),

    /**
     * 保存当前项目绑定的客户表单 Schema 定义
     */
    saveFormSchema: (projectPath, schemaData) => client.post('/api/exporter/schema', {
        project_path: projectPath,
        schema_data: schemaData
    }),

    /**
     * 执行项目打包导出（生成 assets.ebp 加密密包）
     */
    buildExportBundle: (projectPath, formSchema) => client.post('/api/exporter/build', {
        project_path: projectPath,
        form_schema: formSchema
    })
}