package com.example.llama

import android.content.Context
import android.net.Uri
import android.util.Log
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.io.InputStream

data class Downloadable(
    val name: String,
    val destination: File,
    var uri: Uri? = null  // SAF Uri if loaded from user-picked folder
) {
    companion object {
        private val tag: String? = this::class.qualifiedName

        sealed interface State
        data object Ready : State
        data object Loaded : State
        data class Error(val message: String) : State

        @JvmStatic
        @Composable
        fun Button(viewModel: MainViewModel, item: Downloadable) {
            var status by remember { mutableStateOf<State>(Ready) }
            val coroutineScope = rememberCoroutineScope()

            fun onClick(context: Context) {
                coroutineScope.launch {
                    try {
                        // If model comes from SAF → copy into app storage
                        val modelFile = if (item.uri != null) {
                            copyFromSaf(context, item)
                        } else {
                            item.destination
                        }

                        if (modelFile != null && modelFile.exists()) {
                            viewModel.load(modelFile.path)
                            status = Loaded
                        } else {
                            status = Error("Model file not found")
                        }
                    } catch (e: Exception) {
                        Log.e(tag, "Load failed", e)
                        status = Error("Load failed: ${e.message}")
                    }
                }
            }

            androidx.compose.ui.platform.LocalContext.current.let { context ->
                Button(onClick = { onClick(context) }) {
                    when (status) {
                        is Ready -> Text("Load ${item.name}")
                        is Loaded -> Text("Loaded ${item.name}")
                        is Error -> Text("Error loading ${item.name}")
                    }
                }
            }
        }

        /** Copy model from SAF Uri into app’s private storage */
        private suspend fun copyFromSaf(context: Context, item: Downloadable): File? {
            return withContext(Dispatchers.IO) {
                try {
                    val uri = item.uri ?: return@withContext null
                    val inputStream: InputStream? =
                        context.contentResolver.openInputStream(uri)

                    val dstDir = File(context.getExternalFilesDir(null), "models")
                    if (!dstDir.exists()) dstDir.mkdirs()
                    val dstFile = File(dstDir, item.name)

                    inputStream?.use { input ->
                        FileOutputStream(dstFile).use { output ->
                            input.copyTo(output)
                        }
                    }
                    Log.i(tag, "Copied ${item.name} → ${dstFile.path}")
                    dstFile
                } catch (e: Exception) {
                    Log.e(tag, "Failed to copy from SAF", e)
                    null
                }
            }
        }
    }
}
