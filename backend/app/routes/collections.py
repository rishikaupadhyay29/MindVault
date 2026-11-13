
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Collection, CollectionItem, Note, User
from app.security import current_user


router = APIRouter(prefix="/api/collections", tags=["collections"])


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CollectionRename(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CollectionItemCreate(BaseModel):
    note_id: uuid.UUID


class CollectionOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: object
    item_count: int

    model_config = ConfigDict(from_attributes=True)


class CollectionNoteOut(BaseModel):
    id: uuid.UUID
    title: str
    source_type: str
    is_favorite: bool
    created_at: object

    model_config = ConfigDict(from_attributes=True)


def get_collection(db: Session, user: User, collection_id: uuid.UUID):
    collection = db.scalar(
        select(Collection).where(
            Collection.id == collection_id,
            Collection.owner_id == user.id,
        )
    )
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@router.get("", response_model=list[CollectionOut])
def list_collections(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(
            Collection,
            func.count(CollectionItem.note_id).label("item_count"),
        )
        .outerjoin(
            CollectionItem,
            Collection.id == CollectionItem.collection_id,
        )
        .where(Collection.owner_id == user.id)
        .group_by(Collection.id)
        .order_by(Collection.created_at.desc())
    ).all()

    return [
        {
            "id": collection.id,
            "name": collection.name,
            "created_at": collection.created_at,
            "item_count": item_count,
        }
        for collection, item_count in rows
    ]


@router.post("", response_model=CollectionOut, status_code=201)
def create_collection(
    body: CollectionCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Collection name cannot be empty")

    collection = Collection(owner_id=user.id, name=name)
    db.add(collection)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A collection with this name already exists",
        )

    db.refresh(collection)
    return {
        "id": collection.id,
        "name": collection.name,
        "created_at": collection.created_at,
        "item_count": 0,
    }


@router.patch("/{collection_id}", response_model=CollectionOut)
def rename_collection(
    collection_id: uuid.UUID,
    body: CollectionRename,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    collection = get_collection(db, user, collection_id)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Collection name cannot be empty")

    collection.name = name
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A collection with this name already exists",
        )

    db.refresh(collection)
    count = db.scalar(
        select(func.count()).select_from(CollectionItem).where(
            CollectionItem.collection_id == collection.id
        )
    )
    return {
        "id": collection.id,
        "name": collection.name,
        "created_at": collection.created_at,
        "item_count": count or 0,
    }


@router.delete("/{collection_id}")
def delete_collection(
    collection_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    collection = get_collection(db, user, collection_id)
    db.delete(collection)
    db.commit()
    return {"message": "Collection deleted"}


@router.get("/{collection_id}/items", response_model=list[CollectionNoteOut])
def list_collection_items(
    collection_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    get_collection(db, user, collection_id)

    return db.scalars(
        select(Note)
        .join(CollectionItem, CollectionItem.note_id == Note.id)
        .where(
            CollectionItem.collection_id == collection_id,
            Note.owner_id == user.id,
        )
        .order_by(Note.updated_at.desc())
    ).all()


@router.post("/{collection_id}/items", status_code=201)
def add_collection_item(
    collection_id: uuid.UUID,
    body: CollectionItemCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    get_collection(db, user, collection_id)

    note = db.scalar(
        select(Note).where(
            Note.id == body.note_id,
            Note.owner_id == user.id,
        )
    )
    if not note:
        raise HTTPException(status_code=404, detail="Item not found")

    existing = db.get(
        CollectionItem,
        (collection_id, body.note_id),
    )
    if existing:
        return {"message": "Item is already in this collection"}

    db.add(
        CollectionItem(
            collection_id=collection_id,
            note_id=body.note_id,
        )
    )
    db.commit()
    return {"message": "Item added to collection"}


@router.delete("/{collection_id}/items/{note_id}")
def remove_collection_item(
    collection_id: uuid.UUID,
    note_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    get_collection(db, user, collection_id)

    item = db.get(CollectionItem, (collection_id, note_id))
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in collection")

    db.delete(item)
    db.commit()
    return {"message": "Item removed from collection"}
