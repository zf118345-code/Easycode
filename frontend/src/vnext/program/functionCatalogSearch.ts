import type { AvailableFunctionContractDto } from './serverTypes'
import type {
    ExtensionFunctionLibraryItem,
    FunctionLibrarySelection,
    ProgramStructureKind,
    ProjectFunctionLibraryItem,
} from './functionLibraryTypes'

export interface FunctionSemanticPart { text: string; dynamic?: boolean }

export interface StructureLibraryItem {
    id: string
    kind: ProgramStructureKind
    group: string
    label: string
    description: string
    aliases: string[]
    parts: FunctionSemanticPart[]
}

export interface FunctionCatalogCandidate {
    key: string
    selection: FunctionLibrarySelection
    label: string
    namespace: string
    sourceLabel: string
    description: string
    parts: FunctionSemanticPart[]
    searchTerms: string[]
    disabledReason?: string
}

const semanticPart = (text: string, dynamic = false): FunctionSemanticPart => ({ text, dynamic })

export const structureItems: StructureLibraryItem[] = [
    { id: 'if', kind: 'if', group: '流程控制', label: '如果条件', description: '条件成立时执行里面的语句，也可以添加“否则”分支', aliases: ['判断', '条件', '否则'], parts: [semanticPart('如果'), semanticPart('条件', true)] },
    { id: 'loop', kind: 'loop', group: '流程控制', label: '重复执行', description: '按次数、条件或集合内容重复执行', aliases: ['循环', '遍历'], parts: [semanticPart('重复'), semanticPart('次数、条件或列表', true)] },
    { id: 'break', kind: 'break', group: '流程控制', label: '跳出循环', description: '结束当前位置最近一层循环', aliases: ['结束循环'], parts: [semanticPart('跳出循环')] },
    { id: 'continue', kind: 'continue', group: '流程控制', label: '跳过本轮', description: '跳到当前位置最近一层循环的下一轮', aliases: ['继续循环'], parts: [semanticPart('跳过本轮')] },
    { id: 'try', kind: 'try', group: '流程控制', label: '尝试', description: '执行里面的语句，并按需要处理失败或添加最后一定执行的内容', aliases: ['异常', '失败', '最后'], parts: [semanticPart('尝试')] },
    { id: 'target_scope', kind: 'target_scope', group: '流程控制', label: '在目标中执行', description: '暂时在指定 Windows 或 Android 目标中执行，结束后恢复之前的目标', aliases: ['切换目标', '窗口', '设备'], parts: [semanticPart('在'), semanticPart('目标', true), semanticPart('中执行')] },
    { id: 'return', kind: 'return', group: '流程控制', label: '返回结果', description: '结束当前项目函数并返回结果', aliases: ['结束函数'], parts: [semanticPart('返回'), semanticPart('结果', true)] },
    { id: 'fail', kind: 'fail', group: '流程控制', label: '结束为失败', description: '用明确原因结束当前流程，可由“尝试”处理', aliases: ['报错', '错误'], parts: [semanticPart('结束为失败：'), semanticPart('原因', true)] },
    { id: 'assignment.new', kind: 'assignment', group: '变量', label: '新建局部变量', description: '在当前项目函数中创建一个新变量并设置初始值', aliases: ['设置变量', '声明变量', '赋值'], parts: [semanticPart('新建'), semanticPart('局部变量', true)] },
    { id: 'assignment.existing', kind: 'assignment', group: '变量', label: '修改变量', description: '选择一个已经存在的局部变量或项目变量，再设置新值', aliases: ['设置变量', '重新赋值'], parts: [semanticPart('修改'), semanticPart('已有变量', true)] },
    { id: 'listen', kind: 'listen', group: '消息', label: '收到消息时', description: '收到指定消息后执行一个项目函数', aliases: ['监听消息', '异步监听'], parts: [semanticPart('收到'), semanticPart('消息', true), semanticPart('时')] },
]

export function semanticParts(template: string, parameters: Array<{ name: string; display_name: string }>): FunctionSemanticPart[] {
    const parts: FunctionSemanticPart[] = []
    let cursor = 0
    for (const match of template.matchAll(/\{([^}]+)\}/g)) {
        const index = match.index ?? 0
        if (index > cursor) parts.push(semanticPart(template.slice(cursor, index)))
        const parameter = parameters.find((item) => item.name === match[1])
        parts.push(semanticPart(parameter?.display_name || match[1], true))
        cursor = index + match[0].length
    }
    if (cursor < template.length) parts.push(semanticPart(template.slice(cursor)))
    return parts.length ? parts : [semanticPart(template)]
}

export function semanticFunctionParts(item: AvailableFunctionContractDto): FunctionSemanticPart[] {
    return semanticParts(item.summary || item.qualified_name, item.parameters)
}

export function semanticFunctionLabel(item: AvailableFunctionContractDto): string {
    return semanticFunctionParts(item).map((part) => part.text).join('')
}

export function semanticExtensionParts(item: ExtensionFunctionLibraryItem): FunctionSemanticPart[] {
    return semanticParts(item.summary || item.display_name, item.parameters || [])
}

export function semanticExtensionLabel(item: ExtensionFunctionLibraryItem): string {
    return semanticExtensionParts(item).map((part) => part.text).join('')
}

export function normalizeFunctionQuery(value: string): string {
    return value.trim().toLocaleLowerCase('zh-CN')
}

function normalizedTerms(terms: Array<string | undefined>): string[] {
    return terms.filter((term): term is string => Boolean(term?.trim())).map((term) => term.toLocaleLowerCase('zh-CN'))
}

function supportsResultCondition(returnType: string | undefined): boolean {
    return returnType === 'bool' || Boolean(returnType?.startsWith('optional<') && returnType.endsWith('>'))
}

function addCallAndIfCandidate(
    candidates: FunctionCatalogCandidate[],
    candidate: FunctionCatalogCandidate,
    returnType: string | undefined,
): void {
    if (!supportsResultCondition(returnType) || candidate.disabledReason) return
    candidates.push({
        ...candidate,
        key: `${candidate.key}:call-and-if`,
        selection: { ...candidate.selection, intent: 'call_and_if' },
        label: `如果${candidate.label}`,
        sourceLabel: '快捷结构',
        description: `调用一次并根据${returnType === 'bool' ? '结果是否成立' : '是否有结果'}添加条件`,
        parts: [semanticPart('如果'), ...candidate.parts],
        searchTerms: normalizedTerms([
            ...candidate.searchTerms, `如果${candidate.label}`, `${candidate.label}并判断`, '调用并判断', '有结果',
        ]),
    })
}

function addExecuteUntilCandidate(
    candidates: FunctionCatalogCandidate[],
    candidate: FunctionCatalogCandidate,
    returnType: string | undefined,
): void {
    if (!supportsResultCondition(returnType) || candidate.disabledReason) return
    const visualActionAliases = candidate.selection.function_id === 'official.image.find'
        ? ['向左拖动直到图片出现', '向右拖动直到图片出现', '滑动直到图像出现', '滚动直到图像出现']
        : []
    candidates.push({
        ...candidate,
        key: `${candidate.key}:execute-until`,
        selection: { ...candidate.selection, intent: 'execute_until' },
        label: `重复操作直到${candidate.label}`,
        sourceLabel: '快捷结构',
        description: '先检查条件；未满足时执行你随后加入的动作，最多 20 次，仍未满足则明确报错',
        parts: [semanticPart('重复操作直到'), ...candidate.parts],
        searchTerms: normalizedTerms([
            ...candidate.searchTerms,
            `重复操作直到${candidate.label}`,
            `执行直到${candidate.label}`,
            `${candidate.label}出现前重复`,
            '执行直到', '重复直到', '直到出现', ...visualActionAliases,
        ]),
    })
}

function matchScore(candidate: FunctionCatalogCandidate, query: string): number | null {
    if (!query) return 0
    const label = candidate.label.toLocaleLowerCase('zh-CN')
    const namespace = candidate.namespace.toLocaleLowerCase('zh-CN')
    if (label === query) return 0
    if (namespace === query) return 2
    if (label.startsWith(query)) return 4
    if (namespace.startsWith(query)) return 6
    if (label.includes(query)) return 8
    if (namespace.includes(query)) return 10
    const termIndex = candidate.searchTerms.findIndex((term) => term.includes(query))
    return termIndex < 0 ? null : 20 + termIndex
}

export function buildFunctionCatalog(options: {
    officialFunctions?: AvailableFunctionContractDto[]
    projectFunctions?: ProjectFunctionLibraryItem[]
    extensionFunctions?: ExtensionFunctionLibraryItem[]
    activeFunctionId?: string
}): FunctionCatalogCandidate[] {
    const candidates: FunctionCatalogCandidate[] = structureItems.map((item) => ({
        key: `structure:${item.id}`,
        selection: { source: 'structure', function_id: item.id },
        label: item.label,
        namespace: item.group,
        sourceLabel: '结构',
        description: item.description,
        parts: item.parts,
        searchTerms: normalizedTerms([item.group, item.label, item.description, ...item.aliases, ...item.parts.map((part) => part.text)]),
    }))
    for (const item of options.projectFunctions || []) {
        const candidate: FunctionCatalogCandidate = {
            key: `project:${item.function_id}`,
            selection: { source: 'project', function_id: item.function_id },
            label: item.display_name,
            namespace: '项目函数',
            sourceLabel: '项目',
            description: `${item.statement_count} 条语句`,
            parts: [semanticPart(item.display_name)],
            searchTerms: normalizedTerms([
                item.display_name, '调用项目函数',
                ...item.parameters.map((parameter) => parameter.display_name),
            ]),
            disabledReason: item.function_id === options.activeFunctionId
                ? '项目函数不能直接调用自身'
                : item.insert_disabled_reason || (item.insertable === false ? '当前项目函数不可插入' : undefined),
        }
        candidates.push(candidate)
        addCallAndIfCandidate(candidates, candidate, item.return_type)
        addExecuteUntilCandidate(candidates, candidate, item.return_type)
    }
    for (const item of options.officialFunctions || []) {
        if (item.implementation_state !== 'available') continue
        const parts = semanticFunctionParts(item)
        const candidate: FunctionCatalogCandidate = {
            key: `official:${item.function_id}`,
            selection: { source: 'official', function_id: item.function_id },
            label: parts.map((part) => part.text).join(''),
            namespace: item.namespace,
            sourceLabel: '官方',
            description: item.qualified_name,
            parts,
            searchTerms: normalizedTerms([
                item.qualified_name, item.namespace, item.name, item.summary,
                ...item.parameters.flatMap((parameter) => [parameter.name, parameter.display_name]),
            ]),
        }
        candidates.push(candidate)
        addCallAndIfCandidate(candidates, candidate, item.return_type)
        addExecuteUntilCandidate(candidates, candidate, item.return_type)
    }
    for (const item of options.extensionFunctions || []) {
        if (item.implementation_state !== 'available') continue
        const parts = semanticExtensionParts(item)
        const candidate: FunctionCatalogCandidate = {
            key: `extension:${item.function_id}`,
            selection: { source: 'extension', function_id: item.function_id },
            label: parts.map((part) => part.text).join(''),
            namespace: item.namespace,
            sourceLabel: '扩展',
            description: item.description || item.qualified_name || item.display_name,
            parts,
            searchTerms: normalizedTerms([
                item.display_name, item.qualified_name, item.namespace, item.summary, item.description,
                ...(item.parameters?.flatMap((parameter) => [parameter.name, parameter.display_name]) || []),
            ]),
        }
        candidates.push(candidate)
        addCallAndIfCandidate(candidates, candidate, item.return_type)
        addExecuteUntilCandidate(candidates, candidate, item.return_type)
    }
    return candidates
}

export function searchFunctionCatalog(
    candidates: FunctionCatalogCandidate[],
    rawQuery: string,
    options: { limit?: number; recentKeys?: string[]; source?: FunctionLibrarySelection['source'] } = {},
): FunctionCatalogCandidate[] {
    const query = normalizeFunctionQuery(rawQuery)
    const sourceCandidates = options.source ? candidates.filter((candidate) => candidate.selection.source === options.source) : candidates
    const recentIndex = new Map((options.recentKeys || []).map((key, index) => [key, index]))
    return sourceCandidates
        .map((candidate, index) => ({ candidate, index, score: matchScore(candidate, query) }))
        .filter((entry): entry is { candidate: FunctionCatalogCandidate; index: number; score: number } => entry.score !== null)
        .sort((left, right) => {
            if (!query) {
                const leftRecent = recentIndex.get(left.candidate.key)
                const rightRecent = recentIndex.get(right.candidate.key)
                if (leftRecent !== undefined || rightRecent !== undefined) return (leftRecent ?? Number.MAX_SAFE_INTEGER) - (rightRecent ?? Number.MAX_SAFE_INTEGER)
            }
            return left.score - right.score
                || Number(Boolean(left.candidate.disabledReason)) - Number(Boolean(right.candidate.disabledReason))
                || left.index - right.index
        })
        .slice(0, options.limit ?? candidates.length)
        .map((entry) => entry.candidate)
}
