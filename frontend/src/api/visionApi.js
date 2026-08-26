// frontend/src/api/visionApi.js
import client from './client'

export const visionApi = {
    getTemplatesTree: (projectPath) => client.get('/api/templates/tree', { params: { project_path: projectPath } }),
    getTemplatePreview: (projectPath, relativePath) => client.get('/api/templates/preview', { params: { project_path: projectPath, relative_path: relativePath } }),
    getImageThumb: (projectPath, reference) => client.get('/api/image/thumb', { params: { project_path: projectPath, name: reference }, responseType: 'blob' }),
    resolveTemplate: (projectPath, reference) => client.get('/api/templates/resolve', { params: { project_path: projectPath, reference } }),
    createTemplateFolder: (projectPath, parentPath, folderName) => client.post('/api/templates/mkdir', { project_path: projectPath, parent_path: parentPath, folder_name: folderName }),
    getTemplateImpact: (projectPath, relativePath) => client.get('/api/templates/impact', { params: { project_path: projectPath, relative_path: relativePath } }),
    deleteTemplateEntry: (projectPath, relativePath) => client.post('/api/templates/delete', { project_path: projectPath, relative_path: relativePath }),
    moveTemplateEntry: (projectPath, relativePath, targetParentPath, newName = '') => client.post('/api/templates/move', { project_path: projectPath, relative_path: relativePath, target_parent_path: targetParentPath, new_name: newName }),
    listTemplateTrash: (projectPath) => client.get('/api/templates/trash', { params: { project_path: projectPath } }),
    restoreTemplateEntry: (projectPath, transactionId) => client.post(`/api/templates/trash/${encodeURIComponent(transactionId)}/restore`, { project_path: projectPath }),
    registerTemplate: (projectPath, relativePath, kind = '') => client.post('/api/templates/register', { project_path: projectPath, relative_path: relativePath, kind }),
    getRegions: (projectPath) => client.get('/api/regions', { params: { project_path: projectPath } }),
    saveRegion: (projectPath, templateName, cropRect, referenceSize = null) => client.post('/api/regions', { project_path: projectPath, template_name: templateName, crop_rect: cropRect, reference_size: referenceSize }),
    testOcr: (projectPath, regionValue, grayScale, grayThreshold, imageSource, regionReferenceSize = [0, 0]) => client.post('/api/ocr/test', { project_path: projectPath, region_value: regionValue, gray_scale: grayScale, gray_threshold: grayThreshold, image_source: imageSource, region_reference_size: regionReferenceSize }),
    testImage: (projectPath, templateName, grayScale, grayThreshold, previewOnly = false, options = {}) => client.post('/api/image/test', {
        project_path: projectPath,
        template_name: templateName,
        gray_scale: grayScale,
        gray_threshold: grayThreshold,
        preview_only: previewOnly,
        ...options,
    })
}
