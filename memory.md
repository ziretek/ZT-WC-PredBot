# Project Memory - 2026 World Cup AI Predictions Telegram Bot

## Project Overview
Multi-agent Telegram bot delivering AI-powered match predictions for the 2026 World Cup. Built with a modular multi-agent architecture for scalability and maintainability.

## System Architecture (Planned)
- **wcbot** (Telegram Interface Agent): Webhook handling, menus, inline queries — main entry point agent
- **Data Ingestion Agent**: Real-time match data, team stats, historical odds via external sports APIs
- **AI Prediction Engine Agent**: ML models / LLM prompts for match forecasts
- **State Management Agent**: Database sessions, user profiles, prediction history, leaderboard

## Constraints & Directives
- All code execution in isolated containers
- No auto-deploy to production without HITL approval
- Database schema changes require human sign-off
- 3-strike loop limit enforced before HITL escalation
- API budget monitoring required

## Agent Docs
See individual `.md` files for direct agent communication:
- `wcbot.md` — main Telegram interface (talk to this one directly)
- `data_ingestion_agent.md` — data fetcher/normalizer
- `prediction_engine_agent.md` — ML/LLM prediction engine
- `state_manager_agent.md` — database, users, leaderboard

## Known Issues (None yet - fresh project)

## Security Notes
- API keys for Telegram bot and external sports data services must be environment-injected
- User data privacy maintained per Telegram Bot API guidelines
