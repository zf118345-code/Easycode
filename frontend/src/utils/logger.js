// frontend/src/utils/logger.js

// 日志级别：DEBUG(0) < INFO(1) < WARN(2) < ERROR(3)
const LEVELS = { DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3 };

// 默认开发环境为 DEBUG，可随时在浏览器控制台通过 window.__LOG_LEVEL__ = 'INFO' 修改
window.__LOG_LEVEL__ = process.env.NODE_ENV === 'development' ? 'DEBUG' : 'WARN';

function shouldLog(level) {
    const currentLevel = LEVELS[window.__LOG_LEVEL__] ?? LEVELS.INFO;
    return LEVELS[level] >= currentLevel;
}

export const logger = {
    debug(tag, ...args) {
        if (shouldLog('DEBUG')) {
            console.log(`🔍 [${tag}]`, ...args);
        }
    },

    info(tag, ...args) {
        if (shouldLog('INFO')) {
            console.log(`ℹ️ [${tag}]`, ...args);
        }
    },

    warn(tag, ...args) {
        if (shouldLog('WARN')) {
            console.warn(`⚠️ [${tag}]`, ...args);
        }
    },

    error(tag, ...args) {
        if (shouldLog('ERROR')) {
            console.error(`❌ [${tag}]`, ...args);
        }
    },

    // 展开式分组追踪（出 Bug 时看这个极度方便）
    group(tag, title, callback) {
        if (shouldLog('DEBUG')) {
            console.group(`🚀 [${tag}] ${title}`);
            try {
                callback();
            } finally {
                console.groupEnd();
            }
        } else {
            callback();
        }
    },

    // 追踪函数调用栈
    trace(tag, msg) {
        if (shouldLog('DEBUG')) {
            console.groupCollapsed(`🕵️‍♂️ [${tag}] ${msg}`);
            console.trace('调用栈轨迹');
            console.groupEnd();
        }
    }
};