package com.easycode.player.util

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build

internal object AndroidCompat {
    @Suppress("DEPRECATION")
    fun notificationBuilder(context: Context, channelId: String): Notification.Builder =
        if (Build.VERSION.SDK_INT >= 26) Notification.Builder(context, channelId)
        else Notification.Builder(context)

    fun notificationManager(context: Context): NotificationManager =
        context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

    fun startForegroundService(context: Context, intent: Intent) {
        if (Build.VERSION.SDK_INT >= 26) context.startForegroundService(intent)
        else context.startService(intent)
    }

    @Suppress("DEPRECATION")
    fun stopForeground(service: Service) {
        if (Build.VERSION.SDK_INT >= 24) service.stopForeground(Service.STOP_FOREGROUND_REMOVE)
        else service.stopForeground(true)
    }

    fun ensureNotificationChannel(
        context: Context,
        channelId: String,
        name: String,
        description: String,
        silent: Boolean = false,
    ) {
        if (Build.VERSION.SDK_INT >= 26) createNotificationChannel26(
            notificationManager(context), channelId, name, description, silent,
        )
    }

    @android.annotation.TargetApi(26)
    private fun createNotificationChannel26(
        manager: NotificationManager,
        channelId: String,
        name: String,
        description: String,
        silent: Boolean,
    ) {
        manager.createNotificationChannel(
            NotificationChannel(channelId, name, NotificationManager.IMPORTANCE_LOW).apply {
                this.description = description
                if (silent) setSound(null, null)
            },
        )
    }
}
