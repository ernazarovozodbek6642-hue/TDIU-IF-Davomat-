"""
models.py — PostgreSQL modellari (SQLAlchemy async)
"""
from datetime import datetime, date, timezone
from sqlalchemy import (
    Column, Integer, String, BigInteger,
    Date, DateTime, ForeignKey, UniqueConstraint, Boolean
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def utcnow_naive() -> datetime:
    """UTC timestamp compatible with existing TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BotAdmin(Base):
    """Admins granted the same permissions as configured bootstrap admins."""
    __tablename__ = 'bot_admins'

    telegram_id = Column(BigInteger, primary_key=True, autoincrement=False)
    added_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)


class BotSetting(Base):
    __tablename__ = 'bot_settings'

    key = Column(String(100), primary_key=True)
    value = Column(String(500), nullable=False)
    updated_by = Column(BigInteger, nullable=False)


class Tutor(Base):
    """Tyutorlar jadvali"""
    __tablename__ = "tutors"

    id          = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    name        = Column(String(200), nullable=False)
    created_at  = Column(DateTime, default=utcnow_naive)

    groups      = relationship("TutorGroup", back_populates="tutor", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="tutor")
    sessions    = relationship("AttendanceSession", back_populates="tutor")


class TutorGroup(Base):
    """Tyutor → Guruh bog'lanishi"""
    __tablename__ = "tutor_groups"
    __table_args__ = (UniqueConstraint("tutor_id", "group_name"),)

    id         = Column(Integer, primary_key=True)
    tutor_id   = Column(Integer, ForeignKey("tutors.id", ondelete="CASCADE"), nullable=False)
    group_name = Column(String(50), nullable=False)

    tutor      = relationship("Tutor", back_populates="groups")


class Student(Base):
    """Talabalar ro'yxati (Excel import/export uchun)"""
    __tablename__ = "students"
    __table_args__ = (UniqueConstraint("group_name", "full_name"),)

    id         = Column(Integer, primary_key=True)
    group_name = Column(String(50), nullable=False, index=True)
    full_name  = Column(String(300), nullable=False)
    created_at = Column(DateTime, default=utcnow_naive)


class SubjectKafedra(Base):
    """Fanlar va Kafedralar xaritasi (Excel orqali boshqariladi)"""
    __tablename__ = "subject_kafedras"
    __table_args__ = (UniqueConstraint("subject_name"),)

    id           = Column(Integer, primary_key=True)
    subject_name = Column(String(300), nullable=False, index=True)
    kafedra_name = Column(String(300), nullable=False)
    created_at   = Column(DateTime, default=utcnow_naive)


class EdupageGroup(Base):
    """Edupage Guruh ID lari, Guruh nomi va Kursi xaritasi"""
    __tablename__ = "edupage_groups"
    __table_args__ = (UniqueConstraint("edupage_id"),)

    id           = Column(Integer, primary_key=True)
    edupage_id   = Column(String(50), nullable=False, index=True)   # Masalan: "206", "164"
    group_name   = Column(String(50), nullable=False)               # Masalan: "I-50/24"
    kurs         = Column(String(20), nullable=False, default="1-kurs") # Masalan: "1-kurs", "2-kurs"
    num_param    = Column(String(20), nullable=True, default="94")  # Amaldagi EduPage jadval versiyasi
    created_at   = Column(DateTime, default=utcnow_naive)


class Attendance(Base):
    """Kelmagan talabalar yozuvlari"""
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("date", "group_name", "para", "student_name"),
    )

    id           = Column(Integer, primary_key=True)
    date         = Column(Date, nullable=False, default=date.today, index=True)
    group_name   = Column(String(50), nullable=False, index=True)
    para         = Column(Integer, nullable=False)
    student_name = Column(String(300), nullable=False)
    tutor_id     = Column(Integer, ForeignKey("tutors.id"), nullable=True)
    created_at   = Column(DateTime, default=utcnow_naive)

    tutor        = relationship("Tutor", back_populates="attendances")


class AttendanceSession(Base):
    """Yoqlama sessiyasi — har bir guruh+para+sana uchun yozuv"""
    __tablename__ = "attendance_sessions"
    __table_args__ = (
        UniqueConstraint("date", "group_name", "para", "tutor_id"),
    )

    id           = Column(Integer, primary_key=True)
    date         = Column(Date, nullable=False, default=date.today, index=True)
    group_name   = Column(String(50), nullable=False, index=True)
    para         = Column(Integer, nullable=False)
    all_present  = Column(Boolean, default=False)
    tutor_id     = Column(Integer, ForeignKey("tutors.id"), nullable=True)
    created_at   = Column(DateTime, default=utcnow_naive)

    tutor        = relationship("Tutor", back_populates="sessions")
