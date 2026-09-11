package com.easycode.player.schedule

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.easycode.player.EasyCodeApplication

/** Accessing the application-owned coordinator re-registers all future alarms. */
class ScheduleBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action !in setOf(Intent.ACTION_BOOT_COMPLETED, Intent.ACTION_MY_PACKAGE_REPLACED)) return
        (context.applicationContext as EasyCodeApplication).schedules
    }
}
