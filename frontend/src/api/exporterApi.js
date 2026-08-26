// frontend/src/api/exporterApi.js
import client from './client'

export const exporterApi = {
    /** 获取当前项目绑定的 Player 表单 Schema。 */
    getFormSchema: (projectPath) =>
        client.get('/api/exporter/schema', { params: { project_path: projectPath } }),

    /** 保存当前项目绑定的 Player 表单 Schema。 */
    saveFormSchema: (projectPath, schemaData) =>
        client.post('/api/exporter/schema', {
            project_path: projectPath,
            schema_data: schemaData,
        }),

    /** 构建项目资源与配置的加密 assets.ebp 包。 */
    buildExportBundle: (projectPath, formSchema) =>
        client.post('/api/exporter/build', {
            project_path: projectPath,
            form_schema: formSchema,
        }),
}
