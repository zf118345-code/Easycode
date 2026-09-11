package com.easycode.harness;

import com.easycode.extension.api.AndroidExtensionContext;
import com.easycode.extension.api.AndroidExtensionFunction;

/** Cooperatively waits so the host timeout/worker-restart path can be verified. */
public final class SlowExtension implements AndroidExtensionFunction {
    @Override
    public String invoke(AndroidExtensionContext context, String requestJson) throws Exception {
        while (!context.isCancellationRequested()) {
            Thread.sleep(25L);
        }
        return "null";
    }
}
