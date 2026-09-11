package com.easycode.player.runtime

import android.content.Context
import android.content.Intent
import com.easycode.player.bundle.VerifiedBundle
import com.easycode.player.profile.PlayerProfile
import com.easycode.player.profile.ProfileStore
import com.easycode.player.util.AtomicFiles
import com.easycode.player.util.JsonSupport
import com.google.gson.JsonObject
import java.io.File
import java.time.Instant
import java.util.UUID
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class RuntimeController(private val context: Context) {
    private val lock = Any()
    private val observers = CopyOnWriteArrayList<RuntimeObserver>()
    private var executor: ExecutorService? = null
    private var control: RuntimeControl? = null
    private var eventLog: RuntimeEventLog? = null
    @Volatile private var current = RunState()
    private var sequence = 0L

    fun state(): RunState = current

    fun observe(observer: RuntimeObserver) {
        observers += observer
        observer.stateChanged(current)
    }

    fun removeObserver(observer: RuntimeObserver) {
        observers -= observer
    }

    fun start(
        bundle: VerifiedBundle,
        profile: PlayerProfile,
        profileStore: ProfileStore,
        actionControlId: String = "",
        dangerousConfirmations: Set<DangerousRunConfirmation> = emptySet(),
        requestedRunId: String = "",
    ): RunState = synchronized(lock) {
        if (current.active) throw RuntimeFailure("runtime.busy", "已有任务正在运行或暂停")
        val bound = PlayerBindings.bind(bundle, profile, actionControlId)
        val runId = requestedRunId.ifBlank { "run_${UUID.randomUUID().toString().replace("-", "")}" }
        if (!runId.matches(Regex("run_[A-Za-z0-9_.-]{1,120}"))) {
            throw RuntimeFailure("runtime.identity_invalid", "运行编号无效")
        }
        sequence = 0L
        val nextControl = RuntimeControl()
        val nextLog = RuntimeEventLog(File(context.filesDir, "runtime-logs"), runId)
        control = nextControl
        eventLog = nextLog
        current = RunState(
            runId = runId,
            status = RunStatus.STARTING,
            productId = bundle.productId,
            releaseId = bundle.releaseId,
            profileId = profile.profileId,
            profileRevision = profile.revision,
            entryFunctionId = bound.entryFunctionId,
            targetId = bound.targetId,
            sequence = 0,
            startedAt = Instant.now().toString(),
            updatedAt = Instant.now().toString(),
            eventLogPath = nextLog.path,
        )
        publishState(persist = true)
        RuntimeForegroundService.ensureRunning(context)
        val nextExecutor = Executors.newSingleThreadExecutor { runnable ->
            Thread(runnable, "easycode-runtime-$runId").apply { isDaemon = false }
        }
        executor = nextExecutor
        nextExecutor.execute {
            execute(bundle, profile, profileStore, bound, runId, dangerousConfirmations, nextControl, nextLog)
        }
        current
    }

    fun pause(): RunState = synchronized(lock) {
        if (current.status !in setOf(RunStatus.STARTING, RunStatus.RUNNING)) {
            throw RuntimeFailure("runtime.state_invalid", "当前运行状态不能暂停")
        }
        if (control?.pause() != true) throw RuntimeFailure("runtime.state_invalid", "运行无法暂停")
        current = current.copy(status = RunStatus.PAUSED, updatedAt = Instant.now().toString())
        event("info", "runtime", "任务已暂停")
        publishState(persist = true)
        current
    }

    fun resume(): RunState = synchronized(lock) {
        if (current.status != RunStatus.PAUSED || control?.resume() != true) {
            throw RuntimeFailure("runtime.state_invalid", "当前运行状态未暂停")
        }
        current = current.copy(status = RunStatus.RUNNING, updatedAt = Instant.now().toString())
        event("info", "runtime", "任务已继续")
        publishState(persist = true)
        current
    }

    fun stop(): RunState = synchronized(lock) {
        if (!current.active) throw RuntimeFailure("runtime.state_invalid", "当前没有可停止的运行")
        current = current.copy(status = RunStatus.STOPPING, updatedAt = Instant.now().toString())
        event("warning", "runtime", "用户请求停止任务")
        control?.stop()
        publishState(persist = true)
        current
    }

    private fun execute(
        bundle: VerifiedBundle,
        profile: PlayerProfile,
        profileStore: ProfileStore,
        bound: BoundRun,
        runId: String,
        dangerousConfirmations: Set<DangerousRunConfirmation>,
        nextControl: RuntimeControl,
        nextLog: RuntimeEventLog,
    ) {
        updateStatus(RunStatus.RUNNING)
        event("info", "runtime", "Android 本机任务已启动")
        try {
            EcirInterpreter(
                context,
                bundle,
                profile,
                bound,
                runId,
                profileStore,
                nextControl,
                dangerousConfirmations,
                onCheckpoint = { functionId, instructionId -> checkpoint(functionId, instructionId) },
                onEvent = { level, category, message, instructionId, errorId ->
                    event(level, category, message, instructionId, errorId)
                },
            ).use { interpreter -> interpreter.run() }
            if (nextControl.isStopped()) {
                event("warning", "runtime", "任务已停止")
                updateTerminal(RunStatus.STOPPED, "", "")
            } else {
                event("info", "runtime", "任务运行完成")
                updateTerminal(RunStatus.COMPLETED, "", "")
            }
        } catch (_: RuntimeStoppedSignal) {
            event("warning", "runtime", "任务已停止")
            updateTerminal(RunStatus.STOPPED, "", "")
        } catch (error: RuntimeFailure) {
            event("error", "runtime", error.message.orEmpty(), errorId = error.errorId)
            updateTerminal(RunStatus.FAILED, error.errorId, error.message.orEmpty())
        } catch (error: Throwable) {
            event("error", "runtime", "Android Runtime 内部错误：${error.message ?: error.javaClass.simpleName}", errorId = "runtime.internal")
            updateTerminal(RunStatus.FAILED, "runtime.internal", error.message ?: error.javaClass.simpleName)
        } finally {
            synchronized(lock) {
                runCatching { nextLog.close() }
                if (eventLog === nextLog) eventLog = null
                if (control === nextControl) control = null
                executor?.shutdown()
                executor = null
            }
            RuntimeForegroundService.stopIfIdle(context)
        }
    }

    private fun checkpoint(functionId: String, instructionId: String) = synchronized(lock) {
        current = current.copy(
            currentFunctionId = functionId,
            currentInstructionId = instructionId,
            updatedAt = Instant.now().toString(),
        )
        publishState(persist = false)
    }

    private fun updateStatus(status: RunStatus) = synchronized(lock) {
        current = current.copy(status = status, updatedAt = Instant.now().toString())
        publishState(persist = true)
    }

    private fun updateTerminal(status: RunStatus, errorId: String, message: String) = synchronized(lock) {
        current = current.copy(
            status = status,
            errorId = errorId,
            errorMessage = message,
            updatedAt = Instant.now().toString(),
        )
        publishState(persist = true)
    }

    private fun event(
        level: String,
        category: String,
        message: String,
        instructionId: String = current.currentInstructionId,
        errorId: String = "",
    ) = synchronized(lock) {
        val item = RuntimeEvent(
            sequence = ++sequence,
            timestamp = Instant.now().toString(),
            level = level,
            category = category,
            message = message,
            runId = current.runId,
            functionId = current.currentFunctionId,
            instructionId = instructionId,
            errorId = errorId,
        )
        current = current.copy(sequence = item.sequence, updatedAt = item.timestamp)
        eventLog?.append(item)
        observers.forEach { runCatching { it.event(item) } }
        observers.forEach { runCatching { it.stateChanged(current) } }
    }

    private fun publishState(persist: Boolean) {
        if (persist) persistState(current)
        observers.forEach { runCatching { it.stateChanged(current) } }
    }

    private fun persistState(state: RunState) {
        val value = JsonObject().apply {
            addProperty("schema_version", 1)
            addProperty("run_id", state.runId)
            addProperty("status", state.status.name.lowercase())
            addProperty("product_id", state.productId)
            addProperty("release_id", state.releaseId)
            addProperty("profile_id", state.profileId)
            addProperty("profile_revision", state.profileRevision)
            addProperty("entry_function_id", state.entryFunctionId)
            addProperty("current_function_id", state.currentFunctionId)
            addProperty("current_instruction_id", state.currentInstructionId)
            addProperty("target_id", state.targetId)
            addProperty("sequence", state.sequence)
            addProperty("started_at", state.startedAt)
            addProperty("updated_at", state.updatedAt)
            addProperty("error_id", state.errorId)
            addProperty("error_message", state.errorMessage)
            addProperty("event_log_path", state.eventLogPath)
        }
        AtomicFiles.write(File(context.filesDir, "runtime-state/current.json"), JsonSupport.canonicalBytes(value))
    }
}
