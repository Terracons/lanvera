from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from app import database, security
from app.models import models
from app.schemas import schemas
from typing import List
from app.services.cloudinary_config import cloudinary
import cloudinary.uploader

router = APIRouter(prefix="/properties", tags=["Properties"])


@router.post("/", response_model=schemas.PropertyOut)
def create_property(
    title: str,
    description: str,
    price: int,
    location: str,
    images: List[UploadFile] = File(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_agency)
):
    new_property = models.Property(
        title=title,
        description=description,
        price=price,
        location=location,
        owner_id=current_user.id
    )
    db.add(new_property)
    db.commit()
    db.refresh(new_property)

    for image in images:
        uploaded = cloudinary.uploader.upload(image.file)
        db_image = models.PropertyImage(
            property_id=new_property.id,
            url=uploaded["secure_url"]
        )
        db.add(db_image)
    db.commit()

    db.refresh(new_property)
    return new_property


@router.get("/", response_model=List[schemas.PropertyOut])
def list_properties(db: Session = Depends(database.get_db)):
    return db.query(models.Property).all()


@router.get("/{id}", response_model=schemas.PropertyOut)
def get_property(id: int, db: Session = Depends(database.get_db)):
    prop = db.query(models.Property).filter(models.Property.id == id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


@router.put("/{id}", response_model=schemas.PropertyOut)
def update_property(
    id: int,
    update_data: schemas.PropertyUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_agency)
):
    prop = db.query(models.Property).filter(models.Property.id == id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if prop.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(prop, field, value)

    db.commit()
    db.refresh(prop)
    return prop


@router.delete("/{id}")
def delete_property(
    id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_agency)
):
    prop = db.query(models.Property).filter(models.Property.id == id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if prop.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db.delete(prop)
    db.commit()
    return {"message": "Property deleted successfully"}
