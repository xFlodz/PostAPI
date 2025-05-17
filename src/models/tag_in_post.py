from ..db import db
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

class TagInPost(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey('post.id', ondelete='CASCADE'))
    tag_id: Mapped[int] = mapped_column(db.Integer, index=True, nullable=False)
    tag_name: Mapped[str] = mapped_column(db.String(100), nullable=False)

    post: Mapped['Post'] = relationship('Post', back_populates='tags_in_post', overlaps="tags_in_post")

    created_at: Mapped[datetime] = mapped_column(db.DateTime, index=True, default=lambda: datetime.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime, nullable=True)

    __table_args__ = (UniqueConstraint('post_id', 'tag_id', name='uq_post_tag'),)

    def soft_delete(self):
        self.deleted_at = datetime.now()
