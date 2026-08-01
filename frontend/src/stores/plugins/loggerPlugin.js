// frontend/src/stores/plugins/loggerPlugin.js
import { logger } from '@/utils/logger';

export function piniaLoggerPlugin({ store }) {
    if (process.env.NODE_ENV !== 'development') return;

    // 监听所有 Action 执行
    store.$onAction(({ name, args, after, onError }) => {
        const start = performance.now();

        after((result) => {
            const duration = (performance.now() - start).toFixed(2);
            logger.group('Pinia Action', `${store.$id}.${name} (${duration}ms)`, () => {
                logger.debug('Action 入参', args);
                if (result !== undefined) {
                    logger.debug('Action 返回值', result);
                }
            });
        });

        onError((error) => {
            logger.error('Pinia Action 失败', `${store.$id}.${name}:`, error);
        });
    });

    // 监听所有 State 变化
    store.$subscribe((mutation, state) => {
        logger.debug(`Store State 变更 [${store.$id}]`, {
            type: mutation.type,
            payload: mutation.payload,
            updatedState: state
        });
    });
}