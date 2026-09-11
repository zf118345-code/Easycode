import type { InjectionKey } from 'vue'
import type { ProgramValueCatalogDto } from './serverTypes'
import type { LocalSymbolDefinition } from './types'

export type ProgramValueCatalogResolver = (
    statementId: string,
    expectedType: string,
    scopeBindings?: LocalSymbolDefinition[],
) => Promise<ProgramValueCatalogDto>

export const programValueCatalogResolverKey: InjectionKey<ProgramValueCatalogResolver> = Symbol('program-value-catalog-resolver')

