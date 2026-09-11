import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ProgramStatementList from '../ProgramStatementList.vue'
import type { ProgramStatement } from '../types'
import type { FunctionCatalogCandidate } from '../functionCatalogSearch'

function call(statementId: string, displayName: string): ProgramStatement {
    return {
        statement_id: statementId,
        kind: 'call',
        function_id: `builtin.${statementId}`,
        display_name: displayName,
        arguments: {},
    }
}

const quickCandidates: FunctionCatalogCandidate[] = [{
    key: 'official:official.control.click',
    selection: { source: 'official', function_id: 'official.control.click' },
    label: '点击控件', namespace: '控件', sourceLabel: '官方', description: '控件.点击',
    parts: [{ text: '点击控件' }], searchTerms: ['控件', '点击'],
}]

describe('ProgramStatementList', () => {
    it('projects configured target names instead of a generic target placeholder', () => {
        const wrapper = mount(ProgramStatementList, {
            props: {
                statements: [{
                    statement_id: 'scope_windows', kind: 'target_scope',
                    target: { value_id: 'target_value', value_type: 'target_ref', kind: 'target_ref', target_id: 'target_windows' },
                    body: [],
                }],
                targetOptions: [{ label: '微信', value: 'target_windows' }],
            },
        })

        expect(wrapper.text()).toContain('在微信中执行')
        expect(wrapper.find('.statement-dynamic-value').text()).toBe('微信')
        expect(wrapper.text()).not.toContain('运行目标')
    })

    it('teaches the real insertion path in the empty state', async () => {
        const wrapper = mount(ProgramStatementList, { props: { statements: [] } })

        expect(wrapper.text()).toContain('这个函数还没有语句')
        await wrapper.get('button').trigger('click')
        expect(wrapper.emitted('requestFunctionLibrary')).toHaveLength(1)
    })

    it('opens one transient search row after the selected statement and inserts only after confirmation', async () => {
        const insertQuickFunction = vi.fn().mockResolvedValue(undefined)
        const wrapper = mount(ProgramStatementList, {
            props: {
                statements: [call('stmt_1', '第一条'), call('stmt_2', '第二条')],
                selectedStatementIds: ['stmt_1'], quickInsertCandidates: quickCandidates, insertQuickFunction,
            },
        })

        await wrapper.get('[data-statement-id="stmt_1"]').trigger('keydown', { key: 'Enter' })
        expect(wrapper.find('.quick-insert').exists()).toBe(true)
        expect(insertQuickFunction).not.toHaveBeenCalled()
        await wrapper.get('.quick-insert input').setValue('控件')
        await wrapper.get('.quick-insert input').trigger('keydown', { key: 'Enter' })
        await flushPromises()
        expect(insertQuickFunction).toHaveBeenCalledWith({ source: 'official', function_id: 'official.control.click' })
        expect(wrapper.find('.quick-insert').exists()).toBe(false)
    })

    it('places the transient row after the whole selected structure and cancels without an insert', async () => {
        const conditional: ProgramStatement = {
            statement_id: 'stmt_if', kind: 'if',
            condition: { value_id: 'condition', value_type: 'bool', kind: 'literal', value: true },
            then_body: [call('stmt_child', '子语句')], additional_branches: [], else_body: [],
        }
        const insertQuickFunction = vi.fn().mockResolvedValue(undefined)
        const wrapper = mount(ProgramStatementList, {
            props: {
                statements: [conditional, call('stmt_after', '块后语句')], selectedStatementIds: ['stmt_if'],
                quickInsertCandidates: quickCandidates, insertQuickFunction,
            },
        })

        await wrapper.get('[data-statement-id="stmt_if"]').trigger('keydown', { key: 'Enter' })
        const order = wrapper.findAll('.statement-row, .quick-insert').map((item) =>
            item.classes().includes('quick-insert') ? 'quick' : item.attributes('data-statement-id'))
        expect(order).toEqual(['stmt_if', 'stmt_child', 'quick', 'stmt_after'])
        await wrapper.get('.quick-insert input').trigger('keydown', { key: 'Escape' })
        expect(wrapper.find('.quick-insert').exists()).toBe(false)
        expect(insertQuickFunction).not.toHaveBeenCalled()
    })

    it('supports Ctrl+Enter and the select-then-Enter branch workflow', async () => {
        const conditional: ProgramStatement = {
            statement_id: 'stmt_if', kind: 'if',
            condition: { value_id: 'condition', value_type: 'bool', kind: 'literal', value: true },
            then_body: [], additional_branches: [], else_body: [],
        }
        const wrapper = mount(ProgramStatementList, {
            props: {
                statements: [conditional, call('stmt_after', '块后语句')], selectedStatementIds: [],
                quickInsertCandidates: quickCandidates, insertQuickFunction: vi.fn().mockResolvedValue(undefined),
            },
        })

        await wrapper.get('[data-statement-id="stmt_after"]').trigger('keydown', { key: 'Enter', ctrlKey: true })
        expect(wrapper.find('.quick-insert').exists()).toBe(true)
        await wrapper.get('.quick-insert input').trigger('keydown', { key: 'Escape' })

        const branch = wrapper.findAll('.branch-row').find((row) => row.text().includes('那么'))
        await branch?.trigger('keydown', { key: 'Enter' })
        expect(wrapper.find('.quick-insert').exists()).toBe(false)
        await wrapper.setProps({ selectedInsertionTargetKey: branch?.attributes('data-branch-key') })
        await branch?.trigger('keydown', { key: 'Enter' })
        expect(wrapper.find('.quick-insert').exists()).toBe(true)
    })

    it('gives every branch the same nearby plus action and renders the search at the branch end', async () => {
        const conditional: ProgramStatement = {
            statement_id: 'stmt_if', kind: 'if',
            condition: { value_id: 'condition', value_type: 'bool', kind: 'literal', value: true },
            then_body: [call('stmt_then_child', '那么中的语句')], additional_branches: [], else_body: [],
        }
        const insertQuickFunction = vi.fn().mockResolvedValue(undefined)
        const wrapper = mount(ProgramStatementList, {
            props: {
                statements: [conditional, call('stmt_after', '条件块后语句')],
                quickInsertCandidates: quickCandidates, insertQuickFunction,
            },
        })

        const branches = wrapper.findAll('.branch-row')
        expect(branches).toHaveLength(2)
        expect(branches.every((branch) => branch.find('.branch-insert-action').exists())).toBe(true)

        await wrapper.get('button[aria-label="在“那么”中插入语句"]').trigger('click')
        const order = wrapper.findAll('.statement-row, .quick-insert').map((item) =>
            item.classes().includes('quick-insert') ? 'quick' : item.attributes('data-statement-id'))
        expect(order).toEqual(['stmt_if', 'stmt_then_child', 'quick', 'stmt_after'])
        expect(wrapper.emitted('update:insertionTarget')?.at(-1)?.[0]).toMatchObject({ block: 'then' })

        await wrapper.get('.quick-insert input').trigger('keydown', { key: 'Escape' })
        await wrapper.get('button[aria-label="添加“否则”分支并插入语句"]').trigger('click')
        expect(wrapper.find('.quick-insert').exists()).toBe(true)
        expect(wrapper.emitted('update:insertionTarget')?.at(-1)?.[0]).toMatchObject({ block: 'otherwise' })
        expect(insertQuickFunction).not.toHaveBeenCalled()
    })

    it('supports keyboard selection, movement, copy and deletion', async () => {
        const wrapper = mount(ProgramStatementList, {
            props: {
                statements: [call('stmt_1', '第一条'), call('stmt_2', '第二条'), call('stmt_3', '第三条')],
                selectedStatementIds: ['stmt_2'],
            },
        })
        const row = wrapper.get('[data-statement-id="stmt_2"]')

        await row.trigger('keydown', { key: 'ArrowUp', ctrlKey: true })
        expect(wrapper.emitted('action')?.[0]?.[0]).toEqual({
            kind: 'move',
            statement_ids: ['stmt_2'],
            direction: 'up',
        })

        await row.trigger('keydown', { key: 'd', ctrlKey: true })
        expect(wrapper.emitted('action')?.[1]?.[0]).toEqual({ kind: 'duplicate', statement_ids: ['stmt_2'] })

        await row.trigger('keydown', { key: 'Delete' })
        expect(wrapper.emitted('action')?.[2]?.[0]).toEqual({
            kind: 'delete',
            statement_ids: ['stmt_2'],
            fallback_statement_id: 'stmt_3',
        })

        await row.trigger('keydown', { key: 'ArrowDown' })
        expect(wrapper.emitted('update:selectedStatementIds')?.at(-1)?.[0]).toEqual(['stmt_3'])

    })

    it('keeps copy, deferred cut and paste as distinct standard keyboard actions', async () => {
        const wrapper = mount(ProgramStatementList, {
            props: {
                statements: [call('stmt_1', '第一条'), call('stmt_2', '第二条')],
                selectedStatementIds: ['stmt_1'],
                pendingCutStatementIds: ['stmt_1'],
                canPaste: true,
            },
        })
        const row = wrapper.get('[data-statement-id="stmt_1"]')
        expect(row.classes()).toContain('is-cut-pending')
        expect(row.attributes('aria-label')).toContain('已剪切，等待粘贴')

        await row.trigger('keydown', { key: 'c', ctrlKey: true })
        await row.trigger('keydown', { key: 'x', ctrlKey: true })
        await row.trigger('keydown', { key: 'v', ctrlKey: true })
        await row.trigger('keydown', { key: 'Escape' })

        expect(wrapper.emitted('action')?.map((event) => event[0])).toEqual([
            { kind: 'copy', statement_ids: ['stmt_1'] },
            { kind: 'cut', statement_ids: ['stmt_1'] },
            { kind: 'paste', statement_ids: ['stmt_1'] },
            { kind: 'cancel-clipboard', statement_ids: ['stmt_1'] },
        ])
    })

    it('lets Escape cancel a pending cut while the more-actions trigger has focus', async () => {
        const wrapper = mount(ProgramStatementList, {
            props: {
                statements: [call('stmt_1', '第一条')],
                selectedStatementIds: ['stmt_1'],
                pendingCutStatementIds: ['stmt_1'],
            },
        })
        const trigger = wrapper.get('[data-statement-id="stmt_1"] [aria-label="更多语句操作"]')
        await trigger.trigger('keydown', { key: 'Escape' })

        expect(wrapper.emitted('action')?.at(-1)?.[0]).toEqual({
            kind: 'cancel-clipboard', statement_ids: ['stmt_1'],
        })
    })

    it('offers extraction for the current structural selection', async () => {
        const wrapper = mount(ProgramStatementList, {
            props: {
                statements: [call('stmt_1', '第一条'), call('stmt_2', '第二条')],
                selectedStatementIds: ['stmt_1', 'stmt_2'],
            },
        })

        await wrapper.get('button[aria-label="更多语句操作"]').trigger('click')
        await wrapper.findAll('[role="menuitem"]').find((item) => item.text().includes('提取为项目函数'))?.trigger('click')

        expect(wrapper.emitted('action')?.at(-1)?.[0]).toEqual({
            kind: 'extract', statement_ids: ['stmt_1', 'stmt_2'],
        })
    })

    it('uses Tab and Shift+Tab only when a valid structural destination exists', async () => {
        const conditional: ProgramStatement = {
            statement_id: 'stmt_if', kind: 'if',
            condition: { value_id: 'value_condition', value_type: 'bool', kind: 'literal', value: true },
            then_body: [call('stmt_child', '子语句')], additional_branches: [], else_body: [],
        }
        const wrapper = mount(ProgramStatementList, {
            props: { statements: [conditional, call('stmt_after', '块后语句')], selectedStatementIds: ['stmt_after'] },
        })

        await wrapper.get('[data-statement-id="stmt_after"]').trigger('keydown', { key: 'Tab' })
        expect(wrapper.emitted('action')?.at(-1)?.[0]).toEqual({
            kind: 'nest', statement_ids: ['stmt_after'], direction: 'in',
        })
        await wrapper.get('[data-statement-id="stmt_child"]').trigger('keydown', { key: 'Tab', shiftKey: true })
        expect(wrapper.emitted('action')?.at(-1)?.[0]).toEqual({
            kind: 'nest', statement_ids: ['stmt_child'], direction: 'out',
        })
        await wrapper.setProps({ selectedStatementIds: ['stmt_if'] })
        await wrapper.get('[data-statement-id="stmt_if"] button[aria-label="更多语句操作"]').trigger('click')
        const nestIn = wrapper.findAll('[role="menuitem"]').find((item) => item.text().includes('移入上一个语句块'))
        expect(nestIn?.attributes('disabled')).toBeDefined()
    })

    it('preflights batch Tab from the first selected row instead of the focused last row', async () => {
        const conditional: ProgramStatement = {
            statement_id: 'stmt_if', kind: 'if',
            condition: { value_id: 'value_condition', value_type: 'bool', kind: 'literal', value: true },
            then_body: [], additional_branches: [], else_body: [],
        }
        const wrapper = mount(ProgramStatementList, {
            props: {
                statements: [conditional, call('stmt_a', '第一条'), call('stmt_b', '第二条')],
                selectedStatementIds: ['stmt_a', 'stmt_b'],
            },
        })

        await wrapper.get('[data-statement-id="stmt_b"]').trigger('keydown', { key: 'Tab' })
        expect(wrapper.emitted('action')?.at(-1)?.[0]).toEqual({
            kind: 'nest', statement_ids: ['stmt_a', 'stmt_b'], direction: 'in',
        })
    })

    it('keeps common row actions visible and moves lower-frequency actions into one named menu', async () => {
        const wrapper = mount(ProgramStatementList, {
            props: { statements: [call('stmt_1', '第一条')], selectedStatementIds: ['stmt_1'] },
        })

        expect(wrapper.findAll('.statement-actions > button')).toHaveLength(4)
        expect(wrapper.get('button[aria-label="在此语句后插入"]').attributes('title')).toContain('Ctrl+Enter')
        expect(wrapper.find('[role="menu"]').exists()).toBe(false)
        await wrapper.get('button[aria-label="更多语句操作"]').trigger('click')
        expect(wrapper.get('[role="menu"]').attributes('aria-label')).toBe('更多语句操作')
        expect(wrapper.findAll('[role="menuitem"]')).toHaveLength(8)
    })

    it('uses the same object actions from the statement context menu', async () => {
        const wrapper = mount(ProgramStatementList, {
            props: { statements: [call('stmt_1', '第一条'), call('stmt_2', '第二条')], selectedStatementIds: ['stmt_1'] },
        })

        await wrapper.get('[data-statement-id="stmt_2"]').trigger('contextmenu')

        expect(wrapper.emitted('update:selectedStatementIds')?.at(-1)?.[0]).toEqual(['stmt_2'])
        expect(wrapper.get('[role="menu"]').attributes('aria-label')).toBe('更多语句操作')
        expect(wrapper.get('[role="menu"]').text()).toContain('创建语句副本')
        expect(wrapper.get('[role="menu"]').text()).toContain('提取为项目函数')
    })

    it('opens the more-actions menu from the keyboard and restores focus on Escape', async () => {
        const wrapper = mount(ProgramStatementList, {
            attachTo: document.body,
            props: { statements: [call('stmt_1', '第一条')], selectedStatementIds: ['stmt_1'] },
        })
        const trigger = wrapper.get<HTMLButtonElement>('button[aria-label="更多语句操作"]')

        trigger.element.focus()
        await trigger.trigger('keydown', { key: 'ArrowDown' })
        await wrapper.vm.$nextTick()
        expect((document.activeElement as HTMLElement).textContent).toContain('复制语句')

        await wrapper.get('[role="menu"]').trigger('keydown', { key: 'Escape' })
        await wrapper.vm.$nextTick()
        expect(wrapper.find('[role="menu"]').exists()).toBe(false)
        expect(document.activeElement).toBe(trigger.element)
        wrapper.unmount()
    })

    it('supports contiguous multi-selection and controlled block folding', async () => {
        const conditional: ProgramStatement = {
            statement_id: 'stmt_if',
            kind: 'if',
            condition: { value_id: 'value_condition', value_type: 'bool', kind: 'literal', value: true },
            then_body: [call('stmt_child_1', '子语句一'), call('stmt_child_2', '子语句二')],
            additional_branches: [],
            else_body: [],
        }
        const wrapper = mount(ProgramStatementList, { props: { statements: [conditional] } })

        await wrapper.get('[data-statement-id="stmt_child_1"]').trigger('click')
        await wrapper.get('[data-statement-id="stmt_child_2"]').trigger('click', { shiftKey: true })
        expect(wrapper.emitted('update:selectedStatementIds')?.at(-1)?.[0]).toEqual(['stmt_child_1', 'stmt_child_2'])

        await wrapper.get('.collapse-button').trigger('click')
        expect(wrapper.find('[data-statement-id="stmt_child_1"]').exists()).toBe(false)
        expect(wrapper.emitted('update:collapsedStatementIds')?.at(-1)?.[0]).toEqual(['stmt_if'])
    })

    it('uses standard tree keys to fold, enter children, return to parents and select visible rows', async () => {
        const conditional: ProgramStatement = {
            statement_id: 'stmt_if', kind: 'if',
            condition: { value_id: 'value_condition', value_type: 'bool', kind: 'literal', value: true },
            then_body: [call('stmt_child', '子语句')], additional_branches: [], else_body: [],
        }
        const wrapper = mount(ProgramStatementList, {
            attachTo: document.body,
            props: { statements: [conditional, call('stmt_after', '末尾语句')], selectedStatementIds: ['stmt_if'] },
        })
        const parent = wrapper.get('[data-statement-id="stmt_if"]')

        await parent.trigger('keydown', { key: 'ArrowLeft' })
        expect(wrapper.emitted('update:collapsedStatementIds')?.at(-1)?.[0]).toEqual(['stmt_if'])
        await parent.trigger('keydown', { key: 'ArrowRight' })
        expect(wrapper.emitted('update:collapsedStatementIds')?.at(-1)?.[0]).toEqual([])
        await parent.trigger('keydown', { key: 'ArrowRight' })
        expect(wrapper.emitted('update:selectedStatementIds')?.at(-1)?.[0]).toEqual(['stmt_child'])

        const child = wrapper.get('[data-statement-id="stmt_child"]')
        await child.trigger('keydown', { key: 'ArrowLeft' })
        expect(wrapper.emitted('update:selectedStatementIds')?.at(-1)?.[0]).toEqual(['stmt_if'])
        await parent.trigger('keydown', { key: 'a', ctrlKey: true })
        expect(wrapper.emitted('update:selectedStatementIds')?.at(-1)?.[0]).toEqual(['stmt_if', 'stmt_child', 'stmt_after'])
        wrapper.unmount()
    })

    it('lets an empty branch become an explicit nested insertion target', async () => {
        const conditional: ProgramStatement = {
            statement_id: 'stmt_if', kind: 'if',
            condition: { value_id: 'value_condition', value_type: 'bool', kind: 'literal', value: true },
            then_body: [], additional_branches: [], else_body: [],
        }
        const wrapper = mount(ProgramStatementList, { props: { statements: [conditional] } })

        const otherwise = wrapper.findAll('.branch-row').find((row) => row.text().includes('否则'))
        expect(otherwise?.text()).toBe('添加“否则”分支')
        await otherwise?.trigger('click')
        expect(wrapper.emitted('update:insertionTarget')?.at(-1)?.[0]).toEqual({
            key: 'stmt_if:otherwise', parent_statement_id: 'stmt_if', block: 'otherwise', label: '添加“否则”分支',
        })
        expect(wrapper.emitted('update:selectedStatementIds')?.at(-1)?.[0]).toEqual([])
    })

    it('uses one restrained visual grammar for content, scopes, branches and target context', () => {
        const conditional: ProgramStatement = {
            statement_id: 'stmt_if', kind: 'if',
            condition: { value_id: 'value_condition', value_type: 'bool', kind: 'literal', value: true },
            then_body: [call('stmt_child', '点击确认')], additional_branches: [], else_body: [call('stmt_else', '记录未满足')],
        }
        const target: ProgramStatement = {
            statement_id: 'stmt_target', kind: 'target_scope',
            target: { value_id: 'value_target', value_type: 'target_ref', kind: 'target_ref', target_id: 'target_windows', display_name: '微信' },
            body: [conditional],
        }
        const wrapper = mount(ProgramStatementList, { props: { statements: [target, call('stmt_plain', '等待 2 秒')] } })

        expect(wrapper.get('[data-statement-id="stmt_target"]').classes()).toContain('is-structure')
        expect(wrapper.find('[data-statement-id="stmt_target"] .target-context-icon').exists()).toBe(false)
        expect(wrapper.find('[data-statement-id="stmt_plain"] .target-context-icon').exists()).toBe(false)
        expect(wrapper.get('[data-statement-id="stmt_if"]').classes()).toContain('is-nested')
        expect(wrapper.findAll('.branch-row').map((row) => row.text())).toEqual(['那么', '否则'])
        expect(wrapper.findAll('.branch-row').every((row) => row.classes().includes('is-nested'))).toBe(true)
    })

    it('exposes diagnostics and runtime state to assistive technology', () => {
        const wrapper = mount(ProgramStatementList, {
            props: {
                statements: [call('stmt_1', '等待图片')],
                selectedStatementIds: ['stmt_1'],
                statementStates: { stmt_1: { runtime: 'failed', diagnostic_count: 2, breakpoint: true } },
            },
        })

        expect(wrapper.get('[role="treeitem"]').attributes('aria-label')).toBe('等待图片，设有断点，失败，2 个问题')
        expect(wrapper.text()).toContain('2 个问题')
    })

    it('toggles a breakpoint without changing the ProgramDocument', async () => {
        const wrapper = mount(ProgramStatementList, {
            props: {
                statements: [call('stmt_1', '等待图片')],
                selectedStatementIds: ['stmt_1'],
                statementStates: { stmt_1: { breakpoint: true } },
            },
        })

        await wrapper.get('button[aria-label="移除断点"]').trigger('click')
        expect(wrapper.emitted('toggleBreakpoint')?.[0]).toEqual(['stmt_1'])
        expect(wrapper.emitted('action')).toBeUndefined()
    })

    it('draws configurable summary values as half-bracket tokens without storing decorative characters', () => {
        const statement = call('stmt_wait', '等待2 秒')
        if (statement.kind !== 'call') throw new Error('测试语句必须是函数调用')
        statement.summary_parts = [{ text: '等待' }, { text: '2 秒', dynamic: true }]
        const wrapper = mount(ProgramStatementList, { props: { statements: [statement] } })

        expect(wrapper.get('.statement-summary').text()).toBe('等待2 秒')
        expect(wrapper.get('.statement-dynamic-value').text()).toBe('2 秒')
        expect(wrapper.get('.statement-summary').text()).not.toContain('【')
    })

    it('在图片参数原位显示可读名称和缩略图', async () => {
        const statement: ProgramStatement = {
            statement_id: 'stmt_image', kind: 'call', function_id: 'official.image.wait_visible',
            display_name: '图像.等待出现', summary: '等待图片「asset_login」出现',
            arguments: {
                image: { value_id: 'value_image', value_type: 'asset_ref<image>', kind: 'asset_ref', asset_id: 'asset_login', asset_kind: 'image' },
            },
        }
        const loadPreview = vi.fn().mockResolvedValue('blob:asset_login')
        const wrapper = mount(ProgramStatementList, {
            props: {
                statements: [statement],
                assets: [{ asset_id: 'asset_login', display_name: '登录按钮', category: 'image', folder: '', path: 'images/login.png', extension: '.png', mime_type: 'image/png', size_bytes: 10, width: 24, height: 24, sha256: 'login', source: 'capture', created_at: '', updated_at: '', aliases: [], capture: null }],
                loadAssetPreview: loadPreview,
            },
        })

        expect(wrapper.get('.statement-summary').text()).toBe('等待登录按钮出现')
        expect(wrapper.get('.statement-summary').text()).not.toContain('asset_login')
        expect(wrapper.find('.statement-kind-icon').exists()).toBe(false)
        await flushPromises()
        expect(loadPreview).toHaveBeenCalledWith('asset_login')
        expect(wrapper.find('.statement-dynamic-value .asset-thumbnail').exists()).toBe(true)
        expect(wrapper.find('.asset-thumbnail-popover').exists()).toBe(false)
        wrapper.unmount()
    })

    it('隐藏自动图片名、复用预览请求并为失效引用保留可读状态', async () => {
        const imageValue = {
            value_id: 'value_auto_image', value_type: 'asset_ref<image>', kind: 'asset_ref' as const,
            asset_id: 'asset_auto', asset_kind: 'image',
        }
        const imageStatement = (statementId: string): ProgramStatement => ({
            statement_id: statementId, kind: 'call', function_id: 'official.image.find',
            display_name: '图像.查找', arguments: { image: imageValue },
            summary_parts: [
                { text: '查找图像' },
                { text: '图片「image_20260906_112817」', dynamic: true, value: imageValue, parameter_id: 'image' },
            ],
        })
        const loadPreview = vi.fn().mockResolvedValue('blob:asset_auto')
        const wrapper = mount(ProgramStatementList, {
            props: {
                statements: [imageStatement('stmt_a'), imageStatement('stmt_b')],
                assets: [{ asset_id: 'asset_auto', display_name: 'image_20260906_112817', category: 'image', folder: '', path: 'images/auto.png', extension: '.png', mime_type: 'image/png', size_bytes: 10, width: 24, height: 24, sha256: 'auto', source: 'capture', created_at: '', updated_at: '', aliases: [], capture: null }],
                loadAssetPreview: loadPreview,
            },
        })

        await flushPromises()
        expect(wrapper.text()).not.toContain('image_20260906_112817')
        expect(wrapper.findAll('.image-value-name').map((item) => item.text())).toEqual(['未命名图片', '未命名图片'])
        expect(loadPreview).toHaveBeenCalledTimes(1)
        wrapper.unmount()

        const missing = mount(ProgramStatementList, { props: { statements: [imageStatement('stmt_missing')] } })
        expect(missing.get('.image-value-name').text()).toBe('图片已失效')
        expect(missing.text()).not.toContain('asset_auto')
        missing.unmount()
    })

    it('keeps ten thousand statements interactive by progressively materializing DOM rows', async () => {
        const statements = Array.from({ length: 10_000 }, (_, index) => call(`stmt_${index}`, `语句 ${index}`))
        const wrapper = mount(ProgramStatementList, { props: { statements } })

        expect(wrapper.findAll('.statement-row').length).toBeLessThan(80)

        await wrapper.setProps({ selectedStatementIds: ['stmt_9999'] })
        expect(wrapper.find('[data-statement-id="stmt_9999"]').exists()).toBe(true)
        expect(wrapper.findAll('.statement-row').length).toBeLessThan(80)
    })
})
