package com.easycode.player.update

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import com.easycode.player.EasyCodeApplication
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.int
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonObject
import java.io.File
import java.security.MessageDigest

internal class AndroidApkInstaller(private val context: Context) {
    fun begin(file: File, release: JsonObject, artifact: JsonObject): JsonObject {
        if (!file.isFile) fail("UPD-APPLY-001", "暂存 APK 已丢失")
        if (Build.VERSION.SDK_INT >= 26 && !context.packageManager.canRequestPackageInstalls()) {
            context.startActivity(Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:${context.packageName}"),
            ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            return JsonObject().apply {
                addProperty("submitted", false)
                addProperty("permission_requested", true)
            }
        }
        verifyPackage(file, artifact)
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL).apply {
            setAppPackageName(context.packageName)
            if (Build.VERSION.SDK_INT >= 31) setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_REQUIRED)
        }
        val installer = context.packageManager.packageInstaller
        val sessionId = installer.createSession(params)
        try {
            installer.openSession(sessionId).use { session ->
                file.inputStream().use { input ->
                    session.openWrite("EasyCode-${release.string("release_id")}.apk", 0, file.length()).use { output ->
                        input.copyTo(output, 128 * 1024)
                        session.fsync(output)
                    }
                }
                val callback = Intent(context, AndroidUpdateInstallReceiver::class.java).apply {
                    action = ACTION_RESULT
                    putExtra(EXTRA_DOMAIN, "player_application")
                    putExtra(EXTRA_RELEASE_ID, release.string("release_id"))
                    putExtra(EXTRA_RELEASE_SEQUENCE, release.int("release_sequence"))
                }
                val sender = PendingIntent.getBroadcast(
                    context,
                    sessionId,
                    callback,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
                ).intentSender
                session.commit(sender)
            }
        } catch (error: Exception) {
            runCatching { installer.abandonSession(sessionId) }
            throw AndroidUpdateFailure("UPD-PLATFORM-001", "无法提交 Android 安装会话：${error.message}", error)
        }
        return JsonObject().apply {
            addProperty("submitted", true)
            addProperty("session_id", sessionId)
        }
    }

    private fun verifyPackage(file: File, artifact: JsonObject) {
        val archive = (if (Build.VERSION.SDK_INT >= 33) {
            context.packageManager.getPackageArchiveInfo(file.absolutePath, PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong()))
        } else if (Build.VERSION.SDK_INT >= 28) {
            @Suppress("DEPRECATION")
            context.packageManager.getPackageArchiveInfo(file.absolutePath, PackageManager.GET_SIGNING_CERTIFICATES)
        } else {
            @Suppress("DEPRECATION")
            context.packageManager.getPackageArchiveInfo(file.absolutePath, PackageManager.GET_SIGNATURES)
        }) ?: fail("UPD-APK-001", "下载产物不是有效 APK")
        if (archive.packageName != context.packageName) fail("UPD-APK-002", "APK 包名与当前 Player 不一致")
        val version = packageVersionCode(archive)
        if (version != artifact.int("android_version_code").toLong()) fail("UPD-APK-003", "APK versionCode 与签名元数据不一致")
        val installed = (if (Build.VERSION.SDK_INT >= 33) {
            context.packageManager.getPackageInfo(context.packageName, PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong()))
        } else if (Build.VERSION.SDK_INT >= 28) {
            @Suppress("DEPRECATION")
            context.packageManager.getPackageInfo(context.packageName, PackageManager.GET_SIGNING_CERTIFICATES)
        } else {
            @Suppress("DEPRECATION")
            context.packageManager.getPackageInfo(context.packageName, PackageManager.GET_SIGNATURES)
        }) ?: fail("UPD-APK-001", "无法读取当前 Player 安装信息")
        val archiveDigests = signingDigests(archive)
        val installedDigests = signingDigests(installed)
        val declared = artifact.string("android_certificate_sha256")
        if (declared !in archiveDigests) fail("UPD-APK-004", "APK 签名证书与签名元数据不一致")
        if (archiveDigests.intersect(installedDigests).isEmpty()) fail("UPD-APK-005", "APK 签名证书与已安装 Player 不一致")
        if (version <= packageVersionCode(installed)) fail("UPD-APK-006", "APK versionCode 必须高于当前 Player")
    }

    private fun packageVersionCode(info: android.content.pm.PackageInfo): Long =
        if (Build.VERSION.SDK_INT >= 28) info.longVersionCode
        else {
            @Suppress("DEPRECATION")
            info.versionCode.toLong()
        }

    private fun signingDigests(info: android.content.pm.PackageInfo): Set<String> {
        val signatures = if (Build.VERSION.SDK_INT >= 28) {
            val signing = info.signingInfo ?: return emptySet()
            if (signing.hasMultipleSigners()) signing.apkContentsSigners.toList() else signing.signingCertificateHistory.toList()
        } else {
            @Suppress("DEPRECATION") info.signatures?.toList().orEmpty()
        }
        return signatures.mapTo(linkedSetOf()) { signature ->
            MessageDigest.getInstance("SHA-256").digest(signature.toByteArray()).joinToString("") { "%02x".format(it) }
        }
    }

    private fun fail(id: String, message: String): Nothing = throw AndroidUpdateFailure(id, message)

    companion object {
        const val ACTION_RESULT = "com.easycode.player.update.INSTALL_RESULT"
        const val EXTRA_DOMAIN = "domain"
        const val EXTRA_RELEASE_ID = "release_id"
        const val EXTRA_RELEASE_SEQUENCE = "release_sequence"
    }
}

class AndroidUpdateInstallReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != AndroidApkInstaller.ACTION_RESULT) return
        val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)
        if (status == PackageInstaller.STATUS_PENDING_USER_ACTION) {
            val confirmation = if (Build.VERSION.SDK_INT >= 33) {
                intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java)
            } else {
                @Suppress("DEPRECATION") intent.getParcelableExtra(Intent.EXTRA_INTENT)
            }
            confirmation?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)?.let(context::startActivity)
            return
        }
        val app = context.applicationContext as? EasyCodeApplication ?: return
        app.updates.onPackageInstallResult(
            intent.getStringExtra(AndroidApkInstaller.EXTRA_DOMAIN).orEmpty(),
            intent.getStringExtra(AndroidApkInstaller.EXTRA_RELEASE_ID).orEmpty(),
            intent.getIntExtra(AndroidApkInstaller.EXTRA_RELEASE_SEQUENCE, 0),
            status,
            intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE).orEmpty(),
        )
    }
}
