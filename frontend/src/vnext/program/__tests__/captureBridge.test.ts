import { describe, expect, it } from 'vitest'
import type { AssetDefinition, ParameterUiAction } from '../../types'
import {
    captureCommandEnvelope,
    createProgramCaptureDestination,
    focusProgramCaptureOrigin,
    ProgramCaptureBridgeError,
    resolveStatementTargetId,
    validateProgramCaptureDestination,
    valueDraftForAsset,
    valueDraftForCaptureResult,
} from '../captureBridge'
import type { ProgramCaptureContext } from '../captureBridge'
import type { ProgramSnapshotDto, ServerProgramValueNode } from '../serverTypes'
import type { ProgramCaptureEnvelope, ProgramFunctionContract } from '../types'

const workspace = {
    workspace_id: 'workspace_capture', generation: 7, project_id: 'project_capture',
    project_name: 'Capture test', project_path: 'D:/Capture', read_only: false,
}
const target = {
    target_id: 'target_main', name: '测试窗口', type: 'windows' as const,
    window_title: '测试', window_match: 'contains' as const, device_serial: '',
    work_area: { mode: 'client' as const }, allow_physical_fallback: true,
}

function build(
    valueType: string,
    action: ParameterUiAction,
    value: ServerProgramValueNode,
    withActions = true,
): { context: ProgramCaptureContext; envelope: ProgramCaptureEnvelope } {
    const snapshot: ProgramSnapshotDto = {
        revision: `sha256:${'a'.repeat(64)}`,
        diagnostics: [],
        document: {
            schema_version: 1,
            document_id: 'doc_capture',
            function: {
                function_id: 'function_capture', display_name: '捕获演示', parameters: [], return_type: 'unit',
                statements: [{
                    statement_id: 'statement_capture', kind: 'call', function_id: 'official.capture.test',
                    arguments: { parameter_capture: value }, result_binding: null, step_label: null,
                }],
            },
        },
    }
    const contract: ProgramFunctionContract = {
        function_id: 'official.capture.test', display_name: '测试.捕获', return_type: 'void',
        parameters: [{
            parameter_id: 'parameter_capture', display_name: '测试参数', value_type: valueType,
            required: true, ui: { control: 'expression', ...(withActions ? { actions: [action] } : {}) },
        }],
    }
    return {
        context: {
            workspace, snapshot, functionContracts: { [contract.function_id]: contract },
            platform: 'windows', target,
        },
        envelope: {
            document_id: snapshot.document.document_id,
            base_revision: snapshot.revision,
            request: {
                statement_id: 'statement_capture', parameter_id: 'parameter_capture',
                value_id: value.value_id, action,
            },
        },
    }
}

function imageAsset(): AssetDefinition {
    return {
        asset_id: 'asset_login', display_name: '登录按钮', category: 'image', folder: '',
        path: 'assets/image/login.png', extension: '.png', mime_type: 'image/png', size_bytes: 12,
        width: 40, height: 20, sha256: 'a'.repeat(64), source: 'capture',
        created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z', aliases: [], capture: null,
    }
}

describe('Program Capture bridge', () => {
    it('uses the nearest target scope instead of the project default target', () => {
        const { context } = build('point', { id: 'pick-point', capture_kind: 'point' }, {
            value_id: 'value_point', kind: 'point', x: 1, y: 2,
        })
        context.snapshot.document.function.statements = [{
            statement_id: 'scope_wechat', kind: 'target_scope', step_label: null,
            target: { value_id: 'target_wechat_value', kind: 'target_ref', target_id: 'target_wechat' },
            body: [{
                statement_id: 'scope_adb', kind: 'target_scope', step_label: null,
                target: { value_id: 'target_adb_value', kind: 'target_ref', target_id: 'target_adb' },
                body: [{
                    statement_id: 'statement_capture', kind: 'call', function_id: 'official.capture.test',
                    arguments: { parameter_capture: { value_id: 'value_point', kind: 'point', x: 1, y: 2 } },
                    result_binding: null, step_label: null,
                }],
            }],
        }]

        expect(resolveStatementTargetId(context.snapshot, 'statement_capture', 'target_default')).toBe('target_adb')
        expect(resolveStatementTargetId(context.snapshot, 'scope_wechat', 'target_default')).toBe('target_wechat')
    })

    it('never invents a capture action when the backend contract did not publish one', () => {
        const action = { id: 'pick-point', capture_kind: 'point' } as const
        const { context, envelope } = build('point', action, { value_id: 'value_point', kind: 'point', x: 1, y: 2 }, false)

        expect(() => createProgramCaptureDestination(envelope, context)).toThrow('没有开放此捕获动作')
    })

    it('submits a typed point value with the original stable destination identities', () => {
        const action: ParameterUiAction = { id: 'pick-point', capture_kind: 'point', platforms: ['windows'] }
        const { context, envelope } = build('point', action, { value_id: 'value_point', kind: 'point', x: 1, y: 2 })
        const destination = createProgramCaptureDestination(envelope, context)
        const next = valueDraftForCaptureResult(destination, { point: [18, 36] })

        expect(captureCommandEnvelope(destination, next)).toEqual({
            document_id: 'doc_capture',
            base_revision: `sha256:${'a'.repeat(64)}`,
            command: {
                kind: 'update_value', statement_id: 'statement_capture', parameter_id: 'parameter_capture',
                value_id: 'value_point', next: { kind: 'literal', value_type: 'point', value: [18, 36] },
            },
        })
    })

    it('rejects results after the Program revision or target changed', () => {
        const action = { id: 'pick-region', capture_kind: 'region' } as const
        const { context, envelope } = build('optional<rect>', action, { value_id: 'value_rect', kind: 'unset', expected_type: 'optional<rect>' })
        const destination = createProgramCaptureDestination(envelope, context)
        const newer = { ...context, snapshot: { ...context.snapshot, revision: `sha256:${'b'.repeat(64)}` } }
        const otherTarget = { ...context, target: { ...target, target_id: 'target_other' } }

        expect(() => validateProgramCaptureDestination(destination, newer)).toThrow('项目函数已经变化')
        expect(() => validateProgramCaptureDestination(destination, otherTarget)).toThrow('运行目标已经变化')
    })

    it('maps resource selection and captured images to typed asset_ref values', () => {
        const action = { id: 'choose-resource' } as const
        const { context, envelope } = build('asset_ref<image>', action, { value_id: 'value_image', kind: 'unset', expected_type: 'asset_ref<image>' })
        const destination = createProgramCaptureDestination(envelope, context)
        expect(valueDraftForAsset(destination, imageAsset())).toMatchObject({
            kind: 'asset_ref', value_type: 'asset_ref<image>', asset_id: 'asset_login', asset_kind: 'image',
        })

        const captureAction = { id: 'capture-image', capture_kind: 'image' } as const
        const captured = build('asset_ref<image>', captureAction, { value_id: 'value_image', kind: 'unset', expected_type: 'asset_ref<image>' })
        const captureDestination = createProgramCaptureDestination(captured.envelope, captured.context)
        expect(valueDraftForCaptureResult(captureDestination, { asset_refs: ['asset://asset_login'] }, [imageAsset()])).toMatchObject({
            kind: 'asset_ref', asset_id: 'asset_login', asset_kind: 'image',
        })
    })

    it('maps region and gesture-path results without converting them to JSON text', () => {
        const regionAction = { id: 'pick-region', capture_kind: 'region' } as const
        const region = build('optional<rect>', regionAction, { value_id: 'value_region', kind: 'unset', expected_type: 'optional<rect>' })
        const regionDestination = createProgramCaptureDestination(region.envelope, region.context)
        expect(valueDraftForCaptureResult(regionDestination, { rects: [[4, 8, 120, 64]] })).toEqual({
            kind: 'literal', value_type: 'optional<rect>', value: [4, 8, 120, 64],
        })

        const pathAction = { id: 'capture-path', capture_kind: 'path', max_points: 3 } as const
        const path = build('gesture_path', pathAction, { value_id: 'value_path', kind: 'path', points: [{ x: 0, y: 0 }, { x: 1, y: 1 }] })
        const pathDestination = createProgramCaptureDestination(path.envelope, path.context)
        expect(valueDraftForCaptureResult(pathDestination, { path: [[0, 0], [10, 10], [20, 20], [30, 30], [40, 40]] })).toEqual({
            kind: 'literal', value_type: 'gesture_path', value: [[0, 0], [20, 20], [40, 40]],
        })
    })

    it('maps a sampled pixel to the canonical typed color record', () => {
        const action = { id: 'pick-color', capture_kind: 'color' } as const
        const capture = build('color', action, { value_id: 'value_color', kind: 'unset', expected_type: 'color' })
        const destination = createProgramCaptureDestination(capture.envelope, capture.context)

        expect(valueDraftForCaptureResult(destination, {
            color: { red: 97, green: 98, blue: 100, alpha: 255 },
        })).toMatchObject({
            kind: 'record', value_type: 'color', record_type: 'color',
            fields: {
                'color.field.red': { kind: 'literal', value_type: 'int64', value: 97 },
                'color.field.green': { kind: 'literal', value_type: 'int64', value: 98 },
                'color.field.blue': { kind: 'literal', value_type: 'int64', value: 100 },
                'color.field.alpha': { kind: 'literal', value_type: 'int64', value: 255 },
            },
        })
        expect(() => valueDraftForCaptureResult(destination, {
            color: { red: -1, green: 98, blue: 100, alpha: 255 },
        })).toThrow('取色结果包含无效通道')
    })

    it('persists a typed portable selector instead of a runtime control reference', () => {
        const action = { id: 'capture-control', capture_kind: 'control', result_reference_type: 'control_selector' } as const
        const { context, envelope } = build('control_selector', action, { value_id: 'value_control', kind: 'unset', expected_type: 'control_selector' })
        const destination = createProgramCaptureDestination(envelope, context)

        expect(() => valueDraftForCaptureResult(destination, { selector: 'name="开始游戏"' })).toThrow(ProgramCaptureBridgeError)
        expect(valueDraftForCaptureResult(destination, { selector: {
            'control_selector.field.schema_version': 1,
            'control_selector.field.provider': 'android_uiautomator',
            'control_selector.field.target_id': 'target_emulator',
            'control_selector.field.resource_id': 'demo:id/login',
            'control_selector.field.name': '开始游戏',
            'control_selector.field.index': 0,
            'control_selector.field.path': [0, 2],
            'control_selector.field.rect': { kind: 'rect', x: 10, y: 20, width: 100, height: 40 },
            'control_selector.field.ancestor_path': [],
        } })).toMatchObject({
            kind: 'record', value_type: 'control_selector', record_type: 'control_selector',
            fields: {
                'control_selector.field.resource_id': { kind: 'literal', value_type: 'string', value: 'demo:id/login' },
                'control_selector.field.path': { kind: 'list', item_type: 'int64' },
                'control_selector.field.rect': { kind: 'literal', value_type: 'rect', value: [10, 20, 100, 40] },
            },
        })
    })

    it('returns keyboard focus to the exact action that opened the session', () => {
        const action = { id: 'pick-point', capture_kind: 'point' } as const
        const { context, envelope } = build('point', action, { value_id: 'value_point', kind: 'point', x: 1, y: 2 })
        const destination = createProgramCaptureDestination(envelope, context)
        const field = document.createElement('fieldset')
        field.dataset.valueId = 'value_point'
        const button = document.createElement('button')
        button.dataset.parameterActionId = 'pick-point'
        field.append(button)
        document.body.append(field)

        expect(focusProgramCaptureOrigin(destination)).toBe(true)
        expect(document.activeElement).toBe(button)
        field.remove()
    })
})
