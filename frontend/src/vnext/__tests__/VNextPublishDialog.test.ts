import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import VNextPublishDialog from '../components/VNextPublishDialog.vue'

const api = vi.hoisted(() => ({
    playerPublishReport: vi.fn(),
    playerPackageReadiness: vi.fn(),
    publishPlayer: vi.fn(),
    packagePlayer: vi.fn(),
    packageAndroidPlayer: vi.fn(),
}))
vi.mock('../api', () => ({ vnextApi: api }))

const workspace = {
    workspace_id: 'workspace_demo', generation: 1, project_id: 'project_demo',
    project_name: '演示项目', project_path: 'D:/Demo', read_only: false,
}

describe('VNextPublishDialog', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        api.playerPublishReport.mockResolvedValue({
            valid: true, errors: [], warnings: [], source_included: false,
            required_capabilities: ['screen.capture'], supported_platforms: ['windows'],
            android_build_declared: false, minimum_android_api: 21, android_api_requirements: [],
        })
        api.playerPackageReadiness.mockResolvedValue({ ready: true, missing: [] })
        api.publishPlayer.mockResolvedValue({
            created: true, path: 'D:/Demo/dist/Demo.ecplayer', size: 123,
            release_id: 'release_123',
            signature: { algorithm: 'Ed25519', key_id: 'ed25519-sha256:key', public_key: 'key', integrity_sha256: 'hash' },
        })
        api.packagePlayer.mockResolvedValue({
            created: true, path: 'D:/Demo/dist/Player_Bundle', executable: 'D:/Demo/dist/Player_Bundle/EasycodePlayer.exe',
            release_id: 'release_123', signature: { key_id: 'ed25519-sha256:key' },
        })
        api.packageAndroidPlayer.mockResolvedValue({
            apk_path: 'D:/Demo/dist/android/EasyCodePlayer-android-debug.apk',
            evidence_path: 'D:/Demo/dist/android/EasyCodePlayer-android-debug.apk.evidence.json',
            min_sdk: 24,
            release_id: 'release_123',
            signature: { key_id: 'ed25519-sha256:key' },
        })
    })

    it('Android 项目在发布前显示自动推导的最低系统及来源', async () => {
        api.playerPublishReport.mockResolvedValue({
            valid: true, errors: [], warnings: [], source_included: false,
            required_capabilities: ['screen.capture'], supported_platforms: ['android_local'],
            android_build_declared: true,
            minimum_android_api: 24,
            android_api_requirements: [
                { display_name: '点击坐标', minimum_android_api: 24, statement_ids: ['statement.click'] },
            ],
        })
        const wrapper = mount(VNextPublishDialog, { props: { workspace } })
        await flushPromises()

        expect(wrapper.text()).toContain('Android 7.0（API 24）')
        expect(wrapper.text()).toContain('查看 Android 版本要求来源 · 1 项')
        expect(wrapper.text()).toContain('点击坐标')
        const buildButton = wrapper.findAll('footer button').find((button) => button.text().includes('生成 Android 测试 APK'))
        expect(buildButton).toBeTruthy()
        await buildButton!.trigger('click')
        await flushPromises()
        expect(api.packageAndroidPlayer).toHaveBeenCalledWith(workspace)
        expect(wrapper.text()).toContain('Android 测试 APK 已生成')
        wrapper.unmount()
    })

    it('只在后端检查通过后生成签名项目包', async () => {
        const wrapper = mount(VNextPublishDialog, { props: { workspace } })
        await flushPromises()

        expect(wrapper.text()).toContain('项目可以发布')
        expect(wrapper.text()).toContain('不进入 Player')
        await wrapper.get('button:nth-last-child(2)').trigger('click')
        await flushPromises()

        expect(api.publishPlayer).toHaveBeenCalledWith(workspace)
        expect(wrapper.text()).toContain('签名项目包已生成')
        expect(wrapper.text()).toContain('release_123')
        wrapper.unmount()
    })

    it('运行时未准备时保留 .ecplayer 出口并禁用独立 Player', async () => {
        api.playerPackageReadiness.mockResolvedValue({ ready: false, missing: ['D:/runtime/EasycodePlayer.exe'] })
        const wrapper = mount(VNextPublishDialog, { props: { workspace } })
        await flushPromises()

        expect(wrapper.text()).toContain('当前开发环境未构建')
        expect(wrapper.text()).toContain('D:/runtime/EasycodePlayer.exe')
        const buttons = wrapper.findAll('footer button')
        expect(buttons.at(-1)?.attributes('disabled')).toBeDefined()
        expect(buttons.at(-2)?.attributes('disabled')).toBeUndefined()
        wrapper.unmount()
    })

    it('发布检查失败时不给出可执行交付动作', async () => {
        api.playerPublishReport.mockResolvedValue({
            valid: false,
            errors: [{ code: 'P2110', message: '缺少必填参数控件' }],
            warnings: [], source_included: false, required_capabilities: [], supported_platforms: [],
        })
        const wrapper = mount(VNextPublishDialog, { props: { workspace } })
        await flushPromises()

        expect(wrapper.text()).toContain('还有 1 项必须处理')
        expect(wrapper.text()).toContain('P2110')
        const publish = wrapper.findAll('footer button').find((button) => button.text().includes('生成 .ecplayer'))
        expect(publish?.attributes('disabled')).toBeDefined()
        wrapper.unmount()
    })
})
