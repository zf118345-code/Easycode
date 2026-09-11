package com.easycode.player.runtime

class RuntimeControl {
    private val monitor = Object()
    @Volatile private var paused = false
    @Volatile private var stopped = false

    fun pause(): Boolean = synchronized(monitor) {
        if (stopped || paused) return@synchronized false
        paused = true
        true
    }

    fun resume(): Boolean = synchronized(monitor) {
        if (stopped || !paused) return@synchronized false
        paused = false
        monitor.notifyAll()
        true
    }

    fun stop(): Boolean = synchronized(monitor) {
        if (stopped) return@synchronized false
        stopped = true
        paused = false
        monitor.notifyAll()
        true
    }

    fun isStopped(): Boolean = stopped
    fun isPaused(): Boolean = paused

    fun checkpoint() {
        synchronized(monitor) {
            while (paused && !stopped) {
                try {
                    monitor.wait(250L)
                } catch (_: InterruptedException) {
                    if (stopped) break
                }
            }
            if (stopped) throw RuntimeStoppedSignal
        }
    }

    fun sleep(milliseconds: Long) {
        if (milliseconds < 0L) throw RuntimeFailure("runtime.argument_range", "等待时长不能为负数")
        val deadline = System.nanoTime() + milliseconds * 1_000_000L
        while (true) {
            checkpoint()
            val remainingNanos = deadline - System.nanoTime()
            if (remainingNanos <= 0L) return
            val slice = (remainingNanos / 1_000_000L).coerceIn(1L, 50L)
            synchronized(monitor) {
                if (!paused && !stopped) {
                    try {
                        monitor.wait(slice)
                    } catch (_: InterruptedException) {
                        if (stopped) throw RuntimeStoppedSignal
                    }
                }
            }
        }
    }
}

internal data object RuntimeStoppedSignal : RuntimeException()
internal data class ReturnSignal(val value: Any?) : RuntimeException()
internal data object BreakSignal : RuntimeException()
internal data object ContinueSignal : RuntimeException()
