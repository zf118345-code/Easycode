package com.easycode.player.runtime

import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread
import org.junit.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class RuntimeControlTest {
    @Test
    fun pauseBlocksCheckpointUntilResume() {
        val control = RuntimeControl()
        val entered = CountDownLatch(1)
        val released = CountDownLatch(1)
        assertTrue(control.pause())
        val worker = thread(start = true) {
            entered.countDown()
            control.checkpoint()
            released.countDown()
        }
        assertTrue(entered.await(1, TimeUnit.SECONDS))
        assertFalse(released.await(100, TimeUnit.MILLISECONDS))
        assertTrue(control.resume())
        assertTrue(released.await(1, TimeUnit.SECONDS))
        worker.join(1_000)
    }

    @Test
    fun stopWakesPausedCheckpointWithStoppedSignal() {
        val control = RuntimeControl()
        val stopped = CountDownLatch(1)
        assertTrue(control.pause())
        val worker = thread(start = true) {
            try {
                control.checkpoint()
            } catch (_: RuntimeStoppedSignal) {
                stopped.countDown()
            }
        }
        assertTrue(control.stop())
        assertTrue(stopped.await(1, TimeUnit.SECONDS))
        worker.join(1_000)
    }
}
