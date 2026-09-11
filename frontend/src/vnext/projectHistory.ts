export interface RecentProject { name: string; path: string }

const RECENT_PROJECTS_KEY = 'easycode.vnext.recent-projects'

export function readRecentProjects(): RecentProject[] {
    try {
        const value = JSON.parse(localStorage.getItem(RECENT_PROJECTS_KEY) || '[]')
        return Array.isArray(value)
            ? value.filter(item => item && typeof item.name === 'string' && typeof item.path === 'string').slice(0, 8)
            : []
    } catch { return [] }
}

export function rememberProject(name: string, path: string): RecentProject[] {
    const normalized = path.trim().replace(/[\\/]+$/, '')
    const next = [{ name, path: normalized }, ...readRecentProjects().filter(item => item.path.toLocaleLowerCase() !== normalized.toLocaleLowerCase())].slice(0, 8)
    try { localStorage.setItem(RECENT_PROJECTS_KEY, JSON.stringify(next)) } catch { /* private storage may be unavailable */ }
    return next
}
