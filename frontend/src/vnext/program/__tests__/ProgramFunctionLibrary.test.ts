import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it } from 'vitest'
import ProgramFunctionLibrary from '../ProgramFunctionLibrary.vue'
import type { AvailableFunctionContractDto } from '../serverTypes'

function official(
    functionId: string,
    namespace: string,
    name: string,
    state: 'available' | 'planned' = 'available',
): AvailableFunctionContractDto {
    return {
        function_id: functionId,
        namespace,
        name,
        qualified_name: `${namespace}.${name}`,
        summary: `${namespace}${name}`,
        layer: 'atomic',
        parameters: [],
        return_type: 'unit',
        opcode: functionId,
        host_requirements: ['windows'],
        target_kinds: [],
        target_capabilities: [],
        permissions: [],
        side_effects: [],
        errors: [],
        normal_empty: false,
        network_level: 'none',
        dangerous: false,
        implementation_state: state,
        standard_definition_id: '',
        contract_version: '1.0.0',
        schema_version: 1,
        contract_fingerprint: functionId,
    }
}

describe('ProgramFunctionLibrary', () => {
    beforeEach(() => window.localStorage.clear())

    it('separates project and available official functions without list-description noise', async () => {
        const wrapper = mount(ProgramFunctionLibrary, {
            props: {
                projectFunctions: [{
                    document_id: 'doc-main',
                    function_id: 'func-main',
                    display_name: '主程序',
                    statement_count: 2,
                    revision: 'revision',
                    parameters: [],
                    return_type: 'null',
                    contract_version: '1.0.0',
                    contract_fingerprint: 'fingerprint-main',
                }],
                officialFunctions: [
                    official('official.log.output', '日志', '输出'),
                    official('official.wait.duration', '等待', '持续'),
                    official('official.image.find', '图像', '查找', 'planned'),
                ],
            },
        })

        expect(wrapper.text()).toContain('主程序')
        await wrapper.get('#function-tab-official').trigger('click')

        expect(wrapper.text()).toContain('日志')
        expect(wrapper.text()).toContain('等待')
        expect(wrapper.find('[data-function-id="official.log.output"]').exists()).toBe(false)

        await wrapper.findAll('.group-heading').find((button) => button.text().includes('日志'))?.trigger('click')
        expect(wrapper.text()).toContain('输出')
        expect(wrapper.text()).not.toContain('图像.查找')
    })

    it('uses the same semantic sentence template as configured statements while keeping legacy names searchable', async () => {
        const output = official('official.log.output', '日志', '输出')
        output.summary = '输出{content}'
        output.parameters = [{
            parameter_id: 'official.log.output.parameter.content', name: 'content', display_name: '内容',
            value_type: 'string', required: true, has_default: false, default: null, control: 'text', constraints: {}, description: '',
        }]
        const wrapper = mount(ProgramFunctionLibrary, { props: { initialTab: 'official', officialFunctions: [output] } })
        await wrapper.findAll('.group-heading').find((button) => button.text().includes('日志'))?.trigger('click')

        expect(wrapper.get('[data-function-id="official.log.output"]').text()).toBe('输出内容')
        expect(wrapper.get('.semantic-function-value').text()).toBe('内容')
        expect(wrapper.get('[data-function-id="official.log.output"]').attributes('aria-label')).toBe('输出内容')

        await wrapper.get('.library-search input').setValue('日志.输出')
        expect(wrapper.find('[data-function-id="official.log.output"]').exists()).toBe(true)
    })

    it('uses a remembered single-open accordion and expands every matching search group', async () => {
        const wrapper = mount(ProgramFunctionLibrary, {
            props: {
                initialTab: 'official',
                officialFunctions: [
                    official('official.log.output', '日志', '输出'),
                    official('official.wait.duration', '等待', '持续'),
                ],
            },
        })
        const headings = wrapper.findAll('.group-heading')
        const logHeading = headings.find((button) => button.text().includes('日志'))
        const waitHeading = headings.find((button) => button.text().includes('等待'))
        expect(wrapper.findAll('.function-list')).toHaveLength(0)

        await logHeading?.trigger('click')
        expect(logHeading?.attributes('aria-expanded')).toBe('true')
        await waitHeading?.trigger('click')
        expect(logHeading?.attributes('aria-expanded')).toBe('false')
        expect(waitHeading?.attributes('aria-expanded')).toBe('true')
        expect(window.localStorage.getItem('easycode:v6:function-library:official-domain')).toBe('等待')

        await wrapper.get('.library-search input').setValue('输')
        expect(wrapper.find('[data-function-id="official.log.output"]').exists()).toBe(true)
    })

    it('selects on one click and inserts only through double click, Enter or the explicit action', async () => {
        const wrapper = mount(ProgramFunctionLibrary, {
            props: {
                initialTab: 'official',
                officialFunctions: [official('official.log.output', '日志', '输出')],
            },
        })
        await wrapper.findAll('.group-heading').find((button) => button.text().includes('日志'))?.trigger('click')
        const row = wrapper.get('[data-function-id="official.log.output"]')

        await row.trigger('click')
        expect(wrapper.emitted('select')?.[0]?.[0]).toEqual({ source: 'official', function_id: 'official.log.output' })
        expect(wrapper.emitted('insert')).toBeUndefined()

        await row.trigger('keydown', { key: 'Enter' })
        expect(wrapper.emitted('insert')?.[0]?.[0]).toEqual({ source: 'official', function_id: 'official.log.output' })

        await wrapper.get('.row-action').trigger('click')
        expect(wrapper.emitted('insert')).toHaveLength(2)
    })

    it('classifies structures inside official domains and inserts them only through an explicit action', async () => {
        const wrapper = mount(ProgramFunctionLibrary)
        expect(wrapper.find('[data-structure-kind="if"]').exists()).toBe(false)

        await wrapper.get('#function-tab-official').trigger('click')
        expect(wrapper.text()).toContain('流程控制')
        expect(wrapper.text()).toContain('变量')
        expect(wrapper.text()).toContain('消息')
        expect(wrapper.find('[data-structure-kind="if"]').exists()).toBe(false)
        await wrapper.findAll('.group-heading').find((button) => button.text().includes('流程控制'))?.trigger('click')
        expect(wrapper.text()).toContain('尝试')
        expect(wrapper.text()).toContain('在目标中')
        expect(wrapper.text()).not.toContain('异常区域')
        const conditional = wrapper.get('[data-structure-kind="if"]')
        await conditional.trigger('click')
        expect(wrapper.emitted('select')?.at(-1)?.[0]).toEqual({ source: 'structure', function_id: 'if' })
        expect(wrapper.emitted('insert')).toBeUndefined()

        await conditional.trigger('keydown', { key: 'Enter' })
        expect(wrapper.emitted('insert')?.at(-1)?.[0]).toEqual({ source: 'structure', function_id: 'if' })

        await wrapper.findAll('.group-heading').find((button) => button.text().includes('变量'))?.trigger('click')
        expect(wrapper.text()).toContain('新建局部变量')
        const modifyVariable = wrapper.get('[data-structure-mode="assignment.existing"]')
        expect(modifyVariable.attributes('aria-label')).toBe('修改变量')
        expect(modifyVariable.text()).toContain('修改已有变量')
        await modifyVariable.trigger('keydown', { key: 'Enter' })
        expect(wrapper.emitted('insert')?.at(-1)?.[0]).toEqual({ source: 'structure', function_id: 'assignment.existing' })
        await wrapper.findAll('.group-heading').find((button) => button.text().includes('消息'))?.trigger('click')
        expect(wrapper.text()).toContain('收到消息时')
    })

    it('opens a non-callable project function instead of pretending it can be inserted', async () => {
        const wrapper = mount(ProgramFunctionLibrary, {
            props: {
                projectFunctions: [{
                    document_id: 'doc-helper',
                    function_id: 'func-helper',
                    display_name: '领取奖励',
                    statement_count: 3,
                    revision: 'revision',
                    parameters: [],
                    return_type: 'null',
                    contract_version: '1.0.0',
                    contract_fingerprint: 'fingerprint-helper',
                    insertable: false,
                }],
            },
        })

        await wrapper.get('[data-function-id="func-helper"]').trigger('click')
        expect(wrapper.emitted('openProject')?.[0]?.[0]).toBe('func-helper')
        expect(wrapper.emitted('insert')).toBeUndefined()
    })

    it('inserts callable project functions explicitly and disables direct self-call actions', async () => {
        const base = {
            document_id: 'doc-helper', function_id: 'func-helper', display_name: '领取奖励', statement_count: 3,
            revision: 'revision', parameters: [], return_type: 'null', contract_version: '1.0.0', contract_fingerprint: 'fingerprint',
        }
        const wrapper = mount(ProgramFunctionLibrary, {
            props: {
                projectFunctions: [
                    { ...base, insertable: true },
                    { ...base, document_id: 'doc-main', function_id: 'func-main', display_name: '主程序', insertable: false, insert_disabled_reason: '当前函数不能调用自身' },
                ],
            },
        })

        await wrapper.get('[data-function-id="func-helper"]').trigger('click')
        expect(wrapper.emitted('openProject')?.[0]?.[0]).toBe('func-helper')
        expect(wrapper.emitted('insert')).toBeUndefined()
        await wrapper.findAll('.row-action').find((button) => button.text() === '插入')?.trigger('click')
        expect(wrapper.emitted('insert')?.[0]?.[0]).toEqual({ source: 'project', function_id: 'func-helper' })
        const currentAction = wrapper.findAll('.row-action').find((button) => button.text() === '当前')
        expect(currentAction?.attributes('disabled')).toBeDefined()
        expect(currentAction?.attributes('title')).toBe('当前函数不能调用自身')
    })

    it('offers keyboard-accessible project lifecycle actions without turning selection into a mutation', async () => {
        const item = {
            document_id: 'doc-helper', function_id: 'func-helper', display_name: '领取奖励', statement_count: 3,
            revision: 'revision', parameters: [], return_type: 'null', contract_version: '1.0.0', contract_fingerprint: 'fingerprint',
            insertable: true,
        }
        const wrapper = mount(ProgramFunctionLibrary, { props: { projectFunctions: [item] } })

        await wrapper.get('[data-function-id="func-helper"]').trigger('click')
        expect(wrapper.emitted('renameProject')).toBeUndefined()
        expect(wrapper.emitted('deleteProject')).toBeUndefined()

        await wrapper.get('[aria-label="领取奖励的更多操作"]').trigger('click')
        const menu = wrapper.get('[role="menu"]')
        expect(menu.text()).toContain('查看或编辑')
        await menu.findAll('[role="menuitem"]')[2].trigger('click')
        expect(wrapper.emitted('renameProject')?.[0]?.[0]).toMatchObject({ function_id: 'func-helper' })

        await wrapper.get('.project-row').trigger('contextmenu')
        await wrapper.get('.danger-menu-item').trigger('click')
        expect(wrapper.emitted('deleteProject')?.[0]?.[0]).toMatchObject({ function_id: 'func-helper' })
    })

    it('opens the project menu from the keyboard, navigates it, and restores trigger focus', async () => {
        const item = {
            document_id: 'doc-helper', function_id: 'func-helper', display_name: '领取奖励', statement_count: 3,
            revision: 'revision', parameters: [], return_type: 'null', contract_version: '1.0.0', contract_fingerprint: 'fingerprint',
            insertable: true,
        }
        const wrapper = mount(ProgramFunctionLibrary, { attachTo: document.body, props: { projectFunctions: [item] } })
        const trigger = wrapper.get('[aria-label="领取奖励的更多操作"]')

        await trigger.trigger('keydown', { key: 'ArrowDown' })
        await nextTick()
        const items = wrapper.findAll('[role="menuitem"]')
        expect(document.activeElement).toBe(items[0].element)

        await items[0].trigger('keydown', { key: 'End' })
        expect(document.activeElement).toBe(items.at(-1)?.element)
        await items.at(-1)?.trigger('keydown', { key: 'Escape' })
        await nextTick()
        expect(wrapper.find('[role="menu"]').exists()).toBe(false)
        expect(document.activeElement).toBe(trigger.element)
        wrapper.unmount()
    })

    it('sorts project functions by their visible names with numeric ordering', () => {
        const base = {
            document_id: 'doc', statement_count: 1, revision: 'revision', parameters: [], return_type: 'null',
            contract_version: '1.0.0', contract_fingerprint: 'fingerprint', insertable: true,
        }
        const wrapper = mount(ProgramFunctionLibrary, { props: { projectFunctions: [
            { ...base, document_id: 'doc-03', function_id: 'func-03', display_name: '判断示例 03' },
            { ...base, document_id: 'doc-01', function_id: 'func-01', display_name: '判断示例 01' },
            { ...base, document_id: 'doc-02', function_id: 'func-02', display_name: '判断示例 02' },
        ] } })

        expect(wrapper.findAll('.project-list .function-main span').map((item) => item.text())).toEqual([
            '判断示例 01', '判断示例 02', '判断示例 03',
        ])
    })

    it('progressively renders a thousand project functions and still reveals a selected distant item', async () => {
        const projectFunctions = Array.from({ length: 1_000 }, (_, index) => ({
            document_id: `doc-${index}`, function_id: `func-${index}`,
            display_name: `项目函数 ${String(index).padStart(4, '0')}`, statement_count: 10,
            revision: 'revision', parameters: [], return_type: 'null',
            contract_version: '1.0.0', contract_fingerprint: `fingerprint-${index}`, insertable: true,
        }))
        const wrapper = mount(ProgramFunctionLibrary, { props: { projectFunctions } })

        expect(wrapper.findAll('.project-row')).toHaveLength(100)
        expect(wrapper.text()).toContain('已显示 100 / 1000')

        await wrapper.setProps({ selected: { source: 'project', function_id: 'func-999' } })
        expect(wrapper.findAll('.project-row')).toHaveLength(101)
        expect(wrapper.find('[data-function-id="func-999"]').exists()).toBe(true)
        expect(wrapper.findAll('.project-list .function-main span')[0].text()).toBe('项目函数 0999')
        expect(wrapper.text()).toContain('已显示 100 / 1000')
    })

    it('keeps extension functions in their own source tab and inserts them through the shared interaction', async () => {
        const wrapper = mount(ProgramFunctionLibrary, {
            props: {
                officialFunctions: [official('official.log.output', '日志', '输出')],
                extensionFunctions: [{
                    function_id: 'com.easycode.harness.showcase.text.decorate',
                    namespace: '展示扩展',
                    display_name: '装饰文本',
                    summary: '装饰{文本}',
                    parameters: [{ name: '文本', display_name: '文本' }],
                    description: '扩展说明只进入详情',
                    implementation_state: 'available',
                }],
            },
        })

        await wrapper.get('#function-tab-extension').trigger('click')
        expect(wrapper.text()).toContain('装饰文本')
        expect(wrapper.get('.semantic-function-value').text()).toBe('文本')
        expect(wrapper.text()).not.toContain('日志.输出')
        await wrapper.get('[data-function-id="com.easycode.harness.showcase.text.decorate"]').trigger('keydown', { key: 'Enter' })
        expect(wrapper.emitted('insert')?.at(-1)?.[0]).toEqual({
            source: 'extension',
            function_id: 'com.easycode.harness.showcase.text.decorate',
        })
    })
})
