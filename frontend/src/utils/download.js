export function safeDownloadName(value, fallback = 'download') {
    const normalized = String(value || '').trim()
        .replace(/[<>:"/\\|?*]/g, '_')
        .split('')
        .map(character => character.charCodeAt(0) < 32 ? '_' : character)
        .join('')
    return normalized || fallback
}

export function downloadBlob(data, filename) {
    const blob = data instanceof Blob ? data : new Blob([data])
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = safeDownloadName(filename)
    anchor.style.display = 'none'
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    // Keep the object URL alive until the browser has accepted the download.
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
}
