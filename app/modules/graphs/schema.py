"""
Graphs module Pydantic schemas.
"""

from decimal import Decimal

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


class ResolutionChartDataPoint(BaseModel):
    """Single data point for the resolution status chart."""

    label: str
    resolved: int
    unresolved: int


class ResolutionChartSuccessResponse(BaseModel):
    """Response for the resolution status chart endpoint."""

    success: bool = True
    range: str
    data: list[ResolutionChartDataPoint]


class ResponseTimeChartDataPoint(BaseModel):
    """Single data point for the response time chart."""

    label: str
    value: Decimal


class ResponseTimeChartSuccessResponse(BaseModel):
    """Response for the response time chart endpoint."""

    success: bool = True
    range: str
    data: list[ResponseTimeChartDataPoint]
