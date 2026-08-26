// frontend/src/components/__tests__/ProjectSettingsDialog.test.js
// ⚡ 项目设置页：分组元数据渲染 + 保存
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ProjectSettingsDialog from '@/components/ProjectSettingsDialog.vue'
import { useProjectStore } from '@/stores/projectStore'
import client from '@/api/client'

vi.mock('@/api/client', () => ({
    default: {
        get: vi.fn(),
        put: vi.fn()
    }
}))

const GROUPS = [
    {
        key: 'loading', title: '加载与等待', desc: '加载策略',
        fields: [
            { key: 'frame_stable_frames', label: '帧稳定判定帧数', type: 'number', min: 1, max: 10, desc: '连续几帧' },
            { key: 'page_load_poll_ms', label: '静止后识别间隔 (ms)', type: 'number', min: 50, max: 2000, desc: '识别间隔' },
        ],
    },
    {
        key: 'popup', title: '弹窗处理', desc: '弹窗参数',
        fields: [
            { key: 'popup_cooldown_ms', label: '弹窗冷却时间 (ms)', type: 'number', min: 0, max: 10000, desc: '冷却窗口' },
        ],
    },
]

describe('ProjectSettingsDialog', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        setActivePinia(createPinia())
        const store = useProjectStore()
        store.currentProjectPath = 'D:/test/proj'
        client.get.mockResolvedValue({
            settings: { frame_stable_frames: 2, page_load_poll_ms: 300, popup_cooldown_ms: 800 },
            groups: GROUPS
        })
        client.put.mockResolvedValue({
            status: 'success',
            settings: { frame_stable_frames: 4, page_load_poll_ms: 300, popup_cooldown_ms: 800 }
        })
    })

    it('按分组渲染设置项并回显当前值', async () => {
        const wrapper = mount(ProjectSettingsDialog, {
            props: { modelValue: false },
            global: { stubs: { teleport: true } }
        })
        await wrapper.setProps({ modelValue: true })
        await flushPromises()
        await wrapper.vm.$nextTick()

        expect(wrapper.vm.groups.length).toBe(2)
        expect(wrapper.vm.groups[0].title).toBe('加载与等待')
        expect(wrapper.vm.localSettings.frame_stable_frames).toBe(2)
        expect(wrapper.vm.localSettings.page_load_poll_ms).toBe(300)
        expect(wrapper.vm.localSettings.popup_cooldown_ms).toBe(800)
        // 分组标题渲染
        const text = wrapper.text()
        expect(text).toContain('加载与等待')
        expect(text).toContain('弹窗处理')
        expect(text).toContain('帧稳定判定帧数')
    })

    it('保存时只提交已修改的键（空值剔除）', async () => {
        const wrapper = mount(ProjectSettingsDialog, {
            props: { modelValue: false },
            global: { stubs: { teleport: true } }
        })
        await wrapper.setProps({ modelValue: true })
        await flushPromises()

        wrapper.vm.localSettings.frame_stable_frames = 4
        wrapper.vm.localSettings.popup_cooldown_ms = undefined  // 模拟恢复默认
        await wrapper.vm.handleSave()
        await flushPromises()

        const [url, body] = client.put.mock.calls[0]
        expect(url).toBe('/api/project/settings')
        expect(body.settings.frame_stable_frames).toBe(4)
        expect(body.settings.popup_cooldown_ms).toBeUndefined()
        expect(body.project_path).toBe('D:/test/proj')
        expect(useProjectStore().blueprint.settings.frame_stable_frames).toBe(4)
    })

    it('恢复默认清空所有自定义值', async () => {
        const wrapper = mount(ProjectSettingsDialog, {
            props: { modelValue: false },
            global: { stubs: { teleport: true } }
        })
        await wrapper.setProps({ modelValue: true })
        await flushPromises()
        wrapper.vm.restoreDefaults()
        expect(wrapper.vm.localSettings.frame_stable_frames).toBeUndefined()
        expect(wrapper.vm.localSettings.page_load_poll_ms).toBeUndefined()
    })
})
