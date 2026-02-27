from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Boolean, ForeignKey, Table, Column
from datetime import datetime
from typing import List

class Base(DeclarativeBase):
  pass

db = SQLAlchemy(model_class=Base)

# Association Model for explicit ordering
class ChoreParticipant(db.Model):
    __tablename__ = "chore_participant"
    chore_id: Mapped[int] = mapped_column(ForeignKey("chore.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    rotation_order: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    chore: Mapped["Chore"] = relationship("Chore", back_populates="participants_association")

class User(db.Model):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    color: Mapped[str] = mapped_column(String, default="#FF6B6B")

class Chore(db.Model):
    __tablename__ = "chore"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    points: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[str] = mapped_column(String, default="pending") # pending, completed
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # Current assignee
    assigned_to_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=True)
    assigned_to: Mapped["User"] = relationship("User", foreign_keys=[assigned_to_id])

    # Round Robin Logic
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Display order for drag reordering
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationship to association model
    participants_association: Mapped[List["ChoreParticipant"]] = relationship(
        "ChoreParticipant", 
        order_by="ChoreParticipant.rotation_order",
        cascade="all, delete-orphan",
        back_populates="chore"
    )
    
    @property
    def participants(self):
        return [p.user for p in self.participants_association]

class MenuItem(db.Model):
    __tablename__ = "menu_item"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[str] = mapped_column(String, nullable=False)  # Monday, Tuesday, etc.
    meal_type: Mapped[str] = mapped_column(String, nullable=False)  # Lunch or Dinner
    food_name: Mapped[str] = mapped_column(String, default="")
    is_cooked: Mapped[bool] = mapped_column(Boolean, default=False)
