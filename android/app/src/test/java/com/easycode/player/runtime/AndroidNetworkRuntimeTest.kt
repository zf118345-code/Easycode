package com.easycode.player.runtime

import android.content.ContextWrapper
import com.easycode.player.file.SafFileRuntime
import com.sun.net.httpserver.HttpExchange
import com.sun.net.httpserver.HttpServer
import java.io.File
import java.net.InetSocketAddress
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.util.concurrent.atomic.AtomicInteger
import org.junit.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class AndroidNetworkRuntimeTest {
    @Test
    fun typedRequestPreservesRepeatedQueryAndReturnsStableRecord() = fixture { runtime, root ->
        server { exchange ->
            val body = "${exchange.requestMethod}|${exchange.requestURI.rawQuery}"
            exchange.respond(200, body, "text/plain; charset=utf-8", "X-Test" to "one")
        }.use { server ->
            val fid = "official.network.request"
            val result = runtime.execute(
                "network.request",
                fid,
                params(fid, mapOf(
                    "method" to "GET",
                    "url" to server.url("/echo?first=1"),
                    "query" to listOf(pair("tag", "甲"), pair("tag", "乙")),
                    "headers" to emptyList<Any>(),
                )),
                authorization(server),
                "statement.request",
            ) as Map<*, *>
            assertEquals("http_response", result["record_type"])
            assertEquals(200L, result["http_response.field.status"])
            val body = result["http_response.field.body"].toString()
            assertTrue(body.startsWith("GET|first=1&tag="), body)
            assertTrue(body.contains("&tag="), body)
            assertEquals(root, root) // retain the fixture until response consumption completes
        }
    }

    @Test
    fun crossOriginRedirectStripsSensitiveHeaders() = fixture { runtime, _ ->
        val received = arrayOfNulls<String>(2)
        server { exchange ->
            received[1] = exchange.requestHeaders.getFirst("Authorization")
            exchange.respond(200, "ok")
        }.use { destination ->
            server { exchange ->
                received[0] = exchange.requestHeaders.getFirst("Authorization")
                exchange.responseHeaders.add("Location", destination.url("/target"))
                exchange.sendResponseHeaders(302, -1)
                exchange.close()
            }.use { source ->
                val fid = "official.network.request"
                runtime.execute(
                    "network.request",
                    fid,
                    params(fid, mapOf(
                        "method" to "GET",
                        "url" to source.url("/redirect"),
                        "headers" to listOf(pair("Authorization", "Bearer secret", true)),
                        "redirect" to "cross_origin",
                    )),
                    authorization(source, destination),
                    "statement.redirect",
                )
            }
        }
        assertEquals("Bearer secret", received[0])
        assertEquals(null, received[1])
    }

    @Test
    fun multipartUploadStreamsPrivateFile() = fixture { runtime, root ->
        val source = File(root, "upload-测试.txt").apply { writeText("stream-me", Charsets.UTF_8) }
        var received = ""
        server { exchange ->
            received = exchange.requestBody.readBytes().toString(StandardCharsets.UTF_8)
            exchange.respond(201, "uploaded")
        }.use { server ->
            val fid = "official.network.upload_file"
            val result = runtime.execute(
                "network.upload_file",
                fid,
                params(fid, mapOf(
                    "url" to server.url("/upload"),
                    "fields" to listOf(
                        multipartText("note", "hello"),
                        multipartFile("asset", fileReference(source, root, "read"), "上传.txt"),
                    ),
                )),
                authorization(server),
                "statement.upload",
            ) as Map<*, *>
            assertEquals(201L, result["http_response.field.status"])
        }
        assertTrue(received.contains("name=\"note\""), received)
        assertTrue(received.contains("hello"), received)
        assertTrue(received.contains("stream-me"), received)
    }

    @Test
    fun downloadCommitsOnlyTwoXxAndPreservesOldFileOnHttpError() = fixture { runtime, root ->
        val destination = File(root, "download.bin").apply { writeText("old") }
        val fid = "official.network.download_file"
        server { exchange -> exchange.respond(200, "new-content", "application/octet-stream") }.use { success ->
            val result = runtime.execute(
                "network.download_file",
                fid,
                params(fid, mapOf("url" to success.url("/file"), "destination" to fileReference(destination, root, "write"))),
                authorization(success),
                "statement.download.success",
            ) as Map<*, *>
            assertEquals(true, result["http_download_result.field.committed"])
            assertEquals(11L, result["http_download_result.field.bytes_written"])
            assertEquals("new-content", destination.readText())
        }
        destination.writeText("keep-me")
        server { exchange -> exchange.respond(503, "later") }.use { failure ->
            val result = runtime.execute(
                "network.download_file",
                fid,
                params(fid, mapOf("url" to failure.url("/file"), "destination" to fileReference(destination, root, "write"))),
                authorization(failure),
                "statement.download.failure",
            ) as Map<*, *>
            assertEquals(false, result["http_download_result.field.committed"])
            assertEquals(503L, result["http_download_result.field.status"])
            assertEquals("later", result["http_download_result.field.error_body"])
            assertEquals("keep-me", destination.readText())
        }
        assertFalse(root.listFiles().orEmpty().any { it.name.startsWith(".easycode-download-") })
    }

    @Test
    fun binaryRequestAndMissingAuthorizationFailClosed() = fixture { runtime, _ ->
        server { exchange -> exchange.respond(200, "binary", "application/octet-stream") }.use { server ->
            val fid = "official.network.request"
            val args = params(fid, mapOf("url" to server.url("/binary")))
            assertEquals(
                "network.binary_response_unsupported",
                assertFailsWith<RuntimeFailure> {
                    runtime.execute("network.request", fid, args, authorization(server), "statement.binary")
                }.errorId,
            )
            assertEquals(
                "network.permission_denied",
                assertFailsWith<RuntimeFailure> {
                    runtime.execute("network.request", fid, args, null, "statement.denied")
                }.errorId,
            )
        }
    }

    @Test
    fun getAndHeadBodiesFailWithTheSameStableErrorAsWindows() = fixture { runtime, _ ->
        listOf("GET", "HEAD").forEach { method ->
            val fid = "official.network.request"
            val failure = assertFailsWith<RuntimeFailure> {
                runtime.execute(
                    "network.request",
                    fid,
                    params(fid, mapOf(
                        "method" to method,
                        "url" to "http://127.0.0.1:9/not-contacted",
                        "body" to mapOf(
                            "record_type" to "http_body",
                            "http_body.field.kind" to "text",
                            "http_body.field.text" to "unexpected",
                        ),
                    )),
                    mapOf(
                        "schema_version" to 1,
                        "rules" to listOf(mapOf(
                            "rule_id" to "rule.bodyless",
                            "source" to "test",
                            "schemes" to listOf("http"),
                            "hosts" to listOf("127.0.0.1"),
                            "ports" to listOf(9),
                            "address_scopes" to listOf("loopback"),
                        )),
                    ),
                    "statement.bodyless",
                )
            }
            assertEquals("network.body_not_allowed", failure.errorId)
        }
    }

    @Test
    fun unsupportedSafAtomicDestinationIsRejectedBeforeNetwork() = fixture { runtime, _ ->
        val requests = AtomicInteger()
        server { exchange -> requests.incrementAndGet(); exchange.respond(200, "should-not-run") }.use { server ->
            val fid = "official.network.download_file"
            val external = mapOf(
                "kind" to "file_ref",
                "platform" to "android",
                "uri" to "content://provider/document/file",
                "authorization_root_id" to "android-document:test",
                "access" to listOf("write"),
            )
            val failure = assertFailsWith<RuntimeFailure> {
                runtime.execute(
                    "network.download_file",
                    fid,
                    params(fid, mapOf("url" to server.url("/file"), "destination" to external)),
                    authorization(server),
                    "statement.saf",
                )
            }
            assertEquals("file.atomic_commit_unsupported", failure.errorId)
            assertEquals(0, requests.get())
        }
    }

    private fun fixture(block: (AndroidNetworkRuntime, File) -> Unit) {
        val root = Files.createTempDirectory("easycode-android-network").toFile()
        try {
            val context = object : ContextWrapper(null) {
                override fun getFilesDir(): File = root
                override fun getApplicationContext() = this
            }
            val control = RuntimeControl()
            val files = SafFileRuntime(context, root, control, 1, emptySet()) { source, destination ->
                Files.move(
                    source.toPath(),
                    destination.toPath(),
                    java.nio.file.StandardCopyOption.ATOMIC_MOVE,
                    java.nio.file.StandardCopyOption.REPLACE_EXISTING,
                )
            }
            block(AndroidNetworkRuntime(files, control) { _, _, _, _, _ -> }, root)
        } finally {
            root.deleteRecursively()
        }
    }

    private fun server(handler: (HttpExchange) -> Unit): LocalServer = LocalServer(handler)

    private class LocalServer(handler: (HttpExchange) -> Unit) : AutoCloseable {
        private val value = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0).apply {
            createContext("/") { exchange -> handler(exchange) }
            executor = null
            start()
        }
        val port: Int get() = value.address.port
        fun url(path: String) = "http://127.0.0.1:$port$path"
        override fun close() = value.stop(0)
    }

    private fun HttpExchange.respond(status: Int, content: String, contentType: String = "text/plain; charset=utf-8", vararg headers: Pair<String, String>) {
        val bytes = content.toByteArray(StandardCharsets.UTF_8)
        responseHeaders.add("Content-Type", contentType)
        headers.forEach { responseHeaders.add(it.first, it.second) }
        sendResponseHeaders(status, bytes.size.toLong())
        responseBody.use { it.write(bytes) }
        close()
    }

    private fun params(fid: String, values: Map<String, Any?>): Map<String, Any?> =
        values.mapKeys { (name, _) -> "$fid.parameter.$name" }

    private fun pair(name: String, value: String, sensitive: Boolean = false) = mapOf(
        "record_type" to "http_pair",
        "http_pair.field.name" to name,
        "http_pair.field.value" to value,
        "http_pair.field.sensitive" to sensitive,
    )

    private fun multipartText(name: String, value: String) = mapOf(
        "record_type" to "multipart_field",
        "multipart_field.field.kind" to "text",
        "multipart_field.field.name" to name,
        "multipart_field.field.value" to value,
    )

    private fun multipartFile(name: String, reference: Map<String, Any?>, filename: String) = mapOf(
        "record_type" to "multipart_field",
        "multipart_field.field.kind" to "file",
        "multipart_field.field.name" to name,
        "multipart_field.field.file" to reference,
        "multipart_field.field.filename" to filename,
    )

    private fun fileReference(file: File, root: File, access: String) = mapOf(
        "kind" to "file_ref",
        "platform" to "android",
        "source" to "test",
        "display_name" to file.name,
        "private_path" to file.canonicalPath,
        "authorization_root_id" to "project-data:test",
        "access" to listOf(access),
    )

    private fun authorization(vararg servers: LocalServer) = mapOf(
        "schema_version" to 1,
        "rules" to servers.map { server ->
            mapOf(
                "rule_id" to "test:${server.port}",
                "source" to "test",
                "schemes" to listOf("http"),
                "hosts" to listOf("127.0.0.1"),
                "ports" to listOf(server.port),
                "address_scopes" to listOf("loopback"),
            )
        },
    )
}
