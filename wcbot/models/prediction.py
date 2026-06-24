from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class EnsembleBreakdown:
    elo: dict
    poisson_xg: dict
    gradient_boosting: dict
    transformer: dict
    llm_weighted: dict


@dataclass
class PredictionResult:
    winner: str
    home_score: int
    away_score: int
    confidence: float
    ensemble_breakdown: EnsembleBreakdown
    key_factors: list
    reasoning: str
    model_version: str
    low_consensus: bool = False
    calibration_timestamp: Optional[datetime] = None


@dataclass
class Prediction:
    prediction_id: str
    user_id: int
    match_id: str
    home_team: str
    away_team: str
    predicted_home_score: int
    predicted_away_score: int
    predicted_winner: str
    confidence: float
    model_version: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    actual_home_score: Optional[int] = None
    actual_away_score: Optional[int] = None
    points_awarded: Optional[int] = None
    was_correct: Optional[bool] = None
