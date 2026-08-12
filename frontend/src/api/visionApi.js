// frontend/src/api/visionApi.js
import client from './client'

export const visionApi = {
    getTemplatesTree: (projectPath) => client.get('/api/templates/tree', { params: { project_path: projectPath } }),
    getTemplatePreview: (projectPath, relativePath) => client.get('/api/templates/preview', { params: { project_path: projectPath, relative_path: relativePath } }),
    createTemplateFolder: (projectPath, parentPath, folderName) => client.post('/api/templates/mkdir', { project_path: projectPath, parent_path: parentPath, folder_name: folderName }),
    getRegions: (projectPath) => client.get('/api/regions', { params: { project_path: projectPath } }),
    saveRegion: (projectPath, templateName, cropRect) => client.post('/api/regions', { project_path: projectPath, template_name: templateName, crop_rect: cropRect }),
    testOcr: (projectPath, regionValue, grayScale, grayThreshold) => client.post('/api/ocr/test', { project_path: projectPath, region_value: regionValue, gray_scale: grayScale, gray_threshold: grayThreshold }),
    testImage: (projectPath, templateName, grayScale, grayThreshold) => client.post('/api/image/test', { project_path: projectPath, template_name: templateName, gray_scale: grayScale, gray_threshold: grayThreshold })
}