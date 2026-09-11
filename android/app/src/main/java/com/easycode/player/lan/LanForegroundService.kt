package com.easycode.player.lan

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.IBinder
import com.easycode.player.EasyCodeApplication
import com.easycode.player.PlayerActivity
import com.easycode.player.R
import com.easycode.player.util.AndroidCompat

/** Keeps the explicitly enabled LAN inbox reachable while Player is in background. */
class LanForegroundService : Service() {
    override fun onCreate() { super.onCreate(); ensureChannel() }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val app = application as EasyCodeApplication
        if (intent?.action == ACTION_STOP) {
            runCatching { app.lan.stop() }; AndroidCompat.stopForeground(this); stopSelf(); return START_NOT_STICKY
        }
        startForeground(NOTIFICATION_ID, notification())
        runCatching { app.lan.start() }.onFailure {
            AndroidCompat.stopForeground(this); stopSelf()
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun notification(): Notification {
        val open = PendingIntent.getActivity(this, 21, Intent(this, PlayerActivity::class.java), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return AndroidCompat.notificationBuilder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("EasyCode 设备协作")
            .setContentText("局域网消息接收已开启")
            .setContentIntent(open)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setOngoing(true)
            .build()
    }

    private fun ensureChannel() {
        AndroidCompat.ensureNotificationChannel(
            this, CHANNEL_ID, "EasyCode 设备协作",
            "仅在用户开启局域网消息接收时保持设备可达", silent = true,
        )
    }

    companion object {
        private const val CHANNEL_ID = "easycode.lan.v1"
        private const val NOTIFICATION_ID = 6102
        private const val ACTION_START = "com.easycode.player.lan.START"
        private const val ACTION_STOP = "com.easycode.player.lan.STOP"
        fun ensureRunning(context: Context) = AndroidCompat.startForegroundService(context, Intent(context, LanForegroundService::class.java).setAction(ACTION_START))
        fun stop(context: Context) = context.startService(Intent(context, LanForegroundService::class.java).setAction(ACTION_STOP))
    }
}

class LanBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action !in setOf(Intent.ACTION_BOOT_COMPLETED, Intent.ACTION_MY_PACKAGE_REPLACED)) return
        val app = context.applicationContext as EasyCodeApplication
        if (app.lan.configuredEnabled) runCatching { LanForegroundService.ensureRunning(context) }
    }
}
