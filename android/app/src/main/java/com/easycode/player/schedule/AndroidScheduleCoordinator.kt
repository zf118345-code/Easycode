package com.easycode.player.schedule

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import com.easycode.player.EasyCodeApplication
import com.easycode.player.bundle.VerifiedBundle
import com.easycode.player.capture.ScreenCaptureService
import com.easycode.player.input.EasyCodeAccessibilityService
import com.easycode.player.lan.LanException
import com.easycode.player.runtime.RunState
import com.easycode.player.runtime.RunStatus
import com.easycode.player.runtime.RuntimeEvent
import com.easycode.player.runtime.RuntimeObserver
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.bool
import com.easycode.player.util.JsonSupport.long
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import java.time.Duration
import java.time.Instant
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class AndroidScheduleCoordinator(private val app: EasyCodeApplication) : RuntimeObserver {
    private val worker = Executors.newSingleThreadExecutor { task -> Thread(task, "easycode-android-schedule").apply { isDaemon = false } }
    private val store = AndroidScheduleStore(app, app.profiles)
    private val lock = Any()
    private var activeOccurrenceId = ""
    private var activeScheduleId = ""
    private var activeRemoteDispatchId = ""

    init {
        app.runtime.observe(this)
        app.lan.registerHandler("dispatch.start", ::acceptRemoteDispatch)
        app.lan.registerHandler("dispatch.status", ::remoteDispatchStatus)
        worker.execute {
            runCatching { bundle().also { store.sealInterrupted(it); reconcile(it) } }
        }
    }

    fun list(): JsonObject = store.list(bundle())

    fun save(raw: JsonObject): JsonObject {
        val bundle = bundle()
        val saved = store.save(bundle, raw)
        scheduleAlarm(saved)
        return saved
    }

    fun delete(id: String): JsonObject {
        cancelAlarm(id)
        return store.delete(bundle(), id)
    }

    fun runNow(id: String): JsonObject {
        val schedule = store.list(bundle()).array("schedules").firstOrNull {
            it.isJsonObject && it.asJsonObject.string("schedule_id") == id
        }?.asJsonObject ?: error("运行计划不存在")
        worker.execute { dispatch(bundle(), schedule.deepCopy().apply { addProperty("scheduled_at", Instant.now().toString()) }, "manual") }
        return JsonObject().apply { addProperty("accepted", true); addProperty("schedule_id", id); addProperty("source", "manual") }
    }

    fun alarm(scheduleId: String) {
        // BroadcastReceiver.goAsync() must stay alive until the occurrence has
        // been durably accepted, skipped, or blocked. Waiting on the serialized
        // scheduler worker avoids both an early receiver finish and concurrent
        // schedule-store writes.
        worker.submit task@{
            val bundle = runCatching { bundle() }.getOrNull() ?: return@task
            val due = store.due(bundle, scheduleId, Instant.now()) ?: return@task
            scheduleAlarm(due)
            dispatch(bundle, due, "system")
        }.get(25, TimeUnit.SECONDS)
    }

    private fun dispatch(bundle: VerifiedBundle, schedule: JsonObject, source: String) {
        val discoveredAt = Instant.now()
        val scheduledAt = Instant.parse(schedule.string("scheduled_at", discoveredAt.toString()))
        val occurrenceId = "occurrence_${UUID.randomUUID().toString().replace("-", "")}"
        val dispatchId = "dispatch_${com.easycode.player.util.JsonSupport.sha256("$occurrenceId\u0000${schedule.string("schedule_id")}".toByteArray()).take(32)}"
        val occurrence = JsonObject().apply {
            addProperty("occurrence_id", occurrenceId); addProperty("dispatch_id", dispatchId)
            addProperty("schedule_id", schedule.string("schedule_id")); addProperty("schedule_revision", schedule.get("revision")?.asInt ?: 0)
            addProperty("scheduled_at", scheduledAt.toString()); addProperty("discovered_at", discoveredAt.toString()); addProperty("source", source)
            addProperty("profile_id", schedule.string("profile_id")); addProperty("profile_name", schedule.string("profile_name"))
            addProperty("status", "checking"); addProperty("reason", "")
        }
        val late = Duration.between(scheduledAt, discoveredAt).toMillis().coerceAtLeast(0)
        if (source == "system" && late > schedule.long("max_lateness_ms") && schedule.string("misfire_policy") == "skip") {
            occurrence.addProperty("status", "skipped"); occurrence.addProperty("reason", "missed_deadline")
            occurrence.addProperty("finished_at", discoveredAt.toString()); store.appendOccurrence(bundle, occurrence); return
        }
        if (app.runtime.state().active) {
            if (schedule.string("overlap_policy") == "queue_once") {
                store.setPending(bundle, schedule.string("schedule_id"), true)
                occurrence.addProperty("status", "queued"); occurrence.addProperty("reason", "instance_busy_queue_once")
            } else {
                occurrence.addProperty("status", "skipped"); occurrence.addProperty("reason", "instance_busy")
                occurrence.addProperty("finished_at", discoveredAt.toString())
            }
            store.appendOccurrence(bundle, occurrence); return
        }
        val profile = runCatching { app.profiles.reload(bundle, schedule.string("profile_id")) }.getOrElse {
            occurrence.addProperty("status", "blocked"); occurrence.addProperty("reason", "profile_missing")
            occurrence.addProperty("message", it.message); occurrence.addProperty("finished_at", Instant.now().toString())
            store.appendOccurrence(bundle, occurrence); return
        }
        val permission = missingPermission(bundle, profile.recording.bool("enabled"))
        if (permission.isNotBlank()) {
            occurrence.addProperty("status", "blocked"); occurrence.addProperty("reason", permission)
            occurrence.addProperty("finished_at", Instant.now().toString()); store.appendOccurrence(bundle, occurrence); return
        }
        try {
            app.updates.assertTaskStartAllowed()
            val state = app.runtime.start(bundle, profile, app.profiles)
            synchronized(lock) { activeOccurrenceId = occurrenceId; activeScheduleId = schedule.string("schedule_id") }
            occurrence.addProperty("status", "running"); occurrence.addProperty("run_id", state.runId)
            occurrence.addProperty("started_at", state.startedAt); store.appendOccurrence(bundle, occurrence)
            app.recorder.start(bundle, profile, state.runId)
            app.recorder.stateChanged(app.runtime.state())
        } catch (error: Exception) {
            occurrence.addProperty("status", "failed"); occurrence.addProperty("reason", "runtime_rejected")
            occurrence.addProperty("message", error.message); occurrence.addProperty("finished_at", Instant.now().toString())
            store.appendOccurrence(bundle, occurrence)
        }
    }

    override fun stateChanged(state: RunState) {
        if (state.status !in setOf(RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.STOPPED)) return
        val remoteDispatchId = synchronized(lock) {
            activeRemoteDispatchId.also { activeRemoteDispatchId = "" }
        }
        if (remoteDispatchId.isNotBlank()) {
            worker.execute {
                val bundle = runCatching { bundle() }.getOrNull() ?: return@execute
                store.updateRemoteDispatch(bundle, remoteDispatchId, JsonObject().apply {
                    addProperty("status", when (state.status) {
                        RunStatus.COMPLETED -> "completed"
                        RunStatus.STOPPED -> "stopped"
                        else -> "failed"
                    })
                    addProperty("error_id", state.errorId)
                    addProperty("error_message", state.errorMessage)
                    addProperty("finished_at", state.updatedAt)
                })
            }
        }
        val ids = synchronized(lock) {
            if (activeOccurrenceId.isBlank()) return
            (activeOccurrenceId to activeScheduleId).also { activeOccurrenceId = ""; activeScheduleId = "" }
        }
        worker.execute {
            val bundle = runCatching { bundle() }.getOrNull() ?: return@execute
            store.updateOccurrence(bundle, ids.first, JsonObject().apply {
                addProperty("status", when (state.status) { RunStatus.COMPLETED -> "completed"; RunStatus.STOPPED -> "stopped"; else -> "failed" })
                addProperty("reason", state.errorId); addProperty("message", state.errorMessage); addProperty("finished_at", state.updatedAt)
            })
            val pending = store.list(bundle).array("schedules").firstOrNull {
                it.isJsonObject && it.asJsonObject.string("schedule_id") == ids.second && it.asJsonObject.bool("pending_once")
            }?.asJsonObject
            if (pending != null) {
                store.setPending(bundle, ids.second, false)
                dispatch(bundle, pending.deepCopy().apply { addProperty("scheduled_at", Instant.now().toString()) }, "queued")
            }
        }
    }

    override fun event(event: RuntimeEvent) = Unit

    private fun acceptRemoteDispatch(_peer: JsonObject, payload: JsonObject): JsonObject = synchronized(lock) {
        val request = normalizedRemoteRequest(payload)
        val bundle = bundle()
        if (request.string("host_id") != app.lan.identity.hostId) {
            throw LanException("远程启动命令不是发给当前设备", "schedule.reference_unknown")
        }
        if (request.string("product_id") != bundle.productId) {
            throw LanException("远程启动产品不是当前 APK", "schedule.reference_unknown")
        }
        val instance = app.messages.instance(bundle)
        if (request.string("instance_id") != instance.string("instance_id")) {
            throw LanException("远程启动实例不是当前 APK 实例", "schedule.reference_unknown")
        }
        // An ACK-loss retry for an already admitted dispatch must return the
        // original run before the general busy check.  Otherwise the running
        // task would make its own retry look like an unrelated competing run.
        runCatching { store.remoteDispatch(bundle, request.string("dispatch_id")) }
            .getOrNull()
            ?.let {
                val verified = runCatching { store.admitRemoteDispatch(bundle, request) }
                    .getOrElse { error -> throw LanException(error.message ?: "远程派发身份冲突", "schedule.dispatch_identity_conflict", cause = error) }
                return@synchronized remoteAcceptance(verified.record)
            }
        val profile = runCatching { app.profiles.reload(bundle, request.string("profile_id")) }
            .getOrElse { throw LanException("远程启动方案不存在或需要检查", "schedule.profile_not_found", action = "choose_profile", cause = it) }
        val missing = missingPermission(bundle, profile.recording.bool("enabled"))
        if (missing.isNotBlank()) {
            throw LanException("远程启动缺少本机运行权限：$missing", "schedule.$missing", action = "open_player_permissions")
        }
        if (app.runtime.state().active) {
            throw LanException("当前实例已有任务正在运行或暂停", "schedule.instance_busy", transient = true, action = "retry_later")
        }
        val admission = runCatching { store.admitRemoteDispatch(bundle, request) }
            .getOrElse { throw LanException(it.message ?: "远程派发身份冲突", "schedule.dispatch_identity_conflict", cause = it) }
        if (!admission.created) return@synchronized remoteAcceptance(admission.record)
        val dispatchId = request.string("dispatch_id")
        val runId = admission.record.string("run_id")
        activeRemoteDispatchId = dispatchId
        try {
            app.updates.assertTaskStartAllowed()
            val state = app.runtime.start(
                bundle,
                profile,
                app.profiles,
                requestedRunId = runId,
            )
            store.updateRemoteDispatch(bundle, dispatchId, JsonObject().apply {
                addProperty("status", "running")
                addProperty("started_at", state.startedAt)
            })
            app.recorder.start(bundle, profile, state.runId)
            app.recorder.stateChanged(app.runtime.state())
            remoteAcceptance(store.remoteDispatch(bundle, dispatchId))
        } catch (error: Exception) {
            activeRemoteDispatchId = ""
            store.updateRemoteDispatch(bundle, dispatchId, JsonObject().apply {
                addProperty("status", "failed")
                addProperty("error_id", (error as? com.easycode.player.runtime.RuntimeFailure)?.errorId ?: "schedule.execution_start_failed")
                addProperty("error_message", error.message ?: "远程任务启动失败")
                addProperty("finished_at", Instant.now().toString())
            })
            throw LanException(error.message ?: "远程任务启动失败", "schedule.execution_start_failed", cause = error)
        }
    }

    private fun remoteDispatchStatus(_peer: JsonObject, payload: JsonObject): JsonObject {
        val dispatchId = stableId(payload.string("dispatch_id"), "派发编号")
        return runCatching { store.remoteDispatch(bundle(), dispatchId) }
            .getOrElse { throw LanException("远程派发记录不存在", "schedule.dispatch_unknown", cause = it) }
    }

    private fun normalizedRemoteRequest(payload: JsonObject): JsonObject {
        val revision = payload.get("schedule_revision")?.takeUnless { it.isJsonNull }?.asInt ?: 0
        if (revision < 1) throw LanException("计划修订号无效", "schedule.reference_invalid")
        return JsonObject().apply {
            addProperty("dispatch_id", stableId(payload.string("dispatch_id"), "派发编号"))
            addProperty("occurrence_id", stableId(payload.string("occurrence_id"), "发生编号"))
            addProperty("schedule_id", stableId(payload.string("schedule_id"), "计划编号"))
            addProperty("schedule_revision", revision)
            addProperty("entry_id", stableId(payload.string("entry_id"), "条目编号"))
            addProperty("host_id", stableId(payload.string("host_id"), "主机编号"))
            addProperty("instance_id", stableId(payload.string("instance_id"), "实例编号"))
            addProperty("product_id", stableId(payload.string("product_id"), "产品编号"))
            addProperty("profile_id", stableId(payload.string("profile_id"), "方案编号"))
        }
    }

    private fun stableId(value: String, label: String): String = value.trim().takeIf {
        it.matches(Regex("[A-Za-z0-9][A-Za-z0-9_.-]{0,127}"))
    } ?: throw LanException("$label 无效", "schedule.identity_invalid")

    private fun remoteAcceptance(record: JsonObject) = JsonObject().apply {
        addProperty("dispatch_id", record.string("dispatch_id"))
        addProperty("run_id", record.string("run_id"))
        addProperty("status", record.string("status"))
        addProperty("error_id", record.string("error_id"))
        addProperty("error_message", record.string("error_message"))
    }

    private fun missingPermission(bundle: VerifiedBundle, recording: Boolean): String {
        if ((recording || containsOpcode(bundle, CAPTURE_OPS)) && !ScreenCaptureService.ready()) return "capture_permission_missing"
        if (containsOpcode(bundle, INPUT_OPS) && !EasyCodeAccessibilityService.connected()) return "accessibility_permission_missing"
        if (containsOpcode(bundle, setOf("directory.delete_tree"))) return "interactive_confirmation_required"
        return ""
    }

    private fun containsOpcode(bundle: VerifiedBundle, wanted: Set<String>): Boolean {
        fun visit(value: JsonElement): Boolean {
            if (value.isJsonArray) return value.asJsonArray.any(::visit)
            if (!value.isJsonObject) return false
            return value.asJsonObject.string("opcode") in wanted || value.asJsonObject.entrySet().any { visit(it.value) }
        }
        return visit(bundle.ecir.array("functions"))
    }

    private fun reconcile(bundle: VerifiedBundle) {
        store.list(bundle).array("schedules").forEach { raw -> if (raw.isJsonObject) scheduleAlarm(raw.asJsonObject) }
    }

    private fun scheduleAlarm(schedule: JsonObject) {
        cancelAlarm(schedule.string("schedule_id"))
        if (!schedule.bool("enabled")) return
        val at = runCatching { Instant.parse(schedule.string("next_trigger_at")) }.getOrNull() ?: return
        val alarm = app.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val operation = pendingIntent(schedule.string("schedule_id"))
        if (Build.VERSION.SDK_INT >= 23) {
            alarm.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at.toEpochMilli(), operation)
        } else {
            alarm.setExact(AlarmManager.RTC_WAKEUP, at.toEpochMilli(), operation)
        }
    }

    private fun cancelAlarm(id: String) {
        val alarm = app.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        alarm.cancel(pendingIntent(id))
    }

    private fun pendingIntent(id: String): PendingIntent = PendingIntent.getBroadcast(
        app, id.hashCode(), Intent(app, ScheduleAlarmReceiver::class.java).apply {
            action = ACTION_ALARM; data = Uri.parse("easycode://schedule/$id"); putExtra("schedule_id", id)
        }, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
    )

    private fun bundle(): VerifiedBundle {
        val result = app.packages.bootstrap(importInbox = false)
        if (!result.available) error(result.reason.ifBlank { "没有可用的签名 Player 内容" })
        return app.packages.openActive()
    }

    companion object {
        const val ACTION_ALARM = "com.easycode.player.action.SCHEDULE_ALARM"
        private val CAPTURE_OPS = setOf("target.capture_frame", "frame.save", "color.read", "color.find", "vision.find", "vision.find_all", "standard.image.wait_visible", "standard.image.wait_hidden", "standard.image.click_once", "standard.image.click_until_hidden", "standard.image.click_position_until_visible", "standard.image.click_position_until_hidden")
        private val INPUT_OPS = setOf(
            "input.click", "input.text", "input.scroll", "input.drag", "input.key",
            "control.find", "control.click", "control.read_text", "control.input_text",
            "control.read_status", "control.focus", "control.set_value", "control.select",
            "control.toggle", "control.scroll_into_view",
            "standard.control.wait_visible", "standard.control.wait_hidden",
            "standard.image.click_once", "standard.image.click_until_hidden",
            "standard.image.click_position_until_visible", "standard.image.click_position_until_hidden",
        )
    }
}
