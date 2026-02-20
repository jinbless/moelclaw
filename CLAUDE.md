# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Telegram bot for managing a shared Google Calendar via natural language (Korean). Users send messages in Telegram, OpenAI GPT-5 mini parses intent via function calling, and the bot executes corresponding Google Calendar API operations. Also supports navigation via Google Geocoding + Naver Maps directions.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires .env with all required vars)
python -m app.main

# Run with Docker
docker-compose up -d

# Build Docker image
docker build -t tgcalendar:latest .
```

No test framework or linter is configured. Python 3.11+ required (uses `X | Y` union syntax, `ZoneInfo`).

## Architecture

All code lives in `app/`. Single entry point: `python -m app.main`.

### Data flow

1. User sends Telegram message → `telegram_bot.py:handle_text_message`
2. `nlp_service.py:process_message` sends message + history to GPT with function-calling tools
3. GPT returns either a text response or a tool call (e.g. `add_event`, `delete_event`)
4. `telegram_bot.py` dispatches via `FUNCTION_REGISTRY` dict → executor calls `calendar_service.py` → result stored in chat history via `add_tool_result`
5. For queries (`_QUERY_FUNCTIONS`): result fed back to GPT via `get_followup_response` for natural Korean summary
6. For mutations (`_MUTATION_FUNCTIONS`): result shown directly + affected month's full event list appended via `_get_month_summary`
7. For navigation (`_NAVIGATION_FUNCTIONS`): geocode via Google Geocoding API → store in `_pending_navigation` → prompt user for location share → `handle_location` pops pending state, deletes prompt/location messages, builds Naver Maps directions URL

### Key modules

- **config.py** — All env vars and constants. Single source of truth for paths, API keys, timezone. GPT model name (`OPENAI_MODEL`) is hardcoded here.
- **prompts.py** — `SYSTEM_PROMPT` (Korean, with `{today}`/`{weekday}` placeholders) and `TOOLS` list (10 GPT function schemas). This is where all GPT tool definitions and behavior rules live. Edit this file to change GPT behavior without touching bot logic.
- **nlp_service.py** — GPT integration. Per-user conversation history in-memory (`_chat_histories`, max 100 messages FIFO). `process_message` for initial call, `get_followup_response` for query result summarization. Uses `developer` role (not `system`) for the system prompt per OpenAI convention. Both calls use `reasoning_effort="low"`.
- **telegram_bot.py** — Handler registration, `FUNCTION_REGISTRY` dispatch, event formatting. Three function categories: `_MUTATION_FUNCTIONS`, `_QUERY_FUNCTIONS`, `_NAVIGATION_FUNCTIONS`. Each has a `_exec_*` function. Telegram commands: `/start`, `/auth <code>`, `/today`.
- **calendar_service.py** — Google Calendar CRUD. All sync Google API calls wrapped with `asyncio.to_thread()`. Event matching via `_match_event`: title match → time match → single-event fallback.
- **geo_service.py** — Google Geocoding API (`geocode`) + Naver Maps mobile directions URL builder (`build_directions_url`).
- **scheduler.py** — Daily report job via `python-telegram-bot` job queue (not APScheduler). Sends today's events to all authenticated users.
- **web_server.py** — aiohttp server for OAuth callback (`/oauth/callback`). Runs alongside the bot, started in `main.py:post_init`.

### Key patterns

- **Async throughout**: All handlers are async. Sync Google API calls wrapped with `asyncio.to_thread()`.
- **Shared calendar**: All users operate on `SHARED_CALENDAR_ID`, not personal calendars. Query functions use `_get_any_valid_creds()` — any authenticated user's token works.
- **In-memory state**: Both `_chat_histories` (nlp_service) and `_pending_navigation` (telegram_bot) are in-memory only — lost on restart.
- **OAuth via web callback**: `main.py:post_init` starts an aiohttp server. Google OAuth redirects to `/oauth/callback` with `state=chat_id`, which exchanges the code and notifies the user via Telegram. Fallback: `/auth <code>` command for manual exchange.
- **Post-mutation month summary**: After add/edit/delete, `_get_month_summary` determines the affected month from the function args (`date`, `date_from`, or `changes.date`), fetches all events in that month, and sends a numbered grouped-by-date calendar view.
- **Navigation two-step flow**: `_exec_navigate` geocodes destination and stores in `_pending_navigation[chat_id]`, sends location-share keyboard. `handle_location` pops pending state, deletes the prompt and location messages, builds Naver Maps URL.
- **GPT two-pass for queries**: Query results are injected as a `tool` message in history, then second GPT call (no tools, `max_tokens=1000`) composes a natural Korean response.
- **search_events skips Google API `q` param**: Fetches all events in date range; GPT filters semantically. Google's `q` does word-level matching that misses Korean substrings. Note: `delete_events_by_range` *does* use `q` for keyword filtering — this is intentional.
- **All-day event end date is exclusive**: `add_multiday_event` sets `end.date` to `date_to + 1 day` per Google Calendar API convention.
- **`_safe_parse_date`**: Clamps invalid day-of-month to last valid day (e.g., Feb 31 → Feb 28/29).
- **Location extraction**: `_extract_location` in `telegram_bot.py` checks the event `location` field first, then falls back to parsing `장소:` lines from `description`.

### Function registry (10 functions)

| Category | Functions |
|---|---|
| Mutation | `add_event`, `add_events_by_range`, `add_multiday_event`, `delete_event`, `delete_events_by_range`, `edit_event` |
| Query | `get_today_events`, `get_week_events`, `search_events` |
| Navigation | `navigate` |

`add_events_by_range` creates one timed event per day in a range. `add_multiday_event` creates a single all-day spanning event (no time).

## Environment Setup

Copy `.env.example` to `.env`. Required vars: `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SHARED_CALENDAR_ID`. Optional: `GOOGLE_MAPS_API_KEY` (for navigation), `GOOGLE_REDIRECT_URI` (must match the public URL ending in `/oauth/callback`), `DAILY_REPORT_TIME` (default `09:00`), `TIMEZONE` (default `Asia/Seoul`), `OAUTH_SERVER_PORT` (default `8080`).

Token storage: `data/tokens/{chat_id}.json` (volume-mounted in Docker). Docker-compose exposes port 8080 on localhost only — reverse proxy needed for production OAuth flow. Docker-compose also sets `TZ=Asia/Seoul` at the OS level (separate from the app's `TIMEZONE` env var).

Note: `telegram-calendar-bot-spec.md` is the original design spec and is outdated (references Claude/Anthropic API and APScheduler). The actual implementation uses OpenAI GPT-5 mini and python-telegram-bot's built-in job queue.
