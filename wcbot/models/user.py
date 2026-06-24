from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class UserSettings:
    language: str = "en"
    units: str = "metric"
    alert_on_lineups: bool = True
    alert_on_prediction: bool = True
    alert_on_live_score: bool = False
    model_verbosity: str = "normal"  # "simple", "normal", "detailed"


@dataclass
class User:
    chat_id: int
    username: Optional[str]
    first_name: Optional[str]
    language_code: str = "en"
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)
    settings: UserSettings = field(default_factory=UserSettings)
    total_predictions: int = 0
    correct_predictions: int = 0
    points: int = 0

    @property
    def accuracy(self) -> float:
        if self.total_predictions == 0:
            return 0.0
        return self.correct_predictions / self.total_predictions
