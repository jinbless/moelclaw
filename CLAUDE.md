# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Telegram bot for managing a shared Google Calendar via natural language (Korean). Users send messages in Telegram, OpenAI GPT-4.1 parses intent via function calling, and the bot executes corresponding Google Calendar API operations.

## Commands

```bash
# Run locally
pip install -r requirements.txt
python -m app.main

# Run with Docker
docker-compose up -d

# Build Docker image
docker build -t tgcalendar:latest .
```

No test framework or linter is configured.

## Architecture

```
app/
├── main.py              # Entry point: builds telegram Application, starts polling
├── config.py            # All env vars, paths, constants (TIMEZONE, OPENAI_MODEL, etc.)
├── telegram_bot.py      # Command/message handlers, function dispatch, event formatters
├── nlp_service.py       # OpenAI GPT integration with function calling tools + conversation history
├── calendar_service.py  # Google Calendar API wrapper (OAuth, CRUD, event matching)
├── scheduler.py         # APScheduler daily report job
└── web_server.py        # aiohttp server for OAuth callback on /oauth/callback
```

### Data flow

1. User sends message in Telegram → `telegram_bot.py` receives it
2. Message forwarded to `nlp_service.py` which calls GPT with function-calling tools
3. GPT returns tool calls (e.g. `add_event`, `delete_event`, `get_today_events`)
4. `telegram_bot.py` dispatches to the matching executor function, which calls `calendar_service.py`
5. Results fed back to GPT for a natural language summary, then sent to user

### Key patterns

- **Async throughout**: All handlers are async. Sync Google API calls wrapped with `asyncio.to_thread()`.
- **Per-user state**: OAuth tokens stored as `data/tokens/{chat_id}.json`. Conversation history kept in-memory in `nlp_service.py` (max 100 messages per user).
- **Function dispatch**: `telegram_bot.py` uses a dict mapping function names → executor coroutines (see `FUNCTION_EXECUTORS`).
- **Shared calendar model**: All users operate on a single shared calendar (`SHARED_CALENDAR_ID`), not personal calendars.
- **GPT tool definitions**: 9 tools defined as JSON schemas in `nlp_service.py` (`TOOLS` list). The system prompt includes date-relative instructions in Korean.
- **Post-mutation summary**: After add/edit/delete, the bot sends the affected month's event list.

## Environment Setup

Copy `.env.example` to `.env` and fill in required values. Required env vars: `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SHARED_CALENDAR_ID`. Google OAuth credentials file goes in `data/credentials.json`.
