from pydantic import BaseModel


class UsageSummary(BaseModel):
    total_requests: int
    success_count: int
    error_count: int
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
