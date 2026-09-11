package com.easycode.player.capture

import android.app.Activity
import android.app.ActivityManager
import android.app.ActivityOptions
import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.Looper
import android.view.WindowManager
import com.easycode.player.EasyCodeApplication
import com.easycode.player.PlayerActivity
import com.easycode.player.R
import com.easycode.player.input.AndroidControlSnapshot
import com.easycode.player.input.EasyCodeAccessibilityService
import com.easycode.player.profile.PlayerControlDestination
import com.easycode.player.runtime.RuntimeFailure
import com.easycode.player.util.AtomicFiles
import com.easycode.player.util.AndroidCompat
import com.easycode.player.util.JsonSupport
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors

/**
 * Keeps the MediaProjection grant and owns one Android-local Capture Session.
 * Floating controls are removed before a fresh frame is acquired, so product
 * UI can never become part of the captured value.
 */
class ScreenCaptureService : Service() {
    private val captureLock = Any()
    private val worker = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "easycode-capture-action").apply { isDaemon = true }
    }
    private val mainHandler = Handler(Looper.getMainLooper())
    private lateinit var imageThread: HandlerThread
    private lateinit var imageHandler: Handler
    private lateinit var floating: FloatingCaptureController
    @Volatile private var projection: MediaProjection? = null
    @Volatile private var shuttingDown = false
    private var reader: ImageReader? = null
    private var display: VirtualDisplay? = null
    private var captureWidth = 0
    private var captureHeight = 0
    private var latestFrame: Bitmap? = null
    private val armCoordinator = CaptureArmCoordinator()
    @Volatile private var pendingControlSnapshot: List<AndroidControlSnapshot>? = null

    override fun onCreate() {
        super.onCreate()
        imageThread = HandlerThread("easycode-media-projection").also { it.start() }
        imageHandler = Handler(imageThread.looper)
        floating = FloatingCaptureController(this)
        instance = this
        ensureChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_GRANT -> {
                startForeground(NOTIFICATION_ID, notification("屏幕捕获授权正在初始化"))
                val resultCode = intent.getIntExtra(EXTRA_RESULT_CODE, Activity.RESULT_CANCELED)
                val data = projectionData(intent)
                if (resultCode != Activity.RESULT_OK || data == null) {
                    stopSelf()
                } else {
                    try {
                        startProjection(resultCode, data)
                        intent.getStringExtra(EXTRA_DESTINATION)
                            ?.takeIf(String::isNotBlank)
                            ?.let(::armInternal)
                    } catch (error: Exception) {
                        updateNotification(error.message ?: "屏幕捕获授权初始化失败")
                        stopSelf()
                    }
                }
            }
            ACTION_ARM -> {
                startForeground(NOTIFICATION_ID, notification("屏幕捕获已就绪"))
                val destination = intent.getStringExtra(EXTRA_DESTINATION).orEmpty()
                if (projection == null) {
                    returnToPlayer(false, "屏幕捕获授权已失效，请重新开始采集", destinationOrNull(destination))
                } else {
                    armInternal(destination)
                }
            }
            ACTION_STOP -> cancelCurrent("字段采集已取消；旧值保持不变")
            else -> startForeground(NOTIFICATION_ID, notification("屏幕捕获已就绪"))
        }
        return START_NOT_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        if (floating.isActive()) {
            floating.onDisplayChanged {
                cancelCurrent("设备方向已变化，请重新采集；旧值保持不变")
            }
        }
    }

    override fun onDestroy() {
        shuttingDown = true
        floating.dismiss()
        synchronized(captureLock) {
            display?.release()
            display = null
            reader?.close()
            reader = null
            clearLatestFrameLocked()
            projection?.stop()
            projection = null
        }
        worker.shutdownNow()
        armCoordinator.cancel()
        imageThread.quitSafely()
        if (instance === this) instance = null
        super.onDestroy()
    }

    fun captureBitmap(timeoutMs: Long = 3_000L): Bitmap = synchronized(captureLock) {
        val (currentWidth, currentHeight) = displaySize()
        if (currentWidth != captureWidth || currentHeight != captureHeight) {
            resizeProjectionLocked(currentWidth, currentHeight)
            // The replacement Surface needs at least one compositor frame.
            Thread.sleep(80L)
        }
        val activeReader = reader
            ?: throw RuntimeFailure("capture.permission_missing", "MediaProjection 尚未授权或已被系统撤销")
        val started = System.nanoTime()
        val deadline = started + timeoutMs.coerceIn(250L, 10_000L) * 1_000_000L
        // Recording and runtime vision intentionally share this capture
        // session. If another consumer just acquired the only queued image,
        // wait briefly for a fresher compositor frame and then reuse the
        // latest complete bitmap. A static screen is still a valid frame and
        // must not turn into a timeout merely because it did not repaint.
        val freshFrameDeadline = if (latestFrame == null) deadline else minOf(deadline, started + 180_000_000L)
        // acquireLatestImage() already discards older queued images and returns
        // the newest one.  Draining the queue first made a second capture of a
        // static screen wait for a compositor update that might never arrive.
        // Keeping the newest available image therefore gives both freshness
        // and repeatable capture semantics when the screen has not changed.
        var image = activeReader.acquireLatestImage()
        while (image == null && System.nanoTime() < freshFrameDeadline) {
            Thread.sleep(16L)
            image = activeReader.acquireLatestImage()
        }
        if (image == null) {
            latestFrame
                ?.takeUnless { it.isRecycled }
                ?.takeIf { it.width == captureWidth && it.height == captureHeight }
                ?.copy(Bitmap.Config.ARGB_8888, false)
                ?.let { return@synchronized it }
        }
        val captured = image
            ?: throw RuntimeFailure("capture.timeout", "MediaProjection 在限时内没有返回画面", transient = true)
        try {
            val plane = captured.planes.firstOrNull()
                ?: throw RuntimeFailure("capture.frame_invalid", "MediaProjection 返回空画面")
            val pixelStride = plane.pixelStride
            val rowStride = plane.rowStride
            if (pixelStride != 4 || rowStride < captureWidth * pixelStride) {
                throw RuntimeFailure("capture.frame_invalid", "MediaProjection 像素格式不受支持")
            }
            val paddedWidth = rowStride / pixelStride
            val padded = Bitmap.createBitmap(paddedWidth, captureHeight, Bitmap.Config.ARGB_8888)
            padded.copyPixelsFromBuffer(plane.buffer)
            val result = if (paddedWidth == captureWidth) padded else {
                Bitmap.createBitmap(padded, 0, 0, captureWidth, captureHeight).also { padded.recycle() }
            }
            latestFrame?.takeUnless { it === result }?.recycle()
            latestFrame = result.copy(Bitmap.Config.ARGB_8888, false)
            return@synchronized result
        } finally {
            captured.close()
        }
    }

    private fun resizeProjectionLocked(width: Int, height: Int) {
        val activeDisplay = display
            ?: throw RuntimeFailure("capture.permission_missing", "MediaProjection 显示会话已失效")
        val replacement = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 3)
        try {
            activeDisplay.surface = null
            activeDisplay.resize(width, height, resources.displayMetrics.densityDpi)
            activeDisplay.surface = replacement.surface
        } catch (error: Exception) {
            replacement.close()
            throw RuntimeFailure("capture.display_resize_failed", "目标画面尺寸变化后无法刷新采集空间", transient = true)
        }
        reader?.close()
        reader = replacement
        clearLatestFrameLocked()
        captureWidth = width
        captureHeight = height
    }

    private fun startProjection(resultCode: Int, data: Intent) = synchronized(captureLock) {
        display?.release()
        reader?.close()
        clearLatestFrameLocked()
        projection?.stop()
        val manager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        val next = manager.getMediaProjection(resultCode, data)
            ?: throw RuntimeFailure("capture.permission_missing", "系统未返回 MediaProjection 会话")
        next.registerCallback(object : MediaProjection.Callback() {
            override fun onCapturedContentResize(width: Int, height: Int) {
                if (width < 1 || height < 1 || shuttingDown) return
                synchronized(captureLock) {
                    if (projection !== next || display == null) return
                    if (width != captureWidth || height != captureHeight) {
                        runCatching { resizeProjectionLocked(width, height) }
                            .onFailure { updateNotification("目标画面尺寸刷新失败，请重试采集") }
                    }
                }
            }

            override fun onStop() {
                synchronized(captureLock) {
                    display?.release()
                    display = null
                    reader?.close()
                    reader = null
                    clearLatestFrameLocked()
                    projection = null
                }
                if (!shuttingDown) mainHandler.post {
                    if (floating.isActive()) cancelCurrent("屏幕捕获授权已被系统撤销；旧值保持不变")
                    else updateNotification("屏幕捕获授权已被系统撤销")
                }
            }
        }, imageHandler)
        val (width, height) = displaySize()
        val density = resources.displayMetrics.densityDpi
        val nextReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 3)
        val nextDisplay = next.createVirtualDisplay(
            "EasyCodeMediaProjection",
            width,
            height,
            density,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            nextReader.surface,
            null,
            imageHandler,
        )
        projection = next
        reader = nextReader
        display = nextDisplay
        captureWidth = width
        captureHeight = height
        updateNotification("屏幕捕获已授权")
    }

    private fun clearLatestFrameLocked() {
        latestFrame?.recycle()
        latestFrame = null
    }

    private fun armInternal(rawDestination: String, message: String? = null, retry: Boolean = false) {
        val destination = destinationOrNull(rawDestination)
        if (destination == null) {
            returnToPlayer(false, "字段采集目标无效；旧值保持不变", null)
            return
        }
        val ticket = try {
            armCoordinator.arm(rawDestination)
        } catch (error: Exception) {
            returnToPlayer(false, error.message ?: "已有其他采集会话正在进行", destination)
            return
        }
        try {
            floating.showBubble(
                destination = destination,
                message = message,
                retry = retry,
                onCapture = { beginCapture(ticket) },
                onCancel = { cancelCurrent("字段采集已取消；旧值保持不变", destination) },
            )
            updateNotification("悬浮采集已就绪")
        } catch (error: Exception) {
            armCoordinator.cancel()
            returnToPlayer(false, "无法显示悬浮采集控件，请允许悬浮显示后重试", destination)
        }
    }

    private fun beginCapture(ticket: CaptureArmCoordinator.Ticket) {
        if (!armCoordinator.claim(ticket)) return
        floating.hideBubbleForCapture()
        updateNotification("正在获取干净画面")
        worker.execute {
            try {
                // SurfaceFlinger gets two frames to remove EasyCode controls;
                // captureBitmap then drops every queued image as a second gate.
                Thread.sleep(80L)
                val destination = destinationOrNull(ticket.destination)
                    ?: error("字段采集目标已失效")
                pendingControlSnapshot = if (destination.actionId == "capture-control") {
                    EasyCodeAccessibilityService.requireConnectedForControl().snapshotControls()
                } else null
                val bitmap = captureBitmap()
                armCoordinator.complete()
                mainHandler.post { showFrozen(bitmap, ticket.destination) }
            } catch (error: Exception) {
                armCoordinator.complete()
                mainHandler.post {
                    if (error is RuntimeFailure && error.errorId in setOf(
                            "control.semantic_tree_unavailable",
                            "control.permission_required",
                            "control.driver_unavailable",
                        )
                    ) {
                        pendingControlSnapshot = null
                        returnToPlayer(false, error.message ?: "控件捕获不可用；旧值保持不变", destinationOrNull(ticket.destination))
                    } else {
                        armInternal(ticket.destination, error.message ?: "画面采集失败", retry = true)
                    }
                }
            }
        }
    }

    private fun showFrozen(bitmap: Bitmap, rawDestination: String) {
        val destination = destinationOrNull(rawDestination)
        if (destination == null) {
            bitmap.recycle()
            returnToPlayer(false, "字段采集目标已失效；旧值保持不变", null)
            return
        }
        try {
            floating.showFrozen(
                bitmap = bitmap,
                destination = destination,
                controlSnapshot = pendingControlSnapshot,
                onConfirm = { selection -> commitSelection(destination, selection) },
                onCancel = { cancelCurrent("字段采集已取消；旧值保持不变", destination) },
            )
            updateNotification("画面已冻结，请完成选择")
        } catch (error: Exception) {
            bitmap.recycle()
            returnToPlayer(false, error.message ?: "无法显示冻结画面", destination)
        }
    }

    private fun commitSelection(
        destination: PlayerControlDestination,
        selection: FrozenCaptureSelection,
    ) {
        worker.execute {
            try {
                val app = application as EasyCodeApplication
                if (app.runtime.state().active) error("任务运行或暂停期间不能修改字段")
                val bundle = app.packages.openActive()
                app.profiles.validateDestination(bundle, destination)
                val value = if (selection.actionId == "capture-control") {
                    selection.value ?: error("控件捕获缺少已确认的控件选择器")
                } else selection.value ?: privateImageValue(app, destination, selection)
                val profile = app.profiles.commitValue(bundle, destination, value)
                pendingControlSnapshot = null
                mainHandler.post {
                    returnToPlayer(true, "字段已保存到方案 revision ${profile.revision}", destination)
                }
            } catch (error: Exception) {
                mainHandler.post {
                    floating.showFrozenError(error.message ?: "字段回填失败；旧值保持不变")
                }
            }
        }
    }

    private fun privateImageValue(
        app: EasyCodeApplication,
        destination: PlayerControlDestination,
        selection: FrozenCaptureSelection,
    ): JsonObject {
        val source = selection.source ?: error("录入图片缺少原始画面")
        val rect = selection.imageRect ?: error("录入图片缺少框选区域")
        val crop = Bitmap.createBitmap(source, rect[0], rect[1], rect[2], rect[3])
        val png = try {
            ByteArrayOutputStream().use { output ->
                if (!crop.compress(Bitmap.CompressFormat.PNG, 100, output)) {
                    error("录入图片无法编码为 PNG")
                }
                output.toByteArray()
            }
        } finally {
            crop.recycle()
        }
        if (png.size > 32L * 1024L * 1024L) error("录入图片超过 32MB 限制")
        val bundle = app.packages.openActive()
        val digest = JsonSupport.sha256(png)
        AtomicFiles.write(app.profiles.privateImageFile(bundle, destination, digest), png)
        return JsonObject().apply {
            addProperty("asset_id", "profile_$digest")
            addProperty("asset_kind", "image")
            addProperty("sha256", digest)
        }
    }

    private fun cancelCurrent(
        message: String,
        knownDestination: PlayerControlDestination? = null,
    ) {
        val destination = knownDestination ?: armCoordinator.activeTicket()
            ?.destination
            ?.let(::destinationOrNull)
        armCoordinator.cancel()
        pendingControlSnapshot = null
        returnToPlayer(false, message, destination)
    }

    private fun returnToPlayer(
        ok: Boolean,
        message: String,
        destination: PlayerControlDestination?,
    ) {
        pendingControlSnapshot = null
        val target = Intent(this, PlayerActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra(PlayerActivity.EXTRA_STATUS_OK, ok)
            putExtra(PlayerActivity.EXTRA_STATUS_MESSAGE, message)
            destination?.let { putExtra(PlayerActivity.EXTRA_CONTROL_ID, it.controlId) }
        }
        // The confirmation/cancel button is a visible product-owned overlay and
        // therefore an explicit user gesture.  Send a trusted PendingIntent while
        // that window is still visible so Android can attribute the return to the
        // gesture instead of treating it as an unsolicited background launch.
        val creatorOptions = if (Build.VERSION.SDK_INT >= 35) {
            ActivityOptions.makeBasic().apply {
                pendingIntentCreatorBackgroundActivityStartMode =
                    ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED
            }.toBundle()
        } else null
        val returnIntent = PendingIntent.getActivity(
            this,
            RETURN_TO_PLAYER_REQUEST_CODE,
            target,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            creatorOptions,
        )
        val senderOptions = if (Build.VERSION.SDK_INT >= 34) {
            ActivityOptions.makeBasic().apply {
                pendingIntentBackgroundActivityStartMode =
                    if (Build.VERSION.SDK_INT >= 36) {
                        ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOW_IF_VISIBLE
                    } else {
                        ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED
                    }
            }.toBundle()
        } else null
        runCatching {
            if (Build.VERSION.SDK_INT >= 23) {
                returnIntent.send(this, 0, null, null, null, null, senderOptions)
            } else {
                returnIntent.send()
            }
        }
            .onFailure { runCatching { startActivity(target) } }
        // Some OEMs deliver the singleTask intent but leave its existing task
        // behind the app the user just captured. The confirmation/cancel tap
        // is an explicit user action, so bring only EasyCode's own task to the
        // foreground after the result has been committed.
        runCatching {
            (getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).appTasks
                .firstOrNull { task ->
                    task.taskInfo?.baseIntent?.component?.packageName == packageName
                }
                ?.moveToFront()
        }
        floating.dismiss()
        stopSelf()
    }

    private fun destinationOrNull(raw: String): PlayerControlDestination? = runCatching {
        PlayerControlDestination.fromJson(JsonParser.parseString(raw).asJsonObject)
    }.getOrNull()

    private fun notification(text: String): Notification {
        val content = PendingIntent.getActivity(
            this,
            1,
            Intent(this, PlayerActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return AndroidCompat.notificationBuilder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(getString(R.string.capture_notification_title))
            .setContentText(text)
            .setContentIntent(content)
            .setOngoing(true)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setPriority(Notification.PRIORITY_LOW)
            .setOnlyAlertOnce(true)
            .build()
    }

    private fun updateNotification(text: String) {
        AndroidCompat.notificationManager(this).notify(NOTIFICATION_ID, notification(text))
    }

    private fun ensureChannel() {
        AndroidCompat.ensureNotificationChannel(
            this, CHANNEL_ID, "EasyCode 屏幕捕获",
            "MediaProjection 会话状态；采集操作始终在 EasyCode 界面内完成", silent = true,
        )
    }

    private fun displaySize(): Pair<Int, Int> {
        val window = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        return if (Build.VERSION.SDK_INT >= 30) {
            val bounds = window.maximumWindowMetrics.bounds
            Pair(bounds.width(), bounds.height())
        } else {
            @Suppress("DEPRECATION")
            resources.displayMetrics.let { Pair(it.widthPixels, it.heightPixels) }
        }
    }

    @Suppress("DEPRECATION")
    private fun projectionData(intent: Intent): Intent? = if (Build.VERSION.SDK_INT >= 33) {
        intent.getParcelableExtra(EXTRA_RESULT_DATA, Intent::class.java)
    } else {
        intent.getParcelableExtra(EXTRA_RESULT_DATA)
    }

    companion object {
        private const val RETURN_TO_PLAYER_REQUEST_CODE = 6103
        private const val CHANNEL_ID = "easycode.capture.v2"
        private const val NOTIFICATION_ID = 6102
        const val ACTION_GRANT = "com.easycode.player.capture.GRANT"
        const val ACTION_ARM = "com.easycode.player.capture.ARM"
        const val ACTION_STOP = "com.easycode.player.capture.STOP"
        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"
        const val EXTRA_DESTINATION = "destination"

        @Volatile private var instance: ScreenCaptureService? = null

        fun ready(): Boolean = instance?.projection != null

        fun requireReady(): ScreenCaptureService = instance
            ?.takeIf { it.projection != null }
            ?: throw RuntimeFailure(
                "capture.permission_missing",
                "MediaProjection 尚未授权；请回到 Player 完成系统屏幕捕获授权",
            )

        fun grant(context: Context, resultCode: Int, data: Intent, destination: String = "") {
            AndroidCompat.startForegroundService(context, Intent(context, ScreenCaptureService::class.java).apply {
                action = ACTION_GRANT
                putExtra(EXTRA_RESULT_CODE, resultCode)
                putExtra(EXTRA_RESULT_DATA, data)
                putExtra(EXTRA_DESTINATION, destination)
            })
        }

        fun arm(context: Context, destination: String) {
            AndroidCompat.startForegroundService(context, Intent(context, ScreenCaptureService::class.java).apply {
                action = ACTION_ARM
                putExtra(EXTRA_DESTINATION, destination)
            })
        }

        fun cancel(context: Context) {
            context.startService(Intent(context, ScreenCaptureService::class.java).apply {
                action = ACTION_STOP
            })
        }
    }
}
