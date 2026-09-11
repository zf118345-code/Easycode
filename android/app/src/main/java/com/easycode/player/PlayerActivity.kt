package com.easycode.player

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import android.view.Gravity
import android.webkit.MimeTypeMap
import android.webkit.WebView
import android.widget.LinearLayout
import android.widget.TextView
import com.easycode.player.bundle.VerifiedBundle
import com.easycode.player.capture.ScreenCaptureService
import com.easycode.player.file.SafReferences
import com.easycode.player.input.EasyCodeAccessibilityService
import com.easycode.player.lan.LanForegroundService
import com.easycode.player.profile.PlayerControlDestination
import com.easycode.player.profile.PlayerProfile
import com.easycode.player.runtime.DangerousRunConfirmation
import com.easycode.player.runtime.PlayerBindings
import com.easycode.player.runtime.RunState
import com.easycode.player.runtime.RunStatus
import com.easycode.player.runtime.RuntimeEvent
import com.easycode.player.runtime.RuntimeObserver
import com.easycode.player.ui.EasyCodeDialog
import com.easycode.player.util.AtomicFiles
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.bool
import com.easycode.player.util.JsonSupport.obj
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonElement
import com.google.gson.JsonArray
import com.google.gson.JsonNull
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.io.ByteArrayOutputStream
import java.time.Instant
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import com.easycode.player.web.AndroidPlayerWebBridge
import com.easycode.player.web.applySystemFontScale
import com.easycode.player.web.configureOfflinePlayer
import com.easycode.player.web.webViewCompatibility

class PlayerActivity : Activity(), RuntimeObserver {
    private lateinit var bundle: VerifiedBundle
    private lateinit var profile: PlayerProfile
    private lateinit var playerWebView: WebView
    private val webRuntimeEvents = ArrayDeque<RuntimeEvent>()
    private var pendingDestination: PlayerControlDestination? = null
    private var pendingWebFeedback: JsonObject? = null
    private var pendingAccessibilityCapture = false
    private var pendingRecordingExport: java.io.File? = null
    @Volatile private var pendingRuntimePermission: PendingRuntimePermission? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        pendingDestination = savedInstanceState?.getString(STATE_PENDING_DESTINATION)
            ?.takeIf(String::isNotBlank)
            ?.let { raw -> runCatching { PlayerControlDestination.fromJson(JsonParser.parseString(raw).asJsonObject) }.getOrNull() }
        pendingWebFeedback = feedbackFromIntent(intent)
        // The Player is a form, not immersive content.  Keep it inside the
        // system bars so OEM WebViews that report zero CSS safe-area insets
        // cannot place the shared title bar underneath the status bar.
        if (Build.VERSION.SDK_INT >= 30) window.setDecorFitsSystemWindows(true)
        requestNotificationPermission()
        bootstrap()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        pendingDestination?.let {
            outState.putString(STATE_PENDING_DESTINATION, it.toJson().toString())
        }
        super.onSaveInstanceState(outState)
    }

    override fun onResume() {
        super.onResume()
        pendingRuntimePermission
            ?.takeIf { it.kind == "input" && it.leftActivity }
            ?.let { request ->
                awaitAccessibilityConnection { connected ->
                    request.complete(
                        connected,
                        if (connected) "" else "未启用 EasyCode 本机输入服务",
                    )
                }
            }
        if (!pendingAccessibilityCapture) return
        pendingAccessibilityCapture = false
        val destination = pendingDestination ?: return
        awaitAccessibilityConnection { connected ->
            if (connected) {
                beginVisualCapture(destination)
            } else {
                pendingDestination = null
                notifyWebCapture(false, "未启用 EasyCode 控件服务；旧字段值保持不变", destination.controlId)
            }
        }
    }

    override fun onPause() {
        pendingRuntimePermission?.takeIf { it.kind == "input" }?.leftActivity = true
        super.onPause()
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        if (::playerWebView.isInitialized) playerWebView.applySystemFontScale(newConfig.fontScale)
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        setIntent(intent)
        val feedback = feedbackFromIntent(intent)
        if (::bundle.isInitialized) {
            pendingDestination = null
            if (feedback != null) {
                reloadProfileAndNotifyWeb(
                    message = feedback.string("message", "字段采集状态已更新"),
                    ok = feedback.get("ok")?.asBoolean ?: true,
                    controlId = feedback.string("control_id").takeIf(String::isNotBlank),
                )
            }
        } else {
            pendingWebFeedback = feedback
        }
    }

    override fun onStart() {
        super.onStart()
        easyCodeApp.runtime.observe(this)
    }

    override fun onStop() {
        easyCodeApp.runtime.removeObserver(this)
        super.onStop()
    }

    private fun bootstrap() {
        try {
            val result = easyCodeApp.packages.bootstrap(importInbox = true)
            if (!result.available) {
                showFatal(result.reason.ifBlank { "APK 没有可用的已签名 Player 内容包" })
                return
            }
            bundle = easyCodeApp.packages.openActive()
            easyCodeApp.updates.configure(bundle)
            profile = easyCodeApp.profiles.loadOrCreate(bundle)
            if (pendingWebFeedback == null && result.importedFromAdb) {
                queueWebFeedback(true, "已校验并切换到 ADB 传入的签名内容包")
            }
            if (pendingWebFeedback == null && result.rejectedAdbInbox) {
                queueWebFeedback(false, "已拒绝 ADB 内容包并继续使用上一个可信槽：${result.reason}")
            }
            renderWebPlayer()
        } catch (error: Exception) {
            showFatal(error.message ?: "Player 内容包无法打开")
        }
    }

    private fun renderWebPlayer() {
        val candidate = WebView(this)
        val compatibility = webViewCompatibility(
            candidate.settings.userAgentString.orEmpty(),
            BuildConfig.MINIMUM_WEBVIEW_MAJOR,
        )
        if (!compatibility.compatible) {
            candidate.destroy()
            showFatal(
                compatibility.reason +
                    "。请更新 Android System WebView 或系统浏览器后重新打开 Player；项目和运行方案没有被修改。",
                "这是显示内核兼容问题，不是脚本、签名或运行任务失败。",
            )
            return
        }
        playerWebView = candidate.apply {
            configureOfflinePlayer(AndroidPlayerWebBridge(::handleWebRequest))
        }
        setContentView(playerWebView)
    }

    private fun handleWebRequest(method: String, rawUrl: String, body: JsonElement): JsonElement {
        val uri = Uri.parse("https://player.easycode.local$rawUrl")
        val path = uri.path.orEmpty()
        return when {
            method == "GET" && path == "/api/vnext/player/runtime/bootstrap" -> webBootstrap()
            method == "GET" && path == "/api/vnext/player/runtime/profiles" -> JsonObject().apply {
                add("profiles", JsonArray().apply {
                    easyCodeApp.profiles.list(bundle).forEach { add(easyCodeApp.profiles.toJson(it)) }
                })
            }
            method == "PUT" && path == "/api/vnext/player/runtime/profiles" -> saveWebProfile(body.asObject("配置方案"))
            method == "DELETE" && path.startsWith("/api/vnext/player/runtime/profiles/") -> {
                val profileId = Uri.decode(path.substringAfterLast('/'))
                val fallback = easyCodeApp.profiles.delete(bundle, profileId)
                if (fallback != null) profile = fallback
                JsonObject().apply {
                    addProperty("deleted", true)
                    addProperty("profile_id", profileId)
                }
            }
            method == "GET" && path == "/api/vnext/player/runtime/actions" -> webTerminalActions(uri)
            method == "GET" && path == "/api/vnext/player/runtime/preflight" -> webPreflight(uri)
            method == "POST" && path == "/api/vnext/player/runtime/dangerous-operations" -> webDangerousOperations(body.asObject("运行参数"))
            method == "POST" && path == "/api/vnext/player/runtime/run" -> webStartRun(body.asObject("运行参数"))
            method == "GET" && path.startsWith("/api/vnext/runs/") -> webRuntimeSession(easyCodeApp.runtime.state())
            method == "POST" && path.endsWith("/pause") && path.startsWith("/api/vnext/runs/") -> {
                easyCodeApp.runtime.pause()
                webRuntimeSession(easyCodeApp.runtime.state())
            }
            method == "POST" && path.endsWith("/resume") && path.startsWith("/api/vnext/runs/") -> {
                easyCodeApp.runtime.resume()
                webRuntimeSession(easyCodeApp.runtime.state())
            }
            method == "DELETE" && path.startsWith("/api/vnext/runs/") -> {
                easyCodeApp.runtime.stop()
                webRuntimeSession(easyCodeApp.runtime.state())
            }
            method == "POST" && path == "/api/vnext/player/runtime/capture/start" ->
                webStartCapture(body.asObject("字段采集"))
            method == "POST" && path == "/api/vnext/player/runtime/capture/cancel" -> {
                pendingDestination = null
                ScreenCaptureService.cancel(this)
                JsonObject().apply { addProperty("ok", true); addProperty("cancelled", true) }
            }
            method == "GET" && path == "/api/vnext/player/runtime/recording" -> easyCodeApp.recorder.status()
            method == "POST" && path == "/api/vnext/player/runtime/recording/stop" -> easyCodeApp.recorder.stop()
            method == "GET" && path == "/api/vnext/player/runtime/recordings" -> easyCodeApp.recorder.listSessions(bundle)
            method == "GET" && path.matches(Regex("/api/vnext/player/runtime/recordings/[^/]+/frames/[0-9]+")) -> {
                val parts = path.split('/')
                easyCodeApp.recorder.frameData(bundle, Uri.decode(parts[6]), parts[8].toLong())
            }
            method == "GET" && path.matches(Regex("/api/vnext/player/runtime/recordings/[^/]+")) ->
                easyCodeApp.recorder.sessionDetail(bundle, Uri.decode(path.substringAfterLast('/')))
            method == "DELETE" && path.matches(Regex("/api/vnext/player/runtime/recordings/[^/]+")) ->
                easyCodeApp.recorder.deleteSession(bundle, Uri.decode(path.substringAfterLast('/')))
            method == "POST" && path.matches(Regex("/api/vnext/player/runtime/recordings/[^/]+/export")) -> {
                val sessionId = Uri.decode(path.split('/')[6])
                prepareRecordingExport(sessionId)
            }
            method == "GET" && path == "/api/vnext/player/runtime/schedules" -> easyCodeApp.schedules.list()
            method == "PUT" && path == "/api/vnext/player/runtime/schedules" -> easyCodeApp.schedules.save(body.asObject("运行计划"))
            method == "DELETE" && path.matches(Regex("/api/vnext/player/runtime/schedules/[^/]+")) ->
                easyCodeApp.schedules.delete(Uri.decode(path.substringAfterLast('/')))
            method == "POST" && path.matches(Regex("/api/vnext/player/runtime/schedules/[^/]+/run")) ->
                easyCodeApp.schedules.runNow(Uri.decode(path.split('/')[6]))
            method == "GET" && path == "/api/vnext/player/runtime/lan" -> easyCodeApp.lan.status()
            method == "POST" && path == "/api/vnext/player/runtime/lan/listener" -> easyCodeApp.lan.start().also { LanForegroundService.ensureRunning(this) }
            method == "DELETE" && path == "/api/vnext/player/runtime/lan/listener" -> easyCodeApp.lan.stop().also { LanForegroundService.stop(this) }
            method == "POST" && path == "/api/vnext/player/runtime/lan/discovery" -> {
                val input = body.asObject("局域网发现")
                JsonObject().apply {
                    add("devices", easyCodeApp.lan.discover(input.get("timeout_ms")?.asInt ?: 700, input.get("port")?.asInt ?: easyCodeApp.lan.status().get("port")?.asInt ?: 0))
                }
            }
            method == "POST" && path == "/api/vnext/player/runtime/lan/pairing-sessions" ->
                easyCodeApp.lan.createPairingSession(body.asObject("配对会话").get("ttl_ms")?.asLong ?: 300_000L)
            method == "POST" && path == "/api/vnext/player/runtime/lan/pairing/begin" -> {
                val input = body.asObject("发起配对")
                easyCodeApp.lan.beginPairing(
                    input.get("address")?.asString.orEmpty(),
                    input.get("port")?.asInt ?: 0,
                    input.get("code")?.asString.orEmpty(),
                    input.get("session_id")?.asString.orEmpty(),
                    input.get("permissions")?.takeIf(JsonElement::isJsonObject)?.asJsonObject ?: JsonObject(),
                )
            }
            method == "POST" && path == "/api/vnext/player/runtime/lan/pairing/complete" -> {
                val input = body.asObject("完成配对")
                easyCodeApp.lan.completePairing(
                    input.get("pairing")?.takeIf(JsonElement::isJsonObject)?.asJsonObject ?: error("缺少配对上下文"),
                    input.get("expected_fingerprint")?.asString.orEmpty(),
                )
            }
            method == "POST" && path.matches(Regex("/api/vnext/player/runtime/lan/pairing-pending/[^/]+/confirm")) -> {
                val input = body.asObject("确认配对")
                easyCodeApp.lan.confirmPairing(
                    Uri.decode(path.split('/')[7]),
                    input.get("permissions")?.takeIf(JsonElement::isJsonObject)?.asJsonObject ?: JsonObject(),
                )
            }
            method == "PATCH" && path.matches(Regex("/api/vnext/player/runtime/lan/peers/[^/]+/permissions")) ->
                easyCodeApp.lan.setPermissions(Uri.decode(path.split('/')[7]), body.asObject("设备权限"))
            method == "DELETE" && path.matches(Regex("/api/vnext/player/runtime/lan/peers/[^/]+")) ->
                easyCodeApp.lan.revoke(Uri.decode(path.substringAfterLast('/')))
            method == "POST" && path.matches(Regex("/api/vnext/player/runtime/lan/peers/[^/]+/refresh")) ->
                easyCodeApp.lan.refresh(Uri.decode(path.split('/')[7]))
            method == "GET" && path == "/api/vnext/player/runtime/lan/diagnostics" -> JsonObject().apply { add("events", easyCodeApp.lan.diagnostics()) }
            method == "GET" && path == "/api/vnext/player/runtime/messages/instance" -> easyCodeApp.messages.instance(bundle)
            method == "PATCH" && path == "/api/vnext/player/runtime/messages/instance" ->
                easyCodeApp.messages.renameInstance(bundle, body.asObject("实例名称").get("display_name")?.asString.orEmpty())
            method == "GET" && path == "/api/vnext/player/runtime/messages" -> easyCodeApp.messages.status(bundle)
            method == "POST" && path == "/api/vnext/player/runtime/messages/flush" -> easyCodeApp.messages.flush(bundle)
            method == "GET" && path == "/api/vnext/player/runtime/updates" -> easyCodeApp.updates.status()
            method == "POST" && path == "/api/vnext/player/runtime/updates/check" -> body.asObject("更新检查").let {
                easyCodeApp.updates.check(it.string("domain"), it.bool("policy_only"))
            }
            method == "POST" && path == "/api/vnext/player/runtime/updates/download" -> body.asObject("更新下载").let {
                easyCodeApp.updates.download(it.string("domain"))
            }
            method == "POST" && path == "/api/vnext/player/runtime/updates/apply" -> body.asObject("应用更新").let {
                val result = easyCodeApp.updates.apply(it.string("domain"))
                if (result.get("content_applied")?.asBoolean == true) {
                    bundle = easyCodeApp.packages.openActive()
                    easyCodeApp.updates.configure(bundle)
                    profile = easyCodeApp.profiles.loadOrCreate(bundle)
                }
                result
            }
            method == "PUT" && path == "/api/vnext/player/runtime/updates/preferences" -> body.asObject("更新偏好").let {
                easyCodeApp.updates.savePreferences(it.string("domain"), it.obj("preferences"))
            }
            method == "POST" && path == "/api/vnext/player/runtime/updates/reset-group" -> body.asObject("重置更新分组").let {
                easyCodeApp.updates.resetGroupCode(it.string("domain"))
            }
            method == "GET" && path.matches(Regex("/api/vnext/player/runtime/updates/[^/]+/group-code")) ->
                easyCodeApp.updates.groupCode(Uri.decode(path.split('/')[6]))
            method == "PUT" && path == "/api/vnext/player/runtime/updates/safe-point" -> easyCodeApp.updates.status()
            else -> error("Android Player Host 未开放：$method $path")
        }
    }

    private fun webBootstrap(): JsonObject {
        val registry = runCatching {
            JsonSupport.parseObject(bundle.readEntry("assets/registry.json"), "资源注册表")
        }.getOrElse { JsonObject() }
        val knownAssetIds = linkedSetOf<String>()
        val assets = JsonArray().apply {
            registry.get("assets")?.takeIf(JsonElement::isJsonObject)?.asJsonObject
                ?.entrySet()?.sortedBy { it.key }?.forEach { (assetId, value) ->
                    knownAssetIds += assetId
                    add(value.deepCopy())
                }
            easyCodeApp.profiles.list(bundle).forEach { candidate ->
                appendPrivateProfileAssets(this, candidate, knownAssetIds)
            }
        }
        return JsonObject().apply {
            addProperty("available", true)
            add("bundle", JsonObject().apply {
                addProperty("project_id", bundle.productId)
                addProperty("release_id", bundle.releaseId)
                addProperty("name", bundle.title)
                addProperty("created_at", bundle.manifest.string("created_at", ""))
            })
            add("form", bundle.form.deepCopy())
            add("targets", bundle.project.array("targets").deepCopy())
            addProperty("default_target_id", bundle.project.string("default_target_id"))
            add("assets", JsonObject().apply {
                add("categories", JsonArray().apply {
                    listOf("image" to "图像", "ocr" to "文字识别", "page" to "页面").forEach { (id, label) ->
                        add(JsonObject().apply {
                            addProperty("id", id)
                            addProperty("label", label)
                            add("folders", registry.obj("folders").get(id)?.deepCopy() ?: JsonArray())
                        })
                    }
                })
                add("assets", assets)
            })
            add("updates", easyCodeApp.updates.status())
            pendingWebFeedback?.let { feedback ->
                add("host_feedback", feedback.deepCopy())
                pendingWebFeedback = null
            }
        }
    }

    private fun appendPrivateProfileAssets(
        assets: JsonArray,
        candidate: PlayerProfile,
        knownAssetIds: MutableSet<String>,
    ) {
        fun visit(value: JsonElement) {
            if (value.isJsonArray) {
                value.asJsonArray.forEach(::visit)
                return
            }
            if (!value.isJsonObject) return
            val reference = value.asJsonObject
            val assetId = reference.string("asset_id")
            val digest = reference.string("sha256")
            if (
                assetId.startsWith("profile_") &&
                digest.matches(Regex("[0-9a-f]{64}")) &&
                knownAssetIds.add(assetId)
            ) {
                val file = easyCodeApp.profiles.privateImageFile(
                    bundle,
                    PlayerControlDestination(
                        bundle.productId,
                        bundle.releaseId,
                        candidate.profileId,
                        "profile_asset_catalog",
                        "capture-image",
                        candidate.revision,
                        candidate.targetId,
                    ),
                    digest,
                )
                val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                if (file.isFile) BitmapFactory.decodeFile(file.absolutePath, bounds)
                assets.add(JsonObject().apply {
                    addProperty("asset_id", assetId)
                    addProperty("display_name", "${candidate.name} · 截图 ${digest.take(8)}")
                    addProperty("category", "image")
                    addProperty("folder", "Player 采集")
                    addProperty("path", "profiles/${candidate.profileId}/images/$digest.png")
                    addProperty("extension", ".png")
                    addProperty("mime_type", "image/png")
                    addProperty("size_bytes", if (file.isFile) file.length() else 0L)
                    if (bounds.outWidth > 0) addProperty("width", bounds.outWidth) else add("width", JsonNull.INSTANCE)
                    if (bounds.outHeight > 0) addProperty("height", bounds.outHeight) else add("height", JsonNull.INSTANCE)
                    addProperty("sha256", digest)
                    addProperty("source", "player_capture")
                    addProperty("created_at", candidate.updatedAt)
                    addProperty("updated_at", candidate.updatedAt)
                    add("aliases", JsonArray())
                    add("capture", JsonNull.INSTANCE)
                })
            }
            reference.entrySet().forEach { visit(it.value) }
        }
        visit(candidate.values)
    }

    private fun saveWebProfile(body: JsonObject): JsonObject {
        val values = body.get("values")?.takeIf(JsonElement::isJsonObject)?.asJsonObject ?: JsonObject()
        val recording = body.get("recording")?.takeIf(JsonElement::isJsonObject)?.asJsonObject
        val profileId = body.string("profile_id")
        val targetId = body.get("target_id")?.takeUnless(JsonElement::isJsonNull)?.asString.orEmpty()
        val saved = if (profileId.isBlank()) {
            easyCodeApp.profiles.create(bundle, body.string("name", "新方案"), targetId, values, recording)
        } else {
            easyCodeApp.profiles.save(
                bundle,
                profileId,
                body.get("expected_revision")?.asInt ?: easyCodeApp.profiles.reload(bundle, profileId).revision,
                body.string("name", "默认方案"),
                targetId,
                values,
                recording,
            )
        }
        profile = saved
        return JsonObject().apply {
            addProperty("saved", true)
            add("profile", easyCodeApp.profiles.toJson(saved))
        }
    }

    private fun webTerminalActions(uri: Uri): JsonObject {
        val requestedProfile = uri.getQueryParameter("profile_id").orEmpty()
        val selected = requestedProfile.takeIf(String::isNotBlank)
            ?.let { easyCodeApp.profiles.reload(bundle, it) }
        val targetId = uri.getQueryParameter("target_id") ?: selected?.targetId.orEmpty()
        val blocked = when {
            selected == null -> "先保存配置方案，才能使用终端字段采集"
            easyCodeApp.runtime.state().active -> "任务运行或暂停期间不能修改字段"
            else -> ""
        }
        val actions = JsonArray()
        if (selected != null) for (page in bundle.form.array("pages")) {
            if (!page.isJsonObject) continue
            for (rawControl in page.asJsonObject.array("controls")) {
                if (!rawControl.isJsonObject) continue
                val control = rawControl.asJsonObject
                for (rawAction in control.array("terminal_actions")) {
                    if (!rawAction.isJsonObject) continue
                    val action = rawAction.asJsonObject
                    if (action.array("platforms").none { it.asString == "android_local" }) continue
                    val actionId = action.string("action_id")
                    val fileAction = actionId in setOf("choose-resource", "choose-file-read", "choose-file-save", "choose-directory")
                    val enabled = blocked.isBlank() && (targetId.isNotBlank() || fileAction)
                    val destination = PlayerControlDestination(
                        bundle.productId, bundle.releaseId, selected.profileId,
                        control.string("control_id"), actionId, selected.revision, targetId,
                    )
                    actions.add(JsonObject().apply {
                        addProperty("control_id", control.string("control_id"))
                        addProperty("action_id", actionId)
                        addProperty("platform", "android_local")
                        addProperty("capability", "player.capture.$actionId")
                        addProperty("enabled", enabled)
                        addProperty("disabled_reason", if (enabled) "" else blocked.ifBlank { "当前方案没有 Android 本机目标" })
                        add("destination", destination.toJson())
                    })
                }
            }
        }
        return JsonObject().apply {
            addProperty("platform", "android_local")
            if (selected == null) add("profile_id", JsonNull.INSTANCE) else addProperty("profile_id", selected.profileId)
            if (selected == null) add("profile_revision", JsonNull.INSTANCE) else addProperty("profile_revision", selected.revision)
            addProperty("blocked_reason", blocked)
            add("actions", actions)
        }
    }

    private fun webPreflight(uri: Uri): JsonObject {
        val started = System.nanoTime()
        val targetId = uri.getQueryParameter("target_id")
        val checks = JsonArray()
        fun check(id: String, pass: Boolean, message: String) = checks.add(JsonObject().apply {
            addProperty("id", id)
            addProperty("status", if (pass) "pass" else "fail")
            addProperty("message", message)
        })
        val targetReady = targetId.isNullOrBlank() || bundle.project.array("targets").any {
            it.isJsonObject && it.asJsonObject.string("target_id") == targetId && it.asJsonObject.string("type") == "android_local"
        }
        check("target", targetReady, if (targetReady) "运行目标可用" else "Android 本机目标不存在")
        if (ecirNeedsCapture() || profile.recording.bool("enabled")) check("capture", ScreenCaptureService.ready(), if (ScreenCaptureService.ready()) "屏幕捕获已授权" else "运行或录制需要屏幕捕获授权")
        if (ecirNeedsInput()) check("input", EasyCodeAccessibilityService.connected(), if (EasyCodeAccessibilityService.connected()) "本机输入服务已启用" else "请启用 EasyCode 无障碍输入服务")
        return JsonObject().apply {
            addProperty("ready", checks.all { it.asJsonObject.string("status") != "fail" })
            if (targetId == null) add("target_id", JsonNull.INSTANCE) else addProperty("target_id", targetId)
            addProperty("checked_at", Instant.now().toString())
            addProperty("duration_ms", (System.nanoTime() - started) / 1_000_000)
            add("checks", checks)
        }
    }

    private fun runProfile(body: JsonObject): PlayerProfile {
        val profileId = body.string("profile_id").ifBlank { profile.profileId }
        val stored = easyCodeApp.profiles.reload(bundle, profileId)
        val expectedRevision = body.get("profile_revision")?.asInt ?: stored.revision
        if (expectedRevision != stored.revision) error("配置方案 revision 已过期，请重新载入")
        val merged = stored.values.deepCopy()
        body.get("player_values")?.takeIf(JsonElement::isJsonObject)?.asJsonObject?.entrySet()?.forEach { (id, value) ->
            merged.add(id, value.deepCopy())
        }
        val target = body.get("target_id")?.takeUnless(JsonElement::isJsonNull)?.asString ?: stored.targetId
        return stored.copy(targetId = target, values = merged)
    }

    private fun webDangerousOperations(body: JsonObject): JsonObject {
        val candidate = runProfile(body)
        val previous = profile
        profile = candidate
        val requirements = try { dangerousRequirements(body.string("action_control_id")) } finally { profile = previous }
        return JsonObject().apply {
            add("operations", JsonArray().apply {
                requirements.forEach { item ->
                    add(JsonObject().apply {
                        addProperty("confirmation_id", dangerousConfirmationId(item))
                        addProperty("statement_id", item.statementId)
                        addProperty("function_id", "official.directory.delete_tree")
                        addProperty("display_name", "递归删除目录")
                        addProperty("display_path", item.authorizationRootId)
                        addProperty("authorization_root_id", item.authorizationRootId)
                        addProperty("execution_config_revision", item.profileRevision.toString())
                        addProperty("contract_fingerprint", item.contractFingerprint)
                    })
                }
            })
        }
    }

    private fun webStartRun(body: JsonObject): JsonObject {
        easyCodeApp.updates.assertTaskStartAllowed()
        val candidate = runProfile(body)
        profile = candidate
        while (true) {
            val missingPermission = RuntimePermissionGate.next(
                needsCapture = ecirNeedsCapture() || profile.recording.bool("enabled"),
                captureReady = ScreenCaptureService.ready(),
                needsInput = ecirNeedsInput(),
                inputReady = EasyCodeAccessibilityService.connected(),
            ) ?: break
            awaitRuntimePermission(missingPermission.id)
        }
        val actionId = body.string("action_control_id")
        val requirements = dangerousRequirements(actionId)
        val accepted = body.array("dangerous_confirmations").mapNotNull { raw ->
            raw.takeIf(JsonElement::isJsonObject)?.asJsonObject
                ?.takeIf { it.get("confirmed")?.asBoolean == true }
                ?.string("confirmation_id")
        }.toSet()
        val missing = requirements.filter { dangerousConfirmationId(it) !in accepted }
        if (missing.isNotEmpty()) error("本次运行尚未确认递归删除")
        synchronized(webRuntimeEvents) { webRuntimeEvents.clear() }
        val runtimeState = easyCodeApp.runtime.start(bundle, candidate, easyCodeApp.profiles, actionId, requirements)
        runCatching {
            easyCodeApp.recorder.start(bundle, candidate, runtimeState.runId)
            // A very short task may finish between runtime.start() and the
            // recorder start above. Reconcile once so that such a recording
            // is immediately finalized instead of remaining active forever.
            easyCodeApp.recorder.stateChanged(easyCodeApp.runtime.state())
        }
        return webRuntimeSession(easyCodeApp.runtime.state())
    }

    /**
     * The offline WebView host bridge is synchronous. Keep its original Run
     * request pending while Android owns the permission screen, then continue
     * that exact request once permission is usable. This avoids asking the
     * user to press Run twice and also prevents a second run from being
     * created by a retry.
     */
    private fun awaitRuntimePermission(kind: String) {
        if (Looper.myLooper() == Looper.getMainLooper()) {
            error("运行权限请求不能阻塞 Android 主线程")
        }
        val request = PendingRuntimePermission(kind)
        synchronized(this) {
            if (pendingRuntimePermission != null) error("已有运行正在等待系统权限")
            pendingRuntimePermission = request
        }
        runOnUiThread {
            when (kind) {
                "capture" -> requestProjectionPermission(null)
                "input" -> {
                    if (!openAccessibilitySettings()) {
                        request.complete(false, "当前 Android 系统没有可用的无障碍设置入口，运行尚未开始")
                    }
                }
                else -> request.complete(false, "未知运行权限：$kind")
            }
        }
        try {
            if (!request.completed.await(RUNTIME_PERMISSION_TIMEOUT_MINUTES, TimeUnit.MINUTES)) {
                error("等待系统权限超时，运行尚未开始")
            }
            if (!request.granted) error(request.message.ifBlank { "未授予运行所需权限，运行尚未开始" })
            if (kind == "capture") {
                val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(CAPTURE_READY_TIMEOUT_SECONDS)
                while (!ScreenCaptureService.ready() && System.nanoTime() < deadline) Thread.sleep(40L)
                if (!ScreenCaptureService.ready()) error("屏幕捕获授权初始化失败，运行尚未开始")
            }
        } finally {
            synchronized(this) {
                if (pendingRuntimePermission === request) pendingRuntimePermission = null
            }
        }
    }

    private fun dangerousConfirmationId(item: DangerousRunConfirmation): String =
        "danger_${JsonSupport.sha256("${item.statementId}|${item.authorizationRootId}|${item.profileRevision}|${item.contractFingerprint}".toByteArray()).take(24)}"

    private fun webStartCapture(body: JsonObject): JsonObject {
        val destination = PlayerControlDestination.fromJson(body.obj("destination"))
        runOnUiThread {
            runCatching { startTerminalAction(destination) }
                .onFailure { notifyWebCapture(false, it.message ?: "字段动作启动失败") }
        }
        return JsonObject().apply {
            addProperty("ok", true)
            addProperty("capture_id", "android_capture_${UUID.randomUUID().toString().replace("-", "")}")
            addProperty("state", "capturing")
            add("destination", destination.toJson())
        }
    }

    private fun prepareRecordingExport(sessionId: String): JsonObject {
        Thread({
            runCatching { easyCodeApp.recorder.createDefaultExport(bundle, sessionId) }
                .onSuccess { export ->
                    pendingRecordingExport = export
                    runOnUiThread {
                        startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                            type = "application/zip"
                            addCategory(Intent.CATEGORY_OPENABLE)
                            addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
                            putExtra(Intent.EXTRA_TITLE, export.name)
                        }, REQUEST_RECORDING_EXPORT)
                    }
                }
                .onFailure { notifyWebCapture(false, it.message ?: "录制导出准备失败") }
        }, "easycode-recording-export").apply { isDaemon = true; start() }
        return JsonObject().apply {
            addProperty("accepted", true)
            addProperty("state", "preparing")
            addProperty("session_id", sessionId)
        }
    }

    private fun webRuntimeSession(state: RunState): JsonObject = JsonObject().apply {
        addProperty("execution_id", state.runId.ifBlank { "android_idle" })
        addProperty("status", when (state.status) {
            RunStatus.STARTING -> "queued"
            RunStatus.RUNNING -> "running"
            RunStatus.PAUSED -> "paused"
            RunStatus.COMPLETED, RunStatus.IDLE -> "completed"
            RunStatus.FAILED -> "failed"
            RunStatus.STOPPING, RunStatus.STOPPED -> "cancelled"
        })
        addProperty("started_at", state.startedAt)
        addProperty("finished_at", if (state.active) "" else state.updatedAt)
        addProperty("error", state.errorMessage)
        val events = synchronized(webRuntimeEvents) { webRuntimeEvents.filter { it.runId == state.runId } }
        add("events", JsonArray().apply {
            events.forEach { event ->
                add(JsonObject().apply {
                    addProperty("sequence", event.sequence)
                    addProperty("timestamp", event.timestamp)
                    addProperty("level", event.level)
                    addProperty("category", event.category)
                    addProperty("message", event.message)
                    addProperty("instruction_id", event.instructionId)
                })
            }
        })
        addProperty("event_cursor", events.lastOrNull()?.sequence ?: 0)
        addProperty("current_instruction_id", state.currentInstructionId)
        add("current_source", JsonObject().apply {
            addProperty("function_id", state.currentFunctionId)
            addProperty("statement_id", state.currentInstructionId)
        })
        add("variables", JsonObject())
        add("breakpoints", JsonArray())
        addProperty("diagnostic_available", state.eventLogPath.isNotBlank())
        addProperty("failure_frame_available", false)
        add("recording", easyCodeApp.recorder.status())
    }

    private fun JsonElement.asObject(label: String): JsonObject =
        takeIf(JsonElement::isJsonObject)?.asJsonObject ?: error("$label 必须是 JSON 对象")

    private fun startTerminalAction(destination: PlayerControlDestination) {
        if (easyCodeApp.runtime.state().active) error("运行、暂停或停止过程中不能采集字段")
        val control = easyCodeApp.profiles.validateDestination(bundle, destination)
        val fileActions = setOf("choose-resource", "choose-file-read", "choose-file-save", "choose-directory")
        if (destination.targetId.isBlank() && destination.actionId !in fileActions) {
            error("该终端字段动作必须绑定真实 Android 本机目标")
        }
        pendingDestination = destination
        when (destination.actionId) {
            "pick-point", "pick-region", "pick-color", "capture-image", "capture-path" -> {
                beginVisualCapture(destination)
            }
            "capture-control" -> {
                if (EasyCodeAccessibilityService.connected()) beginVisualCapture(destination)
                else {
                    pendingAccessibilityCapture = true
                    if (!openAccessibilitySettings()) {
                        pendingAccessibilityCapture = false
                        pendingDestination = null
                        notifyWebCapture(
                            false,
                            "当前 Android 系统没有可用的无障碍设置入口；旧字段值保持不变",
                            destination.controlId,
                        )
                    }
                }
            }
            "choose-resource" -> launchDocument(Intent.ACTION_OPEN_DOCUMENT, "image/*")
            "choose-file-read" -> launchDocument(Intent.ACTION_OPEN_DOCUMENT, control)
            "choose-file-save" -> launchDocument(Intent.ACTION_CREATE_DOCUMENT, control)
            "choose-directory" -> startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).apply {
                addFlags(
                    SafReferences.directoryIntentFlags(control.string("source_type")) or
                        Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION,
                )
            }, REQUEST_DOCUMENT)
            else -> error("Android Player 没有此字段动作：${destination.actionId}")
        }
    }

    private fun beginVisualCapture(destination: PlayerControlDestination) {
        pendingDestination = destination
        if (!canDrawOverlaysCompat()) {
            startActivityForResult(
                Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:$packageName"),
                ),
                REQUEST_OVERLAY,
            )
            return
        }
        if (ScreenCaptureService.ready()) armCapture(destination)
        else requestProjectionPermission(destination)
    }

    private fun requestProjectionPermission(destination: PlayerControlDestination?) {
        pendingDestination = destination
        val manager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        startActivityForResult(manager.createScreenCaptureIntent(), REQUEST_PROJECTION)
    }

    private fun armCapture(destination: PlayerControlDestination) {
        ScreenCaptureService.arm(this, destination.toJson().toString())
        moveTaskToBack(true)
    }

    private fun launchDocument(action: String, control: JsonObject) {
        val mimeTypes = control.obj("constraints").array("extensions").mapNotNull { raw ->
            val extension = raw.asString.trim().removePrefix(".").lowercase()
            MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension)
        }.distinct()
        launchDocument(action, mimeTypes.singleOrNull() ?: "*/*", mimeTypes)
    }

    private fun launchDocument(action: String, type: String) {
        launchDocument(action, type, emptyList())
    }

    private fun launchDocument(action: String, type: String, mimeTypes: List<String>) {
        startActivityForResult(Intent(action).apply {
            this.type = type
            if (mimeTypes.size > 1) putExtra(Intent.EXTRA_MIME_TYPES, mimeTypes.toTypedArray())
            addCategory(Intent.CATEGORY_OPENABLE)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION or Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
            if (action == Intent.ACTION_CREATE_DOCUMENT) putExtra(Intent.EXTRA_TITLE, "easycode-output.txt")
        }, REQUEST_DOCUMENT)
    }

    @Deprecated("Legacy Activity result is used to keep the Android runtime independent from AndroidX.")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_OVERLAY) {
            val destination = pendingDestination
            if (destination == null) return
            if (!canDrawOverlaysCompat()) {
                pendingDestination = null
                notifyWebCapture(
                    false,
                    "未允许悬浮显示；旧字段值保持不变",
                    destination.controlId,
                )
                return
            }
            if (ScreenCaptureService.ready()) armCapture(destination)
            else requestProjectionPermission(destination)
            return
        }
        if (requestCode == REQUEST_PROJECTION) {
            if (resultCode != RESULT_OK || data == null) {
                val destination = pendingDestination
                pendingDestination = null
                if (destination == null) {
                    pendingRuntimePermission
                        ?.takeIf { it.kind == "capture" }
                        ?.complete(false, "屏幕捕获授权已取消，运行尚未开始")
                }
                if (destination != null) notifyWebCapture(
                    false,
                    "屏幕捕获授权已取消；旧字段值保持不变",
                    destination.controlId,
                )
                return
            }
            val destination = pendingDestination
            ScreenCaptureService.grant(this, resultCode, data, destination?.toJson()?.toString().orEmpty())
            if (destination != null) {
                moveTaskToBack(true)
            } else {
                pendingRuntimePermission
                    ?.takeIf { it.kind == "capture" }
                    ?.complete(true)
            }
            return
        }
        if (requestCode == REQUEST_RECORDING_EXPORT) {
            val export = pendingRecordingExport
            pendingRecordingExport = null
            if (resultCode != RESULT_OK || data?.data == null || export == null) {
                export?.delete()
                notifyWebCapture(false, "录制导出已取消")
                return
            }
            runCatching {
                contentResolver.openOutputStream(data.data!!, "w")?.use { output ->
                    export.inputStream().use { input -> input.copyTo(output) }
                } ?: error("系统没有返回可写入的位置")
            }.onSuccess {
                export.delete()
                notifyWebCapture(true, "录制已导出为“画面与报告”压缩包")
            }.onFailure {
                export.delete()
                notifyWebCapture(false, it.message ?: "录制导出失败")
            }
            return
        }
        if (requestCode != REQUEST_DOCUMENT) return
        val destination = pendingDestination
        pendingDestination = null
        if (resultCode != RESULT_OK || data?.data == null || destination == null) {
            if (destination != null) notifyWebCapture(
                false,
                "文件/目录选择已取消；旧字段值保持不变",
                destination.controlId,
            )
            return
        }
        try {
            easyCodeApp.profiles.validateDestination(bundle, destination)
            val uri = data.data!!
            val control = findControl(destination.controlId)
            val value = when (destination.actionId) {
                "choose-resource" -> importPrivateImage(destination, uri)
                "choose-file-read", "choose-file-save" -> SafReferences.file(
                    this, uri, destination.actionId, control.string("source_type"), data.flags,
                )
                "choose-directory" -> SafReferences.directory(
                    this, uri, control.string("source_type"), data.flags,
                )
                else -> error("文件选择结果动作无效")
            }
            if (
                destination.actionId == "choose-directory" &&
                SafReferences.requiresDeleteTreeAuthorization(control.string("source_type"))
            ) {
                confirmDeleteTreeAuthorization(destination, value.asJsonObject)
                return
            }
            profile = easyCodeApp.profiles.commitValue(bundle, destination, value)
            val message = "字段已保存到方案 revision ${profile.revision}"
            notifyWebCapture(true, message, destination.controlId)
        } catch (error: Exception) {
            val message = error.message ?: "文件/目录回填失败"
            notifyWebCapture(false, message, destination.controlId)
        }
    }

    private fun confirmDeleteTreeAuthorization(
        destination: PlayerControlDestination,
        ordinaryReference: JsonObject,
    ) {
        EasyCodeDialog.show(
            activity = this,
            title = "单独授权递归删除",
            message =
                "普通文件夹选择只授予系统文档访问，不包含递归删除。若继续，此字段会记录对刚才所选稳定授权根的 delete_tree 危险能力；" +
                    "每次实际运行仍会再次显示不可回滚确认，跨运行不会复用。",
            actions = listOf(
                EasyCodeDialog.Action("不授权") {
                    notifyWebCapture(false, "未授予递归删除；旧字段值保持不变", destination.controlId)
                },
                EasyCodeDialog.Action("授权此根", emphasis = true) {
                    try {
                        val control = easyCodeApp.profiles.validateDestination(bundle, destination)
                        val approved = SafReferences.authorizeDeleteTree(
                            ordinaryReference,
                            control.string("source_type"),
                        )
                        profile = easyCodeApp.profiles.commitValue(bundle, destination, approved)
                        val message = "危险目录根已保存到方案 revision ${profile.revision}"
                        notifyWebCapture(true, message, destination.controlId)
                    } catch (error: Exception) {
                        notifyWebCapture(
                            false,
                            error.message ?: "递归删除危险授权失败；旧字段值保持不变",
                            destination.controlId,
                        )
                    }
                },
            ),
            tone = EasyCodeDialog.Tone.WARNING,
            dismissOnOutside = false,
        )
    }

    private fun importPrivateImage(destination: PlayerControlDestination, uri: Uri): JsonObject {
        val source = contentResolver.openInputStream(uri) ?: error("系统选择器没有返回可读图片")
        val bytes = source.use { input ->
            val output = ByteArrayOutputStream()
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            var count = 0L
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                count += read
                if (count > 32L * 1024L * 1024L) error("图片超过 32MB 限制")
                output.write(buffer, 0, read)
            }
            output.toByteArray()
        }
        val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: error("选择的文件不是可解码图片")
        val png = ByteArrayOutputStream().use { output ->
            if (!bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)) error("图片无法规范化")
            output.toByteArray()
        }
        bitmap.recycle()
        val digest = JsonSupport.sha256(png)
        AtomicFiles.write(easyCodeApp.profiles.privateImageFile(bundle, destination, digest), png)
        return JsonObject().apply {
            addProperty("asset_id", "profile_$digest")
            addProperty("asset_kind", "image")
            addProperty("sha256", digest)
        }
    }

    private fun findControl(controlId: String): JsonObject {
        for (page in bundle.form.array("pages")) for (raw in page.asJsonObject.array("controls")) {
            if (raw.isJsonObject && raw.asJsonObject.string("control_id") == controlId) return raw.asJsonObject
        }
        error("Player 字段不存在：$controlId")
    }

    private fun ecirNeedsCapture(): Boolean = containsOpcode(setOf(
        "target.capture_frame", "frame.save", "frame.crop_region", "vision.compare_samples",
        "color.read", "color.find", "vision.find", "vision.find_all",
        "standard.image.wait_visible", "standard.image.wait_hidden",
        "standard.image.click_once", "standard.image.click_until_hidden",
        "standard.image.click_position_until_visible", "standard.image.click_position_until_hidden",
    ))

    private fun ecirNeedsInput(): Boolean = containsOpcode(setOf(
        "input.click", "input.text", "input.scroll", "input.drag", "input.key",
        "control.find", "control.click", "control.read_text", "control.input_text",
        "control.read_status", "control.focus", "control.set_value", "control.select",
        "control.toggle", "control.scroll_into_view",
        "standard.control.wait_visible", "standard.control.wait_hidden",
        "standard.image.click_once", "standard.image.click_until_hidden",
        "standard.image.click_position_until_visible", "standard.image.click_position_until_hidden",
    ))

    private fun containsOpcode(opcodes: Set<String>): Boolean {
        fun visit(value: JsonElement): Boolean {
            if (value.isJsonArray) return value.asJsonArray.any(::visit)
            if (!value.isJsonObject) return false
            val obj = value.asJsonObject
            if (obj.string("opcode") in opcodes) return true
            return obj.entrySet().any { visit(it.value) }
        }
        return visit(bundle.ecir.array("functions"))
    }

    private fun dangerousRequirements(actionControlId: String): Set<DangerousRunConfirmation> {
        val bound = PlayerBindings.bind(bundle, profile, actionControlId)
        val functions = bound.ecir.array("functions").mapNotNull {
            it.takeIf(JsonElement::isJsonObject)?.asJsonObject
        }.associateBy { it.string("function_id") }
        val projectValues = linkedMapOf<String, JsonElement>()
        for (raw in bound.ecir.array("project_variables")) {
            if (!raw.isJsonObject) continue
            val definition = raw.asJsonObject
            definition.get("default_value")?.let { projectValues[definition.string("variable_id")] = it }
        }
        for ((id, value) in bound.ecir.obj("project_variable_overrides").entrySet()) {
            projectValues[id] = value
        }
        val activeFunctions = mutableSetOf<String>()
        val requirements = linkedSetOf<DangerousRunConfirmation>()
        var callVisits = 0
        fun resolveReference(value: JsonElement?, locals: Map<String, JsonObject>): JsonObject? {
            if (value?.isJsonObject != true) return null
            val candidate = value.asJsonObject
            if (candidate.string("kind") == "directory_ref") return candidate
            if (candidate.string("kind") != "reference") return null
            return if (candidate.string("scope") == "project") {
                projectValues[candidate.string("variable_id")]
                    ?.takeIf(JsonElement::isJsonObject)?.asJsonObject
                    ?.takeIf { it.string("kind") == "directory_ref" }
            } else {
                locals[candidate.string("symbol_id")]
            }
        }
        fun visitFunction(id: String, incoming: Map<String, JsonElement>) {
            if (++callVisits > 10_000) error("递归删除运行前授权分析超过 10000 次调用上限")
            val function = functions[id] ?: return
            // The first visit covers the recursive body. If a later recursive
            // invocation resolves another root, SafFileRuntime's exact
            // statement/root/revision/fingerprint match rejects it before
            // the first delete because no confirmation exists for that root.
            if (!activeFunctions.add(id)) return
            val locals = linkedMapOf<String, JsonObject>()
            for (raw in function.array("parameter_definitions")) {
                if (!raw.isJsonObject) continue
                val parameter = raw.asJsonObject
                val value = incoming[parameter.string("parameter_id")] ?: parameter.get("default")
                resolveReference(value, emptyMap())?.let { locals[parameter.string("name")] = it }
            }
            fun visit(value: JsonElement) {
                if (value.isJsonArray) value.asJsonArray.forEach(::visit)
                if (!value.isJsonObject) return
                val obj = value.asJsonObject
                if (obj.string("opcode") == "directory.delete_tree") {
                    val statementId = obj.string("instruction_id")
                    val fingerprint = obj.obj("dangerous_author_review").string("contract_fingerprint")
                    val reference = resolveReference(
                        obj.obj("arguments").get("official.directory.delete_tree.parameter.directory"),
                        locals,
                    ) ?: error("递归删除 $statementId 的真实目录授权根在运行前无法确定")
                    val rootId = reference.string("authorization_root_id")
                    val access = reference.array("access").map { it.asString }.toSet()
                    if (rootId.isBlank() || fingerprint.isBlank()) {
                        error("递归删除 $statementId 缺少授权根或锁定契约，已在运行前拒绝")
                    }
                    if ("delete_tree" !in access) {
                        error("递归删除 $statementId 缺少独立 delete_tree 危险授权；普通 SAF 授权不会升级")
                    }
                    requirements += DangerousRunConfirmation(
                        statementId,
                        rootId,
                        profile.revision,
                        fingerprint,
                    )
                }
                if (obj.string("opcode") == "call.project") {
                    val childArguments = obj.obj("arguments").entrySet().associate { (parameterId, raw) ->
                        parameterId to (resolveReference(raw, locals) ?: raw)
                    }
                    visitFunction(obj.string("callee_function_id"), childArguments)
                }
                obj.entrySet().forEach { visit(it.value) }
            }
            try {
                visit(function.array("instructions"))
            } finally {
                activeFunctions.remove(id)
            }
        }
        val entryArguments = bound.ecir.obj("function_arguments")
            .get(bound.entryFunctionId)
            ?.takeIf(JsonElement::isJsonObject)
            ?.asJsonObject
            ?.entrySet()
            ?.associate { it.key to it.value }
            .orEmpty()
        visitFunction(bound.entryFunctionId, entryArguments)
        return requirements
    }

    private fun reloadProfileAndNotifyWeb(
        message: String = "字段已采集并保存",
        ok: Boolean = true,
        controlId: String? = null,
    ) {
        runCatching { easyCodeApp.profiles.reload(bundle, profile.profileId) }
            .onSuccess {
                profile = it
                notifyWebCapture(ok, message, controlId)
            }
            .onFailure {
                val failure = it.message ?: "配置方案重新载入失败"
                notifyWebCapture(false, failure, controlId)
            }
    }

    private fun notifyWebCapture(ok: Boolean, message: String, controlId: String? = null) {
        val detail = JsonObject().apply {
            addProperty("ok", ok)
            addProperty("message", message)
            controlId?.takeIf(String::isNotBlank)?.let { addProperty("control_id", it) }
        }
        if (!::playerWebView.isInitialized) {
            pendingWebFeedback = detail
            return
        }
        val detailJson = detail.toString()
        playerWebView.post {
            playerWebView.evaluateJavascript(
                "window.dispatchEvent(new CustomEvent('easycode-native-capture-complete',{detail:$detailJson}))",
                null,
            )
        }
    }

    private fun queueWebFeedback(ok: Boolean, message: String, controlId: String? = null) {
        pendingWebFeedback = JsonObject().apply {
            addProperty("ok", ok)
            addProperty("message", message)
            controlId?.takeIf(String::isNotBlank)?.let { addProperty("control_id", it) }
        }
    }

    private fun feedbackFromIntent(source: Intent?): JsonObject? {
        val message = source?.getStringExtra(EXTRA_STATUS_MESSAGE)?.takeIf(String::isNotBlank) ?: return null
        return JsonObject().apply {
            addProperty("ok", source.getBooleanExtra(EXTRA_STATUS_OK, true))
            addProperty("message", message)
            source.getStringExtra(EXTRA_CONTROL_ID)?.takeIf(String::isNotBlank)?.let {
                addProperty("control_id", it)
            }
        }
    }

    override fun stateChanged(state: RunState) = Unit

    override fun event(event: RuntimeEvent) {
        synchronized(webRuntimeEvents) {
            webRuntimeEvents.addLast(event)
            while (webRuntimeEvents.size > 2_000) webRuntimeEvents.removeFirst()
        }
    }

    override fun onDestroy() {
        pendingRuntimePermission?.complete(false, "Player 页面已关闭，运行未开始")
        if (::playerWebView.isInitialized) {
            playerWebView.removeJavascriptInterface("EasyCodeAndroid")
            playerWebView.stopLoading()
            playerWebView.destroy()
        }
        super.onDestroy()
    }

    private fun showFatal(
        message: String,
        assurance: String = "APK 不会绕过签名、源码隔离或扩展检查。",
    ) {
        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(dp(24), dp(24), dp(24), dp(24))
            addView(TextView(this@PlayerActivity).apply {
                text = "EasyCode Player 无法启动\n\n$message\n\n$assurance"
                textSize = 17f
                setTextColor(resources.getColor(R.color.ec_text))
                gravity = Gravity.CENTER
            })
        })
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQUEST_NOTIFICATIONS)
        }
    }

    private fun canDrawOverlaysCompat(): Boolean =
        Build.VERSION.SDK_INT < 23 || Settings.canDrawOverlays(this)

    private fun openAccessibilitySettings(): Boolean {
        val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
        if (intent.resolveActivity(packageManager) == null) return false
        return runCatching { startActivity(intent) }.isSuccess
    }

    private fun awaitAccessibilityConnection(completion: (Boolean) -> Unit) {
        val deadline = SystemClock.elapsedRealtime() + ACCESSIBILITY_CONNECTION_GRACE_MS
        val handler = Handler(Looper.getMainLooper())
        val check = object : Runnable {
            override fun run() {
                if (EasyCodeAccessibilityService.connected()) {
                    completion(true)
                    return
                }
                if (isFinishing || isDestroyed || SystemClock.elapsedRealtime() >= deadline) {
                    completion(false)
                    return
                }
                handler.postDelayed(this, ACCESSIBILITY_CONNECTION_POLL_MS)
            }
        }
        check.run()
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density + 0.5f).toInt()

    companion object {
        const val EXTRA_STATUS_MESSAGE = "status_message"
        const val EXTRA_STATUS_OK = "status_ok"
        const val EXTRA_CONTROL_ID = "control_id"
        private const val REQUEST_PROJECTION = 6101
        private const val REQUEST_DOCUMENT = 6102
        private const val REQUEST_NOTIFICATIONS = 6103
        private const val REQUEST_OVERLAY = 6104
        private const val REQUEST_RECORDING_EXPORT = 6105
        private const val STATE_PENDING_DESTINATION = "pending_destination"
        private const val RUNTIME_PERMISSION_TIMEOUT_MINUTES = 5L
        private const val CAPTURE_READY_TIMEOUT_SECONDS = 10L
        private const val ACCESSIBILITY_CONNECTION_GRACE_MS = 3_000L
        private const val ACCESSIBILITY_CONNECTION_POLL_MS = 100L
    }

    private class PendingRuntimePermission(val kind: String) {
        val completed = CountDownLatch(1)
        @Volatile var granted = false
        @Volatile var message = ""
        @Volatile var leftActivity = false

        fun complete(granted: Boolean, message: String = "") {
            if (completed.count == 0L) return
            this.granted = granted
            this.message = message
            completed.countDown()
        }
    }
}
