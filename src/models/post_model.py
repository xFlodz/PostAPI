from ..db import db
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import json

class Post(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(db.String(150))
    header: Mapped[str] = mapped_column(db.String(70))
    main_image: Mapped[str] = mapped_column(db.String)
    date_range: Mapped[str] = mapped_column(db.String)
    creator_id: Mapped[str] = mapped_column(db.Integer)
    structure: Mapped[str] = mapped_column(db.String)
    is_approved: Mapped[bool] = mapped_column(db.Boolean)

    tags_in_post: Mapped[list['TagInPost']] = relationship(
        'TagInPost', back_populates='post', cascade='all, delete-orphan', overlaps='tags_in_post'
    )
    images_in_post: Mapped[list['ImageInPost']] = relationship(
        'ImageInPost', back_populates='post', cascade='all, delete-orphan', overlaps='images'
    )
    videos_in_post: Mapped[list['VideoInPost']] = relationship(
        'VideoInPost', back_populates='post', cascade='all, delete-orphan', overlaps='videos'
    )
    texts_in_post: Mapped[list['TextInPost']] = relationship(
        'TextInPost', back_populates='post', cascade='all, delete-orphan', overlaps='texts_in_post'
    )

    created_at: Mapped[datetime] = mapped_column(db.DateTime, index=True, default=lambda: datetime.now(timezone.utc))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime, nullable=True)

    def soft_delete(self):
        self.deleted_at = datetime.now()
