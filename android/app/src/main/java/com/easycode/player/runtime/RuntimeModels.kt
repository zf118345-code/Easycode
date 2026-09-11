package com.easycode.player.runtime

import com.google.gson.JsonObject

enum class RunStatus {
    IDLE,
    STARTING,
    RUNNING,
    PAUSED,
    COMPLETED,
    FAILED,
    STOPPING,
    STOPPED,
}

data class RunState(
    val runId: String = "",
    val status: RunStatus = RunStatus.IDLE,
    val productId: String = "",
    val releaseId: String = "",
    val profileId: String = "",
    val profileRevision: Int = 0,
    val entryFunctionId: String = "",
    val currentFunctionId: String = "",
    val currentInstructionId: String = "",
    val targetId: String = "",
    val sequence: Long = 0,
    val startedAt: String = "",
    val updatedAt: String = "",
    val errorId: String = "",
    val errorMessage: String = "",
    val eventLogPath: String = "",
) {
    val active: Boolean get() = status in setOf(
        RunStatus.STARTING,
        RunStatus.RUNNING,
        RunStatus.PAUSED,
        RunStatus.STOPPING,
    )
}

data class RuntimeEvent(
    val sequence: Long,
    val timestamp: String,
    val level: String,
    val category: String,
    val message: String,
    val runId: String,
    val functionId: String = "",
    val instructionId: String = "",
    val errorId: String = "",
)

class RuntimeFailure(
    val errorId: String,
    message: String,
    val transient: Boolean = false,
    cause: Throwable? = null,
    val details: Any? = null,
) : RuntimeException(message, cause)

data class BoundRun(
    val ecir: JsonObject,
    val entryFunctionId: String,
    val targetId: String,
)

/** A destructive-directory approval is intentionally an in-memory run input.
 *
 * It is never stored in a Player profile, schedule, bundle, or runtime-state
 * file.  All four fields must still match when the instruction resolves its
 * concrete DirectoryReference, so changing the call, root, saved profile, or
 * locked contract invalidates the approval before the first delete.
 */
data class DangerousRunConfirmation(
    val statementId: String,
    val authorizationRootId: String,
    val profileRevision: Int,
    val contractFingerprint: String,
)

interface RuntimeObserver {
    fun stateChanged(state: RunState)
    fun event(event: RuntimeEvent)
}
