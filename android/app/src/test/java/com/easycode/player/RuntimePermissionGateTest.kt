package com.easycode.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RuntimePermissionGateTest {
    @Test
    fun `checks every missing requirement after each permission return`() {
        assertEquals(
            RuntimePermissionRequirement.CAPTURE,
            RuntimePermissionGate.next(
                needsCapture = true,
                captureReady = false,
                needsInput = true,
                inputReady = false,
            ),
        )
        assertEquals(
            RuntimePermissionRequirement.INPUT,
            RuntimePermissionGate.next(
                needsCapture = true,
                captureReady = true,
                needsInput = true,
                inputReady = false,
            ),
        )
        assertNull(
            RuntimePermissionGate.next(
                needsCapture = true,
                captureReady = true,
                needsInput = true,
                inputReady = true,
            ),
        )
    }

    @Test
    fun `does not request capabilities the task does not use`() {
        assertNull(
            RuntimePermissionGate.next(
                needsCapture = false,
                captureReady = false,
                needsInput = false,
                inputReady = false,
            ),
        )
        assertEquals(
            RuntimePermissionRequirement.INPUT,
            RuntimePermissionGate.next(
                needsCapture = false,
                captureReady = false,
                needsInput = true,
                inputReady = false,
            ),
        )
    }
}
