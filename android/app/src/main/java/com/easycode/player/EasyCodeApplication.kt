package com.easycode.player

import android.app.Application
import com.easycode.player.bundle.ContentPackageRepository
import com.easycode.player.lan.AndroidLanControl
import com.easycode.player.lan.AndroidLanDirectory
import com.easycode.player.lan.LanForegroundService
import com.easycode.player.message.AndroidMessageRuntime
import com.easycode.player.profile.ProfileStore
import com.easycode.player.recording.AndroidFrameRecorder
import com.easycode.player.runtime.RuntimeController
import com.easycode.player.schedule.AndroidScheduleCoordinator
import com.easycode.player.update.AndroidUpdateManager
import java.io.File

class EasyCodeApplication : Application() {
    lateinit var packages: ContentPackageRepository
        private set
    lateinit var profiles: ProfileStore
        private set
    lateinit var runtime: RuntimeController
        private set
    lateinit var recorder: AndroidFrameRecorder
        private set
    lateinit var schedules: AndroidScheduleCoordinator
        private set
    lateinit var updates: AndroidUpdateManager
        private set
    internal lateinit var lan: AndroidLanControl
        private set
    internal lateinit var messages: AndroidMessageRuntime
        private set

    override fun onCreate() {
        super.onCreate()
        // The extension worker has a deliberately narrow lifecycle. Starting
        // it must not also start LAN discovery, schedules or the main Runtime.
        if (currentProcessName().endsWith(":extension_worker")) return
        packages = ContentPackageRepository(this)
        profiles = ProfileStore(this)
        runtime = RuntimeController(this)
        updates = AndroidUpdateManager(this, packages, runtime)
        recorder = AndroidFrameRecorder(this)
        runtime.observe(recorder)
        lan = AndroidLanControl(AndroidLanDirectory(this))
        messages = AndroidMessageRuntime(this, profiles, { packages.openActive() }, lan)
        if (lan.configuredEnabled) runCatching { LanForegroundService.ensureRunning(this) }
        schedules = AndroidScheduleCoordinator(this)
    }

    private fun currentProcessName(): String = runCatching {
        File("/proc/self/cmdline").readBytes()
            .takeWhile { it.toInt() != 0 }
            .toByteArray()
            .toString(Charsets.UTF_8)
    }.getOrDefault(packageName)
}

val android.app.Activity.easyCodeApp: EasyCodeApplication
    get() = application as EasyCodeApplication
