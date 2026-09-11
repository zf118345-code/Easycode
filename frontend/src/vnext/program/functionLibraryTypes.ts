import type { ProgramSummaryDto } from './serverTypes'

export type ProgramStructureKind = 'assignment' | 'if' | 'loop' | 'break' | 'continue' | 'try' | 'target_scope' | 'listen' | 'return' | 'fail'
export type FunctionLibrarySource = 'structure' | 'project' | 'official' | 'extension'
export type FunctionLibraryTab = Exclude<FunctionLibrarySource, 'structure'>

export interface ProjectFunctionLibraryItem extends ProgramSummaryDto {
    /** The Program Service catalog decides whether this item can be inserted. */
    insertable?: boolean
    insert_disabled_reason?: string
}

export interface ExtensionFunctionLibraryItem {
    function_id: string
    namespace: string
    display_name: string
    qualified_name?: string
    summary?: string
    parameters?: Array<{ name: string; display_name: string }>
    description?: string
    implementation_state: 'available' | 'planned' | string
}

export interface FunctionLibrarySelection {
    source: FunctionLibrarySource
    function_id: string
}
