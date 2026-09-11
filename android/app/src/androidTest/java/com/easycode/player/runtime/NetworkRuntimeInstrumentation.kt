package com.easycode.player.runtime

import android.app.Instrumentation
import android.app.Activity
import android.os.Bundle
import android.util.Log
import com.easycode.player.file.SafFileRuntime
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.File
import java.net.InetAddress
import java.net.ServerSocket
import java.nio.charset.StandardCharsets
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** Real Android socket/file smoke for the typed network runtime. */
class NetworkRuntimeInstrumentation : Instrumentation() {
    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        start()
    }

    override fun onStart() {
        super.onStart()
        val result = Bundle()
        try {
            val root = File(targetContext.filesDir, "network-instrumentation").apply {
                deleteRecursively()
                mkdirs()
            }
            val control = RuntimeControl()
            val files = SafFileRuntime(targetContext, root, control, 1, emptySet())
            val runtime = AndroidNetworkRuntime(files, control) { level, category, message, instruction, error ->
                Log.i(TAG, "$level|$category|$instruction|$error|$message")
            }

            request(runtime)
            upload(runtime, root)
            download(runtime, root)

            result.putString("easycode_status", "passed")
            result.putString("easycode_cases", "request,upload,download")
            finish(Activity.RESULT_OK, result)
        } catch (error: Throwable) {
            Log.e(TAG, "network instrumentation failed", error)
            result.putString("easycode_status", "failed")
            result.putString("easycode_error", "${error::class.java.simpleName}: ${error.message}")
            finish(Activity.RESULT_CANCELED, result)
        }
    }

    private fun request(runtime: AndroidNetworkRuntime) {
        LocalHttpServer(200, "request-ok").use { server ->
            val fid = "official.network.request"
            val value = runtime.execute(
                "network.request",
                fid,
                params(fid, mapOf("method" to "GET", "url" to server.url("/request?one=1"))),
                authorization(server.port),
                "instrumentation.request",
            ) as Map<*, *>
            check(value["http_response.field.status"] == 200L)
            check(value["http_response.field.body"] == "request-ok")
            check(server.awaitRequest().startsWith("GET /request?one=1 HTTP/1.1"))
        }
    }

    private fun upload(runtime: AndroidNetworkRuntime, root: File) {
        val source = File(root, "upload.txt").apply { writeText("android-upload", Charsets.UTF_8) }
        LocalHttpServer(201, "uploaded").use { server ->
            val fid = "official.network.upload_file"
            val value = runtime.execute(
                "network.upload_file",
                fid,
                params(fid, mapOf(
                    "url" to server.url("/upload"),
                    "fields" to listOf(mapOf(
                        "record_type" to "multipart_field",
                        "multipart_field.field.kind" to "file",
                        "multipart_field.field.name" to "asset",
                        "multipart_field.field.file" to fileReference(source, root, "read"),
                        "multipart_field.field.filename" to "upload.txt",
                    )),
                )),
                authorization(server.port),
                "instrumentation.upload",
            ) as Map<*, *>
            check(value["http_response.field.status"] == 201L)
            val request = server.awaitRequest()
            check(request.contains("android-upload"))
            check(request.contains("filename=\"upload.txt\""))
        }
    }

    private fun download(runtime: AndroidNetworkRuntime, root: File) {
        val destination = File(root, "download.txt").apply { writeText("old", Charsets.UTF_8) }
        LocalHttpServer(200, "android-download").use { server ->
            val fid = "official.network.download_file"
            val value = runtime.execute(
                "network.download_file",
                fid,
                params(fid, mapOf(
                    "url" to server.url("/download"),
                    "destination" to fileReference(destination, root, "write"),
                )),
                authorization(server.port),
                "instrumentation.download",
            ) as Map<*, *>
            check(value["http_download_result.field.committed"] == true)
            check(destination.readText(Charsets.UTF_8) == "android-download")
            check(server.awaitRequest().startsWith("GET /download HTTP/1.1"))
        }
    }

    private fun params(functionId: String, values: Map<String, Any?>): Map<String, Any?> =
        values.mapKeys { (name, _) -> "$functionId.parameter.$name" }

    private fun authorization(port: Int) = mapOf(
        "schema_version" to 1,
        "rules" to listOf(mapOf(
            "rule_id" to "instrumentation:$port",
            "source" to "android-instrumentation",
            "schemes" to listOf("http"),
            "hosts" to listOf("127.0.0.1"),
            "ports" to listOf(port),
            "address_scopes" to listOf("loopback"),
        )),
    )

    private fun fileReference(file: File, root: File, access: String) = mapOf(
        "kind" to "file_ref",
        "platform" to "android",
        "source" to "instrumentation",
        "display_name" to file.name,
        "private_path" to file.canonicalPath,
        "authorization_root_id" to "project-data:instrumentation",
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
            Thread({ serveOnce() }, "easycode-network-instrumentation").apply {
                isDaemon = true
                start()
            }
        }

        fun url(path: String): String = "http://127.0.0.1:$port$path"

        fun awaitRequest(): String {
            check(complete.await(10, TimeUnit.SECONDS)) { "本机 HTTP 测试服务没有收到请求" }
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
                        if (separator > 0) headers[line.substring(0, separator).lowercase()] = line.substring(separator + 1).trim()
                    }
                    val length = headers["content-length"]?.toIntOrNull() ?: 0
                    val body = ByteArray(length)
                    var offset = 0
                    while (offset < length) {
                        val count = input.read(body, offset, length - offset)
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
                        output.write(
                            "HTTP/1.1 $responseStatus OK\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: ${bytes.size}\r\nConnection: close\r\n\r\n"
                                .toByteArray(StandardCharsets.US_ASCII),
                        )
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
        private const val TAG = "EasyCodeNetworkHarness"
    }
}
