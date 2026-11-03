"""A tiny agent: an LLM in a loop with three tools.

Usage:
    python tiny_agent.py "Find every TODO comment in this folder and summarize them"

Setup:
    pip install openai
    export LLM_API_KEY="your key"            # never write the key in this file
    export LLM_BASE_URL="https://api.deepseek.com"   # optional, this is the default
    export LLM_MODEL="deepseek-chat"         # optional, check your provider docs for the current name
"""
import json
import os
import subprocess
import sys

from pathlib import Path

from openai import OpenAI

ROOT = Path.cwd().resolve()  # the file tools only work inside this folder
MAX_STEPS = 10               # hard cap on model calls, protects your free tier or balance
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


# ---------- Part 1: the tools ----------

def safe_path(rel: str) -> Path:
    """Turn a relative path into a real path, and refuse anything outside ROOT."""
    p = (ROOT / rel).resolve()
    if not p.is_relative_to(ROOT):
        raise ValueError("path is outside the project folder")
    return p


def list_files(path: str = ".") -> str:
    base = safe_path(path)
    found = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            found.append(str(Path(dirpath, name).relative_to(ROOT)))
            if len(found) >= 200:
                return "\n".join(sorted(found)) + "\n(list cut at 200 files)"
    return "\n".join(sorted(found)) or "(no files)"


def read_file(path: str) -> str:
    text = safe_path(path).read_text(errors="replace")
    if len(text) > 8000:
        return text[:8000] + "\n(file cut at 8000 characters)"
    return text


def run_shell(command: str) -> str:
    # The y/n question is your real protection. cwd only sets the start folder,
    # it does NOT stop a command from touching other places.
    answer = input(f"\nAgent wants to run: {command}\nAllow? [y/N] ").strip().lower()
    if answer != "y":
        return "The user denied this command."
    try:
        done = subprocess.run(
            command, shell=True, cwd=ROOT, capture_output=True, text=True, timeout=20
        )
    except subprocess.TimeoutExpired:
        return "Command timed out after 20 seconds."
    out = (done.stdout + done.stderr).strip() or "(no output)"
    return out[:4000]


TOOL_FUNCS = {"list_files": list_files, "read_file": read_file, "run_shell": run_shell}

# This is how we describe the tools to the model. It only sees these descriptions.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files under a folder, recursively. Path is relative to the project folder.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Folder to list, default '.'"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file. Path is relative to the project folder.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command in the project folder. The user must approve each command.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]


# ---------- Part 2: the loop ----------

def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('Usage: python tiny_agent.py "your task"')

    client = OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"),
    )
    model = os.environ.get("LLM_MODEL", "deepseek-chat")

    messages = [
        {"role": "system", "content": "You are a careful coding assistant. Use the tools to look at files before answering. Be concise."},
        {"role": "user", "content": sys.argv[1]},
    ]
    total_tokens = 0

    for step in range(1, MAX_STEPS + 1):
        resp = client.chat.completions.create(model=model, messages=messages, tools=TOOLS)
        msg = resp.choices[0].message
        if resp.usage:
            total_tokens += resp.usage.total_tokens
        print(f"[request {step}/{MAX_STEPS}, tokens so far: {total_tokens}]")

        # Save the model's reply in the history so it remembers what it asked for.
        entry = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        messages.append(entry)

        # No tool request means the model is done, so print the answer and stop.
        if not msg.tool_calls:
            print("\n" + (msg.content or "(empty answer)"))
            return

        # Otherwise run each tool and feed the result back, then loop again.
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
                print(f"  tool: {tc.function.name}({args})")
                result = TOOL_FUNCS[tc.function.name](**args)
            except Exception as err:  # send the error back so the model can recover
                result = f"Error: {err}"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})

    print("\nStopped: hit the step limit.")


if __name__ == "__main__":
    main()