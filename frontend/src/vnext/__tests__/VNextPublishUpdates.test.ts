import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
    updateConfiguration: vi.fn(),
    saveUpdateConfiguration: vi.fn(),
    initializeUpdateRepository: vi.fn(),
    publishProjectContentUpdate: vi.fn(),
    setUpdateRollout: vi.fn(),
    setRequiredUpdatePolicy: vi.fn(),
}))

vi.mock('../api', () => ({ vnextApi: api }))

import VNextPublishUpdates from '../components/VNextPublishUpdates.vue'
import publishUpdatesSource from '../components/VNextPublishUpdates.vue?raw'

const workspace = {
    workspace_id: 'workspace-updates', generation: 1, project_id: 'project-updates',
    project_name: '更新项目', project_path: 'D:/Updates', read_only: false,
}
const domain = (enabled: boolean, pinned: boolean) => ({
    enabled,
    product_id: enabled ? 'project-updates.project_content' : '',
    provider: 'self_hosted' as const,
    feed_base_url: 'https://updates.example.com/feed',
    channel: 'stable' as const,
    required_policy_capability: true,
    initial_preferences: {},
    pinned_root: pinned ? { key_id: 'test-key' } : null,
})

function installComponentStyles(source: string) {
    const style = document.createElement('style')
    style.dataset.publishUpdatesLayoutTest = 'true'
    style.textContent = source.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] || ''
    document.head.append(style)
}

describe('VNextPublishUpdates form layout', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        api.updateConfiguration.mockResolvedValue({ configuration: {
            schema_version: 1,
            domains: {
                player_application: domain(false, false),
                project_content: domain(true, true),
            },
        } })
    })
    afterEach(() => {
        document.querySelectorAll('[data-publish-updates-layout-test]').forEach((element) => element.remove())
        document.documentElement.style.removeProperty('--app-control-default')
    })

    it('普通发布字段同行且为 32px，发布说明与策略文本保留纵向编辑', async () => {
        installComponentStyles(publishUpdatesSource)
        document.documentElement.style.setProperty('--app-control-default', '32px')
        const wrapper = mount(VNextPublishUpdates, { props: { workspace }, attachTo: document.body })
        await flushPromises()

        const productId = wrapper.get('.domain-settings .inline-field')
        const releaseNotes = wrapper.get('.release-tools .multiline-field')
        expect(getComputedStyle(productId.element).display).toBe('grid')
        expect(getComputedStyle(productId.element).gridTemplateColumns).toContain('minmax')
        expect(getComputedStyle(productId.get('input').element).height).toBe('var(--app-control-default)')
        expect(getComputedStyle(releaseNotes.element).display).toBe('flex')
        expect(releaseNotes.find('textarea').exists()).toBe(true)
        expect(wrapper.get('textarea[placeholder="说明这次内容变化"]').attributes('maxlength')).toBe('4000')
        expect(publishUpdatesSource).toContain('@media(max-width:620px)')
        expect(publishUpdatesSource).toContain('.field-grid label.inline-field,.field-grid.compact label.inline-field')
        wrapper.unmount()
    })
})
