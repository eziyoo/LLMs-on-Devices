import subprocess

context_text = "Ladies and gentlemen, we are very privileged. With us in the theater tonight we have the savior of our nation."

cmd = (
        "cd /data/local/tmp && "
        "LD_LIBRARY_PATH=. ./llama-cli "
        "-m Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf "
        f"-p 'Instruct: Just give me the translation of the following sentence into Italian. Text: {context_text}\\nOutput:' "
        "-st "                  # Single-turn mode
        "-n 64 "                # Fixed token limit
        "-c 2048 -t 8 --temp 0 "
        )
        
subprocess.run(["adb", "-s", "R5CY50M8TDM", "shell", cmd])

"""
For Phi model:

cmd = (
        "cd /data/local/tmp && "
        "LD_LIBRARY_PATH=. ./llama-cli "
        "-m phi-2.Q4_K_M.gguf "
        "-p 'Instruct: Write a story about a robot.\\nOutput:' "
        "-st "                  # Single-turn mode
        "-n 128 "               # Fixed token limit
        "-c 2048 -t 8 --temp 0 "
        )

                                       "qwen2-0_5b-instruct-q4_k_m.gguf"
                                       "qwen2.5-1.5b-instruct-q4_k_m.gguf",
                                       "phi-2.Q4_K_M.gguf",
                                       "qwen2.5-3b-instruct-q4_k_m.gguf",
                                       "qwen2.5-7b-instruct-q4_k_m.gguf",
                                       "OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf",
                                       "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
                                       "gemma-2-9b-it-Q4_K_M.gguf"

                                       
                                       
                                       
        prompt = (
            f"Rate the following story on a scale of 1 to 10 based on creativity, "
            f"coherence, and grammar. Respond with ONLY a single number.\n\n"
            f"Story: {story_text}\n\n"
            f"Score:"
        )
"""