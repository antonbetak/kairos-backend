from datetime import datetime
from secrets import token_urlsafe
from threading import Thread
from uuid import UUID

from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from sqlalchemy import and_
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import obtener_id_usuario
from app.db import Base
from app.db import SessionLocal
from app.db import engine
from app.models import ActivityComment
from app.models import ActivityEvent
from app.models import ActivityInvite
from app.models import ActivityReaction
from app.models import Friendship
from app.schemas import ActivityEventCreate
from app.schemas import ActivityEventResponse
from app.schemas import CommentCreate
from app.schemas import CommentResponse
from app.schemas import FriendRequestCreate
from app.schemas import FriendshipResponse
from app.schemas import InviteCreate
from app.schemas import InviteResponse
from app.schemas import ReactionCreate
from app.schemas import ReactionResponse
from app.schemas import VisibilityUpdate
from app.services.rabbitmq_consumer import start_consumer


app = FastAPI(title="Kairos Activity Service")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def crear_tablas():
    Base.metadata.create_all(bind=engine)
    Thread(target=start_consumer, daemon=True).start()


@app.get("/health")
def health():
    return {"service": "activity_service", "status": "ok"}


@app.get("/ready")
def ready():
    return {"service": "activity_service", "status": "ready"}


def _friend_ids(db: Session, user_id: UUID) -> list[UUID]:
    friendships = (
        db.query(Friendship)
        .filter(Friendship.status == "accepted")
        .filter(
            or_(
                Friendship.requester_id == user_id,
                Friendship.addressee_id == user_id,
            )
        )
        .all()
    )
    ids: list[UUID] = []
    for friendship in friendships:
        if friendship.requester_id == user_id:
            ids.append(friendship.addressee_id)
        else:
            ids.append(friendship.requester_id)
    return ids


def _can_view_event(db: Session, event: ActivityEvent, user_id: UUID) -> bool:
    if event.actor_id == user_id:
        return True
    if event.visibility == "public":
        return True
    if event.visibility != "friends":
        return False
    return event.actor_id in _friend_ids(db, user_id)


@app.get("/activity/me", response_model=list[ActivityEventResponse])
def list_my_activity(
    limit: int = 50,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    limit = min(max(limit, 1), 100)
    return (
        db.query(ActivityEvent)
        .filter(ActivityEvent.actor_id == id_usuario)
        .order_by(ActivityEvent.created_at.desc())
        .limit(limit)
        .all()
    )


@app.get("/activity/feed", response_model=list[ActivityEventResponse])
def list_feed(
    limit: int = 50,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    limit = min(max(limit, 1), 100)
    friend_ids = _friend_ids(db, id_usuario)
    visible_actor_ids = [id_usuario, *friend_ids]
    return (
        db.query(ActivityEvent)
        .filter(ActivityEvent.actor_id.in_(visible_actor_ids))
        .filter(
            or_(
                ActivityEvent.actor_id == id_usuario,
                ActivityEvent.visibility == "friends",
                ActivityEvent.visibility == "public",
            )
        )
        .order_by(ActivityEvent.created_at.desc())
        .limit(limit)
        .all()
    )


@app.post("/activity/events", response_model=ActivityEventResponse)
def create_activity_event(
    payload: ActivityEventCreate,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    event = ActivityEvent(
        actor_id=id_usuario,
        event_type=payload.event_type,
        title=payload.title,
        message=payload.message,
        source_service="activity_service",
        source_entity_id=payload.source_entity_id,
        visibility=payload.visibility,
        extra_data=payload.extra_data,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@app.patch(
    "/activity/events/{event_id}/visibility", response_model=ActivityEventResponse
)
def update_visibility(
    event_id: UUID,
    payload: VisibilityUpdate,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    event = (
        db.query(ActivityEvent)
        .filter(ActivityEvent.id_evento == event_id)
        .filter(ActivityEvent.actor_id == id_usuario)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    event.visibility = payload.visibility
    db.commit()
    db.refresh(event)
    return event


@app.get("/activity/friends", response_model=list[FriendshipResponse])
def list_friendships(
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    return (
        db.query(Friendship)
        .filter(
            or_(
                Friendship.requester_id == id_usuario,
                Friendship.addressee_id == id_usuario,
            )
        )
        .order_by(Friendship.updated_at.desc())
        .all()
    )


@app.post("/activity/friends/request", response_model=FriendshipResponse)
def request_friendship(
    payload: FriendRequestCreate,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    if payload.addressee_id == id_usuario:
        raise HTTPException(status_code=400, detail="No puedes agregarte a ti mismo")

    existing = (
        db.query(Friendship)
        .filter(
            or_(
                and_(
                    Friendship.requester_id == id_usuario,
                    Friendship.addressee_id == payload.addressee_id,
                ),
                and_(
                    Friendship.requester_id == payload.addressee_id,
                    Friendship.addressee_id == id_usuario,
                ),
            )
        )
        .first()
    )
    if existing:
        return existing

    friendship = Friendship(requester_id=id_usuario, addressee_id=payload.addressee_id)
    db.add(friendship)
    db.commit()
    db.refresh(friendship)
    return friendship


@app.post("/activity/friends/{friendship_id}/accept", response_model=FriendshipResponse)
def accept_friendship(
    friendship_id: UUID,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    friendship = (
        db.query(Friendship)
        .filter(Friendship.id == friendship_id)
        .filter(Friendship.addressee_id == id_usuario)
        .first()
    )
    if not friendship:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    friendship.status = "accepted"
    db.commit()
    db.refresh(friendship)
    return friendship


@app.post("/activity/invites", response_model=InviteResponse)
def create_invite(
    payload: InviteCreate,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    invite = ActivityInvite(
        owner_id=id_usuario,
        code=token_urlsafe(24),
        max_uses=payload.max_uses,
        expires_at=payload.expires_at,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


@app.post("/activity/invites/{code}/accept", response_model=FriendshipResponse)
def accept_invite(
    code: str,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    invite = db.query(ActivityInvite).filter(ActivityInvite.code == code).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invitacion no encontrada")
    if invite.owner_id == id_usuario:
        raise HTTPException(status_code=400, detail="No puedes aceptar tu invitacion")
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Invitacion expirada")
    if invite.used_count >= invite.max_uses:
        raise HTTPException(status_code=410, detail="Invitacion agotada")

    existing = (
        db.query(Friendship)
        .filter(
            or_(
                and_(
                    Friendship.requester_id == invite.owner_id,
                    Friendship.addressee_id == id_usuario,
                ),
                and_(
                    Friendship.requester_id == id_usuario,
                    Friendship.addressee_id == invite.owner_id,
                ),
            )
        )
        .first()
    )
    if existing:
        if existing.status == "pending":
            existing.status = "accepted"
        invite.used_count += 1
        db.commit()
        db.refresh(existing)
        return existing

    friendship = Friendship(
        requester_id=invite.owner_id,
        addressee_id=id_usuario,
        status="accepted",
    )
    invite.used_count += 1
    db.add(friendship)
    db.commit()
    db.refresh(friendship)
    return friendship


@app.post("/activity/events/{event_id}/react", response_model=ReactionResponse)
def react_to_event(
    event_id: UUID,
    payload: ReactionCreate,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    event = db.query(ActivityEvent).filter(ActivityEvent.id_evento == event_id).first()
    if not event or not _can_view_event(db, event, id_usuario):
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    reaction = (
        db.query(ActivityReaction)
        .filter(ActivityReaction.event_id == event_id)
        .filter(ActivityReaction.actor_id == id_usuario)
        .first()
    )
    if reaction:
        reaction.reaction = payload.reaction
    else:
        reaction = ActivityReaction(
            event_id=event_id,
            actor_id=id_usuario,
            reaction=payload.reaction,
        )
        db.add(reaction)
    db.commit()
    db.refresh(reaction)
    return reaction


@app.post("/activity/events/{event_id}/comments", response_model=CommentResponse)
def comment_on_event(
    event_id: UUID,
    payload: CommentCreate,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    event = db.query(ActivityEvent).filter(ActivityEvent.id_evento == event_id).first()
    if not event or not _can_view_event(db, event, id_usuario):
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    comment = ActivityComment(
        event_id=event_id,
        actor_id=id_usuario,
        message=payload.message,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@app.get("/activity/events/{event_id}/comments", response_model=list[CommentResponse])
def list_comments(
    event_id: UUID,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    event = db.query(ActivityEvent).filter(ActivityEvent.id_evento == event_id).first()
    if not event or not _can_view_event(db, event, id_usuario):
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    return (
        db.query(ActivityComment)
        .filter(ActivityComment.event_id == event_id)
        .order_by(ActivityComment.created_at.asc())
        .all()
    )
