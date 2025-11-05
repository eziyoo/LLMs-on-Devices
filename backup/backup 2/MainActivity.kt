@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.example.llama

import android.app.ActivityManager
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.StrictMode
import android.os.StrictMode.VmPolicy
import android.text.format.Formatter
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.core.content.edit
import androidx.core.content.getSystemService
import androidx.documentfile.provider.DocumentFile
import com.example.llama.ui.theme.LlamaAndroidTheme
import java.io.File

class MainActivity(
    activityManager: ActivityManager? = null,
    clipboardManager: ClipboardManager? = null,
) : ComponentActivity() {

    private val activityManager by lazy { activityManager ?: getSystemService<ActivityManager>()!! }
    private val clipboardManager by lazy { clipboardManager ?: getSystemService<ClipboardManager>()!! }

    private val viewModel: MainViewModel by viewModels()

    private fun availableMemory(): ActivityManager.MemoryInfo {
        return ActivityManager.MemoryInfo().also { activityManager.getMemoryInfo(it) }
    }

    private val prefName = "llama_prefs"
    private val keyUri = "models_uri"

    private var models: List<Downloadable> = emptyList()

    private val folderPicker =
        registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri: Uri? ->
            if (uri != null) {
                // Persist permission
                contentResolver.takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                )
                getSharedPreferences(prefName, Context.MODE_PRIVATE).edit {
                    putString(keyUri, uri.toString())
                }
                viewModel.log("✅ Folder selected: $uri")
                models = loadModelsFromUri(uri)
                setContentUI()
            } else {
                viewModel.log("❌ No folder selected")
            }
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
        viewModel.log("Scanning for models...")

        val savedUri = getSharedPreferences(prefName, Context.MODE_PRIVATE)
            .getString(keyUri, null)

        if (savedUri != null) {
            val uri = Uri.parse(savedUri)
            models = loadModelsFromUri(uri)
            if (models.isEmpty()) {
                viewModel.log("⚠️ No .gguf files found, please reselect folder")
                folderPicker.launch(null)
            } else {
                viewModel.log("✅ Using saved folder: $savedUri")
                setContentUI()
            }
        } else {
            viewModel.log("Please select the Thesis/models folder")
            folderPicker.launch(null)
        }
    }

    private fun loadModelsFromUri(uri: Uri): List<Downloadable> {
        val docTree = DocumentFile.fromTreeUri(this, uri)
        if (docTree == null || !docTree.isDirectory) {
            viewModel.log("❌ Invalid folder")
            return emptyList()
        }

        val files = docTree.listFiles().filter {
            it.isFile && (it.name?.endsWith(".gguf") == true)
        }

        if (files.isEmpty()) {
            viewModel.log("⚠️ No .gguf files found in folder")
        } else {
            viewModel.log("Found ${files.size} model(s)")
        }

        return files.map { file ->
            val f = File("/dummy/path/${file.name}")
            Downloadable(
                name = file.name ?: "unknown",
                destination = f,
                uri = file.uri
            )
        }
    }

    private fun setContentUI() {
        setContent {
            LlamaAndroidTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    MainCompose(viewModel, clipboardManager, models)
                }
            }
        }
    }
}

@Composable
fun MainCompose(
    viewModel: MainViewModel,
    clipboard: ClipboardManager,
    models: List<Downloadable>
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(8.dp)
    ) {
        val listState = rememberLazyListState()
        val messages = viewModel.messages

        // 👇 Auto-scroll to bottom on new message
        LaunchedEffect(messages.size) {
            if (messages.isNotEmpty()) {
                listState.animateScrollToItem(messages.lastIndex)
            }
        }

        LazyColumn(
            state = listState,
            reverseLayout = false, // 👈 Normal order (top → bottom)
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
        ) {
            items(messages) { message ->
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
                        modifier = Modifier.widthIn(max = 280.dp)
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
                        "Chat Transcript",
                        viewModel.messages.joinToString("\n") { it.text }
                    )
                )
            }) { Text("Copy") }
        }

        Spacer(modifier = Modifier.height(16.dp))

        ModelDropdownMenu(models, viewModel)
    }
}

@Composable
fun ModelDropdownMenu(
    models: List<Downloadable>,
    viewModel: MainViewModel
) {
    var expanded by remember { mutableStateOf(false) }
    var selectedModel by remember { mutableStateOf<Downloadable?>(null) }

    Column {
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

        selectedModel?.let { model ->
            Downloadable.Button(viewModel, model)
        }
    }
}
