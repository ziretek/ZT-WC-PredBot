# State Management Agent (Powerhouse Edition)

## Identity
Manages all persistent state: user profiles, prediction records, leaderboard, model calibration feedback, and system configuration. The feedback loop that closes accuracy improvements.

## Communication
```
create_user(chat_id, username, language)                                    → user profile
save_prediction(user_id, match_id, prediction, model_version)               → stored + queued for scoring
get_prediction_history(user_id, limit, filter_by_tournament_stage)           → history with accuracy stats
resolve_match(match_id, actual_home_score, actual_away_score)               → batch award points + push to calibration
update_leaderboard(timeframe='all'|'matchday'|'group'|'knockout')           → recalculate rankings
get_leaderboard(top_n=50, timeframe)                                        → ranked list with stats
get_user_stats(user_id)                                                     → win rate, points, rank, accuracy by confidence band
get_user_calibration(user_id)                                               → overconfidence/underconfidence bias report
get_team_subscribers(team)                                                  → push notification targets
log_model_feedback(prediction_id, actual_outcome, user_flagged)             → training data for next iteration
get_calibration_data(model_version, date_range)                             → export for model retraining
record_ensemble_weight(model_name, new_weight, reason)                      → dynamic ensemble weight log
```

## Scoring Rules
| Condition | Points |
|-----------|--------|
| Exact score | +5 |
| Correct outcome (W/D/L) | +3 |
| Correct goal difference | +2 |
| Correct both teams to score (Y/N) | +1 |
| Wrong outcome | -1 |
| No prediction | 0 |

## Calibration Feedback Loop
```
Match Result → award_points(user) → save_actual(prediction_id, outcome)
                                   → log_model_feedback(prediction_id, actual, correct/incorrect)
                                   → push to calibration DB
                                   → if batch size > 200: signal Prediction Engine to recalibrate
```

The calibration DB tracks per-model, per-confidence-band accuracy. When a band drifts >5% from ideal, the ensemble weights auto-adjust.

## Directives
- Write-ahead log for all mutations (crash recovery)
- User DB: PostgreSQL (relational), Redis (session/leaderboards)
- Index all predictions by `user_id + match_id` (unique), `model_version`, `confidence_band`
- Leaderboard ties broken by: higher accuracy % → more predictions → earlier registration
- Export calibration batch whenever 200 new resolved predictions accumulate
- Never expose raw user PII in logs; hash user_id in analytics exports
- Purge inactive users (>6 months) quarterly but retain anonymized prediction records for model training
