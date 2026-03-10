from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal, AllowedSender
from schemas import AllowedSenderCreate, AllowedSenderUpdate, AllowedSenderResponse
from auth import get_current_user

router = APIRouter(
    prefix="/senders",
    tags=["Allowed Senders"],
    dependencies=[Depends(get_current_user)]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=List[AllowedSenderResponse])
def get_senders(db: Session = Depends(get_db)):
    senders = db.query(AllowedSender).all()
    return senders

@router.post("/", response_model=AllowedSenderResponse)
def create_sender(sender: AllowedSenderCreate, db: Session = Depends(get_db)):
    db_sender = db.query(AllowedSender).filter(AllowedSender.value == sender.value).first()
    if db_sender:
        raise HTTPException(status_code=400, detail="Sender already registered")
    
    new_sender = AllowedSender(**sender.dict())
    db.add(new_sender)
    db.commit()
    db.refresh(new_sender)
    return new_sender

@router.put("/{sender_id}", response_model=AllowedSenderResponse)
def update_sender(sender_id: int, sender: AllowedSenderUpdate, db: Session = Depends(get_db)):
    db_sender = db.query(AllowedSender).filter(AllowedSender.id == sender_id).first()
    if not db_sender:
        raise HTTPException(status_code=404, detail="Sender not found")
        
    update_data = sender.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_sender, key, value)
        
    db.commit()
    db.refresh(db_sender)
    return db_sender

@router.delete("/{sender_id}")
def delete_sender(sender_id: int, db: Session = Depends(get_db)):
    db_sender = db.query(AllowedSender).filter(AllowedSender.id == sender_id).first()
    if not db_sender:
        raise HTTPException(status_code=404, detail="Sender not found")
        
    db.delete(db_sender)
    db.commit()
    return {"message": "Sender deleted"}
