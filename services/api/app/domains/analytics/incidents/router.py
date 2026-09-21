"""
router.py — Brasaland · Incident analysis endpoints

POST   /api/incidents/analyze        Analyze CSV     (PROTECTED)
GET    /api/incidents/results/export  Export results  (PROTECTED)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response

from app.domains.auth.dependencies import get_current_user
from app.domains.analytics.incidents.schemas import IncidentAnalysisResponse
from app.domains.analytics.incidents.service import analyze_incidents_csv, get_latest_analysis

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.post("/analyze", response_model=IncidentAnalysisResponse)
async def analyze_incidents(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
) -> IncidentAnalysisResponse:
    """Analyze an uploaded CSV of incidents. Requires authentication."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A CSV file is required.",
        )

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported.",
        )

    content = await file.read()
    if not content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file must be UTF-8 encoded.",
        ) from exc

    try:
        return analyze_incidents_csv(csv_text, file.filename)
    except Exception as exc:  # pragma: no cover - defensive boundary for malformed CSV input
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to analyze CSV file: {exc}",
        ) from exc


@router.get("/results/export")
def export_latest_results(
    current_user: dict = Depends(get_current_user),
) -> Response:
    """Export latest analysis results as CSV. Requires authentication."""
    latest = get_latest_analysis()
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis results are available yet.",
        )

    return Response(
        content=latest.csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="results.csv"'},
    )