package com.easycode.player.recording

import android.content.Context
import android.graphics.Bitmap
import android.os.StatFs
import com.easycode.player.util.Base64Codec
import com.easycode.player.bundle.VerifiedBundle
import com.easycode.player.capture.ScreenCaptureService
import com.easycode.player.profile.PlayerProfile
import com.easycode.player.runtime.RunState
import com.easycode.player.runtime.RunStatus
import com.easycode.player.runtime.RuntimeEvent
import com.easycode.player.runtime.RuntimeObserver
import com.easycode.player.util.AtomicFiles
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.bool
import com.easycode.player.util.JsonSupport.long
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonNull
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import java.util.UUID
import java.security.MessageDigest
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlin.math.abs

/** Android-local lossless frame recorder.
 *
 * Runtime execution owns the lifecycle; recording failures are isolated and
 * never stop the user's task. Every committed PNG is fsynced before its JSONL
 * index entry, allowing incomplete sessions to be diagnosed after a crash.
 */
class AndroidFrameRecorder(private val context: Context) : RuntimeObserver {
    private val lock = Any()
    private var worker: ExecutorService? = null
    private var stopFlag: AtomicBoolean? = null
    private var completionLatch: CountDownLatch? = null
    private var state = emptyState()
    private var sessionDir: File? = null
    private var options = JsonObject()
    private var previousSignature: IntArray? = null
    private var segmentId = ""
    private var segmentWidth = 0
    private var segmentHeight = 0
    private var diagnosticTriggered = false
    private var diagnosticPostRemaining = 0
    private val diagnosticRing = ArrayDeque<File>()

    fun status(): JsonObject = synchronized(lock) {
        state.deepCopy().apply {
            val started = get("started_monotonic_ms")?.asLong ?: 0L
            remove("started_monotonic_ms")
            val elapsed = if (started > 0L) (android.os.SystemClock.elapsedRealtime() - started).coerceAtLeast(0L) else 0L
            addProperty("elapsed_ms", elapsed)
            val frames = long("frame_count")
            addProperty("average_fps", if (elapsed > 0L) frames * 1000.0 / elapsed else 0.0)
        }
    }

    fun start(bundle: VerifiedBundle, profile: PlayerProfile, runId: String): JsonObject {
        val recording = profile.recording
        if (!recording.bool("enabled")) return disabled("profile_disabled", false)
        if (recording.get("confirmed_profile_revision")?.takeUnless { it.isJsonNull }?.asInt != profile.revision) {
            return disabled("profile_revision_not_confirmed", true)
        }
        synchronized(lock) {
            if (state.bool("active")) return status()
            if (!ScreenCaptureService.ready()) return disabled("capture_permission_missing", true)
            val root = productRoot(bundle)
            val minFree = recording.long("min_free_bytes", 536_870_912L)
            if (StatFs(root.absolutePath).availableBytes < minFree) return disabled("disk_protection", true, "磁盘可用空间低于录制保护阈值")
            val now = Instant.now()
            val sessionId = "rec_${SESSION_TIME.format(now)}_${UUID.randomUUID().toString().replace("-", "").take(10)}"
            val output = File(root, sessionId)
            check(output.mkdirs()) { "无法创建 Android 录制目录" }
            File(output, "frames").mkdirs()
            File(output, ".diagnostic-ring").mkdirs()
            options = recording.deepCopy()
            sessionDir = output
            previousSignature = null
            segmentId = ""
            segmentWidth = 0
            segmentHeight = 0
            diagnosticTriggered = false
            diagnosticPostRemaining = 0
            diagnosticRing.clear()
            state = emptyState().apply {
                addProperty("active", true)
                addProperty("status", "starting")
                addProperty("requested_enabled", true)
                addProperty("recording_session_id", sessionId)
                addProperty("session_id", sessionId)
                addProperty("output_dir", output.absolutePath)
                addProperty("strategy", recording.string("strategy", "changed_frames"))
                addProperty("recording_mode", recording.string("strategy", "changed_frames"))
                addProperty("started_at", now.toString())
                addProperty("started_monotonic_ms", android.os.SystemClock.elapsedRealtime())
                addProperty("target_fps", recording.get("target_fps")?.asDouble ?: 15.0)
                addProperty("max_duration_ms", recording.long("max_duration_ms", 1_800_000L))
                addProperty("max_session_bytes", recording.long("max_session_bytes", 2_147_483_648L))
                addProperty("min_free_bytes", minFree)
                addProperty("target_id", profile.targetId)
                addProperty("target_kind", "android_local")
                addProperty("target_title", "Android 本机")
                addProperty("capture_backend", "android_mediaprojection")
                addProperty("run_id", runId)
            }
            writeManifest(bundle, profile, final = false)
            val stop = AtomicBoolean(false)
            stopFlag = stop
            completionLatch = CountDownLatch(1)
            worker = Executors.newSingleThreadExecutor { task -> Thread(task, "easycode-android-recorder").apply { isDaemon = false } }
            worker!!.execute { captureLoop(bundle, profile, stop) }
            return status()
        }
    }

    fun stop(reason: String = "user_stopped"): JsonObject {
        synchronized(lock) {
            if (!state.bool("active")) return status()
            state.addProperty("status", "stopping")
            state.addProperty("stop_reason", normalizeReason(reason))
            stopFlag?.set(true)
            return status()
        }
    }

    /** Read-only history surface used by the compact Android Player UI. */
    fun listSessions(bundle: VerifiedBundle): JsonObject = synchronized(lock) {
        JsonObject().apply {
            add("sessions", JsonArray().apply {
                productRoot(bundle).listFiles()
                    ?.filter { it.isDirectory && it.name.startsWith("rec_") }
                    ?.sortedByDescending(File::lastModified)
                    ?.forEach { directory -> recoverInterrupted(directory)?.let { add(sessionSummary(it)) } }
            })
        }
    }

    fun sessionDetail(bundle: VerifiedBundle, sessionId: String): JsonObject = synchronized(lock) {
        val directory = resolveSession(bundle, sessionId)
        val manifest = recoverInterrupted(directory) ?: error("录制记录缺少 session.json")
        JsonObject().apply {
            add("session", sessionSummary(manifest))
            add("frames", readJsonLines(File(directory, "frames.jsonl")))
            add("segments", readJsonLines(File(directory, "segments.jsonl")))
            add("drops", readJsonLines(File(directory, "drops.jsonl")))
            add("terminal", readObject(File(directory, "terminal.json")) ?: JsonNull.INSTANCE)
        }
    }

    fun frameData(bundle: VerifiedBundle, sessionId: String, sequence: Long): JsonObject = synchronized(lock) {
        require(sequence > 0) { "帧序号必须大于 0" }
        val directory = resolveSession(bundle, sessionId)
        val frame = readJsonLines(File(directory, "frames.jsonl")).firstOrNull {
            it.isJsonObject && it.asJsonObject.long("sequence") == sequence
        }?.asJsonObject ?: error("没有找到第 $sequence 帧")
        val file = File(directory, frame.string("file")).canonicalFile
        require(file.path.startsWith(directory.canonicalPath + File.separator) && file.isFile) { "录制帧路径无效" }
        val bytes = file.readBytes()
        require(JsonSupport.sha256(bytes) == frame.string("sha256")) { "录制帧校验失败" }
        JsonObject().apply {
            add("frame", frame.deepCopy())
            addProperty("mime_type", "image/png")
            addProperty("data_base64", Base64Codec.encode(bytes))
        }
    }

    fun deleteSession(bundle: VerifiedBundle, sessionId: String): JsonObject = synchronized(lock) {
        require(sessionId != state.string("session_id") || !state.bool("active")) { "正在录制的记录不能删除" }
        val directory = resolveSession(bundle, sessionId)
        require(directory.deleteRecursively()) { "无法删除录制记录" }
        JsonObject().apply { addProperty("deleted", true); addProperty("session_id", sessionId) }
    }

    /** Create the privacy-minimal "画面与报告" export. Project logic and secrets are never included. */
    fun createDefaultExport(bundle: VerifiedBundle, sessionId: String): File = synchronized(lock) {
        val directory = resolveSession(bundle, sessionId)
        val manifest = recoverInterrupted(directory) ?: error("录制记录缺少 session.json")
        require(manifest.bool("final")) { "活动录制不能导出" }
        val candidates = directory.walkTopDown().filter { file ->
            file.isFile && !file.relativeTo(directory).invariantSeparatorsPath.startsWith("exports/") &&
                !file.relativeTo(directory).invariantSeparatorsPath.startsWith(".diagnostic-ring/")
        }.toList()
        val total = candidates.sumOf(File::length)
        require(total <= 1_073_741_824L) { "Android 单次导出暂不支持超过 1GB 的录制" }
        val destination = File(context.cacheDir, "$sessionId-画面与报告.zip")
        ZipOutputStream(FileOutputStream(destination)).use { zip ->
            val entries = JsonArray()
            candidates.sortedBy { it.relativeTo(directory).invariantSeparatorsPath }.forEach { source ->
                val relative = source.relativeTo(directory).invariantSeparatorsPath
                val archivePath = "recording/$relative"
                zip.putNextEntry(ZipEntry(archivePath))
                source.inputStream().use { it.copyTo(zip) }
                zip.closeEntry()
                entries.add(JsonObject().apply {
                    addProperty("path", archivePath)
                    addProperty("size", source.length())
                    addProperty("sha256", sha256File(source))
                })
            }
            val privacy = JsonObject().apply {
                addProperty("schema_version", 1)
                addProperty("mode", "default")
                addProperty("display_name", "画面与报告")
                addProperty("recording_session_id", sessionId)
                addProperty("contains_sensitive_frames", true)
                addProperty("contains_program_document", false)
                addProperty("contains_ecir", false)
                addProperty("contains_project_resources", false)
                addProperty("contains_profile_values", false)
                addProperty("contains_secrets", false)
                addProperty("automatic_upload", false)
            }
            zip.putNextEntry(ZipEntry("privacy-manifest.json"))
            val privacyBytes = JsonSupport.canonicalBytes(privacy)
            zip.write(privacyBytes)
            zip.closeEntry()
            entries.add(JsonObject().apply {
                addProperty("path", "privacy-manifest.json")
                addProperty("size", privacyBytes.size)
                addProperty("sha256", JsonSupport.sha256(privacyBytes))
            })
            zip.putNextEntry(ZipEntry("content-manifest.json"))
            zip.write(JsonSupport.canonicalBytes(JsonObject().apply {
                addProperty("schema_version", 1)
                add("entries", entries)
            }))
            zip.closeEntry()
        }
        destination
    }

    override fun stateChanged(state: RunState) {
        if (state.status in setOf(RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.STOPPED)) {
            stop(if (state.status == RunStatus.COMPLETED) "completed" else if (state.status == RunStatus.STOPPED) "user_cancelled" else "task_failed")
            // A terminal runtime response must not be published while its
            // recording still looks active.  Finalization runs on the
            // recorder worker so it can finish the current complete frame,
            // seal indexes and write terminal.json without truncation.
            synchronized(lock) { completionLatch }?.await(FINALIZE_WAIT_SECONDS, TimeUnit.SECONDS)
        }
    }

    override fun event(event: RuntimeEvent) {
        if (event.level.equals("error", ignoreCase = true)) synchronized(lock) {
            if (state.bool("active") && options.string("strategy") == "diagnostic") {
                diagnosticTriggered = true
                diagnosticPostRemaining = 20
            }
        }
    }

    private fun captureLoop(bundle: VerifiedBundle, profile: PlayerProfile, stop: AtomicBoolean) {
        var terminalReason = "completed"
        var terminalError = ""
        var consecutiveErrors = 0
        try {
            while (!stop.get()) {
                val loopStarted = android.os.SystemClock.elapsedRealtime()
                val elapsed = loopStarted - synchronized(lock) { state.long("started_monotonic_ms") }
                if (elapsed >= options.long("max_duration_ms", 1_800_000L)) { terminalReason = "duration_reached"; break }
                if (synchronized(lock) { state.long("disk_bytes") } >= options.long("max_session_bytes", 2_147_483_648L)) { terminalReason = "quota_reached"; break }
                val output = requireNotNull(sessionDir)
                if (StatFs(output.absolutePath).availableBytes < options.long("min_free_bytes", 536_870_912L)) { terminalReason = "disk_protection"; break }
                try {
                    val bitmap = ScreenCaptureService.requireReady().captureBitmap()
                    try { processBitmap(bitmap) } finally { bitmap.recycle() }
                    consecutiveErrors = 0
                } catch (error: Exception) {
                    consecutiveErrors += 1
                    terminalError = error.message ?: error.javaClass.simpleName
                    if (consecutiveErrors >= 5) { terminalReason = if (ScreenCaptureService.ready()) "driver_failed" else "permission_revoked"; break }
                }
                val fps = options.get("target_fps")?.asDouble?.coerceIn(0.2, 60.0) ?: 15.0
                val delay = (1000.0 / fps).toLong() - (android.os.SystemClock.elapsedRealtime() - loopStarted)
                if (delay > 0) Thread.sleep(delay)
            }
            synchronized(lock) { state.string("stop_reason").takeIf(String::isNotBlank)?.let { terminalReason = it } }
        } catch (error: Throwable) {
            terminalReason = "driver_failed"
            terminalError = error.message ?: error.javaClass.simpleName
        } finally {
            finish(bundle, profile, terminalReason, terminalError)
        }
    }

    private fun processBitmap(bitmap: Bitmap) {
        val capturedAt = Instant.now().toString()
        val captureSequence = synchronized(lock) {
            val next = state.long("capture_count") + 1
            state.addProperty("capture_count", next)
            state.addProperty("last_capture_at", capturedAt)
            next
        }
        ensureSegment(bitmap.width, bitmap.height, captureSequence, capturedAt)
        val signatureBitmap = Bitmap.createScaledBitmap(bitmap, 64, 36, true)
        val signature = IntArray(64 * 36)
        signatureBitmap.getPixels(signature, 0, 64, 0, 0, 64, 36)
        signatureBitmap.recycle()
        val previous = previousSignature
        previousSignature = signature
        var difference = 1.0
        if (previous != null) {
            var sum = 0L
            for (index in signature.indices) {
                val a = signature[index]; val b = previous[index]
                sum += abs(((a shr 16) and 255) - ((b shr 16) and 255))
                sum += abs(((a shr 8) and 255) - ((b shr 8) and 255))
                sum += abs((a and 255) - (b and 255))
            }
            difference = sum.toDouble() / (signature.size * 3.0 * 255.0)
        }
        val strategy = options.string("strategy", "changed_frames")
        when (strategy) {
            "all_frames" -> commitBitmap(bitmap, captureSequence, capturedAt, difference)
            "diagnostic" -> processDiagnostic(bitmap, captureSequence, capturedAt, difference)
            else -> if (previous == null || difference >= 0.006) {
                commitBitmap(bitmap, captureSequence, capturedAt, difference)
            } else synchronized(lock) {
                state.addProperty("policy_skipped_frame_count", state.long("policy_skipped_frame_count") + 1)
                appendJsonLine(File(requireNotNull(sessionDir), "drops.jsonl"), JsonObject().apply {
                    addProperty("recording_format", 3)
                    addProperty("drop_id", "drop_${UUID.randomUUID().toString().replace("-", "")}")
                    addProperty("recording_session_id", state.string("session_id"))
                    addProperty("recording_segment_id", segmentId)
                    addProperty("kind", "policy_filtered")
                    addProperty("reason", "recording_policy")
                    addProperty("start_capture_sequence", captureSequence)
                    addProperty("end_capture_sequence", captureSequence)
                    addProperty("started_at", capturedAt)
                    addProperty("ended_at", capturedAt)
                    addProperty("count", 1)
                })
                state.addProperty("drop_event_count", state.long("drop_event_count") + 1)
            }
        }
    }

    private fun processDiagnostic(bitmap: Bitmap, captureSequence: Long, capturedAt: String, difference: Double) {
        if (previousSignature == null || synchronized(lock) { state.long("frame_count") } == 0L) {
            commitBitmap(bitmap, captureSequence, capturedAt, difference)
            return
        }
        val triggered = synchronized(lock) { diagnosticTriggered }
        if (triggered) {
            flushDiagnosticRing()
            commitBitmap(bitmap, captureSequence, capturedAt, difference)
            synchronized(lock) {
                diagnosticPostRemaining -= 1
                if (diagnosticPostRemaining <= 0) diagnosticTriggered = false
            }
            return
        }
        val bytes = pngBytes(bitmap)
        val ringDir = File(requireNotNull(sessionDir), ".diagnostic-ring")
        val file = File(ringDir, String.format(Locale.ROOT, "capture-%09d.png", captureSequence))
        AtomicFiles.write(file, bytes)
        synchronized(lock) {
            diagnosticRing.addLast(file)
            while (diagnosticRing.size > 45) diagnosticRing.removeFirst().delete()
        }
    }

    private fun flushDiagnosticRing() {
        val pending = synchronized(lock) { diagnosticRing.toList().also { diagnosticRing.clear() } }
        pending.forEach { source ->
            val captureSequence = source.name.substringAfter("capture-").substringBefore('.').toLongOrNull() ?: return@forEach
            val bytes = source.readBytes()
            commitBytes(bytes, captureSequence, Instant.now().toString(), 1.0)
            source.delete()
        }
    }

    private fun commitBitmap(bitmap: Bitmap, captureSequence: Long, capturedAt: String, difference: Double) =
        commitBytes(pngBytes(bitmap), captureSequence, capturedAt, difference)

    private fun pngBytes(bitmap: Bitmap): ByteArray = ByteArrayOutputStream().use { output ->
        check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)) { "Android 画面无法编码为 PNG" }
        output.toByteArray()
    }

    private fun commitBytes(bytes: ByteArray, captureSequence: Long, capturedAt: String, difference: Double) {
        val output = requireNotNull(sessionDir)
        val frameSequence = synchronized(lock) { state.long("frame_count") + 1 }
        val frameId = "frame_${UUID.randomUUID().toString().replace("-", "")}"
        val relative = "frames/${String.format(Locale.ROOT, "%09d", frameSequence)}-$frameId.png"
        val destination = File(output, relative)
        AtomicFiles.write(destination, bytes)
        val record = JsonObject().apply {
            addProperty("recording_format", 3)
            addProperty("frame_id", frameId)
            addProperty("recording_session_id", state.string("session_id"))
            addProperty("recording_segment_id", segmentId)
            addProperty("sequence", frameSequence)
            addProperty("capture_sequence", captureSequence)
            addProperty("captured_at", capturedAt)
            addProperty("file", relative)
            addProperty("sha256", JsonSupport.sha256(bytes))
            addProperty("bytes", bytes.size)
            addProperty("width", segmentWidth)
            addProperty("height", segmentHeight)
            addProperty("orientation", if (segmentWidth >= segmentHeight) "landscape" else "portrait")
            addProperty("dpi", context.resources.displayMetrics.densityDpi)
            addProperty("target_id", state.string("target_id"))
            addProperty("target_kind", "android_local")
            addProperty("target_title", "Android 本机")
            addProperty("space_version", "${state.string("target_id")}:android-local:${segmentWidth}x$segmentHeight")
            add("screen_region", com.google.gson.JsonArray().apply {
                add(0); add(0); add(segmentWidth); add(segmentHeight)
            })
            addProperty("timestamp_ns", System.nanoTime())
            addProperty("change_score", difference)
            addProperty("pixel_encoding", "png_lossless")
        }
        appendJsonLine(File(output, "frames.jsonl"), record)
        synchronized(lock) {
            state.addProperty("frame_count", frameSequence)
            state.addProperty("disk_bytes", state.long("disk_bytes") + bytes.size)
            state.addProperty("last_frame_id", frameId)
            state.addProperty("status", "recording")
        }
    }

    private fun ensureSegment(width: Int, height: Int, captureSequence: Long, capturedAt: String) {
        if (segmentId.isNotBlank() && width == segmentWidth && height == segmentHeight) return
        val output = requireNotNull(sessionDir)
        if (segmentId.isNotBlank()) appendJsonLine(File(output, "segments.jsonl"), JsonObject().apply {
            addProperty("recording_format", 3); addProperty("event", "closed")
            addProperty("recording_session_id", state.string("session_id")); addProperty("recording_segment_id", segmentId)
            addProperty("ended_at", capturedAt); addProperty("end_capture_sequence", captureSequence - 1)
            addProperty("reason", "target_space_changed")
        })
        segmentId = "segment_${UUID.randomUUID().toString().replace("-", "")}"
        segmentWidth = width
        segmentHeight = height
        appendJsonLine(File(output, "segments.jsonl"), JsonObject().apply {
            addProperty("recording_format", 3); addProperty("event", "opened")
            addProperty("recording_session_id", state.string("session_id")); addProperty("recording_segment_id", segmentId)
            addProperty("opened_at", capturedAt); addProperty("start_capture_sequence", captureSequence)
            addProperty("target_id", state.string("target_id")); addProperty("target_kind", "android_local")
            addProperty("orientation", if (width >= height) "landscape" else "portrait")
            addProperty("width", width); addProperty("height", height)
            addProperty("space_version", "${state.string("target_id")}:android-local:${width}x$height")
        })
        synchronized(lock) { state.addProperty("segment_count", state.long("segment_count") + 1) }
    }

    private fun finish(bundle: VerifiedBundle, profile: PlayerProfile, reason: String, error: String) {
        val output = synchronized(lock) { sessionDir } ?: return
        val finalReason = normalizeReason(reason)
        val stoppedAt = Instant.now().toString()
        if (options.string("strategy") == "diagnostic" && (diagnosticTriggered || finalReason == "driver_failed")) {
            runCatching { flushDiagnosticRing() }
        } else {
            synchronized(lock) { diagnosticRing.forEach(File::delete); diagnosticRing.clear() }
        }
        if (segmentId.isNotBlank()) runCatching { appendJsonLine(File(output, "segments.jsonl"), JsonObject().apply {
            addProperty("recording_format", 3); addProperty("event", "closed")
            addProperty("recording_session_id", state.string("session_id")); addProperty("recording_segment_id", segmentId)
            addProperty("ended_at", stoppedAt); addProperty("end_capture_sequence", state.long("capture_count")); addProperty("reason", finalReason)
        }) }
        synchronized(lock) {
            state.addProperty("active", false)
            state.addProperty("status", if (finalReason in setOf("completed", "task_failed")) "completed" else if (finalReason in setOf("user_stopped", "user_cancelled")) "stopped" else "error")
            state.addProperty("terminal_reason", finalReason)
            state.addProperty("stopped_at", stoppedAt)
            state.addProperty("last_error", error)
        }
        val terminal = JsonObject().apply {
            addProperty("recording_format", 3); addProperty("recording_session_id", state.string("session_id"))
            addProperty("status", state.string("status")); addProperty("terminal_reason", finalReason)
            addProperty("stopped_at", stoppedAt); addProperty("last_error", error)
            addProperty("capture_count", state.long("capture_count")); addProperty("frame_count", state.long("frame_count"))
        }
        AtomicFiles.write(File(output, "terminal.json"), JsonSupport.canonicalBytes(terminal))
        writeManifest(bundle, profile, final = true)
        val completed = synchronized(lock) {
            diagnosticRing.forEach(File::delete); diagnosticRing.clear()
            File(output, ".diagnostic-ring").delete()
            stopFlag = null
            worker?.shutdown(); worker = null
            sessionDir = null
            completionLatch.also { completionLatch = null }
        }
        completed?.countDown()
    }

    private fun writeManifest(bundle: VerifiedBundle, profile: PlayerProfile, final: Boolean) {
        val output = requireNotNull(sessionDir)
        val indexes = JsonObject()
        if (final) for (name in listOf("frames.jsonl", "segments.jsonl", "markers.jsonl", "drops.jsonl", "terminal.json")) {
            val file = File(output, name)
            if (file.isFile) indexes.add(name, JsonObject().apply {
                addProperty("sha256", JsonSupport.sha256(file.readBytes())); addProperty("bytes", file.length())
            })
        }
        val manifest = JsonObject().apply {
            addProperty("recording_format", 3); addProperty("recording_session_id", state.string("session_id")); addProperty("session_id", state.string("session_id"))
            addProperty("project_id", bundle.productId); addProperty("project_name", bundle.title); addProperty("run_id", state.string("run_id")); addProperty("instance_id", "android_local")
            addProperty("started_at", state.string("started_at")); addProperty("stopped_at", state.string("stopped_at")); addProperty("status", state.string("status")); addProperty("terminal_reason", state.string("terminal_reason"))
            addProperty("strategy", state.string("strategy")); addProperty("target_id", profile.targetId); addProperty("target_kind", "android_local"); addProperty("target_title", "Android 本机")
            addProperty("capture_backend", "android_mediaprojection"); add("options", options.deepCopy()); addProperty("lossless_pixel_encoding", "png")
            addProperty("retention_policy", "explicit_user_delete_only"); addProperty("local_only", true)
            addProperty("capture_count", state.long("capture_count")); addProperty("frame_count", state.long("frame_count")); addProperty("segment_count", state.long("segment_count")); addProperty("marker_count", state.long("marker_count")); addProperty("drop_event_count", state.long("drop_event_count")); addProperty("dropped_frame_count", state.long("dropped_frame_count")); addProperty("policy_skipped_frame_count", state.long("policy_skipped_frame_count")); addProperty("disk_bytes", state.long("disk_bytes"))
            add("indexes", indexes); addProperty("content_digest", if (final) JsonSupport.sha256(JsonSupport.canonicalBytes(indexes)) else ""); addProperty("final", final)
        }
        AtomicFiles.write(File(output, "session.json"), JsonSupport.canonicalBytes(manifest))
    }

    private fun appendJsonLine(file: File, value: JsonObject) {
        file.parentFile?.mkdirs()
        FileOutputStream(file, true).use { stream ->
            stream.write(JsonSupport.canonicalBytes(value)); stream.write('\n'.code); stream.fd.sync()
        }
    }

    private fun productRoot(bundle: VerifiedBundle): File =
        File(context.filesDir, "recordings/${JsonSupport.sha256(bundle.productId.toByteArray())}").apply { mkdirs() }

    private fun sha256File(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun resolveSession(bundle: VerifiedBundle, sessionId: String): File {
        require(sessionId.matches(Regex("rec_[A-Za-z0-9_]+"))) { "录制编号无效" }
        val root = productRoot(bundle).canonicalFile
        val directory = File(root, sessionId).canonicalFile
        require(directory.parentFile == root && directory.isDirectory) { "录制记录不存在" }
        return directory
    }

    private fun readObject(file: File): JsonObject? = runCatching {
        if (!file.isFile) null else JsonParser.parseString(file.readText(Charsets.UTF_8)).asJsonObject
    }.getOrNull()

    private fun readJsonLines(file: File): JsonArray = JsonArray().apply {
        if (!file.isFile) return@apply
        file.useLines(Charsets.UTF_8) { lines ->
            lines.filter(String::isNotBlank).forEach { raw ->
                runCatching { JsonParser.parseString(raw) }.getOrNull()?.let(::add)
            }
        }
    }

    /** Seal evidence left by a dead process; never resumes the old task or recorder. */
    private fun recoverInterrupted(directory: File): JsonObject? {
        val manifestFile = File(directory, "session.json")
        val manifest = readObject(manifestFile) ?: return null
        if (manifest.bool("final") || (state.bool("active") && directory.name == state.string("session_id"))) return manifest
        val recoveredAt = Instant.now().toString()
        val frames = readJsonLines(File(directory, "frames.jsonl"))
        val segments = readJsonLines(File(directory, "segments.jsonl"))
        val terminal = JsonObject().apply {
            addProperty("recording_format", 3)
            addProperty("recording_session_id", directory.name)
            addProperty("status", "error")
            addProperty("terminal_reason", "process_interrupted")
            addProperty("stopped_at", recoveredAt)
            addProperty("recovered_at", recoveredAt)
            addProperty("last_error", "上次录制进程未写入正常终态；未自动恢复录制")
            addProperty("capture_count", frames.filter(JsonElement::isJsonObject).maxOfOrNull { it.asJsonObject.long("capture_sequence") } ?: manifest.long("capture_count"))
            addProperty("frame_count", frames.count(JsonElement::isJsonObject))
        }
        AtomicFiles.write(File(directory, "terminal.json"), JsonSupport.canonicalBytes(terminal))
        val indexes = JsonObject()
        for (name in listOf("frames.jsonl", "segments.jsonl", "markers.jsonl", "drops.jsonl", "terminal.json")) {
            val file = File(directory, name)
            if (file.isFile) indexes.add(name, JsonObject().apply {
                addProperty("sha256", JsonSupport.sha256(file.readBytes()))
                addProperty("bytes", file.length())
            })
        }
        manifest.addProperty("status", "error")
        manifest.addProperty("terminal_reason", "process_interrupted")
        manifest.addProperty("stopped_at", recoveredAt)
        manifest.addProperty("last_error", terminal.string("last_error"))
        manifest.addProperty("capture_count", terminal.long("capture_count"))
        manifest.addProperty("frame_count", frames.count(JsonElement::isJsonObject))
        manifest.addProperty("segment_count", segments.count { item -> item.isJsonObject && item.asJsonObject.string("event") == "opened" })
        manifest.add("indexes", indexes)
        manifest.addProperty("content_digest", JsonSupport.sha256(JsonSupport.canonicalBytes(indexes)))
        manifest.addProperty("final", true)
        manifest.addProperty("recovered", true)
        AtomicFiles.write(manifestFile, JsonSupport.canonicalBytes(manifest))
        return manifest
    }

    private fun sessionSummary(manifest: JsonObject): JsonObject = JsonObject().apply {
        listOf(
            "session_id", "recording_session_id", "project_name", "run_id", "started_at", "stopped_at",
            "status", "terminal_reason", "strategy", "target_title", "capture_backend", "content_digest",
        ).forEach { key -> manifest.get(key)?.let { add(key, it.deepCopy()) } }
        listOf("capture_count", "frame_count", "segment_count", "drop_event_count", "dropped_frame_count", "disk_bytes")
            .forEach { key -> manifest.get(key)?.let { add(key, it.deepCopy()) } }
        addProperty("final", manifest.bool("final"))
    }

    private fun disabled(reason: String, requested: Boolean, error: String = ""): JsonObject = synchronized(lock) {
        state = emptyState().apply { addProperty("requested_enabled", requested); addProperty("status", if (error.isBlank()) "disabled" else "error"); addProperty("reason", reason); addProperty("terminal_reason", reason); addProperty("last_error", error) }
        status()
    }

    private fun normalizeReason(reason: String): String = reason.takeIf { it in TERMINAL_REASONS } ?: "driver_failed"

    private fun emptyState(): JsonObject = JsonObject().apply {
        addProperty("active", false); addProperty("status", "idle"); addProperty("requested_enabled", false)
        addProperty("recording_format", 3); addProperty("recording_session_id", ""); addProperty("session_id", ""); addProperty("output_dir", "")
        addProperty("strategy", "changed_frames"); addProperty("recording_mode", "changed_frames"); addProperty("started_at", ""); addProperty("stopped_at", "")
        addProperty("terminal_reason", ""); addProperty("stop_reason", ""); addProperty("reason", ""); addProperty("last_error", "")
        addProperty("frame_count", 0); addProperty("capture_count", 0); addProperty("segment_count", 0); addProperty("marker_count", 0)
        addProperty("drop_event_count", 0); addProperty("dropped_frame_count", 0); addProperty("policy_skipped_frame_count", 0); addProperty("disk_bytes", 0)
        addProperty("queue_depth", 0); addProperty("queue_capacity", 0); addProperty("target_fps", 0.0); addProperty("change_threshold", 0.006)
        addProperty("max_duration_ms", 0); addProperty("max_session_bytes", 0); addProperty("min_free_bytes", 0)
        addProperty("target_id", ""); addProperty("target_kind", ""); addProperty("target_title", ""); addProperty("capture_backend", "")
        addProperty("last_frame_id", ""); addProperty("last_capture_at", ""); addProperty("last_write_lag_ms", 0.0); addProperty("owned_by_current_workspace", true)
        add("confirmed_profile_revision", JsonNull.INSTANCE)
    }

    companion object {
        private const val FINALIZE_WAIT_SECONDS = 15L
        private val SESSION_TIME = DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss_SSSSSS").withZone(ZoneId.systemDefault())
        private val TERMINAL_REASONS = setOf("completed", "task_failed", "user_stopped", "user_cancelled", "disk_protection", "permission_revoked", "driver_failed", "quota_reached", "duration_reached")
    }
}
