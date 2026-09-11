package com.easycode.player.runtime

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import android.os.PowerManager
import com.easycode.player.EasyCodeApplication
import com.easycode.player.PlayerActivity
import com.easycode.player.R
import com.easycode.player.util.AndroidCompat

class RuntimeForegroundService : Service(), RuntimeObserver {
    private var wakeLock: PowerManager.WakeLock? = null

    override fun onCreate() {
        super.onCreate()
        ensureChannel()
        (application as EasyCodeApplication).runtime.observe(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val runtime = (application as EasyCodeApplication).runtime
        when (intent?.action) {
            ACTION_PAUSE -> runCatching { runtime.pause() }
            ACTION_RESUME -> runCatching { runtime.resume() }
            ACTION_STOP -> runCatching { runtime.stop() }
        }
        startForeground(NOTIFICATION_ID, notification(runtime.state()))
        updateWakeLock(runtime.state())
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        (application as EasyCodeApplication).runtime.removeObserver(this)
        wakeLock?.takeIf { it.isHeld }?.release()
        wakeLock = null
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun stateChanged(state: RunState) {
        AndroidCompat.notificationManager(this).notify(NOTIFICATION_ID, notification(state))
        updateWakeLock(state)
        if (!state.active && state.status != RunStatus.IDLE) stopSelf()
    }

    override fun event(event: RuntimeEvent) = Unit

    private fun notification(state: RunState): Notification {
        val content = PendingIntent.getActivity(
            this,
            1,
            Intent(this, PlayerActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val text = when (state.status) {
            RunStatus.STARTING -> "正在启动"
            RunStatus.RUNNING -> "正在运行 · ${state.currentInstructionId.ifBlank { "准备步骤" }}"
            RunStatus.PAUSED -> "已暂停"
            RunStatus.STOPPING -> "正在停止"
            RunStatus.COMPLETED -> "运行完成"
            RunStatus.FAILED -> "运行失败 · ${state.errorMessage}"
            RunStatus.STOPPED -> "已停止"
            RunStatus.IDLE -> "空闲"
        }
        return AndroidCompat.notificationBuilder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(getString(R.string.runtime_notification_title))
            .setContentText(text)
            .setStyle(Notification.BigTextStyle().bigText(text))
            .setContentIntent(content)
            .setOngoing(state.active)
            .setCategory(Notification.CATEGORY_SERVICE)
            .apply {
                if (state.status == RunStatus.RUNNING) addAction(action("暂停", ACTION_PAUSE, 2))
                if (state.status == RunStatus.PAUSED) addAction(action("继续", ACTION_RESUME, 3))
                if (state.active) addAction(action("停止", ACTION_STOP, 4))
            }
            .build()
    }

    private fun action(label: String, command: String, requestCode: Int): Notification.Action =
        Notification.Action.Builder(
            R.drawable.ic_notification,
            label,
            PendingIntent.getService(
                this,
                requestCode,
                Intent(this, RuntimeForegroundService::class.java).setAction(command),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            ),
        ).build()

    private fun updateWakeLock(state: RunState) {
        if (state.active) {
            if (wakeLock?.isHeld != true) {
                wakeLock = (getSystemService(Context.POWER_SERVICE) as PowerManager)
                    .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "EasyCode:Runtime")
                    .apply { acquire(12 * 60 * 60 * 1000L) }
            }
        } else {
            wakeLock?.takeIf { it.isHeld }?.release()
            wakeLock = null
        }
    }

    private fun ensureChannel() {
        AndroidCompat.ensureNotificationChannel(
            this, CHANNEL_ID, "EasyCode 任务运行",
            "离线任务状态、暂停、继续与停止",
        )
    }

    companion object {
        private const val CHANNEL_ID = "easycode.runtime.v1"
        private const val NOTIFICATION_ID = 6101
        private const val ACTION_ENSURE = "com.easycode.player.runtime.ENSURE"
        private const val ACTION_PAUSE = "com.easycode.player.runtime.PAUSE"
        private const val ACTION_RESUME = "com.easycode.player.runtime.RESUME"
        private const val ACTION_STOP = "com.easycode.player.runtime.STOP"

        fun ensureRunning(context: Context) {
            AndroidCompat.startForegroundService(context, Intent(context, RuntimeForegroundService::class.java).setAction(ACTION_ENSURE))
        }

        fun stopIfIdle(context: Context) {
            context.stopService(Intent(context, RuntimeForegroundService::class.java))
        }
    }
}
