import type {
    ExpressionNamespaceDto,
    ExpressionOperationDiscoveryDto,
    ProgramValueCatalogDto,
    PureOperationCandidateDto,
} from './serverTypes'

const NAMESPACE_BY_PREFIX: Record<string, string> = {
    number: '数值',
    value: '类型',
    text: '文本',
    duration: '时间',
    optional: '结果',
    select: '条件',
    point: '坐标',
    rect: '坐标',
    list: '列表',
    map: '字典',
    json: 'JSON',
    file: '文件',
}

export interface ExpressionOperationSuggestion {
    key: string
    candidate: PureOperationCandidateDto
    syntaxName: string
    signature: string
}

export interface ExpressionOperationDirectorySuggestion {
    key: string
    discovery: ExpressionOperationDiscoveryDto
    candidate: PureOperationCandidateDto | null
    disabledReason: string
}

function operationPrefix(operationId: string): string {
    return operationId.split('.')[1]?.split('_')[0] || ''
}

export function operationNamespace(candidate: Pick<PureOperationCandidateDto, 'operation_id' | 'category'>): string {
    return NAMESPACE_BY_PREFIX[operationPrefix(candidate.operation_id)] || candidate.category
}

export function operationShortName(candidate: Pick<PureOperationCandidateDto, 'operation_id' | 'display_name' | 'category'>): string {
    const namespace = operationNamespace(candidate)
    let name = candidate.display_name.trim()
    if (namespace === '文本') name = name.replaceAll('文本', '')
    if (namespace === '列表') name = name.replaceAll('列表项', '').replaceAll('列表', '')
    if (namespace === '字典') name = name.replaceAll('字典项', '').replaceAll('字典', '')
    if (namespace === 'JSON') name = name.replaceAll('JSON', '')
    if (namespace === '坐标') name = name.replaceAll('坐标', '')
    name = name.replaceAll(' ', '')
    return name.trim() || candidate.display_name
}

export function operationSyntaxName(candidate: Pick<PureOperationCandidateDto, 'operation_id' | 'display_name' | 'category' | 'syntax_name'>): string {
    if (candidate.syntax_name?.trim()) return candidate.syntax_name
    const displayName = candidate.display_name.trim()
    if (!displayName || displayName === candidate.operation_id || /^(?:core|official|extension)\./.test(displayName)) {
        return '不可用操作'
    }
    if (displayName.includes('.')) return displayName
    const namespace = operationNamespace(candidate)
    return namespace ? `${namespace}.${operationShortName(candidate)}` : displayName
}

export function normalizeSyntaxKey(value: string): string {
    return value
        .replaceAll('。', '.')
        .replaceAll('．', '.')
        .replace(/\s+/g, '')
        .toLocaleLowerCase('zh-CN')
}

export function operationSyntaxAliases(candidate: PureOperationCandidateDto): string[] {
    const namespace = operationNamespace(candidate)
    return [...new Set([
        operationSyntaxName(candidate),
        `${namespace}.${candidate.display_name}`,
        `${candidate.category}.${candidate.display_name}`,
        candidate.display_name,
    ].map(normalizeSyntaxKey))]
}

export function operationSignature(candidate: PureOperationCandidateDto): string {
    return `${operationSyntaxName(candidate)}(${candidate.inputs.map((input) => input.display_name).join(', ')})`
}

export function operationSuggestions(catalogs: ProgramValueCatalogDto[], query = ''): ExpressionOperationSuggestion[] {
    const normalizedQuery = normalizeSyntaxKey(query)
    const seen = new Set<string>()
    return catalogs.flatMap((catalog) => catalog.operations).flatMap((candidate) => {
        const key = `${candidate.operation_id}:${candidate.result_type}:${candidate.inputs.map((item) => item.value_type).join(',')}`
        if (seen.has(key)) return []
        const syntaxName = operationSyntaxName(candidate)
        const searchable = normalizeSyntaxKey(`${syntaxName} ${candidate.display_name} ${candidate.description}`)
        if (normalizedQuery && !searchable.includes(normalizedQuery)) return []
        seen.add(key)
        return [{ key, candidate, syntaxName, signature: operationSignature(candidate) }]
    })
}

export function expressionNamespaces(catalog: ProgramValueCatalogDto | null | undefined): ExpressionNamespaceDto[] {
    if (catalog?.discovery?.namespaces?.length) return catalog.discovery.namespaces
    const counts = new Map<string, number>()
    for (const operation of catalog?.operations || []) {
        const namespace = operationNamespace(operation)
        counts.set(namespace, (counts.get(namespace) || 0) + 1)
    }
    return [...counts].map(([name, count]) => ({
        name,
        description: `查看${name}相关操作`,
        keywords: [],
        operation_count: count,
        compatible_count: count,
    }))
}

export function operationDirectorySuggestions(
    catalog: ProgramValueCatalogDto | null | undefined,
    query = '',
    candidateCatalogs: ProgramValueCatalogDto[] = [],
): ExpressionOperationDirectorySuggestion[] {
    if (!catalog) return []
    const normalizedQuery = normalizeSyntaxKey(query)
    const dotIndex = normalizedQuery.indexOf('.')
    const namespaceQuery = dotIndex >= 0 ? normalizedQuery.slice(0, dotIndex) : ''
    const actionQuery = dotIndex >= 0 ? normalizedQuery.slice(dotIndex + 1) : normalizedQuery
    const compatible = new Map<string, PureOperationCandidateDto>()
    for (const source of [catalog, ...candidateCatalogs]) {
        for (const candidate of source.operations) {
            if (!compatible.has(candidate.operation_id)) compatible.set(candidate.operation_id, candidate)
        }
    }
    const directory = catalog.discovery?.operations || catalog.operations.map((candidate): ExpressionOperationDiscoveryDto => ({
        operation_id: candidate.operation_id,
        display_name: candidate.display_name,
        namespace: operationNamespace(candidate),
        group: '可用操作',
        description: candidate.description,
        syntax_name: operationSyntaxName(candidate),
        aliases: [candidate.display_name],
        keywords: [],
        input_labels: candidate.inputs.map((input) => input.display_name),
        example: operationSignature(candidate),
        result_type_hints: [candidate.result_type],
        compatible: true,
        disabled_reason: '',
    }))
    return directory.flatMap((item) => {
        const searchable = normalizeSyntaxKey([
            item.display_name,
            item.group,
            item.description,
            ...item.aliases,
            ...item.keywords,
        ].join(' '))
        if (namespaceQuery && !normalizeSyntaxKey(item.namespace).includes(namespaceQuery)) return []
        if (actionQuery && !searchable.includes(actionQuery)) return []
        const candidate = compatible.get(item.operation_id) || null
        return [{
            key: item.operation_id,
            discovery: item,
            candidate,
            disabledReason: candidate ? '' : (item.disabled_reason || '不能用于当前字段'),
        }]
    })
}

export function expressionHelpExamples(expectedType: string): string[] {
    if (expectedType === 'bool') return ['@队伍已准备', '@当前体力 >= @最低体力', '@已登录 且 非 @正在战斗']
    if (['int64', 'float64', 'percentage'].includes(expectedType)) return ['18', '@当前等级 + 3', '数值.四舍五入(@平均耗时, 2)']
    if (expectedType === 'duration') return ['500 毫秒', '2 秒', '@等待时间']
    if (expectedType === 'date') return ['2026-09-04', '@今天', '时间.增加天数(@今天, 3)']
    if (expectedType === 'datetime') return ['2026-09-04 18:30:00', '@开始时间', '时间.增加分钟(@开始时间, 30)']
    if (expectedType.startsWith('list<')) return ['列表.追加(@副本列表, "经验副本")', '列表.去重(@副本列表)']
    if (expectedType.startsWith('map<')) return ['字典.设置值(@角色配置, "最低体力", 30)', '字典.合并(@默认配置, @玩家配置, "以后者为准")']
    if (expectedType === 'json' || expectedType === 'json_value' || expectedType.startsWith('optional<json')) {
        return ['JSON.读取路径(@接口结果, ["data", "roomCode"])', 'JSON.路径存在(@接口结果, ["data"])']
    }
    if (expectedType === 'point' || expectedType === 'coordinate') return ['坐标.偏移(@登录按钮.中心, @偏移量)', '坐标.区域中心(@识别区域)']
    if (expectedType === 'rect' || expectedType === 'region') return ['@识别区域', '坐标.移动区域(@识别区域, 10, 20)']
    return ['直接输入普通内容', '@公告内容', '文本.替换(@公告内容, "旧服", "新服")']
}

export function normalizeExpressionPunctuation(value: string): string {
    let result = ''
    let quote = ''
    for (const char of value) {
        if (!quote && ['"', "'", '“', '‘'].includes(char)) {
            quote = char === '“' ? '”' : char === '‘' ? '’' : char
            result += char === '“' || char === '‘' ? '"' : char
            continue
        }
        if (quote && char === quote) {
            quote = ''
            result += char === '”' || char === '’' ? '"' : char
            continue
        }
        if (quote) { result += char; continue }
        if (char === '。' || char === '．') result += '.'
        else if (char === '，') result += ','
        else if (char === '（') result += '('
        else if (char === '）') result += ')'
        else result += char
    }
    return result
}

export function splitFunctionArguments(value: string): { arguments: string[]; error: string } {
    if (!value.trim()) return { arguments: [], error: '' }
    const result: string[] = []
    let current = ''
    let roundDepth = 0
    let squareDepth = 0
    let braceDepth = 0
    let quote = ''
    for (const char of value) {
        if (!quote && ['"', "'", '“', '‘'].includes(char)) {
            quote = char === '“' ? '”' : char === '‘' ? '’' : char
            current += char
            continue
        }
        if (quote && char === quote) { quote = ''; current += char; continue }
        if (quote) { current += char; continue }
        if (char === '(' || char === '（') roundDepth += 1
        else if (char === ')' || char === '）') roundDepth -= 1
        else if (char === '[') squareDepth += 1
        else if (char === ']') squareDepth -= 1
        else if (char === '{') braceDepth += 1
        else if (char === '}') braceDepth -= 1
        if ((char === ',' || char === '，') && roundDepth === 0 && squareDepth === 0 && braceDepth === 0) {
            result.push(current.trim())
            current = ''
            continue
        }
        current += char
    }
    if (quote) return { arguments: [], error: '文本引号没有闭合。' }
    if (roundDepth || squareDepth || braceDepth) return { arguments: [], error: '括号没有闭合。' }
    result.push(current.trim())
    if (result.some((item) => !item)) return { arguments: [], error: '函数参数之间不能留空。' }
    return { arguments: result, error: '' }
}
