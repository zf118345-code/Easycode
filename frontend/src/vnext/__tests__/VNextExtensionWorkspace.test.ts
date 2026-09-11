import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import VNextExtensionWorkspace from '../components/VNextExtensionWorkspace.vue'
import extensionWorkspaceSource from '../components/VNextExtensionWorkspace.vue?raw'
import { useVNextStore } from '../store'

const api = vi.hoisted(() => ({
    list: vi.fn(), detail: vi.fn(), scaffold: vi.fn(), importFolder: vi.fn(),
    validate: vi.fn(), references: vi.fn(), trust: vi.fn(), untrust: vi.fn(),
    enable: vi.fn(), disable: vi.fn(), build: vi.fn(), openFolder: vi.fn(),
    sealAndroidJvm: vi.fn(), runTests: vi.fn(), delete: vi.fn(),
}))

vi.mock('../extensionApi', () => ({ extensionApi: api }))
vi.mock('../api', () => ({
    VNextApiError: class VNextApiError extends Error {},
    vnextApi: { chooseFolder: vi.fn(), chooseFile: vi.fn(), functions: vi.fn(), active: vi.fn() },
}))

const workspace = {
    workspace_id: 'workspace_1', generation: 1, project_id: 'project_1',
    project_name: '测试项目', project_path: 'D:/Projects/Test', read_only: false,
}
const unsignedPackage = {
    package_id: 'com.example.demo', display_name: '示例扩展', description: '测试严格扩展生命周期',
    version: '1.0.0', tier: 'function', publisher: { publisher_id: 'com.example', display_name: '示例' },
    scope: 'project' as const, path: 'D:/Projects/Test/extensions/com.example.demo', valid: true,
    signature_verified: true, trusted: false, enabled: false, lock_current: false, trust: null,
    permissions: ['screen.read'], network: { level: 'none' as const, rules: [] }, dependencies: [],
    contributions: [], sealed_artifacts: [], diagnostics: [],
    function_contracts: [{
        function_id: 'extension.com.example.demo.echo', qualified_name: '测试.回显', description: '返回输入',
        contract_version: '1.0.0', parameters: [{ parameter_id: 'text', name: 'text', display_name: '文本', value_type: 'text', required: true }],
        return_type: 'text', targets: ['none'], permissions: [], timeout_ms: 1000,
    }],
    host_variants: [{ variant_id: 'windows', host: 'windows' as const, runtime: 'python-worker-3.12', targets: ['none'], development_entry: 'src/main.py', entrypoints: { 'extension.com.example.demo.echo': 'echo' } }],
}

function installComponentStyles(source: string) {
    const style = document.createElement('style')
    style.dataset.extensionLayoutTest = 'true'
    style.textContent = source.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] || ''
    document.head.append(style)
}

describe('VNextExtensionWorkspace strict lifecycle', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        vi.clearAllMocks()
        vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
        api.list.mockResolvedValue({ schema_version: 1, packages: [unsignedPackage], scopes: [], worker_notice: 'Worker 不是恶意代码沙箱。' })
        api.detail.mockResolvedValue(unsignedPackage)
        api.references.mockResolvedValue({ package_id: unsignedPackage.package_id, scope: 'project', references: [] })
        api.trust.mockResolvedValue({ trusted: true })
    })
    afterEach(() => {
        vi.unstubAllGlobals()
        document.querySelectorAll('[data-extension-layout-test]').forEach((element) => element.remove())
        document.documentElement.style.removeProperty('--app-control-default')
    })

    it('使用三栏清单工作区且不提供内置 Python 源码编辑器', async () => {
        const store = useVNextStore()
        store.workspace = workspace
        store.refreshFunctions = vi.fn()
        const wrapper = mount(VNextExtensionWorkspace)
        await flushPromises()

        expect(wrapper.text()).toContain('示例扩展')
        expect(wrapper.text()).toContain('函数契约')
        expect(wrapper.text()).toContain('开发者信息')
        expect(wrapper.text()).toContain('运行模块')
        expect(wrapper.get('.developer-details').attributes('open')).toBeUndefined()
        expect(wrapper.text()).toContain('信任此发布者代码')
        expect(wrapper.find('textarea[aria-label="Python 扩展源码"]').exists()).toBe(false)
        expect(api.detail).toHaveBeenCalledWith(workspace, 'com.example.demo', 'project')
    })

    it('信任按钮调用真实生命周期 API 而不自动启用', async () => {
        const store = useVNextStore()
        store.workspace = workspace
        store.refreshFunctions = vi.fn()
        const wrapper = mount(VNextExtensionWorkspace)
        await flushPromises()

        const trust = wrapper.findAll('button').find((button) => button.text().includes('信任此发布者代码'))
        expect(trust).toBeTruthy()
        await trust!.trigger('click')
        await flushPromises()

        expect(api.trust).toHaveBeenCalledWith(workspace, 'com.example.demo', 'project')
        expect(api.enable).not.toHaveBeenCalled()
    })

    it('项目与用户范围都从同一个签名包导入且不自动信任', async () => {
        const store = useVNextStore()
        store.workspace = workspace
        store.chooseFolder = vi.fn().mockResolvedValue('D:/Packages/minimal-python')
        store.refreshFunctions = vi.fn()
        api.importFolder.mockResolvedValue({ imported: true, package: unsignedPackage })
        const wrapper = mount(VNextExtensionWorkspace)
        await flushPromises()

        await wrapper.get('button[aria-label="导入扩展到当前用户"]').trigger('click')
        await flushPromises()
        expect(api.importFolder).toHaveBeenCalledWith(workspace, 'D:/Packages/minimal-python', 'user')
        expect(api.trust).not.toHaveBeenCalled()
        expect(api.enable).not.toHaveBeenCalled()

        await wrapper.get('button[aria-label="导入扩展到当前项目"]').trigger('click')
        await flushPromises()
        expect(api.importFolder).toHaveBeenCalledWith(workspace, 'D:/Packages/minimal-python', 'project')
    })

    it('扩展创建的普通字段同行并保持 32px Control，多行说明独立纵向', async () => {
        const store = useVNextStore()
        store.workspace = workspace
        store.refreshFunctions = vi.fn()
        installComponentStyles(extensionWorkspaceSource)
        document.documentElement.style.setProperty('--app-control-default', '32px')
        const wrapper = mount(VNextExtensionWorkspace, { attachTo: document.body })
        await flushPromises()
        await wrapper.get('[aria-label="新建扩展骨架"]').trigger('click')
        await flushPromises()

        const ordinary = wrapper.get('.create-dialog .inline-field')
        const description = wrapper.get('.create-dialog .multiline-field')
        expect(getComputedStyle(ordinary.element).display).toBe('grid')
        expect(getComputedStyle(ordinary.element).gridTemplateColumns).toContain('minmax')
        expect(getComputedStyle(ordinary.get('input').element).height).toBe('var(--app-control-default)')
        expect(getComputedStyle(description.element).display).toBe('flex')
        expect(description.get('textarea').attributes('placeholder')).toContain('适用场景')
        expect(extensionWorkspaceSource).toContain('@media(max-width:620px)')
        expect(extensionWorkspaceSource).toContain('.create-dialog label.inline-field{grid-template-columns:1fr')
        wrapper.unmount()
    })

    it('对 Android Kotlin 变体选择 JAR 并调用密封入口', async () => {
        const androidPackage = {
            ...unsignedPackage,
            trusted: true,
            host_variants: [{
                variant_id: 'android.api24', host: 'android_native' as const,
                runtime: 'android-kotlin-v1', targets: ['android_native'],
                minimum_android_api: 24,
                entrypoints: { 'extension.com.example.demo.echo': 'com.example.demo.EchoExtension' },
            }],
        }
        api.list.mockResolvedValue({ schema_version: 1, packages: [androidPackage], scopes: [], worker_notice: 'Worker 不是恶意代码沙箱。' })
        api.detail.mockResolvedValue(androidPackage)
        api.sealAndroidJvm.mockResolvedValue({ sealed: true })
        const store = useVNextStore()
        store.workspace = workspace
        store.refreshFunctions = vi.fn()
        store.chooseFile = vi.fn().mockResolvedValue('D:/Build/demo.jar')
        const wrapper = mount(VNextExtensionWorkspace)
        await flushPromises()

        expect(wrapper.text()).toContain('Android 7.0+')
        const importJar = wrapper.findAll('button').find((button) => button.text().includes('导入 JAR'))
        expect(importJar).toBeTruthy()
        await importJar!.trigger('click')
        await flushPromises()

        expect(store.chooseFile).toHaveBeenCalledWith('选择 Android 扩展 JAR', ['jar'])
        expect(api.sealAndroidJvm).toHaveBeenCalledWith(
            workspace, androidPackage.package_id, 'project', 'android.api24', 'D:/Build/demo.jar',
        )
    })

    it('窄屏按需打开扩展状态抽屉并可用 Escape 关闭', async () => {
        vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
        const store = useVNextStore()
        store.workspace = workspace
        store.refreshFunctions = vi.fn()
        const wrapper = mount(VNextExtensionWorkspace, { attachTo: document.body })
        await flushPromises()

        expect(wrapper.find('.action-pane').exists()).toBe(false)
        await wrapper.get('button[aria-label="打开扩展状态与操作"]').trigger('click')
        await flushPromises()
        expect(wrapper.find('.action-pane.is-compact').exists()).toBe(true)
        expect(document.activeElement).toBe(wrapper.get('.action-pane-close').element)

        await wrapper.get('.action-pane').trigger('keydown', { key: 'Escape' })
        await flushPromises()
        expect(wrapper.find('.action-pane').exists()).toBe(false)
        expect(document.activeElement).toBe(wrapper.get('button[aria-label="打开扩展状态与操作"]').element)
        wrapper.unmount()
    })
})
