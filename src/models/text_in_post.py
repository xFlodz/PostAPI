from ..db import db
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

class TextInPost(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(db.String)

    post_id: Mapped[int] = mapped_column(ForeignKey('post.id'))
    post: Mapped['Post'] = relationship('Post', back_populates='texts_in_post')

    created_at: Mapped[datetime] = mapped_column(db.DateTime, index=True, default=lambda: datetime.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime, nullable=True)

    def soft_delete(self):
        self.deleted_at = datetime.now()
