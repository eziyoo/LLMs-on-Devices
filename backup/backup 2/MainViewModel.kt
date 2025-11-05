package com.example.llama

import android.llama.cpp.LLamaAndroid
import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch

data class ChatMessage(val text: String, val isUser: Boolean)

class MainViewModel(
    private val llamaAndroid: LLamaAndroid = LLamaAndroid.instance()
) : ViewModel() {
    companion object {
        @JvmStatic

        private val NanosPerSecond = 1_000_000_000.0
    }

    private val tag: String? = this::class.simpleName

    var messages by mutableStateOf(listOf(ChatMessage("Initializing...", isUser = false)))
        private set

    var message by mutableStateOf("")
        private set

    override fun onCleared() {
        super.onCleared()

        viewModelScope.launch {
            try {
                llamaAndroid.unload()
            } catch (exc: IllegalStateException) {
                messages += ChatMessage(exc.message ?: "Error unloading model", isUser = false)
            }
        }
    }

    fun send() {
        val text = message
        message = ""

        // Add user message and a placeholder for model response
        messages += ChatMessage(text, isUser = true)
        messages += ChatMessage("", isUser = false)

        viewModelScope.launch {
            llamaAndroid.send(text)
                .catch {
                    Log.e(tag, "send() failed", it)
                    messages += ChatMessage(it.message ?: "Error", isUser = false)
                }
                .collect {
                    val updated = messages.dropLast(1).toMutableList()
                    val last = messages.last().text + it
                    updated += ChatMessage(last, isUser = false)
                    messages = updated
                }
        }
    }

    fun bench(pp: Int, tg: Int, pl: Int, nr: Int = 1) {
        viewModelScope.launch {
            try {
                val start = System.nanoTime()
                val warmupResult = llamaAndroid.bench(pp, tg, pl, nr)
                val end = System.nanoTime()

                messages += ChatMessage(warmupResult, isUser = false)

                val warmup = (end - start).toDouble() / NanosPerSecond
                messages += ChatMessage("Warm up time: $warmup seconds, please wait...", isUser = false)

                if (warmup > 5.0) {
                    messages += ChatMessage("Warm up took too long, aborting benchmark", isUser = false)
                    return@launch
                }

                messages += ChatMessage(llamaAndroid.bench(512, 128, 1, 3), isUser = false)
            } catch (exc: IllegalStateException) {
                Log.e(tag, "bench() failed", exc)
                messages += ChatMessage(exc.message ?: "Benchmark failed", isUser = false)
            }
        }
    }

    fun load(pathToModel: String) {
        viewModelScope.launch {
            try {
                llamaAndroid.load(pathToModel)
                messages += ChatMessage("Loaded $pathToModel", isUser = false)
            } catch (exc: IllegalStateException) {
                Log.e(tag, "load() failed", exc)
                messages += ChatMessage(exc.message ?: "Load failed", isUser = false)
            }
        }
    }

    fun updateMessage(newMessage: String) {
        message = newMessage
    }

    fun clear() {
        messages = listOf()
    }

    fun log(message: String) {
        messages += ChatMessage(message, isUser = false)
    }
}
