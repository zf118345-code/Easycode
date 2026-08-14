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
                    <span>⚠️ 模板图片加载失败</span>
                </div>

                <!-- 实时显示二值化提示与参数角标 -->
                <div v-if="isGrayScale && !hasError" class="binary-badge">
                    二值化 (阈值: {{ grayThreshold }})
                </div>
                <div class="preview-name-badge">{{ modelValue }}</div>
            </template>
            <div v-else class="preview-empty-text">
                <Image style="width: 14px; height: 14px; margin-bottom: -3px; margin-right: 2px; opacity: 0.6;" />
                <span>暂无模板图片（悬停可选择或录入）</span>
            </div>
        </div>

        <div class="hover-action-overlay">
            <div class="overlay-half left-half" @click.stop="$emit('openBrowser', 'select')">
                <span class="action-tip">选择图片</span>
            </div>
            <div class="overlay-divider"></div>
            <div class="overlay-half right-half" @click.stop="$emit('openScreenshot', 'template')">
                <span class="action-tip">录入图片</span>
            </div>
        </div>
    </div>
</template>

<script setup>
    import { ref, computed, watch } from 'vue'
    import { Image } from 'lucide-vue-next'
    import { useMainStore } from '@/stores'
    import { visionApi } from '@/api/visionApi'

    const props = defineProps({
        config: { type: Object, required: true },
        modelValue: { type: String, default: '' },
        imageVersion: { type: Number, default: Date.now() },
        context: { type: Object, default: () => ({}) }
    })

    defineEmits(['update:modelValue', 'openBrowser', 'openScreenshot'])

    const store = useMainStore()
    const currentDisplayUrl = ref('')
    const hasError = ref(false)
    let timer = null

    const handleImgError = () => {
        if (currentDisplayUrl.value) {
            hasError.value = true
        }
    }

    const isGrayScale = computed(() => !!props.context?.gray_scale)
    const grayThreshold = computed(() => props.context?.gray_threshold ?? 127)

    const rawPreviewUrl = computed(() => {
        if (!props.modelValue) return ''
        if (props.modelValue.startsWith('http') || props.modelValue.startsWith('data:')) return props.modelValue
        let cleanName = props.modelValue.replace(/\\/g, '/')
        if (!/\.(png|jpg|jpeg)$/i.test(cleanName)) {
            cleanName += '.png'
        }
        return `/api/image/thumb?project_path=${encodeURIComponent(store.currentProjectPath || '')}&name=${encodeURIComponent(cleanName)}&t=${props.imageVersion}`
    })

    watch(
        () => [props.modelValue, isGrayScale.value, grayThreshold.value, store.currentProjectPath, props.imageVersion],
        async ([imgName, grayOn, threshold, projPath]) => {
            hasError.value = false

            if (!imgName || !projPath) {
                currentDisplayUrl.value = ''
                return
            }

            if (!grayOn) {
                currentDisplayUrl.value = rawPreviewUrl.value
                return
            }

            if (timer) clearTimeout(timer)
            timer = setTimeout(async () => {
                try {
                    const res = await visionApi.testImage(projPath, imgName, true, threshold)
                    if (res && res.image) {
                        currentDisplayUrl.value = res.image
                    } else {
                        currentDisplayUrl.value = rawPreviewUrl.value
                    }
                } catch (err) {
                    console.error('二值化预览生成失败:', err)
                    currentDisplayUrl.value = rawPreviewUrl.value
                }
            }, 120)
        },
        { immediate: true }
    )
</script>

<style scoped>
    .file-hover-card {
        position: relative;
        width: 100%;
        background: rgba(18, 19, 28, 0.95);
        border: 1px solid var(--el-border-color-light);
        border-radius: var(--app-radius-md, 8px);
        overflow: hidden;
        user-select: none;
        transition: border-color 0.3s, box-shadow 0.3s;
    }

        .file-hover-card.is-binary {
            border-color: var(--el-color-success);
            box-shadow: 0 0 8px rgba(103, 194, 58, 0.2);
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
        background: rgba(103, 194, 58, 0.85);
        color: #fff;
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: bold;
        z-index: 3;
        pointer-events: none;
    }

    .preview-name-badge {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        background: rgba(25, 26, 38, 0.85);
        color: #fff;
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
        background: rgba(25, 26, 38, 0.8);
        backdrop-filter: blur(2px);
        display: flex;
        align-items: center;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s ease;
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
        border: 2px dashed transparent;
        transition: all 0.2s;
    }

    .left-half:hover {
        border-color: var(--el-color-primary);
        background: rgba(78, 209, 156, 0.15);
    }

    .right-half:hover {
        border-color: #67C23A;
        background: rgba(103, 194, 58, 0.15);
    }

    .overlay-divider {
        width: 1px;
        height: 60%;
        background: rgba(255, 255, 255, 0.2);
    }

    .action-tip {
        font-size: 12px;
        font-weight: 600;
        color: #fff;
        text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
    }
</style>