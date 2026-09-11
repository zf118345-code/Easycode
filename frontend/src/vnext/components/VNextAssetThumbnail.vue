<template>
    <span
        v-if="asset"
        class="asset-thumbnail"
        :style="{ '--asset-thumb-size': `${size}px` }"
        role="img"
        :aria-label="`图片资源：${displayName || asset.display_name}`"
        tabindex="0"
        @mouseenter="ensurePreview"
        @focus="ensurePreview"
    >
        <img v-if="previewUrl" class="asset-thumbnail-image" :src="previewUrl" alt="" />
        <ImageIcon v-else :size="Math.max(12, size - 3)" aria-hidden="true" />
        <span v-if="previewUrl && showPopover" class="asset-thumbnail-popover" role="tooltip">
            <img :src="previewUrl" alt="" />
            <span>{{ displayName || asset.display_name }}</span>
        </span>
    </span>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Image as ImageIcon } from 'lucide-vue-next'
import type { AssetDefinition } from '../types'

const props = withDefaults(defineProps<{
    asset?: AssetDefinition | null
    loadPreview?: ((assetId: string) => Promise<string>) | null
    size?: number
    eager?: boolean
    ownsPreviewUrl?: boolean
    displayName?: string
    showPopover?: boolean
}>(), {
    asset: null,
    loadPreview: null,
    size: 18,
    eager: false,
    ownsPreviewUrl: true,
    displayName: '',
    showPopover: true,
})

const previewUrl = ref('')
const loading = ref(false)
const failedAssetId = ref('')
let generation = 0

function releasePreview(): void {
    if (props.ownsPreviewUrl && previewUrl.value.startsWith('blob:') && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(previewUrl.value)
    }
    previewUrl.value = ''
}

async function ensurePreview(): Promise<void> {
    const assetId = props.asset?.asset_id || ''
    if (!assetId || !props.loadPreview || previewUrl.value || loading.value || failedAssetId.value === assetId) return
    const requestGeneration = ++generation
    loading.value = true
    try {
        const url = await props.loadPreview(assetId)
        if (requestGeneration !== generation || props.asset?.asset_id !== assetId) {
            if (props.ownsPreviewUrl && url.startsWith('blob:') && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(url)
            return
        }
        previewUrl.value = url
    } catch {
        if (requestGeneration === generation) failedAssetId.value = assetId
    } finally {
        if (requestGeneration === generation) loading.value = false
    }
}

watch(() => `${props.asset?.asset_id || ''}:${props.asset?.updated_at || ''}`, () => {
    generation += 1
    loading.value = false
    failedAssetId.value = ''
    releasePreview()
    if (props.eager) void Promise.resolve().then(ensurePreview)
})

onMounted(() => {
    if (props.eager) void ensurePreview()
})

onBeforeUnmount(() => {
    generation += 1
    releasePreview()
})
</script>

<style scoped>
.asset-thumbnail {
    --asset-thumb-size: 18px;
    position: relative;
    width: var(--asset-thumb-size);
    height: var(--asset-thumb-size);
    display: inline-grid;
    flex: 0 0 var(--asset-thumb-size);
    place-items: center;
    border: 1px solid var(--app-border-subtle);
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-input);
    color: var(--app-text-muted);
    outline: none;
}
.asset-thumbnail:focus-visible { box-shadow: var(--focus-ring); }
.asset-thumbnail-image { width: 100%; height: 100%; border-radius: 3px; object-fit: cover; }
.asset-thumbnail-popover {
    position: absolute;
    z-index: 40;
    inset-inline-start: calc(100% + 7px);
    top: 50%;
    width: 174px;
    display: none;
    overflow: hidden;
    transform: translateY(-50%);
    border: 1px solid var(--app-border-strong);
    border-radius: var(--app-radius-md);
    background: var(--app-bg-raised);
    box-shadow: 0 10px 28px rgba(0, 0, 0, .32);
    color: var(--app-text-regular);
}
.asset-thumbnail-popover img { width: 100%; max-height: 132px; display: block; object-fit: contain; background: var(--app-bg-input); }
.asset-thumbnail-popover span { display: block; overflow: hidden; padding: 7px 8px; font-size: var(--app-font-caption); text-overflow: ellipsis; white-space: nowrap; }
.asset-thumbnail:hover .asset-thumbnail-popover,
.asset-thumbnail:focus .asset-thumbnail-popover { display: block; }
</style>
