package com.hermesandroid

import android.util.Log
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod

/**
 * Native bridge between React Native and Python backend via Chaquopy.
 */
class PythonBridge(reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext) {

    companion object {
        private const val TAG = "PythonBridge"
    }

    override fun getName(): String = "PythonBridge"

    @ReactMethod
    fun getServerStatus(promise: Promise) {
        try {
            if (!Python.isStarted()) {
                promise.resolve("{\"status\": \"stopped\"}")
                return
            }
            val python = Python.getInstance()
            val module = python.getModule("hermes_server")
            val result = module.callAttr("get_status").toString()
            promise.resolve(result)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to get server status", e)
            promise.resolve("{\"status\": \"error\", \"message\": \"${e.message}\"}")
        }
    }

    @ReactMethod
    fun isPythonStarted(promise: Promise) {
        try {
            promise.resolve(Python.isStarted())
        } catch (e: Exception) {
            promise.resolve(false)
        }
    }

    @ReactMethod
    fun startPython(promise: Promise) {
        try {
            if (!Python.isStarted()) {
                Python.start(AndroidPlatform(reactApplicationContext))
            }
            promise.resolve(true)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start Python", e)
            promise.reject("PYTHON_START_ERROR", e.message)
        }
    }
}
