"""ORM модели (SQLAlchemy 2.0, Declarative Base)."""
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Telegram ID
    role: Mapped[str] = mapped_column(String(10))  # 'teacher' / 'student'
    name: Mapped[str] = mapped_column(String(128), default="")
    language_level: Mapped[Optional[str]] = mapped_column(String(4), default="A1")  # A1..B2

    topics: Mapped[list["Topic"]] = relationship(back_populates="teacher")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    teacher: Mapped["User"] = relationship(back_populates="topics")
    words: Mapped[list["Word"]] = relationship(back_populates="topic", cascade="all, delete-orphan")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="topic")


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    korean: Mapped[str] = mapped_column(Text)
    russian: Mapped[str] = mapped_column(Text)
    examples_json: Mapped[Optional[str]] = mapped_column(Text, default="[]")  # JSON массив примеров
    approved: Mapped[bool] = mapped_column(Boolean, default=False)

    topic: Mapped["Topic"] = relationship(back_populates="words")
    errors: Mapped[list["ErrorWord"]] = relationship(back_populates="word", cascade="all, delete-orphan")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    topic: Mapped["Topic"] = relationship(back_populates="assignments")


class ErrorWord(Base):
    __tablename__ = "error_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"))
    error_count: Mapped[int] = mapped_column(Integer, default=1)
    correct_streak: Mapped[int] = mapped_column(Integer, default=0)

    word: Mapped["Word"] = relationship(back_populates="errors")
