# LocalTaskClaw

Personal AI agent with Telegram bot, admin UI, and kanban board for multi-agent task management.

![LocalTaskClaw Admin UI](photo_2026-03-05_08-36-20.jpg)

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/vakovalskii/LocalTaskClaw/main/install.sh | bash
```

## What you get

- **Telegram bot** — stream replies, live typing preview
- **Admin UI** — chat, sessions, kanban, tasks, files, logs, settings
- **Kanban board** — up to 10 agents with custom identities, 4-column board (Backlog → In Progress → Ready for Review → Done), run agents on tasks, view .md artifacts
- **Any OpenAI-compatible model** — local (Ollama) or cloud
- **Web search** via Brave
- **Real token streaming** — both in UI and Telegram
- **Three isolation modes** — Docker (recommended), native processes, or restricted to agent folder

## Requirements

- Linux server (Ubuntu/Debian/CentOS)
- Docker + Docker Compose
- Telegram Bot Token (from @BotFather)
- OpenAI-compatible model endpoint

## Architecture

4 containers:

| Container | Role |
|-----------|------|
| `core` | Python ReAct agent + API |
| `bot` | Telegram bot |
| `admin` | React admin panel |
| `postgres` | Storage |
| `traefik` | HTTPS (optional, with domain) |

## Status

Work in progress. See [PLAN.md](PLAN.md) for roadmap.
