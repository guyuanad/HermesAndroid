package com.hermesandroid

import android.content.Intent
import android.os.Bundle
import android.util.Log
import com.facebook.react.ReactActivity
import com.facebook.react.ReactActivityDelegate
import com.facebook.react.defaults.DefaultReactActivityDelegate

class MainActivity : ReactActivity() {

    companion object {
        private const val TAG = "MainActivity"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Start the Python backend service
        startHermesService()
    }

    private fun startHermesService() {
        val serviceIntent = Intent(this, HermesService::class.java).apply {
            action = HermesService.ACTION_START
        }
        try {
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                startForegroundService(serviceIntent)
            } else {
                startService(serviceIntent)
            }
            Log.i(TAG, "Hermes service start requested")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start Hermes service", e)
        }
    }

    override fun onDestroy() {
        // Don't stop the service when activity is destroyed
        // The service runs independently in the background
        super.onDestroy()
    }

    override fun getMainComponentName(): String = "HermesAndroid"

    override fun createReactActivityDelegate(): ReactActivityDelegate {
        return DefaultReactActivityDelegate(
            this,
            mainComponentName,
            fabricEnabled = true,
            concurrentReactEnabled = true
        )
    }
}
