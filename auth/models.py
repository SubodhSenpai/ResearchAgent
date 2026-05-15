from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, ForeignKey, Text, JSON, Index, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime
import uuid


class Base(DeclarativeBase):
    pass


# ── Portable UUID type (works on SQLite + PostgreSQL) ────────
class GUID(TypeDecorator):
    """Platform-independent UUID type.
    Uses PostgreSQL's UUID type when available, otherwise stores as CHAR(36).
    """
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value) if not isinstance(value, uuid.UUID) else value
        return value


class User(Base):
    __tablename__ = "users"

    user_id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    chat_histories = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")
    api_tokens = relationship("APIToken", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("UserDocument", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(user_id={self.user_id}, username={self.username}, email={self.email})>"


class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.user_id"), nullable=False, index=True)
    query = Column(String(1000), nullable=False)
    final_answer = Column(Text, nullable=True)
    quality_score = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), default="running", nullable=False)
    tokens_used = Column(Integer, default=0, nullable=False)
    cost_estimate = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="sessions")
    chat_histories = relationship("ChatHistory", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Session(session_id={self.session_id}, user_id={self.user_id}, status={self.status})>"


class ChatHistory(Base):
    __tablename__ = "chat_history"

    history_id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    session_id = Column(GUID(), ForeignKey("sessions.session_id"), nullable=False, index=True)
    user_id = Column(GUID(), ForeignKey("users.user_id"), nullable=False, index=True)
    message_type = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    embedding_vector = Column(JSON, nullable=True)
    relevance_score = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    session = relationship("Session", back_populates="chat_histories")
    user = relationship("User", back_populates="chat_histories")

    def __repr__(self):
        return f"<ChatHistory(history_id={self.history_id}, session_id={self.session_id}, type={self.message_type})>"


class APIToken(Base):
    __tablename__ = "api_tokens"

    token_id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.user_id"), nullable=False, index=True)
    token_hash = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_used = Column(DateTime, nullable=True)
    is_revoked = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", back_populates="api_tokens")

    def __repr__(self):
        return f"<APIToken(token_id={self.token_id}, user_id={self.user_id}, expires_at={self.expires_at})>"


class UserDocument(Base):
    __tablename__ = "user_documents"

    document_id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.user_id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    pageindex_doc_id = Column(String(255), nullable=False, unique=True)
    status = Column(String(50), default="indexed", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="documents")

    def __repr__(self):
        return f"<UserDocument(document_id={self.document_id}, filename={self.filename}, user_id={self.user_id})>"
