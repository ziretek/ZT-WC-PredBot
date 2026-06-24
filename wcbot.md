# ZT WC PredBot

Telegram bot for 2026 World Cup predictions using an Elo model, Poisson xG model, heuristic feature weighting, and optional LLM reasoning.

The bot is designed as a practical prediction assistant: users can request match forecasts, inspect model reasoning, view prediction history, run simple tournament simulations, and opt into live match alerts when API coverage is configured.

## Current Capabilities

### Prediction Engine

- **Elo model** with seeded national-team ratings, K-factor updates, and a home-advantage adjustment.
- **Poisson xG model** with attack/defense parameters per team and scoreline probability estimates.
- **Feature-weighted model** that combines Elo, Poisson, rest/context features, and home advantage into a third forecast.
- **Optional LLM reasoning** through an OpenAI-compatible chat-completions API. The default config points at DeepSeek, but the API URL and model are configurable.
- **Ensemble voting** with configurable model weights.
- **Abstention mode** for low-confidence or low-consensus matches. By default, the bot requires at least 3 of 4 models to agree and at least 80% ensemble confidence before issuing a saved prediction.
- **Team normalization** for common aliases such as `USA`, `USMNT`, `Korea Republic`, `Cote d'Ivoire`, and `Curacao`.

### Persistence

The following model artifacts are saved under `DATA_DIR`:

- Elo ratings
- Poisson team parameters
- Ensemble weights
- Calibration feedback

User profiles, prediction history, subscriptions, and leaderboard state are stored in SQLite through `StateManagerAgent`. By default, the database lives at `DATA_DIR/state.db`, or at `STATE_DB_PATH` when that override is set.

### Telegram Commands

| Command | Status | Description |
|---------|--------|-------------|
| `/start` | Implemented | Create a user profile and show the model card |
| `/predict <home> vs <away>` | Implemented | Predict a match when the ensemble is confident enough |
| `/predict round of 32` | Implemented, API/LLM-dependent | Show live advancing teams or a Round of 32 outlook |
| `/predictions` | Implemented | Show the stored prediction history for the user |
| `/leaderboard` | Implemented | Show the stored leaderboard |
| `/standings` | Implemented, API-dependent | Show standings when `SPORTS_API_KEY` is configured |
| `/teams` | Implemented | List configured 2026 World Cup teams by continent |
| `/match <team1> vs <team2>` | Implemented | Show Elo ratings, basic H2H fallback data, and AI verdict |
| `/simulate` | Implemented | Run a Monte Carlo-style tournament simulation |
| `/model` | Implemented | Show model version, calibration stats, weights, and tracked teams |
| `/insights` | Implemented | Surface high-value/upset-style predictions from the local engine |
| `/track <home> vs <away>` | Implemented, API-dependent | Enable realtime polling for a match |
| `/rtstatus` | Implemented | Show realtime engine status |
| `/value <home> vs <away>` | Implemented, API-dependent | Compare model prediction against market odds |
| `/injuries <team>` | Implemented, API-dependent | Fetch injuries when Sportmonks coverage is configured |
| `/subscribe <team>` | Implemented | Subscribe to team alerts |
| `/unsubscribe <team>` | Implemented | Remove a team subscription |
| `/feedback <prediction_id> <y/n>` | Implemented | Submit feedback for calibration |
| `/settings` | Implemented | Show current user settings |
| `/chat` | Implemented | Enter conversational mode with follow-up actions |
| `/cancel` | Implemented | Exit chat mode |
| `/help` | Implemented | Show command help |

There is realtime lineup polling internally, but no separate `/lineups` command is currently registered.

## Chat Mode

`/chat` starts a guided conversation flow. Users can ask for predictions, compare teams, request deeper explanation, run a simulation, or ask a new question without restarting the command flow.

The conversation stores the latest home/away teams in Telegram `user_data`, so follow-ups can stay connected while the chat session is active.

## Realtime System

When `SPORTS_API_KEY` or `ODDS_API_KEY` is configured, the bot starts a background `RealtimeEngine`.

```text
LiveMatchTracker   -> score/status polling
OddsMonitor        -> market movement polling
LineupWatcher      -> lineup availability polling
PushNotifier       -> Telegram alerts for subscribers
PredictionEngine   -> optional re-forecast on score changes
```

The engine currently polls every 10 seconds. Data freshness depends on the configured external API, its coverage, and its rate limits.

Realtime behavior:

- `/track` registers a match for live score, odds, and lineup monitoring.
- `/subscribe` registers a user for team alerts and persists the subscription in SQLite.
- Score changes can trigger a fresh prediction when confidence is above 60%.
- Full-time events update Elo ratings and Poisson parameters.

## API Keys And Environment

Required:

- `TELEGRAM_TOKEN` - Telegram bot token.

Optional:

- `SPORTS_API_KEY` - Sportmonks football data for fixtures, standings, results, injuries, and live match data.
- `ODDS_API_KEY` - The Odds API key for market odds and value-pick comparisons.
- `OPENAI_API_KEY` - API key for the configured OpenAI-compatible LLM endpoint.
- `OPENAI_API_URL` - Chat completions endpoint. Defaults to `https://api.deepseek.com/v1/chat/completions`.
- `LLM_MODEL` - LLM model name. Defaults to `deepseek-chat`.
- `WEBHOOK_URL` - Public Render/app URL for Telegram webhook mode.
- `DATA_DIR` - Directory for model artifacts. Defaults to `./data` locally and `/data` in the Docker image.
- `STATE_DB_PATH` - Optional SQLite database path. Defaults to `DATA_DIR/state.db`.
- `LOG_LEVEL` - Python logging level. Defaults to `INFO`.
- `PORT` - Webhook port. Render usually provides this automatically.

## Render Deployment

This repository includes a `Dockerfile` and `render.yaml`.

Recommended Render setup:

1. Connect the GitHub repository as a Render web service.
2. Set `TELEGRAM_TOKEN`.
3. Set `WEBHOOK_URL` to `https://<app-name>.onrender.com`, or let the app infer `RENDER_EXTERNAL_HOSTNAME`.
4. Set optional API keys as needed.
5. Use `DATA_DIR=/data`.
6. Add a persistent disk mounted at `/data` if you want SQLite state, Elo ratings, Poisson parameters, calibration, and weights to survive restarts.

Without a persistent disk, SQLite state and saved model artifacts can be lost on redeploy or restart.

## Architecture

| Area | Code | Responsibility |
|------|------|----------------|
| Telegram app | `wcbot/bot.py` | Build the Telegram application, register commands, choose webhook or polling mode |
| Prediction engine | `wcbot/agents/prediction_engine.py` | Run model forecasts, ensemble voting, abstention, simulation, calibration |
| Model implementations | `wcbot/agents/models/` | Elo, Poisson xG, heuristic feature weighting, optional LLM reasoning |
| Data ingestion | `wcbot/agents/data_ingestion.py` | Fetch fixtures, standings, odds, injuries, and fallback H2H data |
| State manager | `wcbot/agents/state_manager.py` | Persist users, predictions, subscriptions, and leaderboard scoring in SQLite |
| Realtime engine | `wcbot/realtime/` | Poll live match state, odds, lineups, and push notifications |
| Handlers | `wcbot/handlers/` | Telegram command and chat-mode behavior |
| Formatting | `wcbot/utils/formatting.py` | Markdown response formatting |
| Static team data | `wcbot/data/teams.py` | Configured 2026 team list and continent mapping |

## Known Limitations

- SQLite state still needs a persistent Render disk at `/data` to survive redeploys and restarts in production.
- The static team list should be synced against an authoritative source as qualification and tournament data change.
- Standings, injuries, odds, and live match data depend on external API availability and coverage.
- Calibration metrics start at zero and only become meaningful after resolved predictions are logged.
- The feature-weighted model is heuristic; it is not currently trained with a real gradient boosting library.
- There is no registered `/lineups` command yet.
- The automated test suite is still small and should be expanded before larger refactors.

## Roadmap

1. Add a Render persistent disk at `/data` in the dashboard.
2. Add broader tests for command handlers, prediction abstention, scoring, and realtime behavior.
3. Consider Postgres if the bot grows beyond one Render instance.
4. Replace static qualification data with a verified update path.
5. Add real leaderboard timeframes for matchday, group stage, knockout stage, and all-time views.
6. Register a `/lineups` command or remove lineup references from user-facing help.
7. Improve calibration with proper Brier score/log loss updates.
8. Add admin tools for resolving matches, inspecting state, and exporting predictions.

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m wcbot
```

At minimum, `.env` must include `TELEGRAM_TOKEN`.
