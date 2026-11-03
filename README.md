# tiny-agent

A small AI agent I wrote in Python to understand how tools like Claude Code actually work. It's one file, about 170 lines. A language model runs in a loop and can use three tools: list files, read a file, and run a shell command.

## How it works

1. You give it a task. The script sends the task and a short description of each tool to the model.
2. If the model asks to use a tool, the script runs it and sends the result back.
3. This repeats until the model answers in plain text, or until it hits 10 requests.

The three tools:

- `list_files` lists the files in a folder
- `read_file` reads a text file
- `run_shell` runs a shell command, but only after you type `y` to approve it

## Setup

You need Python 3 and an API key from any provider that supports the OpenAI-style chat API with tool calling.

```
python3 -m venv .venv
source .venv/bin/activate
pip install openai
cp .env.example .env
```

Open `.env`, paste your API key after `LLM_API_KEY=`, then load it:

```
set -a; source .env; set +a
```

I used Groq's free tier with `openai/gpt-oss-120b`. To use a different provider, change `LLM_BASE_URL` and `LLM_MODEL` in `.env`. Free model names change often, so check your provider's model list if you get a 404.

## Usage

Run it from inside the folder you want it to look at:

```
python /path/to/tiny_agent.py "Find every TODO comment in this folder and summarize them"
```

Example output:

```
[request 1/10, tokens so far: 274]
  tool: list_files({'path': '.'})
[request 2/10, tokens so far: 575]
  tool: read_file({'path': 'a.py'})
...
TODO items found
a.py: Add input validation
b.js: Handle empty list
```

## Safety

- Every shell command asks `Allow? [y/N]` first. This is the real protection.
- The file tools only work inside the folder you run the script from. This limit does not apply to shell commands, so read each command before you type `y`.
- It stops after 10 requests and prints a token count, so it can't burn through a free tier by accident.
- File reads are cut at 8000 characters, shell output at 4000, and shell commands time out after 20 seconds.
- Some free API tiers may use your prompts to improve their products, so only point it at folders you don't mind sharing.

## What I learned

- The core of an agent is a pretty simple loop. Most of the work is describing the tools clearly.
- The model doesn't always pick the tool you expect. I asked it to run `ls` and it used `list_files` instead, so the shell prompt never showed up.
- Free model catalogs change without warning. I hit a 503 (server busy) and a 404 (model name gone) before I got it running.

## Ideas for later

- Retry automatically on 503 errors
- A `write_file` tool that also needs approval
- Fall back to a second provider when one is down
- A few tests for the file tools