import { flushPromises, mount, shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import ProgramStructuredValueEditor from '../ProgramStructuredValueEditor.vue'
import ProgramJsonValueField from '../ProgramJsonValueField.vue'
import ProgramExpressionInput from '../ProgramExpressionInput.vue'
import ProgramValueTreeField from '../ProgramValueTreeField.vue'
import { uiValueUpdateToServerCommand } from '../adapter'
import { programValueToDraft } from '../valueFactories'
import type { ProgramValueCatalogDto } from '../serverTypes'
import type { ProgramValueNode } from '../types'

function literal(id: string, value: string | number | boolean, valueType = 'string'): ProgramValueNode {
    return { value_id: id, kind: 'literal', value_type: valueType, value }
}

function buttonByText(wrapper: ReturnType<typeof mount>, text: string) {
    const button = wrapper.findAll('button').find((item) => item.text() === text)
    if (!button) throw new Error(`button not found: ${text}`)
    return button
}

describe('focused Program value editor', () => {
    it('keeps simple leaf fields on one row and declares a narrow-container fallback', () => {
        const leaf = mount(ProgramValueTreeField, {
            props: {
                label: '名称',
                value: literal('value_name', 'attachment'),
                ui: { control: 'text', placeholder: '例如：attachment', help: '发送时使用的字段名。' },
                required: true,
            },
        })
        expect(leaf.classes()).toContain('is-inline-leaf')
        expect(leaf.get(':scope > header').text()).toContain('名称')
        expect(leaf.get(':scope > .expression-composer').element).toBeTruthy()

        const collection = mount(ProgramValueTreeField, {
            props: { label: '项目', value: { value_id: 'value_items', kind: 'list', value_type: 'list<string>', item_type: 'string', items: [] } },
        })
        expect(collection.classes()).not.toContain('is-inline-leaf')

        const source = readFileSync('src/vnext/program/ProgramValueTreeField.vue', 'utf8')
        expect(source).toContain('@container (max-width: 350px)')
        expect(source).toContain('grid-template-columns: minmax(108px, .38fr) minmax(0, 1fr)')
    })

    it('does not silently turn an empty JSON number into zero', async () => {
        const wrapper = mount(ProgramJsonValueField, { props: { modelValue: 18 } })
        const input = wrapper.get('input[type="number"]')
        await input.setValue('')

        expect(wrapper.emitted('update:modelValue')).toBeUndefined()
        expect((input.element as HTMLInputElement).value).toBe('18')
    })

    it('preserves every existing nested value ID through the real update_argument adapter', () => {
        const tree: ProgramValueNode = {
            value_id: 'value_root', kind: 'list', value_type: 'list<any>', item_type: 'any', items: [{
                value_id: 'value_map', kind: 'map', value_type: 'map<string,any>', key_type: 'string', entry_value_type: 'any', duplicate_policy: 'error', entries: [{
                    key: literal('value_key', 'rank'),
                    value: {
                        value_id: 'value_operation', kind: 'computed', value_type: 'int64',
                        operation_id: 'core.number_add.v1', operation_name: '相加', inputs: {
                            'core.number_add.v1.input.left': {
                                value_id: 'value_member', kind: 'member_access', value_type: 'int64', field_id: 'rank', field_name: '等级',
                                source: { value_id: 'value_player', kind: 'symbol_ref', value_type: 'PlayerInfo', symbol_id: 'symbol_player', display_name: '玩家' },
                            },
                            'core.number_add.v1.input.right': literal('value_one', 1, 'int64'),
                        },
                    },
                }],
            }],
        }
        const command = uiValueUpdateToServerCommand({
            statement_id: 'statement_assignment', parameter_id: 'value', value_id: tree.value_id,
            next: programValueToDraft(tree),
        })
        if (command.kind !== 'update_argument' || command.value.kind !== 'list') throw new Error('expected list update')
        const map = command.value.items[0]
        if (map?.kind !== 'map') throw new Error('expected map')
        const operation = map.entries[0]?.value
        if (operation?.kind !== 'operation') throw new Error('expected operation')
        const member = operation.inputs['core.number_add.v1.input.left']
        expect([
            command.value.value_id, map.value_id, map.entries[0]?.key.value_id, operation.value_id,
            member?.value_id, member?.kind === 'member_access' ? member.source.value_id : '',
            operation.inputs['core.number_add.v1.input.right']?.value_id,
        ]).toEqual(['value_root', 'value_map', 'value_key', 'value_operation', 'value_member', 'value_player', 'value_one'])
        expect(operation).not.toHaveProperty('operation_name')
    })

    it('supports list add, delete and reorder without changing identities of retained items', async () => {
        const value: ProgramValueNode = {
            value_id: 'value_list', kind: 'list', value_type: 'list<string>', item_type: 'string',
            items: [literal('value_a', '甲'), literal('value_b', '乙')],
        }
        const wrapper = mount(ProgramStructuredValueEditor, { props: { title: '副本列表', value } })
        const rows = wrapper.findAll('.list-entry')
        await rows[0]?.findAll('.row-actions button')[1]?.trigger('click')
        await buttonByText(wrapper, '添加一项').trigger('click')
        const movedRows = wrapper.findAll('.list-entry')
        await movedRows[1]?.findAll('.row-actions button')[2]?.trigger('click')
        const remainingRows = wrapper.findAll('.list-entry')
        const newItemSurface = remainingRows[1]?.find('.expression-surface')
        await newItemSurface?.trigger('click')
        const newItemInput = remainingRows[1]?.find('.expression-editor')
        await newItemInput?.setValue('丙')
        await newItemInput?.trigger('keydown.enter')
        await wrapper.get('form').trigger('submit')

        const saved = wrapper.emitted('save')?.[0]?.[0] as ProgramValueNode
        if (saved.kind !== 'list') throw new Error('expected list')
        expect(saved.items[0]?.value_id).toBe('value_b')
        expect(saved.items[1]?.value_id).not.toBe('value_a')
        expect(saved.items[1]?.value_id).toMatch(/^value_/)
        expect(new Set(saved.items.map((item) => item.value_id)).size).toBe(saved.items.length)
    })

    it('enforces collection constraints before sending a Program command', async () => {
        const value: ProgramValueNode = {
            value_id: 'value_list', kind: 'list', value_type: 'list<string>', item_type: 'string',
            items: [literal('value_a', '重复'), literal('value_b', '重复')],
        }
        const wrapper = mount(ProgramStructuredValueEditor, {
            props: { title: '唯一列表', value, constraints: { min_items: 1, max_items: 3, unique_items: true } },
        })
        await wrapper.get('form').trigger('submit')
        expect(wrapper.emitted('save')).toBeUndefined()
        expect(wrapper.text()).toContain('重复的固定值')

        const rows = wrapper.findAll('.list-entry')
        await rows[1]?.findAll('.row-actions button')[2]?.trigger('click')
        await wrapper.get('form').trigger('submit')
        expect(wrapper.emitted('save')).toHaveLength(1)
    })

    it('does not fabricate empty record items when no type-field catalog exists', () => {
        const value: ProgramValueNode = {
            value_id: 'value_records', kind: 'list', value_type: 'list<PlayerInfo>', item_type: 'PlayerInfo', items: [],
        }
        const wrapper = mount(ProgramStructuredValueEditor, { props: { title: '玩家列表', value } })
        expect(buttonByText(wrapper, '添加一项').attributes('disabled')).toBeDefined()
        expect(wrapper.text()).toContain('缺少可创建的类型结构')
    })

    it('edits JSON structurally without a raw text escape hatch and blocks duplicate map keys', async () => {
        const json: ProgramValueNode = { value_id: 'value_json', kind: 'json', value_type: 'json_value', payload: { ok: true } }
        const wrapper = mount(ProgramStructuredValueEditor, { props: { title: '请求数据', value: json } })
        expect(wrapper.find('textarea').exists()).toBe(false)
        expect(wrapper.text()).toContain('1 个字段')
        await wrapper.get('.json-child input[type="checkbox"]').setValue(false)
        await wrapper.get('form').trigger('submit')
        expect(wrapper.emitted('save')?.[0]?.[0]).toMatchObject({ value_id: 'value_json', kind: 'json', payload: { ok: false } })

        const map: ProgramValueNode = {
            value_id: 'value_map', kind: 'map', value_type: 'map<string,string>', key_type: 'string', entry_value_type: 'string', duplicate_policy: 'error',
            entries: [
                { key: literal('key_1', 'same'), value: literal('entry_1', 'A') },
                { key: literal('key_2', 'same'), value: literal('entry_2', 'B') },
            ],
        }
        const mapWrapper = mount(ProgramStructuredValueEditor, { props: { title: '字典', value: map } })
        await mapWrapper.get('form').trigger('submit')
        expect(mapWrapper.emitted('save')).toBeUndefined()
        expect(mapWrapper.text()).toContain('重复的固定键')
    })

    it('keeps operation and member contracts read-only while editing their existing inputs', async () => {
        const value: ProgramValueNode = {
            value_id: 'value_operation', kind: 'computed', value_type: 'int64',
            operation_id: 'core.number_add.v1', operation_name: '相加', inputs: {
                'core.number_add.v1.input.left': literal('value_left', 1, 'int64'),
                'core.number_add.v1.input.right': {
                    value_id: 'value_member', kind: 'member_access', value_type: 'int64', field_id: 'score', field_name: '分数',
                    source: { value_id: 'value_result', kind: 'symbol_ref', value_type: 'Result', symbol_id: 'symbol_result', display_name: '识别结果' },
                },
            },
        }
        const wrapper = mount(ProgramStructuredValueEditor, { props: { title: '计算', value } })
        expect(wrapper.get('.expression-surface').text()).toContain('识别结果')
        expect(wrapper.get('.expression-surface').text()).toContain('分数')
        expect(wrapper.text()).toContain('识别结果.分数')
        expect(wrapper.text()).not.toContain('core.number_add.v1')
        expect(wrapper.text()).not.toContain('score')
        expect(wrapper.find('input[value="core.number_add.v1"]').exists()).toBe(false)
        await wrapper.get('form').trigger('submit')
        const saved = wrapper.emitted('save')?.[0]?.[0] as ProgramValueNode
        if (saved.kind !== 'computed') throw new Error('expected operation')
        expect(saved.operation_id).toBe('core.number_add.v1')
        expect(saved.inputs['core.number_add.v1.input.left']).toMatchObject({ value_id: 'value_left', value: 1 })
        expect(saved.inputs['core.number_add.v1.input.right']).toMatchObject({ value_id: 'value_member', field_id: 'score' })
    })

    it('creates a concrete pure operation from the authoritative catalog and preserves the root value ID', async () => {
        const value = literal('value_root', 3, 'int64')
        const catalog: ProgramValueCatalogDto = {
            schema_version: 1,
            registry_version: 1,
            registry_hash: 'sha256:test',
            revision: 'sha256:revision',
            expected_type: 'int64',
            sources: [],
            members: [],
            record: null,
            operations: [{
                candidate_id: 'candidate_add',
                operation_id: 'core.number_add.v1',
                display_name: '相加',
                category: '数值',
                description: '把两个数相加',
                result_type: 'int64',
                inputs: [
                    { input_id: 'core.number_add.v1.input.left', display_name: '左侧', value_type: 'int64', choices: [] },
                    { input_id: 'core.number_add.v1.input.right', display_name: '右侧', value_type: 'int64', choices: [] },
                ],
            }],
        }
        const wrapper = mount(ProgramValueTreeField, {
            props: { label: '次数', value, resolveCatalog: async () => catalog },
        })

        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        const expression = wrapper.get('.expression-editor')
        await expression.setValue('数值.相加(3, 4)')
        await expression.trigger('keydown.enter')
        await flushPromises()

        const next = wrapper.emitted('replace')?.at(-1)?.[0] as ProgramValueNode
        expect(next).toMatchObject({
            value_id: 'value_root',
            kind: 'computed',
            value_type: 'int64',
            operation_id: 'core.number_add.v1',
        })
        if (next.kind !== 'computed') throw new Error('expected operation')
        expect(Object.keys(next.inputs)).toEqual([
            'core.number_add.v1.input.left',
            'core.number_add.v1.input.right',
        ])
        expect(Object.values(next.inputs).map((item) => item.value_type)).toEqual(['int64', 'int64'])
        expect(new Set(Object.values(next.inputs).map((item) => item.value_id)).size).toBe(2)

        // The chosen operation returns to the same compact formula surface.
        await wrapper.setProps({ value: next })
        await flushPromises()
        expect(wrapper.get('.expression-surface').text()).toContain('3')
        expect(wrapper.get('.expression-surface').text()).toContain('4')
        expect(wrapper.findAll('.expression-surface')).toHaveLength(1)
    })

    it('asks for the root source only once and hides the old value while choosing a calculation', async () => {
        const catalog: ProgramValueCatalogDto = {
            schema_version: 1, registry_version: 1, registry_hash: 'sha256:test', revision: 'sha256:revision',
            expected_type: 'int64', sources: [], members: [], record: null,
            operations: [{
                candidate_id: 'candidate_add', operation_id: 'core.number_add.v1', display_name: '相加',
                category: '数值', description: '把两个数相加', result_type: 'int64', inputs: [],
            }],
        }
        const wrapper = shallowMount(ProgramStructuredValueEditor, {
            props: {
                title: '当前等级', value: literal('value_level', 18, 'int64'), initialSource: 'computed',
            },
        })
        // Replace the network resolver by mounting the tree behavior directly through the same contract.
        const tree = mount(ProgramValueTreeField, {
            props: {
                label: '值', value: literal('value_level', 18, 'int64'), initialCatalogMode: 'computed',
                hideSourcePicker: true, resolveCatalog: async () => catalog,
            },
        })
        await flushPromises()

        expect(wrapper.getComponent(ProgramValueTreeField).props('hideSourcePicker')).toBe(true)
        expect(tree.find('.source-picker').exists()).toBe(false)
        expect(tree.find('.catalog-picker').exists()).toBe(true)
        expect(tree.find('input[type="number"]').exists()).toBe(false)
        expect((tree.get('.catalog-picker select').element as HTMLSelectElement).value).toBe('')
    })

    it('materializes a scoped collection selector with stable local bindings', async () => {
        const value: ProgramValueNode = {
            value_id: 'value_numbers', kind: 'list', value_type: 'list<int64>', item_type: 'int64', items: [],
        }
        const catalog: ProgramValueCatalogDto = {
            schema_version: 1, registry_version: 4, registry_hash: 'sha256:test', revision: 'sha256:revision',
            expected_type: 'list<int64>', sources: [], members: [], record: null,
            operations: [{
                candidate_id: 'candidate_filter', operation_id: 'core.list_filter.v1',
                display_name: '筛选列表', category: '列表', description: '只保留满足条件的项目。',
                result_type: 'list<int64>', inputs: [
                    { input_id: 'core.list_filter.v1.input.list', display_name: '列表', value_type: 'list<int64>', choices: [] },
                    { input_id: 'core.list_filter.v1.input.predicate', display_name: '保留条件', value_type: 'list_selector<int64,bool>', choices: [] },
                ],
            }],
        }
        const wrapper = mount(ProgramValueTreeField, {
            props: { label: '筛选结果', value, resolveCatalog: async () => catalog },
        })
        await buttonByText(wrapper, '使用已有值或计算').trigger('click')
        await wrapper.get('.whole-value-composer .expression-surface').trigger('click')
        await flushPromises()
        await wrapper.get('.whole-value-composer .expression-editor').setValue('列表.筛选([], 每项 => 开启)')
        await wrapper.get('.whole-value-composer .expression-editor').trigger('keydown.enter')
        await flushPromises()
        const next = wrapper.emitted('replace')?.at(-1)?.[0] as ProgramValueNode
        if (next.kind !== 'computed') throw new Error('expected operation')
        const selector = next.inputs['core.list_filter.v1.input.predicate']
        if (selector?.kind !== 'selector') throw new Error('expected selector')
        expect(selector.bindings.map((item) => item.role)).toEqual(['item', 'index'])
        expect(new Set(selector.bindings.map((item) => item.symbol_id)).size).toBe(2)
        expect(selector.expression).toMatchObject({ kind: 'literal', value_type: 'bool', value: true })
    })

    it('creates optional-record member access only from a server-approved member candidate', async () => {
        const value: ProgramValueNode = { value_id: 'value_center', kind: 'unset', value_type: 'point' }
        const catalog: ProgramValueCatalogDto = {
            schema_version: 1,
            registry_version: 1,
            registry_hash: 'sha256:test',
            revision: 'sha256:revision',
            expected_type: 'point',
            sources: [{
                source: 'local', source_id: 'symbol_match', display_name: '登录按钮',
                value_type: 'optional<image_match>', narrowed_type: 'image_match',
            }],
            operations: [],
            record: null,
            members: [{
                candidate_id: 'candidate_center',
                source: 'local',
                source_id: 'symbol_match',
                source_display_name: '登录按钮',
                source_value_type: 'optional<image_match>',
                result_type: 'point',
                path: [{ field_id: 'image_match.field.center', display_name: '中心', result_type: 'point' }],
            }],
        }
        const wrapper = mount(ProgramValueTreeField, {
            props: {
                label: '点击位置',
                value,
                availableValues: [{
                    id: 'symbol_match', source: 'local', display_name: '登录按钮',
                    value_type: 'optional<image_match>',
                }],
                resolveCatalog: async () => catalog,
            },
        })

        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        await wrapper.get('.expression-editor').setValue('[局部 · 登录按钮].中心')
        await wrapper.get('.expression-editor').trigger('keydown.enter')
        await flushPromises()

        const next = wrapper.emitted('replace')?.at(-1)?.[0] as ProgramValueNode
        expect(next).toMatchObject({
            value_id: 'value_center', kind: 'member_access', value_type: 'point',
            field_id: 'image_match.field.center', field_name: '中心',
            source: {
                kind: 'symbol_ref', symbol_id: 'symbol_match', value_type: 'optional<image_match>',
            },
        })
    })

    it('creates a fully typed record form from backend field schema without JSON editing', async () => {
        const value: ProgramValueNode = { value_id: 'value_body', kind: 'unset', value_type: 'http_body' }
        const catalog: ProgramValueCatalogDto = {
            schema_version: 1,
            registry_version: 1,
            registry_hash: 'sha256:test',
            revision: 'sha256:revision',
            expected_type: 'http_body',
            sources: [],
            operations: [],
            members: [],
            record: {
                type_id: 'http_body',
                display_name: 'HTTP 正文',
                authoring_mode: 'constructible',
                editor_strategy: 'inline_record',
                fields: [
                    {
                        field_id: 'http_body.field.kind', display_name: '正文类型',
                        value_type: 'enum<http_body_kind>', description: '',
                        choices: [{ label: '文本', value: 'text' }, { label: 'JSON', value: 'json' }],
                        required: true, has_default: true, default: 'text',
                        ui: { control: 'select' },
                    },
                    {
                        field_id: 'http_body.field.text', display_name: '文本',
                        value_type: 'optional<string>', description: '', choices: [],
                        required: false, has_default: true, default: null,
                        ui: { control: 'text', placeholder: '输入正文' },
                    },
                    {
                        field_id: 'http_body.field.retries', display_name: '重试次数',
                        value_type: 'int64', description: '', choices: [],
                        required: false, has_default: true, default: 7,
                        ui: { control: 'number' },
                    },
                    {
                        field_id: 'http_body.field.label', display_name: '标记',
                        value_type: 'string', description: '', choices: [],
                        required: true, has_default: false,
                        ui: { control: 'text', placeholder: '输入标记' },
                    },
                ],
            },
        }
        const wrapper = mount(ProgramValueTreeField, {
            props: { label: '正文', value, resolveCatalog: async () => catalog },
        })

        await buttonByText(wrapper, '选择填写方式').trigger('click')
        await flushPromises()
        await buttonByText(wrapper, '开始填写').trigger('click')

        const next = wrapper.emitted('replace')?.at(-1)?.[0] as ProgramValueNode
        expect(next).toMatchObject({
            value_id: 'value_body', kind: 'record', value_type: 'http_body', record_type: 'http_body',
            fields: {
                'http_body.field.kind': { kind: 'literal', value_type: 'enum<http_body_kind>', value: 'text' },
                'http_body.field.text': { kind: 'literal', value_type: 'optional<string>', value: null },
                'http_body.field.retries': { kind: 'literal', value_type: 'int64', value: 7 },
                'http_body.field.label': { kind: 'unset', value_type: 'string' },
            },
        })
        if (next.kind !== 'record') throw new Error('expected record')
        expect(new Set(Object.values(next.fields).map((item) => item.value_id)).size).toBe(4)
    })

    it('does not prompt on an untouched unset collection and prevents deleting the last condition', async () => {
        const unset: ProgramValueNode = { value_id: 'value_unset', kind: 'unset', value_type: 'list<string>' }
        const wrapper = mount(ProgramStructuredValueEditor, { props: { title: '列表', value: unset } })
        await wrapper.get('button[aria-label="关闭"]').trigger('click')
        expect(wrapper.emitted('cancel')).toHaveLength(1)
        expect(wrapper.find('.discard-dialog').exists()).toBe(false)

        const condition: ProgramValueNode = {
            value_id: 'value_group', kind: 'condition_group', value_type: 'bool', operator: 'all',
            conditions: [literal('value_condition', true, 'bool')],
        }
        const conditionWrapper = mount(ProgramStructuredValueEditor, { props: { title: '条件', value: condition } })
        expect(conditionWrapper.find('.remove-condition').exists()).toBe(false)
        expect(conditionWrapper.text()).not.toContain('更多操作')
        await conditionWrapper.get('form').trigger('submit')
        expect(conditionWrapper.emitted('save')?.[0]?.[0]).toMatchObject({ value_id: 'value_group', conditions: [{ value_id: 'value_condition' }] })
    })

    it('builds a structured condition from the fixed boolean inserted by a new if statement', async () => {
        const value = literal('value_condition_root', true, 'bool')
        const wrapper = mount(ProgramStructuredValueEditor, {
            props: { title: '条件', value, allowConditionBuilder: true },
        })

        expect(wrapper.text()).toContain('输入判断')
        await wrapper.get('.expression-surface').trigger('click')
        const expression = wrapper.get('.expression-editor')
        await expression.setValue('18 大于等于 3')
        await expression.trigger('keydown.enter')
        await wrapper.get('form').trigger('submit')

        const saved = wrapper.emitted('save')?.[0]?.[0] as ProgramValueNode
        expect(saved).toMatchObject({
            value_id: 'value_condition_root',
            kind: 'compare',
            value_type: 'bool',
            operator: 'gte',
        })
        if (saved.kind !== 'compare') throw new Error('expected compare condition')
        expect(saved.left.value_type).toBe('int64')
        expect(saved.right.value_type).toBe('int64')
        expect(saved.left.value_id).not.toBe(saved.right.value_id)
        expect(saved.left.value_id).toMatch(/^value_left_/)
        expect(saved.right.value_id).toMatch(/^value_right_/)
    })

    it('opens the requested calculation catalog with the owning field context intact', async () => {
        const value: ProgramValueNode = { value_id: 'value_number', kind: 'unset', value_type: 'int64' }
        const catalog: ProgramValueCatalogDto = {
            schema_version: 1, registry_version: 1, registry_hash: 'sha256:test', revision: 'sha256:revision',
            expected_type: 'int64', sources: [], members: [], record: null, operations: [],
        }
        const wrapper = mount(ProgramValueTreeField, {
            props: {
                label: '默认值', value, initialCatalogMode: 'computed', resolveCatalog: async () => catalog,
            },
        })
        await flushPromises()

        expect(wrapper.find('.source-picker').exists()).toBe(false)
        expect(wrapper.find('.catalog-picker').exists()).toBe(true)
    })

    it('shows exactly one collection editing mode and keeps enumerations constrained', async () => {
        const listValue: ProgramValueNode = {
            value_id: 'value_list', kind: 'list', value_type: 'list<int64>', item_type: 'int64',
            items: [{ value_id: 'value_item', kind: 'literal', value_type: 'int64', value: 18 }],
        }
        const list = mount(ProgramValueTreeField, { props: { label: '等级列表', value: listValue } })
        expect(list.find('.whole-value-composer').exists()).toBe(false)
        expect(list.findAll('.expression-surface')).toHaveLength(1)
        expect(list.get('.expression-surface').text()).toContain('18')
        await buttonByText(list, '使用已有值或计算').trigger('click')
        expect(list.find('.list-editor').exists()).toBe(false)
        expect(list.findAll('.expression-surface')).toHaveLength(1)
        expect(list.get('.expression-surface').text()).toContain('[18]')

        const enumeration = mount(ProgramValueTreeField, {
            props: {
                label: '正文类型',
                value: { value_id: 'value_kind', kind: 'literal', value_type: 'enum<http_body_kind>', value: 'text' },
                constraints: { choices: [{ label: '文本', value: 'text' }, { label: 'JSON', value: 'json' }] },
            },
        })
        expect(enumeration.find('.expression-surface').exists()).toBe(false)
        expect(enumeration.find('.source-picker').exists()).toBe(false)
        expect(enumeration.get('select').findAll('option').map((option) => option.text())).toEqual(['文本', 'JSON'])

        const point = mount(ProgramValueTreeField, {
            props: {
                label: '坐标',
                value: { value_id: 'value_point', kind: 'literal', value_type: 'point', value: [12, 34] },
            },
        })
        expect(point.get('.expression-surface').text()).toContain('坐标(12, 34)')
        expect(point.find('.value-vector').exists()).toBe(false)
    })

    it('keeps a small named record compact without synthetic field numbers or duplicate editors', async () => {
        const record: ProgramValueNode = {
            value_id: 'value_preprocess',
            kind: 'record',
            value_type: 'ocr_preprocess',
            record_type: 'ocr_preprocess',
            record_name: 'OCR 预处理',
            field_names: {
                'ocr_preprocess.field.grayscale': '灰度化',
                'ocr_preprocess.field.invert': '反色',
                'ocr_preprocess.field.threshold': '阈值',
                'ocr_preprocess.field.denoise': '降噪',
            },
            fields: {
                'ocr_preprocess.field.grayscale': literal('value_grayscale', false, 'bool'),
                'ocr_preprocess.field.invert': literal('value_invert', false, 'bool'),
                'ocr_preprocess.field.threshold': literal('value_threshold', 127, 'int64'),
                'ocr_preprocess.field.denoise': literal('value_denoise', false, 'bool'),
            },
        }
        const wrapper = mount(ProgramStructuredValueEditor, { props: { title: '预处理', value: record } })
        await flushPromises()

        expect(wrapper.get('.structured-dialog').attributes('data-editor-size')).toBe('compact')
        expect(wrapper.find('.value-tree-field.is-root > header').exists()).toBe(false)
        expect(wrapper.find('.whole-value-composer').exists()).toBe(false)
        expect(wrapper.text()).toContain('灰度化')
        expect(wrapper.text()).not.toMatch(/字段\s*[1-4]/)
        expect(wrapper.findAll('[data-value-kind="literal"]')).toHaveLength(4)
    })

    it('renders focused record metadata with conditional fields, advanced disclosure, and no dead file action', async () => {
        const fieldIds = {
            kind: 'multipart_field.field.kind',
            name: 'multipart_field.field.name',
            value: 'multipart_field.field.value',
            file: 'multipart_field.field.file',
            filename: 'multipart_field.field.filename',
            contentType: 'multipart_field.field.content_type',
        }
        const catalog: ProgramValueCatalogDto = {
            schema_version: 1, registry_version: 1, registry_hash: 'sha256:test', revision: 'sha256:revision',
            expected_type: 'multipart_field', sources: [], operations: [], members: [],
            record: {
                type_id: 'multipart_field', display_name: '上传字段', authoring_mode: 'constructible', editor_strategy: 'focused',
                fields: [
                    { field_id: fieldIds.kind, display_name: '字段类型', value_type: 'enum<multipart_field_kind>', description: '', required: true, has_default: true, default: 'text', choices: [{ label: '文本', value: 'text' }, { label: '文件', value: 'file' }], ui: { control: 'select' } },
                    { field_id: fieldIds.name, display_name: '名称', value_type: 'string', description: '', required: true, has_default: false, choices: [], ui: { control: 'text', placeholder: '例如：attachment' } },
                    { field_id: fieldIds.value, display_name: '文本值', value_type: 'optional<string>', description: '', required: false, has_default: false, choices: [], ui: { control: 'text', visible_when: { field_id: fieldIds.kind, operator: 'equals', value: 'text' } } },
                    { field_id: fieldIds.file, display_name: '文件', value_type: 'optional<file_ref<read>>', description: '', required: false, has_default: false, choices: [], ui: { control: 'file', actions: [{ id: 'choose-file-read', platforms: ['windows'] }], visible_when: { field_id: fieldIds.kind, operator: 'equals', value: 'file' } } },
                    { field_id: fieldIds.filename, display_name: '文件名', value_type: 'optional<string>', description: '', required: false, has_default: false, choices: [], ui: { control: 'text', importance: 'advanced', placeholder: '留空使用原文件名', visible_when: { field_id: fieldIds.kind, operator: 'equals', value: 'file' } } },
                    { field_id: fieldIds.contentType, display_name: '内容类型', value_type: 'optional<string>', description: '', required: false, has_default: false, choices: [], ui: { control: 'text', importance: 'advanced', placeholder: '例如：application/octet-stream', visible_when: { field_id: fieldIds.kind, operator: 'equals', value: 'file' } } },
                ],
            },
        }
        const textRecord: ProgramValueNode = {
            value_id: 'value_multipart', kind: 'record', value_type: 'multipart_field', record_type: 'multipart_field',
            fields: {
                [fieldIds.kind]: literal('value_kind', 'text', 'enum<multipart_field_kind>'),
                [fieldIds.name]: literal('value_name', '', 'string'),
                [fieldIds.value]: literal('value_text', null as never, 'optional<string>'),
                [fieldIds.file]: literal('value_file', null as never, 'optional<file_ref<read>>'),
                [fieldIds.filename]: literal('value_filename', null as never, 'optional<string>'),
                [fieldIds.contentType]: literal('value_content_type', null as never, 'optional<string>'),
            },
        }
        const wrapper = mount(ProgramValueTreeField, { props: { label: '上传字段', value: textRecord, resolveCatalog: async () => catalog } })
        await flushPromises()

        expect(wrapper.text()).toContain('字段类型')
        expect(wrapper.text()).toContain('文本值')
        expect(wrapper.findAllComponents(ProgramValueTreeField).some((item) => item.props('label') === '文件名')).toBe(false)
        const kindField = wrapper.findAllComponents(ProgramValueTreeField).find((item) => item.props('label') === '字段类型')
        expect(kindField?.find('select').exists()).toBe(true)
        expect(kindField?.find('header strong b').exists()).toBe(true)
        expect(kindField?.classes()).toContain('is-inline-leaf')
        const nameField = wrapper.findAllComponents(ProgramValueTreeField).find((item) => item.props('label') === '名称')
        expect(nameField?.classes()).toContain('is-inline-leaf')
        expect(nameField?.getComponent(ProgramExpressionInput).props('placeholder')).toBe('例如：attachment')

        await wrapper.setProps({
            value: {
                ...textRecord,
                fields: { ...textRecord.fields, [fieldIds.kind]: literal('value_kind', 'file', 'enum<multipart_field_kind>') },
            },
        })
        expect(wrapper.text()).toContain('文件')
        expect(wrapper.text()).not.toContain('文本值')
        expect(wrapper.get('.record-advanced').attributes('open')).toBeUndefined()
        const fileField = wrapper.findAllComponents(ProgramValueTreeField).find((item) => item.props('label') === '文件')
        expect(fileField?.props('ui')?.actions).toEqual([{ id: 'choose-file-read', platforms: ['windows'] }])
        expect(fileField?.find('.app-field-action').exists()).toBe(false)
        expect(fileField?.findComponent(ProgramExpressionInput).exists()).toBe(true)
        const filenameField = wrapper.findAllComponents(ProgramValueTreeField).find((item) => item.props('label') === '文件名')
        expect(filenameField?.getComponent(ProgramExpressionInput).props('placeholder')).toBe('留空使用原文件名')
    })

    it('applies record slider constraints and reports missing field presentation metadata without exposing ids', async () => {
        const thresholdId = 'ocr_preprocess.field.threshold'
        const catalog: ProgramValueCatalogDto = {
            schema_version: 1, registry_version: 1, registry_hash: 'sha256:test', revision: 'sha256:revision',
            expected_type: 'ocr_preprocess', sources: [], operations: [], members: [],
            record: {
                type_id: 'ocr_preprocess', display_name: '识字预处理', authoring_mode: 'constructible', editor_strategy: 'inline_record',
                fields: [{ field_id: thresholdId, display_name: '阈值', value_type: 'int64', description: '', required: false, has_default: true, default: 127, choices: [], constraints: { min: 0, max: 255, step: 1 }, ui: { control: 'slider-number' } }],
            },
        }
        const record: ProgramValueNode = { value_id: 'value_preprocess', kind: 'record', value_type: 'ocr_preprocess', record_type: 'ocr_preprocess', fields: { [thresholdId]: literal('value_threshold', 140, 'int64') } }
        const wrapper = mount(ProgramValueTreeField, { props: { label: '预处理', value: record, resolveCatalog: async () => catalog } })
        await flushPromises()

        const threshold = wrapper.findAllComponents(ProgramValueTreeField).find((item) => item.props('label') === '阈值')
        expect(threshold?.find('.value-slider').exists()).toBe(true)
        expect(threshold?.get('input[type="range"]').attributes()).toMatchObject({ min: '0', max: '255', step: '1' })

        const broken = mount(ProgramValueTreeField, {
            props: { label: '损坏结构', value: { value_id: 'value_broken', kind: 'record', value_type: 'broken_record', record_type: 'broken_record', fields: { 'broken_record.field.raw': literal('value_raw', 'x') } } },
        })
        expect(broken.get('[role="alert"]').text()).toContain('字段定义暂不可用')
        expect(broken.text()).not.toContain('broken_record.field.raw')
        expect(broken.text()).not.toMatch(/字段\s*1/)

        const malformedCatalog: ProgramValueCatalogDto = {
            ...catalog,
            expected_type: 'broken_record',
            record: { type_id: 'broken_record', display_name: '损坏结构', authoring_mode: 'constructible', editor_strategy: 'focused', fields: [{ field_id: 'broken_record.field.raw', display_name: '', value_type: 'string', description: '', choices: [] }] },
        }
        const catalogBroken = mount(ProgramValueTreeField, { props: { label: '损坏结构', value: broken.props('value'), resolveCatalog: async () => malformedCatalog } })
        await flushPromises()
        expect(catalogBroken.get('[role="alert"]').text()).toContain('字段定义暂不可用')
        expect(catalogBroken.text()).not.toContain('broken_record.field.raw')
    })

    it.each(['reference_only', 'capture_only'] as const)('does not offer record construction for %s catalogs', async (authoringMode) => {
        const value: ProgramValueNode = { value_id: `value_${authoringMode}`, kind: 'unset', value_type: 'http_response' }
        const catalog: ProgramValueCatalogDto = {
            schema_version: 1, registry_version: 1, registry_hash: 'sha256:test', revision: 'sha256:revision',
            expected_type: 'http_response', sources: [], operations: [], members: [],
            record: { type_id: 'http_response', display_name: 'HTTP 响应', authoring_mode: authoringMode, editor_strategy: authoringMode === 'capture_only' ? 'capture' : 'reference', fields: [{ field_id: 'http_response.field.status', display_name: '状态码', value_type: 'int64', description: '', choices: [] }] },
        }
        const wrapper = mount(ProgramValueTreeField, { props: { label: '响应', value, resolveCatalog: async () => catalog } })

        await buttonByText(wrapper, '选择填写方式').trigger('click')
        await flushPromises()
        expect(wrapper.text()).toContain(authoringMode === 'capture_only' ? '只能通过宿主捕获获得' : '只能通过已有值引用获得')
        expect(wrapper.findAll('button').some((item) => item.text() === '开始填写')).toBe(false)
        expect(wrapper.text()).not.toContain('创建结构化值')
    })

    it('uses a wide bounded editor for large collections and reveals more on demand', async () => {
        const value: ProgramValueNode = {
            value_id: 'value_many',
            kind: 'list',
            value_type: 'list<int64>',
            item_type: 'int64',
            items: Array.from({ length: 50 }, (_, index) => literal(`value_${index}`, index, 'int64')),
        }
        const wrapper = mount(ProgramStructuredValueEditor, { props: { title: '编号', value } })

        expect(wrapper.get('.structured-dialog').attributes('data-editor-size')).toBe('wide')
        expect(wrapper.findAll('.list-entry')).toHaveLength(40)
        await buttonByText(wrapper, '再显示 10 项').trigger('click')
        expect(wrapper.findAll('.list-entry')).toHaveLength(50)
    })

    it('owns focus during discard confirmation and restores the launch control on unmount', async () => {
        const launchControl = document.createElement('button')
        document.body.append(launchControl)
        launchControl.focus()
        const wrapper = mount(ProgramStructuredValueEditor, {
            attachTo: document.body,
            props: { title: '次数', value: literal('value_count', 18, 'int64') },
        })
        await flushPromises()

        expect(document.activeElement).toBe(wrapper.get('.expression-surface').element)
        await wrapper.get('.expression-surface').trigger('click')
        await wrapper.get('.expression-editor').setValue('19')
        await wrapper.get('.expression-editor').trigger('keydown.enter')
        await wrapper.get('.structured-dialog').trigger('keydown', { key: 'Escape' })
        await flushPromises()

        expect(wrapper.get('.structured-dialog').attributes('aria-hidden')).toBe('true')
        expect(wrapper.get('.structured-dialog').attributes('inert')).toBeDefined()
        expect(document.activeElement).toBe(wrapper.get('[data-dialog-initial-focus]').element)
        await wrapper.get('.discard-dialog').trigger('keydown', { key: 'Escape' })
        expect(wrapper.find('.discard-dialog').exists()).toBe(false)

        wrapper.unmount()
        expect(document.activeElement).toBe(launchControl)
        launchControl.remove()
    })

    it('confirms before replacing non-empty JSON with a different container type', async () => {
        const wrapper = mount(ProgramJsonValueField, { props: { modelValue: { enabled: true } } })

        await wrapper.findAll('select')[0].setValue('array')
        expect(wrapper.find('[role="alert"]').exists()).toBe(true)
        expect(wrapper.emitted('update:modelValue')).toBeUndefined()
        await buttonByText(wrapper, '仍要切换').trigger('click')
        expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toEqual([])
    })

})
