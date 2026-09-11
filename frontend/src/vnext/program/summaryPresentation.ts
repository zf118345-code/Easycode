import type { ProgramAsset, ProgramSummaryPart } from './types'

const generatedImageName = /^image(?:[_-]?\d{8}(?:[_-]?\d{6,})?|[_-]?\d{12,})$/i

export function readableImageName(name: string): string {
    const normalized = name.trim()
    return !normalized || generatedImageName.test(normalized) ? '未命名图片' : normalized
}

export function summaryPartText(part: ProgramSummaryPart, assets: ProgramAsset[]): string {
    const value = part.value
    if (value?.kind !== 'asset_ref' || value.asset_kind !== 'image') return part.text
    const asset = assets.find((item) => item.asset_id === value.asset_id)
    return asset ? readableImageName(asset.display_name || value.display_name || '') : '图片已失效'
}
