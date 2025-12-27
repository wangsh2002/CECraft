from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.models.resume import Resume
from app.models.user import User
from app.schemas.resume import Resume as ResumeSchema, ResumeCreate, ResumeUpdate

router = APIRouter()

@router.get("/", response_model=List[ResumeSchema])
def read_resumes(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve resumes.
    """
    resumes = db.query(Resume).filter(Resume.user_id == current_user.id).offset(skip).limit(limit).all()
    return resumes

@router.post("/", response_model=ResumeSchema)
def create_resume(
    *,
    db: Session = Depends(deps.get_db),
    resume_in: ResumeCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Create new resume.
    """
    resume = Resume(
        title=resume_in.title,
        content=resume_in.content,
        user_id=current_user.id,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume

@router.put("/{id}", response_model=ResumeSchema)
def update_resume(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    resume_in: ResumeUpdate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update a resume.
    """
    resume = db.query(Resume).filter(Resume.id == id, Resume.user_id == current_user.id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    resume.title = resume_in.title
    if resume_in.content is not None:
        resume.content = resume_in.content
    
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume

@router.delete("/{id}", response_model=ResumeSchema)
def delete_resume(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Delete a resume.
    """
    resume = db.query(Resume).filter(Resume.id == id, Resume.user_id == current_user.id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    db.delete(resume)
    db.commit()
    return resume
