import subprocess

cmd = (
        "cd /data/local/tmp && "
        "LD_LIBRARY_PATH=. ./llama-cli "
        "-m qwen2.5-7b-instruct-q4_k_m.gguf "
        "-p 'Write a story about a robot.' "
        "-st "                  # Single-turn mode
        "-n 128 "               # Fixed token limit
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

        
        "--chat-template auto "
"""