"""
Graphs module Pydantic schemas.
"""

from pydantic import BaseModel


class ChartDataPoint(BaseModel):
    """Single data point for a dashboard chart."""

    label: str
    value: int


class ChartSuccessResponse(BaseModel):
    """Response for dashboard chart endpoints."""

    success: bool = True
    range: str
    data: list[ChartDataPoint]
