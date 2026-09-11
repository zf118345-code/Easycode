package com.easycode.player.schedule

import android.content.Context
import com.easycode.player.bundle.VerifiedBundle
import com.easycode.player.profile.ProfileStore
import com.easycode.player.util.AtomicFiles
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.bool
import com.easycode.player.util.JsonSupport.long
import com.easycode.player.util.JsonSupport.obj
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import java.io.File
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.util.UUID

class AndroidScheduleStore(private val context: Context, private val profiles: ProfileStore) {
    private val lock = Any()

    fun list(bundle: VerifiedBundle): JsonObject = synchronized(lock) { document(bundle).deepCopy() }

    fun save(bundle: VerifiedBundle, raw: JsonObject): JsonObject = synchronized(lock) {
        val document = document(bundle)
        val id = raw.string("schedule_id").ifBlank { "schedule_${UUID.randomUUID().toString().replace("-", "")}" }
        require(id.matches(Regex("schedule_[A-Za-z0-9_]+"))) { "计划编号无效" }
        val existing = document.array("schedules").mapNotNull { if (it.isJsonObject && it.asJsonObject.string("schedule_id") == id) it.asJsonObject else null }.singleOrNull()
        val expected = raw.get("expected_revision")?.takeUnless { it.isJsonNull }?.asInt
        if (existing != null && expected != existing.get("revision")?.asInt) error("计划 revision 已过期，请重新载入")
        if (existing == null && expected != null) error("新计划不能指定 revision")
        val now = Instant.now()
        val profileId = raw.string("profile_id")
        val profile = profiles.reload(bundle, profileId)
        val trigger = normalizeTrigger(raw.obj("trigger"), now)
        val next = if (raw.bool("enabled", true)) nextScheduleTrigger(trigger, now.minusMillis(1)) else null
        val value = JsonObject().apply {
            addProperty("schedule_id", id)
            addProperty("revision", (existing?.get("revision")?.asInt ?: 0) + 1)
            addProperty("name", raw.string("name").trim().ifBlank { "运行计划" }.take(80))
            addProperty("enabled", raw.bool("enabled", true))
            addProperty("profile_id", profile.profileId)
            addProperty("profile_name", profile.name)
            addProperty("profile_revision_at_save", profile.revision)
            add("trigger", trigger)
            addProperty("misfire_policy", raw.string("misfire_policy", "run_once").also { require(it in setOf("skip", "run_once")) })
            addProperty("max_lateness_ms", raw.long("max_lateness_ms", 3_600_000L).coerceIn(60_000L, 7 * 86_400_000L))
            addProperty("overlap_policy", raw.string("overlap_policy", "queue_once").also { require(it in setOf("skip", "queue_once")) })
            addProperty("next_trigger_at", next?.toString().orEmpty())
            addProperty("pending_once", false)
            addProperty("created_at", existing?.string("created_at") ?: now.toString())
            addProperty("updated_at", now.toString())
        }
        val schedules = document.array("schedules")
        existing?.let { schedules.remove(it) }
        schedules.add(value)
        write(bundle, document)
        value.deepCopy()
    }

    fun delete(bundle: VerifiedBundle, id: String): JsonObject = synchronized(lock) {
        val document = document(bundle)
        val schedules = document.array("schedules")
        val existing = schedules.firstOrNull { it.isJsonObject && it.asJsonObject.string("schedule_id") == id }
            ?: error("运行计划不存在")
        schedules.remove(existing)
        write(bundle, document)
        JsonObject().apply { addProperty("deleted", true); addProperty("schedule_id", id) }
    }

    fun due(bundle: VerifiedBundle, id: String, discoveredAt: Instant): JsonObject? = synchronized(lock) {
        val document = document(bundle)
        val schedule = document.array("schedules").firstOrNull { it.isJsonObject && it.asJsonObject.string("schedule_id") == id }
            ?.asJsonObject ?: return null
        if (!schedule.bool("enabled")) return null
        val scheduledAt = runCatching { Instant.parse(schedule.string("next_trigger_at")) }.getOrNull() ?: return null
        if (scheduledAt.isAfter(discoveredAt.plusSeconds(2))) return null
        val trigger = schedule.obj("trigger")
        val next = nextScheduleTrigger(trigger, scheduledAt.plusMillis(1))
        if (trigger.string("kind") == "one_time") schedule.addProperty("enabled", false)
        schedule.addProperty("next_trigger_at", next?.toString().orEmpty())
        schedule.addProperty("updated_at", discoveredAt.toString())
        write(bundle, document)
        return schedule.deepCopy().apply { addProperty("scheduled_at", scheduledAt.toString()) }
    }

    fun setPending(bundle: VerifiedBundle, id: String, pending: Boolean) = synchronized(lock) {
        val document = document(bundle)
        document.array("schedules").firstOrNull { it.isJsonObject && it.asJsonObject.string("schedule_id") == id }
            ?.asJsonObject?.addProperty("pending_once", pending)
        write(bundle, document)
    }

    fun appendOccurrence(bundle: VerifiedBundle, value: JsonObject) = synchronized(lock) {
        val document = document(bundle)
        val history = document.array("occurrences")
        history.add(value)
        while (history.size() > 500) history.remove(0)
        write(bundle, document)
    }

    fun updateOccurrence(bundle: VerifiedBundle, occurrenceId: String, update: JsonObject) = synchronized(lock) {
        val document = document(bundle)
        document.array("occurrences").firstOrNull {
            it.isJsonObject && it.asJsonObject.string("occurrence_id") == occurrenceId
        }?.asJsonObject?.let { target -> update.entrySet().forEach { (key, value) -> target.add(key, value.deepCopy()) } }
        write(bundle, document)
    }

    fun admitRemoteDispatch(bundle: VerifiedBundle, request: JsonObject): RemoteDispatchAdmission = synchronized(lock) {
        val document = document(bundle)
        val dispatches = document.array("remote_dispatches")
        val dispatchId = request.string("dispatch_id")
        val fingerprint = remoteDispatchFingerprint(request)
        val existing = dispatches.firstOrNull {
            it.isJsonObject && it.asJsonObject.string("dispatch_id") == dispatchId
        }?.asJsonObject
        if (existing != null) {
            require(existing.string("request_fingerprint") == fingerprint) {
                "同一派发编号的内容发生变化"
            }
            return@synchronized RemoteDispatchAdmission(existing.deepCopy(), false)
        }
        val now = Instant.now().toString()
        val value = JsonObject().apply {
            addProperty("dispatch_id", dispatchId)
            addProperty("occurrence_id", request.string("occurrence_id"))
            addProperty("schedule_id", request.string("schedule_id"))
            addProperty("schedule_revision", request.get("schedule_revision").asInt)
            addProperty("entry_id", request.string("entry_id"))
            addProperty("host_id", request.string("host_id"))
            addProperty("instance_id", request.string("instance_id"))
            addProperty("product_id", request.string("product_id"))
            addProperty("profile_id", request.string("profile_id"))
            addProperty("request_fingerprint", fingerprint)
            addProperty("run_id", remoteDispatchRunId(dispatchId))
            addProperty("status", "admitting")
            addProperty("error_id", "")
            addProperty("error_message", "")
            addProperty("created_at", now)
            addProperty("updated_at", now)
        }
        dispatches.add(value)
        while (dispatches.size() > 500) dispatches.remove(0)
        write(bundle, document)
        RemoteDispatchAdmission(value.deepCopy(), true)
    }

    fun remoteDispatch(bundle: VerifiedBundle, dispatchId: String): JsonObject = synchronized(lock) {
        document(bundle).array("remote_dispatches").firstOrNull {
            it.isJsonObject && it.asJsonObject.string("dispatch_id") == dispatchId
        }?.asJsonObject?.deepCopy() ?: error("远程派发记录不存在")
    }

    fun updateRemoteDispatch(bundle: VerifiedBundle, dispatchId: String, update: JsonObject): JsonObject = synchronized(lock) {
        val document = document(bundle)
        val target = document.array("remote_dispatches").firstOrNull {
            it.isJsonObject && it.asJsonObject.string("dispatch_id") == dispatchId
        }?.asJsonObject ?: error("远程派发记录不存在")
        update.entrySet().forEach { (key, value) -> target.add(key, value.deepCopy()) }
        target.addProperty("updated_at", Instant.now().toString())
        write(bundle, document)
        target.deepCopy()
    }

    fun sealInterrupted(bundle: VerifiedBundle, recoveredAt: Instant = Instant.now()) = synchronized(lock) {
        val document = document(bundle)
        var changed = false
        document.array("occurrences").forEach { raw ->
            if (!raw.isJsonObject) return@forEach
            val item = raw.asJsonObject
            if (item.string("status") in setOf("accepted", "running")) {
                item.addProperty("status", "failed")
                item.addProperty("reason", "process_interrupted")
                item.addProperty("finished_at", recoveredAt.toString())
                changed = true
            }
        }
        document.array("remote_dispatches").forEach { raw ->
            if (!raw.isJsonObject) return@forEach
            val item = raw.asJsonObject
            if (item.string("status") in setOf("admitting", "running")) {
                item.addProperty("status", "failed")
                item.addProperty("error_id", "schedule.process_interrupted")
                item.addProperty("error_message", "Player 进程中断；旧运行现场不会自动恢复")
                item.addProperty("finished_at", recoveredAt.toString())
                item.addProperty("updated_at", recoveredAt.toString())
                changed = true
            }
        }
        if (changed) write(bundle, document)
    }

    private fun normalizeTrigger(raw: JsonObject, now: Instant): JsonObject {
        val kind = raw.string("kind")
        return JsonObject().apply {
            addProperty("kind", kind)
            when (kind) {
                "one_time" -> {
                    val at = Instant.parse(raw.string("at"))
                    require(at.isAfter(now.minusSeconds(5))) { "单次计划时间已经过去" }
                    addProperty("at", at.toString())
                }
                "daily" -> {
                    val time = LocalTime.parse(raw.string("local_time"))
                    val zone = ZoneId.of(raw.string("timezone_id", ZoneId.systemDefault().id))
                    addProperty("local_time", time.toString())
                    addProperty("timezone_id", zone.id)
                }
                "interval" -> {
                    val interval = raw.long("interval_ms")
                    require(interval in 60_000L..(30L * 86_400_000L)) { "固定间隔必须为 1 分钟到 30 天" }
                    addProperty("anchor_time", Instant.parse(raw.string("anchor_time", now.toString())).toString())
                    addProperty("interval_ms", interval)
                }
                else -> error("计划触发类型必须为单次、每日或固定间隔")
            }
        }
    }

    private fun file(bundle: VerifiedBundle) = File(profiles.dataRoot(bundle), "schedules.json")
    private fun document(bundle: VerifiedBundle): JsonObject = (runCatching {
        val file = file(bundle)
        if (file.isFile) JsonSupport.parseObject(file.readBytes(), "Android 运行计划") else null
    }.getOrNull() ?: JsonObject().apply {
        addProperty("schema_version", 1); add("schedules", JsonArray()); add("occurrences", JsonArray())
    }).also {
        if (!it.has("remote_dispatches") || !it.get("remote_dispatches").isJsonArray) {
            it.add("remote_dispatches", JsonArray())
        }
    }
    private fun write(bundle: VerifiedBundle, value: JsonObject) = AtomicFiles.write(file(bundle), JsonSupport.canonicalBytes(value))
}

data class RemoteDispatchAdmission(val record: JsonObject, val created: Boolean)

internal fun remoteDispatchFingerprint(request: JsonObject): String =
    "sha256:" + JsonSupport.sha256(JsonSupport.canonicalBytes(request))

internal fun remoteDispatchRunId(dispatchId: String): String =
    "run_${JsonSupport.sha256("remote-dispatch\u0000$dispatchId".toByteArray()).take(32)}"

fun nextScheduleTrigger(trigger: JsonObject, after: Instant): Instant? = when (trigger.string("kind")) {
    "one_time" -> Instant.parse(trigger.string("at")).takeIf { it.isAfter(after) }
    "daily" -> {
        val zone = ZoneId.of(trigger.string("timezone_id"))
        val localTime = LocalTime.parse(trigger.string("local_time"))
        val localAfter = after.atZone(zone)
        var date = localAfter.toLocalDate()
        var candidate = resolveScheduleLocal(date, localTime, zone)
        if (!candidate.toInstant().isAfter(after)) { date = date.plusDays(1); candidate = resolveScheduleLocal(date, localTime, zone) }
        candidate.toInstant()
    }
    "interval" -> {
        val anchor = Instant.parse(trigger.string("anchor_time"))
        val interval = trigger.long("interval_ms")
        if (anchor.isAfter(after)) anchor else {
            val elapsed = Duration.between(anchor, after).toMillis()
            anchor.plusMillis((elapsed / interval + 1) * interval)
        }
    }
    else -> null
}

private fun resolveScheduleLocal(date: LocalDate, time: LocalTime, zone: ZoneId): ZonedDateTime {
    val local = LocalDateTime.of(date, time)
    val rules = zone.rules
    val offsets = rules.getValidOffsets(local)
    if (offsets.isNotEmpty()) return ZonedDateTime.ofLocal(local, zone, offsets.first())
    val transition = rules.getTransition(local) ?: return local.atZone(zone)
    return transition.dateTimeAfter.atZone(zone)
}
