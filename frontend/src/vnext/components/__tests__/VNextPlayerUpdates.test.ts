import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import VNextPlayerUpdates from '../VNextPlayerUpdates.vue'
import playerUpdatesSource from '../VNextPlayerUpdates.vue?raw'
import type { PlayerUpdatesResponse } from '../../types'

vi.mock('../../playerApi', () => ({
    vnextApi: {
        markPlayerUpdateSafePoint: vi.fn().mockResolvedValue({}),
        playerUpdateStatus: vi.fn().mockResolvedValue({ enabled: true, domains: {} }),
        playerUpdateApply: vi.fn().mockResolvedValue({ status: { state: 'awaiting_platform_install' } }),
    },
}))

describe('VNextPlayerUpdates', () => {
    it('renders when the bootstrap update document is a Vue reactive proxy', () => {
        const initial = reactive({
            enabled: true,
            telemetry: false,
            task_execution_requires_network: false,
            domains: {
                project_content: {
                    enabled: true,
                    state: 'available',
                    current_release_id: 'release-old',
                    current_release_sequence: 0,
                    selected_release: { release_id: 'release-new', release_sequence: 2, display_version: '2.0.0' },
                    selected_artifact: null,
                    download_path: '',
                    last_error: null,
                    last_checked_at: '',
                    preferences: { automatic_check: true, automatic_download: false, automatic_apply: false },
                    automatic_checks: true,
                    required_policy_capability: false,
                    can_start_task: true,
                    policy_block: null,
                },
            },
        } as PlayerUpdatesResponse)

        const wrapper = mount(VNextPlayerUpdates, {
            props: { initial, runtimeActive: false, uncommittedDraft: false },
        })

        expect(wrapper.text()).toContain('在线更新')
        expect(wrapper.text()).toContain('有可用版本')
        expect(wrapper.text()).toContain('2.0.0')
        expect(wrapper.findAll('.preferences label')).toHaveLength(3)
        expect(playerUpdatesSource).toContain('.preferences label{min-height:var(--app-control-default);display:flex;align-items:center')
        expect(playerUpdatesSource).toContain('.policy-block{display:flex;align-items:flex-start')
        wrapper.unmount()
    })

    it('uses an in-product confirmation before preparing an application update', async () => {
        const initial: PlayerUpdatesResponse = {
            enabled: true,
            telemetry: false,
            task_execution_requires_network: false,
            domains: {
                player_application: {
                    enabled: true,
                    state: 'staged',
                    current_release_id: 'release-old',
                    current_release_sequence: 1,
                    selected_release: { release_id: 'release-new', release_sequence: 2, display_version: '2.0.0' },
                    selected_artifact: null,
                    download_path: 'local',
                    last_error: null,
                    preferences: { automatic_check: true, automatic_download: false, automatic_apply: false },
                    automatic_checks: true,
                    required_policy_capability: false,
                    can_start_task: true,
                    policy_block: null,
                },
            },
        }
        const wrapper = mount(VNextPlayerUpdates, {
            props: { initial, runtimeActive: false, uncommittedDraft: false },
        })

        await wrapper.get('.update-actions button:last-child').trigger('click')

        expect(document.body.textContent).toContain('准备安装 Player 更新？')
        expect(document.body.textContent).toContain('启动失败时自动恢复旧版本')
        wrapper.unmount()
    })
})
