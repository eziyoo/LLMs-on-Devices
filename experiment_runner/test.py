import subprocess

context_text = (
    "The World Wide Web (WWW) was invented by British scientist Tim Berners-Lee "
    "in 1989. He was working at CERN, the European Organization for Nuclear "
    "Research, near Geneva, Switzerland. Berners-Lee created the Web to meet "
    "the demand for automatic information-sharing between scientists in "
    "universities and institutes around the world."
)


"""
qwen2-0_5b
final_prompt = (
    f"<|im_start|>user\n"
    f"Summarize the following text.\nText: {context_text}\n"
    f"<|im_end|>\n"
    f"<|im_start|>assistant\n"
    )
"""
final_prompt = (
    f"<start_of_turn>user\n"
    f"Summarize the following text.\nText: {context_text}<end_of_turn>\n"
    f"<start_of_turn>model\n"
    )


cmd = (
    f"cd /data/local/tmp && "
    f"LD_LIBRARY_PATH=. ./llama-cli "
    f"-m gemma-2-9b-it-Q4_K_M.gguf "
    f"-p '{final_prompt}' "
    f"-st "
    f"-v "
    f"-n 128 "
    f"-c 512 -t 8 --temp 0 "
    )

subprocess.run(["adb", "-s", "R5CY50M8TDM", "shell", cmd])

"""

    "qwen2-0_5b-instruct-q4_k_m.gguf"
    "qwen2.5-1.5b-instruct-q4_k_m.gguf",
    "phi-2.Q4_K_M.gguf",
    "qwen2.5-3b-instruct-q4_k_m.gguf",
    "qwen2.5-7b-instruct-q4_k_m.gguf",
    "OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf",
    "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
    "gemma-2-9b-it-Q4_K_M.gguf"

The World Wide Web (WWW) is a network of interconnected computer networks that allow users to access information from any location on Earth through the Internet. It was invented by British scientist Tim Berners-Lee in 1989, who worked at CERN, the European Organization for Nuclear Research near Geneva, Switzerland.
The WWW allows users to browse and search for information using a web browser program such as Google Chrome or Mozilla Firefox.

The World Wide Web (WWW) is a network of interconnected computer networks that allow users to access information from any location on Earth through the Internet. It was invented by British scientist Tim Berners-Lee in 1989, who worked at CERN, the European Organization for Nuclear Research near Geneva, Switzerland.
The WWW allows users to browse and search for information using a web browser program such as Google Chrome or Mozilla Firefox. The goal of the World Wide Web is to make it easier for people to access and share information with others around the world.


"""