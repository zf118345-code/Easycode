<template>
    <section class="vnext-form-section" :aria-labelledby="titleId || undefined">
        <header v-if="title || $slots.title || $slots.actions" class="vnext-form-section__header"><h3 v-if="title || $slots.title" :id="titleId"><slot name="title">{{ title }}</slot></h3><div v-if="$slots.actions" class="vnext-form-section__actions"><slot name="actions" /></div></header>
        <p v-if="description || $slots.description" class="vnext-form-section__description"><slot name="description">{{ description }}</slot></p>
        <div class="vnext-form-section__body"><slot /></div>
    </section>
</template>
<script setup lang="ts">withDefaults(defineProps<{ title?: string; titleId?: string; description?: string }>(), { title: '', titleId: '', description: '' })</script>
<style scoped>
.vnext-form-section { min-width: 0; padding: var(--app-form-section-padding) 0; border-bottom: 1px solid var(--app-border-subtle); }
.vnext-form-section__header { min-height: var(--app-control-compact); display: flex; align-items: center; justify-content: space-between; gap: var(--app-spacing-sm); margin-bottom: var(--app-form-heading-field-gap); }
.vnext-form-section__header h3 { min-width: 0; margin: 0; color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 600; line-height: var(--app-line-height-compact); }
.vnext-form-section__actions { display: flex; align-items: center; gap: var(--app-spacing-xs); }
.vnext-form-section__description { margin: calc(-1 * var(--app-spacing-xs)) 0 var(--app-spacing-sm); color: var(--app-text-secondary); font-size: var(--app-font-xs); line-height: var(--app-line-height-regular); }
.vnext-form-section__body { min-width: 0; display: grid; gap: var(--app-form-field-gap); }
</style>
