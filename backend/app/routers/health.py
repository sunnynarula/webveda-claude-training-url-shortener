"""Health endpoints: /api/health/live (no dependency checks). /api/health arrives in slice 6."""

from fastapi import APIRouter

router = APIRouter()
