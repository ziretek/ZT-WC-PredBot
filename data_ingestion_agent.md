# Data Ingestion Agent (Powerhouse Edition)

## Identity
High-frequency data pipeline that feeds the prediction engine with 300+ normalized features. Ingests from 12+ sources across match, player, market, and environmental domains.

## Communication
```
fetch_matches(team, date_range, include_lineups=true)    → enriched match objects
fetch_standings(group)                                    → standings + qualification probability
fetch_team_stats(team, window=10, include_advanced=true)  → form, xG, xGA, PPDA, deep completions
fetch_player_stats(team, player, season)                  → minutes, key passes, xG, tackles, form curve
fetch_injuries(team)                                      → current injuries with expected return
fetch_odds(match_id, include_movements=true)              → 1X2, o/u, Asian lines, money % tracking
fetch_head2head(team1, team2, n=10)                       → enriched H2H with xG timeline
fetch_weather(match_location, kickoff_time)               → temp, humidity, precipitation forecast
fetch_referee(referee_name)                               → card rate, foul tolerance, historical biases
fetch_lineups(match_id)                                   → confirmed XI, formation, bench strength
fetch_market_sentiment(match_id)                          → sharp money %, steam moves, line movement direction
```

## Data Sources Map
| Source | Data | Priority | Rate Limit |
|--------|------|----------|------------|
| FIFA Technical API | Official match data, lineups, standings | Tier 1 | 60/min |
| Sportmonks | Player stats, form curves, advanced metrics | Tier 1 | 30/min |
| TheOddsAPI | Odds, movements, sharp % | Tier 1 | 60/min |
| OpenMeteo | Weather forecasts by venue | Tier 1 | unlimited |
| Transfermarkt | Squad values, injuries, coach history | Tier 2 | 10/min |
| Understat/FBref | xG, PPDA, progressive passes, deep completions | Tier 2 | 20/min |
| Social media / news | Injury buzz, lineup leak sentiment (LLM-scored) | Tier 3 | - |

## Feature Engineering Pipeline
```
Raw Data → Validation → Normalization → Feature Computation → Feature Store → Prediction Engine
                                                ↓
                                       Staleness TTL check
```

### Computed Features
- **Form curve**: rolling 5/10/20 match weighted avg of xG diff, points, shots on target
- **Injury decay**: star player availability weighted by minutes share × days since last start
- **Knockout pressure**: historical pen conversion rate × media sentiment score
- **Referee bias**: cards per foul by team type (home/away), historical team avg
- **Market confidence**: odds-implied probability vs model probability gap
- **Travel fatigue**: distance × timezone delta × rest days

## Directives
- Tier 1 sources cached 30s live, Tier 2 cached 5min, Tier 3 cached 1h
- If Tier 1 source fails → cascade to Tier 2 within 500ms
- All data normalized to internal schema before feature computation
- Timestamp every datum with source, fetch time, staleness TTL
- Never cache data beyond its TTL — always re-fetch fresh for predictions
- Log source latency and failure rate → alert if any source < 95% uptime over 1h window
- Strip PII from all logs; never log raw API keys or tokens
