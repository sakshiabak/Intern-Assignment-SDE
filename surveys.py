from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import geo, models, schemas
from app.database import get_db
from app.deps import get_owned_project

router = APIRouter(prefix="/projects/{project_id}/surveys", tags=["surveys"])


def _get_survey(db: Session, project: models.Project, survey_id: int) -> models.Survey:
    survey = db.get(models.Survey, survey_id)
    if survey is None or survey.project_id != project.id:
        raise HTTPException(404, "Survey not found")
    return survey


@router.post("", response_model=schemas.SurveyOut, status_code=201)
def create_survey(
    payload: schemas.SurveyCreate,
    project: models.Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    ring = geo.validate_polygon(payload.area)
    min_lon, min_lat, max_lon, max_lat = geo.bbox(ring)
    survey = models.Survey(
        project_id=project.id,
        name=payload.name,
        status=payload.status.value,
        captured_at=payload.captured_at,
        image_count=payload.image_count,
        area=payload.area,
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
        area_sq_km=round(geo.polygon_area_sq_km(ring), 6),
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)
    return survey


@router.get("", response_model=schemas.Page)
def list_surveys(
    project: models.Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
    status: schemas.SurveyStatus | None = None,
    bbox: str | None = Query(
        None,
        description="Spatial filter: min_lon,min_lat,max_lon,max_lat. "
        "Returns surveys whose bounding box intersects it.",
        examples=["77.4,12.8,77.8,13.2"],
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    S = models.Survey
    conditions = [S.project_id == project.id]
    if status:
        conditions.append(S.status == status.value)
    if bbox:
        try:
            a, b, c, d = (float(x) for x in bbox.split(","))
        except ValueError:
            raise HTTPException(422, "bbox must be 4 comma-separated numbers")
        if a > c or b > d:
            raise HTTPException(422, "bbox must be min_lon,min_lat,max_lon,max_lat")
        # Two boxes intersect unless one lies fully to a side of the other
        conditions += [S.min_lon <= c, S.max_lon >= a, S.min_lat <= d, S.max_lat >= b]

    total = db.scalar(select(func.count(S.id)).where(*conditions)) or 0
    items = list(
        db.scalars(
            select(S).where(*conditions).order_by(S.id).limit(limit).offset(offset)
        )
    )
    return schemas.Page(total=total, limit=limit, offset=offset, items=items)


@router.get("/geojson")
def surveys_geojson(
    project: models.Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """All survey footprints as a FeatureCollection, ready for Leaflet / Mapbox."""
    surveys = db.scalars(
        select(models.Survey).where(models.Survey.project_id == project.id)
    )
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": s.area,
                "properties": {
                    "id": s.id,
                    "name": s.name,
                    "status": s.status,
                    "area_sq_km": s.area_sq_km,
                },
            }
            for s in surveys
        ],
    }


@router.get("/{survey_id}", response_model=schemas.SurveyOut)
def get_survey(
    survey_id: int,
    project: models.Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    return _get_survey(db, project, survey_id)


@router.patch("/{survey_id}", response_model=schemas.SurveyOut)
def update_survey(
    survey_id: int,
    payload: schemas.SurveyUpdate,
    project: models.Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    survey = _get_survey(db, project, survey_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        data["status"] = data["status"].value
    for key, value in data.items():
        setattr(survey, key, value)
    db.commit()
    db.refresh(survey)
    return survey


@router.delete("/{survey_id}", status_code=204)
def delete_survey(
    survey_id: int,
    project: models.Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    db.delete(_get_survey(db, project, survey_id))
    db.commit()
    return Response(status_code=204)
