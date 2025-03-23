from ..db import db
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

class ImageInPost(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    address: Mapped[str] = mapped_column(db.String)
    description: Mapped[str] = mapped_column(db.String(255))

    post_id: Mapped[int] = mapped_column(ForeignKey('post.id'))
    post: Mapped['Post'] = relationship('Post', back_populates='images_in_post')

    created_at: Mapped[datetime] = mapped_column(db.DateTime, index=True, default=lambda: datetime.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime, nullable=True)

    def soft_delete(self):
        self.deleted_at = datetime.now()