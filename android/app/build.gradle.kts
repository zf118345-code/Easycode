import groovy.json.JsonSlurper
import java.security.MessageDigest
import java.util.zip.ZipFile
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
}

fun String.sha256(): String = MessageDigest.getInstance("SHA-256")
    .digest(toByteArray(Charsets.UTF_8))
    .joinToString("") { "%02x".format(it) }

val releaseSigningProperties = mapOf(
    "storeFile" to providers.gradleProperty("easycode.release.storeFile").orNull,
    "storePassword" to providers.gradleProperty("easycode.release.storePassword").orNull,
    "keyAlias" to providers.gradleProperty("easycode.release.keyAlias").orNull,
    "keyPassword" to providers.gradleProperty("easycode.release.keyPassword").orNull,
)
// Gradle may retain test filters and -P values in the raw start parameters.
// Match only the terminal task selector so a test class in a `.bundle` package
// or a web-assets path containing `release` cannot accidentally enable APK
// assembly / production-signing gates.
val requestedTaskNames = gradle.startParameter.taskNames.map { selector ->
    selector.substringAfterLast(':')
}
val apkAssemblyRequested = requestedTaskNames.any { taskName ->
    taskName.startsWith("assemble", ignoreCase = true) ||
        taskName.startsWith("bundle", ignoreCase = true)
}
val releaseRequested = requestedTaskNames.any { taskName ->
    (taskName.startsWith("assemble", ignoreCase = true) ||
        taskName.startsWith("bundle", ignoreCase = true)) &&
        taskName.contains("release", ignoreCase = true)
}
val applicationUpdatesEnabled = providers.gradleProperty("easycode.applicationUpdatesEnabled")
    .map(String::toBooleanStrict)
    .orElse(false)
val easyCodeVersionCode = providers.gradleProperty("easycode.versionCode")
    .map(String::toInt)
    .orElse(1)
val easyCodeVersionName = providers.gradleProperty("easycode.versionName")
    .orElse("6.0.0")
val easyCodeMinSdk = providers.gradleProperty("easycode.minSdk")
    .map(String::toInt)
    .orElse(21)
val easyCodeInstrumentationRunner = providers.gradleProperty("easycode.instrumentationRunner")
    .orElse("com.easycode.player.input.ControlVerificationInstrumentation")
val easyCodeExtensionJars = providers.gradleProperty("easycode.extensionJars").orNull
    ?.takeIf(String::isNotBlank)
    ?.let(::file)
val easyCodeManifest = providers.gradleProperty("easycode.manifest").orNull
    ?.takeIf(String::isNotBlank)
    ?.let(::file)
if (easyCodeMinSdk.get() !in 21..37) {
    throw GradleException("[AND-SDK-001] easycode.minSdk 必须位于 API 21..37")
}
val missingReleaseSigning = releaseSigningProperties.filterValues { it.isNullOrBlank() }.keys
if (releaseRequested && missingReleaseSigning.isNotEmpty()) {
    throw GradleException(
        "[AND-SIGN-001] release 需要项目外部签名参数：" +
            missingReleaseSigning.sorted().joinToString(", ")
    )
}

android {
    namespace = "com.easycode.player"
    compileSdk = 37
    buildToolsVersion = "37.0.0"

    defaultConfig {
        applicationId = "com.easycode.player"
        minSdk = easyCodeMinSdk.get()
        targetSdk = 37
        versionCode = easyCodeVersionCode.get()
        versionName = easyCodeVersionName.get()
        testInstrumentationRunner = easyCodeInstrumentationRunner.get()
        buildConfigField("String", "RUNTIME_CONTRACT", "\"easycode.android-runtime.v1\"")
        buildConfigField("boolean", "APPLICATION_UPDATES_ENABLED", applicationUpdatesEnabled.get().toString())
        buildConfigField("int", "MINIMUM_WEBVIEW_MAJOR", "64")
    }

    sourceSets.getByName("main").manifest.srcFile(
        easyCodeManifest ?: file("src/main/AndroidManifest.xml")
    )

    signingConfigs {
        if (missingReleaseSigning.isEmpty()) {
            create("externalRelease") {
                val configuredStore = file(releaseSigningProperties.getValue("storeFile")!!)
                if (!configuredStore.isFile) {
                    throw GradleException("[AND-SIGN-002] release keystore 不存在：$configuredStore")
                }
                storeFile = configuredStore
                storePassword = releaseSigningProperties.getValue("storePassword")
                keyAlias = releaseSigningProperties.getValue("keyAlias")
                keyPassword = releaseSigningProperties.getValue("keyPassword")
                enableV1Signing = true
                enableV2Signing = true
                enableV3Signing = true
                enableV4Signing = false
            }
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
            isDebuggable = true
        }
        release {
            isDebuggable = false
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            if (missingReleaseSigning.isEmpty()) {
                signingConfig = signingConfigs.getByName("externalRelease")
            }
        }
    }

    flavorDimensions += "deviceAbi"
    productFlavors {
        create("production") {
            dimension = "deviceAbi"
            ndk.abiFilters += setOf("arm64-v8a", "armeabi-v7a")
            buildConfigField("String", "DISTRIBUTION_KIND", "\"production-arm\"")
        }
        create("emulator") {
            dimension = "deviceAbi"
            applicationIdSuffix = ".emulator"
            versionNameSuffix = "-emulator"
            ndk.abiFilters += setOf("x86_64")
            buildConfigField("String", "DISTRIBUTION_KIND", "\"development-x86_64\"")
        }
    }

    buildFeatures {
        buildConfig = true
    }
    compileOptions {
        isCoreLibraryDesugaringEnabled = true
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
    packaging {
        resources.excludes += setOf(
            "META-INF/DEPENDENCIES",
            "META-INF/LICENSE*",
            "META-INF/NOTICE*",
            "META-INF/versions/9/OSGI-INF/MANIFEST.MF",
        )
    }
    // `preBuild` below owns generation.  Resolve to a concrete directory so
    // AGP 9 does not mistake this static source-set declaration for an
    // untracked Provider-backed generated source.
    sourceSets["main"].assets.srcDir(
        layout.buildDirectory.dir("generated/easycodeAssets").get().asFile,
    )
}

dependencies {
    implementation(project(":extension-api"))
    if (easyCodeExtensionJars != null) {
        implementation(fileTree(easyCodeExtensionJars) { include("*.jar") })
    }
    if (applicationUpdatesEnabled.get()) {
        implementation(project(":application-update-capability"))
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
        freeCompilerArgs.add("-Xjvm-default=all")
    }
}

androidComponents {
    beforeVariants { variant ->
        if (
            variant.buildType == "release" &&
            variant.productFlavors.any { it.second == "emulator" }
        ) {
            variant.enable = false
        }
    }
}

val generatedAssets = layout.buildDirectory.dir("generated/easycodeAssets")
val prepareEasyCodeAssets = tasks.register("prepareEasyCodeAssets") {
    val bundleProperty = providers.gradleProperty("easycode.player.bundle")
    val trustProperty = providers.gradleProperty("easycode.player.trustRoot")
    val webAssetsProperty = providers.gradleProperty("easycode.player.webAssets")
    val extensionRegistryProperty = providers.gradleProperty("easycode.extensionRegistry")
    inputs.property("bundlePath", bundleProperty.orElse(""))
    inputs.property("trustRootPath", trustProperty.orElse(""))
    inputs.property("webAssetsPath", webAssetsProperty.orElse(""))
    inputs.property("extensionRegistryPath", extensionRegistryProperty.orElse(""))
    inputs.files(bundleProperty.map { raw -> raw.takeIf(String::isNotBlank)?.let(::file) })
        .withPropertyName("playerBundleContent")
        .withPathSensitivity(PathSensitivity.NONE)
        .optional()
    inputs.files(trustProperty.map { raw -> raw.takeIf(String::isNotBlank)?.let(::file) })
        .withPropertyName("playerTrustRootContent")
        .withPathSensitivity(PathSensitivity.NONE)
        .optional()
    inputs.files(webAssetsProperty.map { raw -> raw.takeIf(String::isNotBlank)?.let(::file) })
        .withPropertyName("playerWebAssetContents")
        .withPathSensitivity(PathSensitivity.RELATIVE)
        .optional()
    inputs.files(extensionRegistryProperty.map { raw -> raw.takeIf(String::isNotBlank)?.let(::file) })
        .withPropertyName("extensionRegistryContent")
        .withPathSensitivity(PathSensitivity.NONE)
        .optional()
    outputs.dir(generatedAssets)
    doLast {
        val root = generatedAssets.get().asFile
        root.deleteRecursively()
        val player = root.resolve("player")
        player.mkdirs()
        val webAssets = webAssetsProperty.orNull?.takeIf { it.isNotBlank() }?.let(::file)
        if (webAssets == null) {
            if (apkAssemblyRequested) {
                throw GradleException("[AND-WEB-001] Android Player APK 必须提供编译后的共享 Player Web 资源")
            }
            // JVM unit compilation does not launch WebView. A clearly marked
            // inert document keeps test tasks independent from Node; every APK
            // assemble path above still fails closed without the real bundle.
            root.resolve("player-web").mkdirs()
            root.resolve("player-web/player.html").writeText("<!doctype html><title>unit-test-only</title>")
        } else {
            if (!webAssets.isDirectory || !webAssets.resolve("player.html").isFile) {
                throw GradleException("[AND-WEB-001] 共享 Player Web 资源不存在或缺少 player.html：$webAssets")
            }
            val forbiddenWeb = webAssets.walkTopDown().filter { candidate ->
                candidate.isFile && (
                    candidate.extension.lowercase() in setOf("map", "vue", "ts", "tsx") ||
                        candidate.invariantSeparatorsPath.contains("/src/")
                )
            }.firstOrNull()
            if (forbiddenWeb != null) {
                throw GradleException("[AND-WEB-002] 共享 Player Web 资源包含源码或 source map：$forbiddenWeb")
            }
            webAssets.copyRecursively(root.resolve("player-web"), overwrite = true)
        }
        val bundlePath = bundleProperty.orNull?.takeIf { it.isNotBlank() }?.let(::file)
        val trustPath = trustProperty.orNull?.takeIf { it.isNotBlank() }?.let(::file)
        if ((bundlePath == null) != (trustPath == null)) {
            throw GradleException("[AND-BUNDLE-001] bundle 与 trustRoot 必须同时提供")
        }
        if (bundlePath != null && trustPath != null) {
            if (!bundlePath.isFile || !trustPath.isFile) {
                throw GradleException("[AND-BUNDLE-002] Player 包或信任根不存在")
            }
            if (releaseRequested) {
                val report = ZipFile(bundlePath).use { archive ->
                    val entry = archive.getEntry("publish-report.json")
                        ?: throw GradleException("[AND-REL-001] release Player 包缺少 publish-report.json")
                    @Suppress("UNCHECKED_CAST")
                    JsonSlurper().parseText(archive.getInputStream(entry).bufferedReader(Charsets.UTF_8).readText())
                        as? Map<String, Any?>
                        ?: throw GradleException("[AND-REL-001] release 发布报告格式无效")
                }
                val supported = report["supported_platforms"] as? Collection<*>
                if (report["valid"] != true || supported?.contains("android_local") != true) {
                    throw GradleException(
                        "[AND-REL-001] ADR-053：release 仅接受已通过断线真机 Harness 的 android_local 发布报告",
                    )
                }
            }
            bundlePath.copyTo(player.resolve("project.ecplayer"), overwrite = true)
            trustPath.copyTo(player.resolve("trust-root.json"), overwrite = true)
            val extensionRegistry = extensionRegistryProperty.orNull
                ?.takeIf { it.isNotBlank() }
                ?.let(::file)
                ?: throw GradleException("[AND-EXT-001] Android APK 必须提供构建期扩展注册表")
            if (!extensionRegistry.isFile) {
                throw GradleException("[AND-EXT-001] Android 扩展注册表不存在：$extensionRegistry")
            }
            extensionRegistry.copyTo(player.resolve("extensions.json"), overwrite = true)
            player.resolve("bootstrap.json").writeText(
                "{\"schema_version\":1,\"embedded\":true," +
                    "\"bundle_path\":\"player/project.ecplayer\"," +
                    "\"trust_root_path\":\"player/trust-root.json\"," +
                    "\"source_identity\":\"${bundlePath.absolutePath.sha256()}\"}",
                Charsets.UTF_8,
            )
        } else {
            if (releaseRequested) {
                throw GradleException("[AND-BUNDLE-003] release 必须内嵌签名 Player 包与固定信任根")
            }
            player.resolve("bootstrap.json").writeText(
                "{\"schema_version\":1,\"embedded\":false}",
                Charsets.UTF_8,
            )
        }
    }
}

tasks.named("preBuild").configure {
    dependsOn(prepareEasyCodeAssets)
}

tasks.matching { it.name == "assembleProductionRelease" }.configureEach {
    doLast {
        val apk = layout.buildDirectory.file("outputs/apk/production/release/app-production-release.apk").get().asFile
        if (!apk.isFile) throw GradleException("[AND-ABI-001] release APK 产物不存在，无法验证 ABI 闭包")
        val declared = ZipFile(apk).use { archive ->
            archive.entries().asSequence()
                .map { it.name.replace('\\', '/') }
                .mapNotNull { Regex("^lib/([^/]+)/[^/]+\\.so$").matchEntire(it)?.groupValues?.get(1) }
                .toSortedSet()
        }
        val expected = sortedSetOf("arm64-v8a", "armeabi-v7a")
        if (declared != expected) {
            throw GradleException(
                "[AND-ABI-001] release 原生 ABI 闭包必须精确为 $expected，实际为 ${declared.ifEmpty { sortedSetOf("<none>") }}；" +
                    "纯 JVM 候选不能冒充正式 ABI 验收",
            )
        }
    }
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs_nio:2.0.1")
    implementation("com.google.code.gson:gson:2.13.2")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.bouncycastle:bcprov-jdk18on:1.82")
    // The Android Player must keep OCR available with no Google Play/runtime
    // download.  This is the bundled Chinese recognizer; it also recognizes
    // Latin text and therefore implements the public "自动（中英文）" mode.
    implementation("com.google.mlkit:text-recognition-chinese:16.0.1")

    testImplementation(kotlin("test"))
    testImplementation("junit:junit:4.13.2")
}
