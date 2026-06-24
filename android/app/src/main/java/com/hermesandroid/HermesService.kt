package com.hermesandroid

import android.app.*
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlinx.coroutines.*

class HermesService : Service() {

    companion object {
        const val CHANNEL_ID = "hermes_service_channel"
        const val NOTIFICATION_ID = 1
        const val ACTION_START = "com.hermesandroid.ACTION_START"
        const val ACTION_STOP = "com.hermesandroid.ACTION_STOP"
        const val TAG = "HermesService"
    }

    private var serverJob: Job? = null
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopSelf()
                return START_NOT_STICKY
            }
        }

        // Start as foreground service to prevent being killed
        val notification = createNotification("Hermes Agent is running")
        startForeground(NOTIFICATION_ID, notification)

        startPythonServer()

        return START_STICKY
    }

    private fun startPythonServer() {
        serviceScope.launch {
            try {
                // Ensure Python is started
                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(this@HermesService))
                }

                val python = Python.getInstance()
                val module = python.getModule("hermes_server")

                Log.i(TAG, "Starting Hermes Python server...")
                updateNotification("Starting Hermes Agent...")

                // This blocks until the server stops
                module.callAttr("start_server")

            } catch (e: Exception) {
                Log.e(TAG, "Failed to start Python server", e)
                updateNotification("Hermes Agent error: ${e.message}")
            }
        }
    }

    private fun stopPythonServer() {
        try {
            if (Python.isStarted()) {
                val python = Python.getInstance()
                val module = python.getModule("hermes_server")
                module.callAttr("stop_server")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping Python server", e)
        }
    }

    override fun onDestroy() {
        stopPythonServer()
        serverJob?.cancel()
        serviceScope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Hermes Agent Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Keeps Hermes Agent running in background"
                setShowBadge(false)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(text: String): Notification {
        val stopIntent = Intent(this, HermesService::class.java).apply {
            action = ACTION_STOP
        }
        val stopPendingIntent = PendingIntent.getService(
            this, 0, stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Hermes Agent")
            .setContentText(text)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setOngoing(true)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Stop", stopPendingIntent)
            .build()
    }

    private fun updateNotification(text: String) {
        val notification = createNotification(text)
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, notification)
    }
}
