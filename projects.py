from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_user, get_owned_project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=schemas.ProjectOut, status_code=201)
def create_project(
    payload: schemas.ProjectCreate,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = models.Project(
        name=payload.name,
        industry=payload.industry.value,
        description=payload.description,
        owner_id=user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(
    user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    stmt = (
        select(models.Project)
        .where(models.Project.owner_id == user.id)
        .order_by(models.Project.id)
    )
    return list(db.scalars(stmt))


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project: models.Project = Depends(get_owned_project)):
    return project


@router.patch("/{project_id}", response_model=schemas.ProjectOut)
def update_project(
    payload: schemas.ProjectUpdate,
    project: models.Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if "industry" in data and data["industry"] is not None:
        data["industry"] = data["industry"].value
    for key, value in data.items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project: models.Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    db.delete(project)
    db.commit()
    return Response(status_code=204)


@router.get("/{project_id}/stats", response_model=schemas.ProjectStats)
def project_stats(
    project: models.Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    S = models.Survey
    count, area, images = db.execute(
        select(
            func.count(S.id),
            func.coalesce(func.sum(S.area_sq_km), 0.0),
            func.coalesce(func.sum(S.image_count), 0),
        ).where(S.project_id == project.id)
    ).one()
    by_status = dict(
        db.execute(
            select(S.status, func.count(S.id))
            .where(S.project_id == project.id)
            .group_by(S.status)
        ).all()
    )
    return schemas.ProjectStats(
        project_id=project.id,
        survey_count=count,
        total_area_sq_km=round(area, 4),
        total_images=images,
        by_status=by_status,
    )
