package com.easycode.extension.api;

import android.content.Context;

/** Host services available to a trusted Android extension worker. */
public interface AndroidExtensionContext {
    Context applicationContext();

    String runId();

    String packageId();

    String functionId();

    boolean isCancellationRequested();

    void emit(String level, String category, String message);
}
