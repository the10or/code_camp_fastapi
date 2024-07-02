from http.client import HTTPException
from typing import List

from fastapi import Depends, HTTPException, status, Response, APIRouter
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, oauth2
from ..database import get_db
from ..schemas import Post, PostCreate, PostOut

router = APIRouter(prefix="/posts", tags=["Posts"])


@router.get("/", response_model=List[PostOut])
def get_posts(
        db: Session = Depends(get_db), limit: int = 10, skip: int = 0, search: str = ""
):
    # posts = (
    #     db.query(models.Post)
    #     .filter(models.Post.title.contains(search))
    #     .limit(limit)
    #     .offset(skip)
    #     .all()
    # )

    posts = (db.query(models.Post, func.count(models.Vote.post_id).label("votes")).join(
        models.Vote, models.Vote.post_id == models.Post.id, isouter=True).group_by(models.Post.id).
             filter(models.Post.title.contains(search)).limit(limit).offset(skip).all())

    return posts


@router.get("/latest")
def get_latest_post(db: Session = Depends(get_db)):
    post = db.query(models.Post).order_by(models.Post.created_at.desc()).first()
    return post


@router.get("/{id}", response_model=Post)
def get_post(id: str, db: Session = Depends(get_db)):
    # post = db.query(models.Post).filter(models.Post.id == id).first()

    post = (db.query(models.Post, func.count(models.Vote.post_id).label("votes")).join(
            models.Vote, models.Vote.post_id == models.Post.id, isouter=True).group_by(models.Post.id).
            filter(models.Post.id == id).first())

    if not post:
        raise HTTPException(status_code=404, detail=f"post id:{id} Not found")
    return post


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Post)
def create_posts(
        post: PostCreate,
        db: Session = Depends(get_db),
        current_user: int = Depends(oauth2.get_current_user),
):
    print(current_user.email)
    try:
        new_post = models.Post(owner_id=current_user.id, **post.dict())
        db.add(new_post)
        db.commit()
        db.refresh(new_post)
        return new_post
    except Exception as e:
        return {"error": str(e)}


@router.delete("/{id}", status_code=204)
def delete_post(
        id: int,
        db: Session = Depends(get_db),
        current_user: int = Depends(oauth2.get_current_user),
):
    post_to_delete = db.query(models.Post).filter(models.Post.id == id)
    if post_to_delete.first() is None:
        raise HTTPException(status_code=404, detail=f"post id:{id} Not found")

    if post_to_delete.first().owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not Authorized to perform the requested action",
        )

    post_to_delete.delete(synchronize_session=False)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/posts/{id}", response_model=Post)
def update_post(
        id: int,
        post: PostCreate,
        db: Session = Depends(get_db),
        current_user: int = Depends(oauth2.get_current_user),
):
    post_query = db.query(models.Post).filter(models.Post.id == id)
    post_to_update = post_query.first()

    if post_to_update is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"post id:{id} Not found"
        )

    if post_to_update.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not Authorized to perform the requested action",
        )

    post_query.update(post.dict(), synchronize_session=False)
    db.commit()
    return post_to_update
