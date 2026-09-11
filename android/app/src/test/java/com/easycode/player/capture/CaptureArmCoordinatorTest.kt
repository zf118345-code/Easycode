package com.easycode.player.capture

import org.junit.Test
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class CaptureArmCoordinatorTest {
    @Test
    fun countdownAndNotificationCanClaimOnlyOnce() {
        val coordinator = CaptureArmCoordinator()
        val ticket = coordinator.arm("field-a")

        assertTrue(coordinator.claim(ticket))
        assertFalse(coordinator.claim(ticket))
        assertFailsWith<IllegalStateException> { coordinator.arm("field-b") }

        coordinator.complete()
        assertTrue(coordinator.claim(coordinator.arm("field-b")))
    }

    @Test
    fun staleNotificationCannotClaimNewArm() {
        val coordinator = CaptureArmCoordinator()
        val stale = coordinator.arm("field-a")
        val current = coordinator.arm("field-b")

        assertFalse(coordinator.claim(stale))
        assertTrue(coordinator.claim(current))
    }

    @Test
    fun cancelInvalidatesPendingTicket() {
        val coordinator = CaptureArmCoordinator()
        val ticket = coordinator.arm("field-a")

        coordinator.cancel()

        assertFalse(coordinator.claim(ticket))
    }
}
