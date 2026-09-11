plugins {
    id("com.android.library")
}

android {
    namespace = "com.easycode.extension.api"
    compileSdk = 37

    defaultConfig {
        minSdk = 21
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
