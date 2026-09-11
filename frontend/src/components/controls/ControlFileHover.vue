<!-- frontend/src/components/controls/ControlFileHover.vue -->
<template>
    <div
class="file-hover-card aspect-ratio-box"
         :class="{ 'is-binary': isGrayScale }"
         :title="modelValue ? `当前图片: ${modelValue}${isGrayScale ? ' (二值化视图)' : ''}` : '未选择图片'">
        <div class="card-preview-area">
            <template v-if="modelValue">
                <!-- 只有当有有效 URL 且未报错时才渲染图片 -->
                <img
v-if="currentDisplayUrl && !hasError"
                     :src="currentDisplayUrl"
                     class="preview-image-full"
                     alt="模板预览"
                     @error="handleImgError" />

                <!-- 图片加载失败时的优雅兜底 -->
                <div v-else-if="hasError" class="preview-empty-text error-text">
                    <TriangleAlert :size="14" />
                    <span>模板图片加载失败</span>
                </div>

                <!-- 实时显示二值化提示与参数角标 -->
                <div v-if="isGrayScale && !hasError" class="binary-badge">
                    二值化 (阈值: {{ grayThreshold }})
                </div>
                <div class="preview-name-badge">{{ displayName }}</div>
            </template>
            <div v-else class="preview-empty-text">
                <Image style="width: 14px; height: 14px; margin-bottom: -3px; margin-right: 2px; opacity: 0.6;" />
                <span>暂无模板图片（悬停可选择或录入）</span>
            </div>
        </div>

        <div class="hover-action-overlay">
            <button type="button" class="overlay-half left-half" @click.stop="$emit('openBrowser', 'select')">
                <span class="action-tip"><FolderOpen :size="15" />选择图片</span>
            </button>
            <div class="overlay-divider"></div>
            <button type="button" class="overlay-half right-half" @click.stop="$emit('openScreenshot', 'template')">
                <span class="action-tip"><Camera :size="15" />录入图片</span>
            </button>
        </div>
    </div>
</template>

<script setup>
    import { ref, computed, onUnmounted, watch } from 'vue'
    import { Camera, FolderOpen, Image, TriangleAlert } from 'lucide-vue-next'
    import { useIdeStore } from '@/stores'
    import { visionApi } from '@/api/visionApi'
    import { loadAssetPreview, releaseAssetPreview } from '@/utils/assetPreview'

    const props = defineProps({
        config: { type: Object, required: true },
        modelValue: { type: String, default: '' },
        imageVersion: { type: Number, default: Date.now() },
        context: { type: Object, default: () => ({}) }
    })

    defineEmits(['update:modelValue', 'openBrowser', 'openScreenshot'])

    const store = useIdeStore()
    const currentDisplayUrl = ref('')
    const resolvedDisplayName = ref('')
    const hasError = ref(false)
    let timer = null
    let activePreview = null
    let previewRequestId = 0

    const handleImgError = () => {
        if (currentDisplayUrl.value) {
            hasError.value = true
        }
    }

    const isGrayScale = computed(() => !!props.context?.gray_scale)
    const grayThreshold = computed(() => props.context?.gray_threshold ?? 127)
    const displayName = computed(() => resolvedDisplayName.value || props.modelValue)

    const clearPreview = () => {
        releaseAssetPreview(activePreview)
        activePreview = null
        currentDisplayUrl.value = ''
    }

    const loadRawPreview = async (projectPath, imageName, requestId) => {
        const preview = await loadAssetPreview(projectPath, imageName)
        if (requestId !== previewRequestId) {
            releaseAssetPreview(preview)
            return false
        }
        releaseAssetPreview(activePreview)
        activePreview = preview
        currentDisplayUrl.value = preview.url
        return true
    }

    // 预览只响应「换图 / 外部确认图像参数」；滑块拖动过程不直接触发后端请求。
    // NodeInspectorPanel 在灰度开关或阈值提交后更新 imageVersion，保证每次操作只刷新一次。
    watch(
        () => [props.modelValue, store.currentProjectPath, props.imageVersion],
        async ([imgName, projPath]) => {
            const grayOn = isGrayScale.value
            const threshold = grayThreshold.value
            const requestId = ++previewRequestId
            if (timer) clearTimeout(timer)
            timer = null
            clearPreview()
            hasError.value = false
            resolvedDisplayName.value = ''

            if (!imgName || !projPath) {
                currentDisplayUrl.value = ''
                return
            }

            if (imgName.startsWith('asset://')) {
                visionApi.resolveTemplate(projPath, imgName)
                    .then(asset => { resolvedDisplayName.value = asset.display_name || asset.path || imgName })
                    .catch(() => { resolvedDisplayName.value = imgName })
            }

            if (!grayOn) {
                try {
                    await loadRawPreview(projPath, imgName, requestId)
                } catch {
                    if (requestId === previewRequestId) hasError.value = true
                }
                return
            }

            timer = setTimeout(async () => {
                try {
                    const res = await visionApi.testImage(projPath, imgName, true, threshold, true)
                    if (requestId !== previewRequestId) return
                    if (res && res.image) {
                        currentDisplayUrl.value = res.image
                    } else {
                        await loadRawPreview(projPath, imgName, requestId)
                    }
                } catch (err) {
                    console.error('二值化预览生成失败:', err)
                    try {
                        await loadRawPreview(projPath, imgName, requestId)
                    } catch {
                        if (requestId === previewRequestId) hasError.value = true
                    }
                }
            }, 120)
        },
        { immediate: true }
    )

    onUnmounted(() => {
        previewRequestId += 1
        if (timer) clearTimeout(timer)
        clearPreview()
    })
</script>

<style scoped>
    .file-hover-card {
        position: relative;
        width: 100%;
        background: var(--app-bg-input);
        border: 1px solid var(--app-border-default);
        border-radius: var(--app-radius-md, 8px);
        overflow: hidden;
        user-select: none;
        transition: border-color var(--app-transition-fast);
    }

        .file-hover-card.is-binary {
            border-color: var(--app-border-strong);
        }

    .aspect-ratio-box {
        aspect-ratio: 4 / 3;
        box-sizing: border-box;
    }

    .card-preview-area {
        position: relative;
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 4px;
        box-sizing: border-box;
    }

    .preview-image-full {
        max-width: 100%;
        max-height: 100%;
        width: auto;
        height: auto;
        object-fit: contain;
    }

    .binary-badge {
        position: absolute;
        top: 6px;
        right: 6px;
        background: var(--app-bg-raised);
        border: 1px solid var(--app-border-default);
        color: var(--app-text-secondary);
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 600;
        z-index: 3;
        pointer-events: none;
    }

    .preview-name-badge {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        background: rgba(15, 15, 14, 0.9);
        color: var(--app-text-regular);
        font-size: 10px;
        padding: 2px 6px;
        text-align: center;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        z-index: 3;
    }

    .preview-empty-text {
        font-size: 11px;
        color: var(--el-text-color-placeholder);
        z-index: 2;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 5px;
    }

    .error-text {
        color: var(--el-color-danger);
    }

    .hover-action-overlay {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(15, 15, 14, 0.88);
        display: flex;
        align-items: center;
        opacity: 0;
        pointer-events: none;
        transition: opacity var(--app-transition-fast);
        z-index: 4;
    }

    .file-hover-card:hover .hover-action-overlay {
        opacity: 1;
        pointer-events: auto;
    }

    .overlay-half {
        flex: 1;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        box-sizing: border-box;
        padding: 0;
        background: transparent;
        color: inherit;
        border: 1px solid transparent;
        font: inherit;
        transition: background-color var(--app-transition-fast), border-color var(--app-transition-fast), color var(--app-transition-fast);
    }

    .overlay-half:focus-visible {
        outline: 0;
        border-color: var(--app-color-primary);
        box-shadow: inset var(--focus-ring);
    }

    .overlay-half:hover { border-color: var(--app-color-primary); background: var(--app-color-primary-dim); }

    .overlay-divider {
        width: 1px;
        height: 60%;
        background: var(--app-overlay-separator);
    }

    .action-tip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        font-weight: 600;
        color: var(--app-text-primary);
    }
</style>
