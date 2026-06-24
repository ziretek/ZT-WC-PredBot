# ZT WC PredBot (@ZTWCPredBot) — Telegram Interface Agent (Powerhouse Edition v2)

## Identity
Entry-point Telegram bot for the 2026 World Cup AI Predictions system. Wields a calibrated ensemble prediction engine with persistent Elo ratings, Poisson xG parameters, gradient-boosted feature weighting, and optional LLM reasoning.

## Core Accuracy Pillars
1. **4-Model Ensemble** — Elo (persistent ratings, K-factor = 32, home advantage = 70 pts), Poisson xG (attack/defense params per team, league avg baselines), Gradient Boosting (feature-weighted scoring with self-correcting weights), LLM Weighted (OpenAI gpt-4o-mini or ensemble fallback)
2. **Persistent Learning** — Elo ratings + Poisson params saved to disk after every resolved match. Merge strategy: saved data layers on top of 40+ seeded team defaults
3. **Calibration Feedback Loop** — every prediction logged by confidence band; accuracy tracked per band for calibration curve
4. **Dynamic Ensemble Weights** — configurable weight distribution (default Elo 28%, Poisson 27%, GB 25%, LLM 20%)
5. **Stochastic Monte Carlo** — knockout bracket simulation with Elo-based match outcomes + Gaussian noise

## Commands
| Command | Description |
|---------|-------------|
| `/start` | Initialize user profile, show welcome + model accuracy card |
| `/predict <home> vs <away>` | Deep prediction: score, winner, confidence, key factors |
| `/predictions` | View your prediction history with accuracy breakdown |
| `/leaderboard` | Global leaderboard — overall, matchday, group-stage specific |
| `/standings` | Group + knockout bracket with AI-predicted advancement odds |
| `/teams` | List qualified teams + each team's AI power ranking (1-100) |
| `/match <team1> vs <team2>` | Full dossier: H2H, form curves, key battles, xG timeline, AI verdict |
| `/simulate` | Run Monte Carlo (10k sims) — show most likely champion, top 4, dark horses |
| `/model` | Show live model performance: accuracy, Brier score, calibration curve |
| `/insights` | Top 3 high-value upsets predicted today |
| `/lineups <match>` | Projected lineups + XI strength rating when available |
| `/track <home> vs <away>` | Enable live real-time monitoring for a match |
| `/rtstatus` | Show realtime engine status (matches tracked, odds monitored) |
| `/subscribe <team>` | Get push alerts: lineups, score changes, odds swings |
| `/feedback <prediction_id> <correct/incorrect>` | Flag a prediction for model retraining |
| `/settings` | Configure units, language, alert preferences, model verbosity |
| `/help` | Show all commands |

## Real-Time System
The bot runs a background `RealtimeEngine` that polls every 10 seconds for tracked matches:

```
LiveMatchTracker (score/min/status) ──┐
OddsMonitor (odds swings >15%) ───────┤──→ PushNotifier → Telegram subscribers
LineupWatcher (XI confirmations) ─────┘       └→ Re-forecast via PredictionEngine
                                              └→ Elo/Poisson auto-update on FT
```

- `/track <home> vs <away>` — activates live monitoring (score, odds, lineups)
- `/subscribe <team>` — get push alerts when events fire
- Match end triggers automatic Elo rating update and Poisson parameter adjustment
- Re-forecasts run when score changes mid-match (if confidence > 60%)

## Data Freshness Guarantees
| Data Type | Refresh | TTL |
|-----------|---------|-----|
| Live scores / match state | Real-time (WebSocket) | 5s |
| Odds movements | Every 60s | 1m |
| Lineups / injuries | Push on official confirmation | immediate |
| Team form / player stats | Daily | 24h |
| Historical models | Before each matchday | on-demand |

## Deploy to Render (Free, 24/7)

1. Push this repo to GitHub:
```bash
git init && git add . && git commit -m "init" && git remote add origin <your-repo-url> && git push -u origin main
```

2. Go to [render.com](https://render.com) → **New Web Service** → Connect your repo

3. Render auto-detects `Dockerfile` — set these env vars:
   - `TELEGRAM_TOKEN` — your bot token
   - `WEBHOOK_URL` → `https://<app-name>.onrender.com`
   - `DATA_DIR` → `/data`

4. Add a **Disk** mount at `/data` (1GB free) so Elo ratings survive restarts

5. Deploy — Render builds the Docker container, starts the bot, and keeps it alive 24/7

Webhook mode is automatic: if `WEBHOOK_URL` is set, the bot registers the webhook with Telegram on startup. No polling needed.

## Directives
- Respond < 2s; background heavy predictions with "wcbot is thinking..." placeholder
- Split long messages with pagination inline keyboard
- Log every prediction with `user_id`, `match_id`, `model_version`, `confidence` for calibration
- Flag predictions where ensemble disagreement > 0.3 → append "⚠️ Low consensus" warning
- Expose model card on `/model` — accuracy by conf band, recency-weighted performance
