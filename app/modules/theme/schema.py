"""
Theme module Pydantic schemas.
"""

from pydantic import BaseModel, Field


class UpdateThemeRequest(BaseModel):
    """Request body for updating the authenticated user's theme."""

    theme: str = Field(..., description="Dashboard theme preference (dark or light)")


class ThemeData(BaseModel):
    """Theme preference payload."""

    theme: str


class ThemeSuccessResponse(BaseModel):
    """Response for theme fetch and update endpoints."""

    success: bool = True
    message: str | None = None
    data: ThemeData


class UpdateThemeSuccessResponse(BaseModel):
    """Response for the theme update endpoint."""

    success: bool = True
    message: str
    data: ThemeData
