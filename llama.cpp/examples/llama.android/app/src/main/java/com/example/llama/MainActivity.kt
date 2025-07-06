@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.example.llama

import android.app.ActivityManager
import android.app.DownloadManager
import android.content.ClipData
import android.content.ClipboardManager
import android.net.Uri
import android.os.Bundle
import android.os.StrictMode
import android.os.StrictMode.VmPolicy
import android.text.format.Formatter
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.content.getSystemService
import com.example.llama.ui.theme.LlamaAndroidTheme
import java.io.File

class MainActivity(
    activityManager: ActivityManager? = null,
    downloadManager: DownloadManager? = null,
    clipboardManager: ClipboardManager? = null,
) : ComponentActivity() {

    private val activityManager by lazy { activityManager ?: getSystemService<ActivityManager>()!! }
    private val downloadManager by lazy { downloadManager ?: getSystemService<DownloadManager>()!! }
    private val clipboardManager by lazy { clipboardManager ?: getSystemService<ClipboardManager>()!! }

    private val viewModel: MainViewModel by viewModels()

    private fun availableMemory(): ActivityManager.MemoryInfo {
        return ActivityManager.MemoryInfo().also { activityManager.getMemoryInfo(it) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        StrictMode.setVmPolicy(
            VmPolicy.Builder(StrictMode.getVmPolicy())
                .detectLeakedClosableObjects()
                .build()
        )

        val free = Formatter.formatFileSize(this, availableMemory().availMem)
        val total = Formatter.formatFileSize(this, availableMemory().totalMem)

        viewModel.log("Current memory: $free / $total")
        viewModel.log("Downloads directory: ${getExternalFilesDir(null)}")

        val extFilesDir = getExternalFilesDir(null)

        val models = listOf(
            Downloadable(
                "qwen2.5-1.5b-instruct (Q4_K_M, 1.12 GB)",
                Uri.parse("https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf?download=true"),
                File(extFilesDir, "qwen2.5-1.5b-instruct-q4_k_m.gguf")
            ),
            Downloadable(
                "phi-2 (Q4_K_M, 1.79 GB)",
                Uri.parse("https://huggingface.co/TheBloke/phi-2-GGUF/resolve/main/phi-2.Q4_K_M.gguf?download=true"),
                File(extFilesDir, "phi-2.Q4_K_M.gguf")
            ),
            Downloadable(
                "qwen2.5-3b-instruct (Q4_K_M, 2.1 GB)",
                Uri.parse("https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf?download=true"),
                File(extFilesDir, "qwen2.5-3b-instruct-q4_k_m.gguf")
            ),
            Downloadable(
                "OLMoE-1B-7B-0125-Instruct (Q4_K_M, 4.21 GB)",
                Uri.parse("https://huggingface.co/allenai/OLMoE-1B-7B-0125-Instruct-GGUF/resolve/main/OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf?download=true"),
                File(extFilesDir, "OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf")
            ),
            Downloadable(
                "qwen2.5-7b-instruct (Q4_K_M, 3.99 GB)",
                Uri.parse("https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf?download=true"),
                File(extFilesDir, "qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf")
            ),
            Downloadable(
                "Meta-Llama-3.1-8B-Instruct (Q4_K_M, 4.92 GB)",
                Uri.parse("https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf?download=true"),
                File(extFilesDir, "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf")
            ),
            Downloadable(
                "gemma-2-9b-it (Q4_K_M, 5.76 GB)",
                Uri.parse("https://huggingface.co/bartowski/gemma-2-9b-it-GGUF/resolve/main/gemma-2-9b-it-Q4_K_M.gguf?download=true"),
                File(extFilesDir, "gemma-2-9b-it-Q4_K_M.gguf")
            ),
            Downloadable(
                "Qwen2.5-7B.Q4_K_M.gguf (Q4_K_M, 4.68 GB)",
                Uri.parse("https://huggingface.co/QuantFactory/Qwen2.5-7B-GGUF/resolve/main/Qwen2.5-7B.Q4_K_M.gguf?download=true"),
                File(extFilesDir, "Qwen2.5-7B.Q4_K_M.gguf")
            )

        )

        setContent {
            LlamaAndroidTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    MainCompose(viewModel, clipboardManager, downloadManager, models)
                }
            }
        }
    }
}

@Composable
fun MainCompose(
    viewModel: MainViewModel,
    clipboard: ClipboardManager,
    dm: DownloadManager,
    models: List<Downloadable>
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(8.dp)
    ) {
        val scrollState = rememberLazyListState()

        LazyColumn(
            state = scrollState,
            reverseLayout = true,
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
        ) {
            items(viewModel.messages.reversed()) { message ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp, horizontal = 8.dp),
                    horizontalArrangement = if (message.isUser) Arrangement.End else Arrangement.Start
                ) {
                    Surface(
                        color = if (message.isUser)
                            MaterialTheme.colorScheme.primaryContainer
                        else
                            MaterialTheme.colorScheme.secondaryContainer,
                        shape = MaterialTheme.shapes.medium,
                        tonalElevation = 2.dp,
                        modifier = Modifier
                            .widthIn(max = 280.dp)
                    ) {
                        Text(
                            text = message.text.trim(),
                            modifier = Modifier.padding(12.dp),
                            color = if (message.isUser)
                                MaterialTheme.colorScheme.onPrimaryContainer
                            else
                                MaterialTheme.colorScheme.onSecondaryContainer,
                            style = MaterialTheme.typography.bodyLarge
                        )
                    }
                }
            }
        }

        OutlinedTextField(
            value = viewModel.message,
            onValueChange = { viewModel.updateMessage(it) },
            label = { Text("Type a message") },
            modifier = Modifier.fillMaxWidth(),
            trailingIcon = {
                IconButton(
                    onClick = {
                        if (viewModel.message.isNotBlank()) viewModel.send()
                    }
                ) {
                    Icon(Icons.Filled.Send, contentDescription = "Send")
                }
            }
        )

        Spacer(modifier = Modifier.height(8.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Button(onClick = { viewModel.bench(8, 4, 1) }) { Text("Bench") }
            Button(onClick = { viewModel.clear() }) { Text("Clear") }
            Button(onClick = {
                clipboard.setPrimaryClip(
                    ClipData.newPlainText(
                        "",
                        viewModel.messages.joinToString("\n") { it.text }
                    )
                )
            }) { Text("Copy") }
        }

        Spacer(modifier = Modifier.height(16.dp))

        ModelDropdownMenu(models, viewModel, dm)
    }
}

@Composable
fun ModelDropdownMenu(
    models: List<Downloadable>,
    viewModel: MainViewModel,
    dm: DownloadManager
) {
    var expanded by remember { mutableStateOf(false) }
    var selectedModel by remember { mutableStateOf<Downloadable?>(null) }

    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = !expanded }
    ) {
        OutlinedTextField(
            readOnly = true,
            value = selectedModel?.name ?: "Select a model",
            onValueChange = {},
            label = { Text("Model") },
            modifier = Modifier
                .menuAnchor()
                .fillMaxWidth(),
            trailingIcon = {
                ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded)
            }
        )

        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false }
        ) {
            models.forEach { model ->
                DropdownMenuItem(
                    text = { Text(model.name) },
                    onClick = {
                        selectedModel = model
                        expanded = false
                    }
                )
            }
        }
    }

    Spacer(modifier = Modifier.height(8.dp))

    selectedModel?.let {
        Downloadable.Button(viewModel, dm, it)
    }
}
