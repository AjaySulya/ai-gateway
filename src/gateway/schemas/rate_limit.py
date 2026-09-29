from pydantic import BaseModel


class RateLimitStatus(BaseModel):
    scope: str
    limit_rpm: int
    current_count: int
