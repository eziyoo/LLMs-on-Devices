# 🧠 LlamaAndroid: On-Device LLM Inference for Android

Welcome to the official repository for device LLMs project: **on-device large language model inference using Llama.cpp on Android**. This project explores the feasibility, performance, and usability of running quantized LLMs natively on Android devices — with no server-side dependency.

---

## 📱 About the Project

This Android app demonstrates how to:
- Run LLMs directly on-device using [llama.cpp](https://github.com/ggerganov/llama.cpp)
- Download GGUF models dynamically from Hugging Face
- Interact with the model via a simple chat interface
- Benchmark performance under different configurations

This setup is designed to help evaluate the **efficiency and limitations of local inference** on mobile hardware, especially for research and offline use cases.

---

## 📂 Project Structure

```
thesis-repo/
├── android-app                           # Android app code (Jetpack Compose UI)
├── figures                               # Figures and visual assets
├── benchmark dataset downloader          # A script for downloading HuggingFace datasets
├── hugging face GGUF Models extract      # A extracter of GGUF models
└── README.md                             # You're here!
```

---

## 🔧 Setup Instructions

### 1. Clone with Submodule

```bash
git clone https://github.com/your-username/thesis-repo.git
cd thesis-repo
```

### 2. Open in Android Studio

- Make sure you’re using the **NDK** and **CMake**
- Sync Gradle and let Android Studio build native sources

### 3. Run on Device

- Connect your Android device or use an emulator with sufficient RAM
- Click **Run** in Android Studio
- Use the dropdown to select and download a GGUF model
- Start chatting!

---

## 🧪 Models Included

The app includes downloadable links to quantized versions of(update continuously):

- ✅ Phi-2 7B (Q4_0)
- ✅ TinyLlama 1.1B (f16)
- ✅ Phi-2 DPO (Q3_K_M)
- ✅ Add your own model easily via the `MainActivity.kt` model list

---

## 📊 Benchmarking

Use the **Bench** button in the app to run performance tests. Results include:
- Token throughput
- Warm-up time
- Memory usage

This feature helps evaluate real-world performance across model sizes and device types.

---

## 📚 Thesis Focus

My thesis explores:
- Feasibility of local LLM inference on consumer-grade Android hardware
- Trade-offs in model size, quantization, latency, and UX
- Application design challenges with native + Compose + JNI

---

## 🔗 Dependencies

- [llama.cpp (fork)](https://github.com/ehsaani/llama.cpp)
- Android Jetpack Compose
- CMake + NDK (for JNI integration)

---

## 🙋‍♂️ Author

**M. Ehsani**  
[Università degli Studi di Napoli Federico II]    
🔗 [www.linkedin.com/in/eziyo]

---

## 📝 License

This project is for academic and research purposes. See individual licenses for dependencies like `llama.cpp`.
