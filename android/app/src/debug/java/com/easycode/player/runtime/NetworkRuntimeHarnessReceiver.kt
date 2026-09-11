package com.easycode.player.runtime

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.easycode.player.file.SafFileRuntime
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.File
import java.net.InetAddress
import java.net.ServerSocket
import java.nio.charset.StandardCharsets
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Debug-only, vendor-neutral real-device harness for the Android network Runtime.
 *
 * Some vendor ROMs reject a separate instrumentation APK.  This explicit
 * receiver keeps verification in the debuggable main APK, does not display a
 * system or application window, and is absent from every release build.
 */
class NetworkRuntimeHarnessReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION) return
        val pending = goAsync()
        Thread({
            val result = runCatching { execute(context.applicationContext) }
                .fold(
                    onSuccess = { mapOf("status" to "passed", "cases" to "request,upload,download") },
                    onFailure = { error -> mapOf(
                        "status" to "failed",
                        "error" to "${error::class.java.simpleName}: ${error.message}",
                    ) },
                )
            val output = File(context.filesDir, RESULT_FILE)
            output.writeText(JSONObject(result).toString(), Charsets.UTF_8)
            Log.i(TAG, output.readText(Charsets.UTF_8))
            pending.finish()
        }, "easycode-network-device-harness").start()
    }

    private fun execute(context: Context) {
        val root = File(context.filesDir, "network-device-harness").apply {
            deleteRecursively()
            check(mkdirs()) { "无法创建真机网络验收目录" }
        }
        val control = RuntimeControl()
        val files = SafFileRuntime(context, root, control, 1, emptySet())
        val runtime = AndroidNetworkRuntime(files, control) { level, category, message, instruction, error ->
            Log.i(TAG, "$level|$category|$instruction|$error|$message")
        }
        verifyRequest(runtime)
        verifyUpload(runtime, root)
        verifyDownload(runtime, root)
    }

    private fun verifyRequest(runtime: AndroidNetworkRuntime) {
        LocalHttpServer(200, "request-ok").use { server ->
            val functionId = "official.network.request"
            val response = runtime.execute(
                "network.request",
                functionId,
                params(functionId, mapOf("method" to "GET", "url" to server.url("/request"))),
                authorization(server.port),
                "device-harness.request",
            ) as Map<*, *>
            check(response["http_response.field.status"] == 200L)
            check(response["http_response.field.body"] == "request-ok")
            check(server.awaitRequest().startsWith("GET /request HTTP/1.1"))
        }
    }

    private fun verifyUpload(runtime: AndroidNetworkRuntime, root: File) {
        val source = File(root, "upload.txt").apply { writeText("android-upload", Charsets.UTF_8) }
        LocalHttpServer(201, "uploaded").use { server ->
            val functionId = "official.network.upload_file"
            val response = runtime.execute(
                "network.upload_file",
                functionId,
                params(functionId, mapOf(
                    "url" to server.url("/upload"),
                    "fields" to listOf(mapOf(
                        "record_type" to "multipart_field",
                        "multipart_field.field.kind" to "file",
                        "multipart_field.field.name" to "asset",
                        "multipart_field.field.file" to fileReference(source, "read"),
                        "multipart_field.field.filename" to "upload.txt",
                    )),
                )),
                authorization(server.port),
                "device-harness.upload",
            ) as Map<*, *>
            check(response["http_response.field.status"] == 201L)
            val request = server.awaitRequest()
            check(request.contains("android-upload"))
            check(request.contains("filename=\"upload.txt\""))
        }
    }

    private fun verifyDownload(runtime: AndroidNetworkRuntime, root: File) {
        val destination = File(root, "download.txt").apply { writeText("old", Charsets.UTF_8) }
        LocalHttpServer(200, "android-download").use { server ->
            val functionId = "official.network.download_file"
            val response = runtime.execute(
                "network.download_file",
                functionId,
                params(functionId, mapOf(
                    "url" to server.url("/download"),
                    "destination" to fileReference(destination, "write"),
                )),
                authorization(server.port),
                "device-harness.download",
            ) as Map<*, *>
            check(response["http_download_result.field.committed"] == true)
            check(destination.readText(Charsets.UTF_8) == "android-download")
            check(server.awaitRequest().startsWith("GET /download HTTP/1.1"))
        }
    }

    private fun params(functionId: String, values: Map<String, Any?>): Map<String, Any?> =
        values.mapKeys { (name, _) -> "$functionId.parameter.$name" }

    private fun authorization(port: Int) = mapOf(
        "schema_version" to 1,
        "rules" to listOf(mapOf(
            "rule_id" to "device-harness:$port",
            "source" to "android-debug-harness",
            "schemes" to listOf("http"),
            "hosts" to listOf("127.0.0.1"),
            "ports" to listOf(port),
            "address_scopes" to listOf("loopback"),
        )),
    )

    private fun fileReference(file: File, access: String) = mapOf(
        "kind" to "file_ref",
        "platform" to "android",
        "source" to "debug-harness",
        "display_name" to file.name,
        "private_path" to file.canonicalPath,
        "authorization_root_id" to "project-data:device-harness",
        "access" to listOf(access),
    )

    private class LocalHttpServer(
        private val responseStatus: Int,
        private val responseBody: String,
    ) : AutoCloseable {
        private val server = ServerSocket(0, 1, InetAddress.getByName("127.0.0.1"))
        private val complete = CountDownLatch(1)
        @Volatile private var request = ""
        @Volatile private var failure: Throwable? = null
        val port: Int get() = server.localPort

        init {
            Thread({ serveOnce() }, "easycode-network-device-server").apply {
                isDaemon = true
                start()
            }
        }

        fun url(path: String): String = "http://127.0.0.1:$port$path"

        fun awaitRequest(): String {
            check(complete.await(10, TimeUnit.SECONDS)) { "本机 HTTP 服务没有收到请求" }
            failure?.let { throw it }
            return request
        }

        private fun serveOnce() {
            try {
                server.accept().use { socket ->
                    socket.soTimeout = 10_000
                    val input = BufferedInputStream(socket.getInputStream())
                    val firstLine = readLine(input)
                    val headers = linkedMapOf<String, String>()
                    while (true) {
                        val line = readLine(input)
                        if (line.isEmpty()) break
                        val separator = line.indexOf(':')
                        if (separator > 0) {
                            headers[line.substring(0, separator).lowercase()] = line.substring(separator + 1).trim()
                        }
                    }
                    val body = ByteArray(headers["content-length"]?.toIntOrNull() ?: 0)
                    var offset = 0
                    while (offset < body.size) {
                        val count = input.read(body, offset, body.size - offset)
                        check(count >= 0) { "HTTP 请求体提前结束" }
                        offset += count
                    }
                    request = buildString {
                        append(firstLine).append('\n')
                        headers.forEach { (name, value) -> append(name).append(": ").append(value).append('\n') }
                        append('\n').append(String(body, StandardCharsets.UTF_8))
                    }
                    val bytes = responseBody.toByteArray(StandardCharsets.UTF_8)
                    BufferedOutputStream(socket.getOutputStream()).use { output ->
                        output.write((
                            "HTTP/1.1 $responseStatus OK\r\nContent-Type: text/plain; charset=utf-8\r\n" +
                                "Content-Length: ${bytes.size}\r\nConnection: close\r\n\r\n"
                        ).toByteArray(StandardCharsets.US_ASCII))
                        output.write(bytes)
                    }
                }
            } catch (error: Throwable) {
                failure = error
            } finally {
                complete.countDown()
            }
        }

        private fun readLine(input: BufferedInputStream): String {
            val bytes = ArrayList<Byte>()
            while (true) {
                val value = input.read()
                check(value >= 0) { "HTTP 请求头提前结束" }
                if (value == '\n'.code) break
                if (value != '\r'.code) bytes += value.toByte()
            }
            return String(bytes.toByteArray(), StandardCharsets.US_ASCII)
        }

        override fun close() {
            runCatching { server.close() }
        }
    }

    companion object {
        private const val ACTION = "com.easycode.player.RUN_NETWORK_HARNESS"
        private const val RESULT_FILE = "network-device-harness-result.json"
        private const val TAG = "EasyCodeNetworkHarness"
    }
}
