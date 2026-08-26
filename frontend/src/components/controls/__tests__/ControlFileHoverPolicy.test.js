import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ControlFileHover from '../ControlFileHover.vue'
import { useProjectStore } from '@/stores'
import { visionApi } from '@/api/visionApi'

vi.mock('@/utils/assetPreview', () => ({
    loadAssetPreview: vi.fn(async () => ({ url: 'blob:preview' })),
    releaseAssetPreview: vi.fn()
}))

describe('ControlFileHover 预览刷新策略', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        useProjectStore().currentProjectPath = 'D:/project'
    })

    it('空模板不请求，参数原值变化不请求，仅显式预览版本变化后刷新一次', async () => {
        vi.useFakeTimers()
        try {
            const testImage = vi.spyOn(visionApi, 'testImage').mockResolvedValue({ image: 'data:image/png;base64,AA==' })
            const wrapper = mount(ControlFileHover, {
                props: {
                    config: { type: 'file' }, modelValue: '', imageVersion: 1,
                    context: { gray_scale: true, gray_threshold: 127 }
                }
            })
            await vi.advanceTimersByTimeAsync(150)
            expect(testImage).not.toHaveBeenCalled()

            await wrapper.setProps({ modelValue: 'templates/image/button' })
            await vi.advanceTimersByTimeAsync(150)
            await flushPromises()
            expect(testImage).toHaveBeenCalledTimes(1)

            await wrapper.setProps({ context: { gray_scale: true, gray_threshold: 180 } })
            await vi.advanceTimersByTimeAsync(150)
            expect(testImage).toHaveBeenCalledTimes(1)

            await wrapper.setProps({ imageVersion: 2 })
            await vi.advanceTimersByTimeAsync(150)
            await flushPromises()
            expect(testImage).toHaveBeenCalledTimes(2)
            wrapper.unmount()
        } finally {
            vi.useRealTimers()
        }
    })
})
