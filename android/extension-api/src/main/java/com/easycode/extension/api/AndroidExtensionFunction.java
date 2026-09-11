package com.easycode.extension.api;

/**
 * Stable ABI implemented by one trusted Android extension function entrypoint.
 *
 * <p>The request and response are versioned UTF-8 JSON objects. Implementations
 * must not retain the context after this call returns.</p>
 */
public interface AndroidExtensionFunction {
    String invoke(AndroidExtensionContext context, String requestJson) throws Exception;
}
