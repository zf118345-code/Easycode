package com.easycode.player.capture

/** Guarantees one floating Capture Session can claim one clean frame. */
class CaptureArmCoordinator {
    data class Ticket(val token: Long, val destination: String)

    private var nextToken = 0L
    private var armed: Ticket? = null
    private var captureInProgress = false

    @Synchronized
    fun arm(destination: String): Ticket {
        require(destination.isNotBlank()) { "字段采集目标无效" }
        check(!captureInProgress) { "已有画面正在冻结，请稍候" }
        return Ticket(++nextToken, destination).also { armed = it }
    }

    @Synchronized
    fun claim(ticket: Ticket): Boolean {
        if (captureInProgress || armed != ticket) return false
        armed = null
        captureInProgress = true
        return true
    }

    @Synchronized
    fun complete() {
        captureInProgress = false
    }

    @Synchronized
    fun activeTicket(): Ticket? = armed

    @Synchronized
    fun cancel() {
        armed = null
    }
}
