package com.easycode.harness;

import com.easycode.extension.api.AndroidExtensionContext;
import com.easycode.extension.api.AndroidExtensionFunction;

/** Real JVM fixture used by the Android extension end-to-end harness. */
public final class AddExtension implements AndroidExtensionFunction {
    @Override
    public String invoke(AndroidExtensionContext context, String requestJson) {
        context.emit("info", "extension", "Android extension worker returned five");
        return "5";
    }
}
