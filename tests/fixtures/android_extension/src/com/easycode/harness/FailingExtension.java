package com.easycode.harness;

import com.easycode.extension.api.AndroidExtensionContext;
import com.easycode.extension.api.AndroidExtensionFunction;

/** Produces a stable worker-side failure for isolation verification. */
public final class FailingExtension implements AndroidExtensionFunction {
    @Override
    public String invoke(AndroidExtensionContext context, String requestJson) {
        throw new IllegalStateException("fixture failure");
    }
}
