package com.easycode.player

internal enum class RuntimePermissionRequirement(val id: String) {
    CAPTURE("capture"),
    INPUT("input"),
}

/**
 * Selects one currently missing runtime permission in a stable order.
 *
 * The caller must evaluate this again after returning from each Android
 * permission surface.  A task can require both screen capture and input, and
 * satisfying the first requirement must never bypass the second one.
 */
internal object RuntimePermissionGate {
    fun next(
        needsCapture: Boolean,
        captureReady: Boolean,
        needsInput: Boolean,
        inputReady: Boolean,
    ): RuntimePermissionRequirement? = when {
        needsCapture && !captureReady -> RuntimePermissionRequirement.CAPTURE
        needsInput && !inputReady -> RuntimePermissionRequirement.INPUT
        else -> null
    }
}
