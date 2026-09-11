package com.easycode.player.schedule

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.easycode.player.EasyCodeApplication

class ScheduleAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != AndroidScheduleCoordinator.ACTION_ALARM) return
        val scheduleId = intent.getStringExtra("schedule_id").orEmpty()
        if (scheduleId.isBlank()) return
        val pending = goAsync()
        Thread({
            try { (context.applicationContext as EasyCodeApplication).schedules.alarm(scheduleId) }
            catch (error: Exception) { Log.e("EasyCodeSchedule", "系统计划交接失败：$scheduleId", error) }
            finally { pending.finish() }
        }, "easycode-schedule-receiver").apply { isDaemon = false; start() }
    }
}
