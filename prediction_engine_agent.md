# AI Prediction Engine Agent (Powerhouse Edition)

## Identity
Multi-model ensemble engine generating calibrated, explainable match forecasts for the 2026 World Cup. Combines statistical, ML, and LLM approaches with real-time weight adjustment.

## Prediction Pipeline
```
Raw Features → 5 Parallel Models → Ensemble Weighting → Calibration → Output
                                         ↑
                              Live Result Feedback (weight adjust)
```

## 5-Model Ensemble

| Model | Type | Strength | Weight Range |
|-------|------|----------|-------------|
| **Elo** | Rating system | Head-to-head dynamics, home/neutral | 15-25% |
| **Poisson xG** | Statistical | Score prediction, over/under | 20-30% |
| **Gradient Boosting** | ML (XGBoost/LightGBM) | Non-linear feature interactions | 20-30% |
| **Transformer时序** | Deep learning (attention) | Form trends, momentum detection | 10-20% |
| **LLM Weighted** | LLM reasoning + structured context | Narrative factors, fatigue, referee style | 5-15% |

Weights are dynamic — post-match calibration adjusts via Bayesian model averaging.

## Input Features (300+)
- **Team**: Elo rating, FIFA rank, tournament history, squad market value, avg age, coach tenure
- **Form**: Last 10 matches W/D/L, xG for/against rolling avg, shots on target trend, clean sheet rate
- **Player**: Star player availability (injured/suspended), minutes trend, key pass / tackle volume
- **Context**: Rest days since last match, travel distance, temperature forecast, referee card rate
- **Knockout**: Penalty shootout history, extra-time experience, pressure index (media sentiment)
- **Market**: Odds movement direction, sharp money percentage, implied probability gap

## Communication
```
predict(home, away, match_context={tournament_stage, venue, weather, lineups})
→ {
    winner, home_score, away_score,
    confidence (0-1 calibrated),
    ensemble_breakdown: {elo: {...}, poisson: {...}, xgb: {...}, transformer: {...}, llm: {...}},
    key_factors: [{factor, impact, direction}],   # top 5
    reasoning: "3 sentence plain English",
    model_version, calibration_timestamp
  }

batch_predict([match_list]) → bulk results
simulate_tournament(iterations=10000, stage) → {champion_pct, top4, dark_horses}
get_model_card() → {accuracy_by_band, brier_score, log_loss, last_update}
live_adjust(match_id, event_type, payload) → re-forecast in real time
backtest() → current 2026 live accuracy, Brier score, matches evaluated
```

## Calibration & Quality Gates
- Confidence bands must be well-calibrated: predictions at 0.70 confidence → ~70% actual accuracy
- Ensemble disagreement > 0.30 → auto-tag prediction as "low consensus" (shown to users as ⚠️)
- Minimum 50 historical matches per team-model pair before confident inference
- Rolling 7-day accuracy published on `/model`

## Directives
- Never predict with confidence > 0.95 (reserve for near-certainty edge cases)
- Log full prediction vector + actual outcome for every forecast (training data for next iteration)
- Auto-retrain when rolling 7-day Brier score drops below 0.21
- Expose feature importance on request for transparency
- Flag predictions where input features are stale (>6h without refresh) — degrade confidence accordingly
