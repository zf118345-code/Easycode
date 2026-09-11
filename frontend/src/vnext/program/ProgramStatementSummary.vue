<template>
    <span class="statement-summary" :title="accessibleText">
        <span
            v-for="(part, index) in parts"
            :key="`${index}:${part.parameter_id || part.text}`"
            :class="{ 'statement-dynamic-value': part.dynamic, 'is-image-value': imageValue(part) }"
        >
            <template v-if="imageValue(part)">
                <VNextAssetThumbnail
                    v-if="imageAsset(part)"
                    :asset="imageAsset(part)"
                    :load-preview="loadAssetPreview"
                    :size="20"
                    eager
                    :owns-preview-url="false"
                    :display-name="imageLabel(part)"
                    :show-popover="false"
                />
                <ImageIcon v-else :size="15" class="missing-image-icon" aria-hidden="true" />
                <span class="image-value-name">{{ imageLabel(part) }}</span>
            </template>
            <template v-else>{{ part.text }}</template>
        </span>
    </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Image as ImageIcon } from 'lucide-vue-next'
import VNextAssetThumbnail from '../components/VNextAssetThumbnail.vue'
import type { ProgramAsset, ProgramSummaryPart } from './types'
import { readableImageName, summaryPartText } from './summaryPresentation'

const props = withDefaults(defineProps<{
    parts: ProgramSummaryPart[]
    assets?: ProgramAsset[]
    loadAssetPreview?: ((assetId: string) => Promise<string>) | null
}>(), {
    assets: () => [],
    loadAssetPreview: null,
})

const assetsById = computed(() => new Map(props.assets.map((asset) => [asset.asset_id, asset])))
function imageValue(part: ProgramSummaryPart) {
    return part.value?.kind === 'asset_ref' && part.value.asset_kind === 'image' ? part.value : null
}

function imageAsset(part: ProgramSummaryPart): ProgramAsset | null {
    const value = imageValue(part)
    return value ? assetsById.value.get(value.asset_id) || null : null
}

function imageLabel(part: ProgramSummaryPart): string {
    const value = imageValue(part)
    const asset = imageAsset(part)
    if (!value || !asset) return '图片已失效'
    return readableImageName(asset.display_name || value.display_name || '')
}

const accessibleText = computed(() => props.parts.map((part) => summaryPartText(part, props.assets)).join(''))
</script>

<style scoped>
.statement-summary {
    overflow: hidden;
    color: inherit;
    font-size: var(--app-font-sm);
    font-weight: 450;
    line-height: inherit;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.statement-dynamic-value {
    position: relative;
    display: inline-block;
    margin-inline: 2px;
    padding-inline: 6px;
    color: inherit;
    font: inherit;
    letter-spacing: inherit;
    line-height: inherit;
    vertical-align: baseline;
}

.statement-dynamic-value::before,
.statement-dynamic-value::after {
    position: absolute;
    width: 4px;
    height: 55%;
    border-color: var(--app-text-muted);
    content: '';
    pointer-events: none;
}

.statement-dynamic-value::before {
    inset-block-start: 2px;
    inset-inline-start: 0;
    border-block-start: 1px solid;
    border-inline-start: 1px solid;
}

.statement-dynamic-value::after {
    inset-inline-end: 0;
    inset-block-end: 2px;
    border-inline-end: 1px solid;
    border-block-end: 1px solid;
}

.is-image-value {
    display: inline-flex;
    min-width: 0;
    align-items: center;
    gap: 5px;
}
.image-value-name {
    overflow: hidden;
    max-width: 132px;
    text-overflow: ellipsis;
}
.missing-image-icon { flex: 0 0 auto; color: var(--app-color-danger); }
</style>
