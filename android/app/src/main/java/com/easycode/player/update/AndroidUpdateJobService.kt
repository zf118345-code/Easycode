package com.easycode.player.update

import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.ComponentName
import android.content.Context
import android.os.Build
import com.easycode.player.EasyCodeApplication
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * Native, persisted, network-constrained update check.  It is present in the
 * APK but has no scheduled job when the signed project enables no update domain.
 */
class AndroidUpdateJobService : JobService() {
    private val executor = Executors.newSingleThreadExecutor()

    override fun onStartJob(parameters: JobParameters): Boolean {
        executor.execute {
            val app = applicationContext as EasyCodeApplication
            runCatching {
                val bootstrap = app.packages.bootstrap(importInbox = false)
                if (!bootstrap.available) error(bootstrap.reason.ifBlank { "没有可用的签名项目包" })
                app.updates.configure(app.packages.openActive())
                app.updates.automaticPass()
            }
            jobFinished(parameters, false)
        }
        return true
    }

    override fun onStopJob(parameters: JobParameters): Boolean = true

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }

    companion object {
        private const val JOB_ID = 0x45435550 // "ECUP"
        private val PERIOD_MS = TimeUnit.HOURS.toMillis(6)
        private val FLEX_MS = TimeUnit.HOURS.toMillis(1)

        fun schedule(context: Context, enabled: Boolean) {
            val scheduler = context.getSystemService(Context.JOB_SCHEDULER_SERVICE) as JobScheduler
            if (!enabled) {
                scheduler.cancel(JOB_ID)
                return
            }
            // Re-scheduling an identical periodic job while it is running cancels that
            // very run. Configuration is loaded inside the job, so preserve the existing
            // registration instead of replacing it on every bootstrap.
            val existing = if (Build.VERSION.SDK_INT >= 24) scheduler.getPendingJob(JOB_ID)
            else scheduler.allPendingJobs.firstOrNull { it.id == JOB_ID }
            if (existing != null) return
            val builder = JobInfo.Builder(JOB_ID, ComponentName(context, AndroidUpdateJobService::class.java))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPersisted(true)
            if (Build.VERSION.SDK_INT >= 24) builder.setPeriodic(PERIOD_MS, FLEX_MS)
            else builder.setPeriodic(PERIOD_MS)
            scheduler.schedule(builder.build())
        }
    }
}
