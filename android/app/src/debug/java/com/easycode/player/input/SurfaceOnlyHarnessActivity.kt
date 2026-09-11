package com.easycode.player.input

import android.app.Activity
import android.os.Bundle
import android.view.SurfaceView

/** Debug-only real-host fixture: intentionally exposes no semantic control nodes. */
class SurfaceOnlyHarnessActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(SurfaceView(this))
    }
}
