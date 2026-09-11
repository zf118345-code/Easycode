<template>
    <section class="vnext-inspector-section app-inspector-section" :aria-labelledby="titleId || undefined">
        <div v-if="title || $slots.title || $slots.actions" class="vnext-inspector-section__header">
            <h2 v-if="title || $slots.title" :id="titleId" class="vnext-inspector-section__title">
                <slot name="title">{{ title }}</slot>
            </h2>
            <div v-if="$slots.actions" class="vnext-inspector-section__actions">
                <slot name="actions" />
            </div>
        </div>
        <div class="vnext-inspector-section__content">
            <slot />
        </div>
    </section>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
    title?: string
    titleId?: string
}>(), {
    title: '',
    titleId: '',
})
</script>

<style scoped>
.vnext-inspector-section {
    min-width: 0;
    padding: var(--app-form-section-padding) 0;
    border-bottom: 1px solid var(--app-border-subtle);
}

.vnext-inspector-section__header {
    min-width: 0;
    min-height: var(--app-control-compact);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--app-spacing-sm);
    margin-bottom: var(--app-form-heading-field-gap);
}

.vnext-inspector-section__title {
    min-width: 0;
    margin: 0;
    overflow: hidden;
    color: var(--app-text-primary);
    font-size: var(--app-font-sm);
    font-weight: 600;
    line-height: var(--app-line-height-compact);
    text-overflow: ellipsis;
    white-space: nowrap;
}

.vnext-inspector-section__actions {
    min-width: 0;
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    gap: var(--app-spacing-xs);
}
</style>
