import os
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index, text

db = SQLAlchemy()


class Generation(db.Model):
    __tablename__ = "generations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(128), nullable=False, index=True)
    doc_type = db.Column(db.String(64), nullable=True)
    prompt_length = db.Column(db.Integer, default=0)
    status = db.Column(db.String(32), default="started")
    success = db.Column(db.Boolean, default=False)
    error = db.Column(db.Text, nullable=True)
    model = db.Column(db.String(64), nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)
    tool_calls = db.Column(db.Integer, default=0)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    finished_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        Index("idx_generation_session", "session_id", "created_at"),
        Index("idx_generation_status", "status", "created_at"),
    )


class Export(db.Model):
    __tablename__ = "exports"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(128), nullable=False, index=True)
    fmt = db.Column(db.String(16), nullable=False)
    doc_type = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(32), default="started")
    success = db.Column(db.Boolean, default=False)
    error = db.Column(db.Text, nullable=True)
    content_size = db.Column(db.Integer, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_export_session", "session_id", "created_at"),
        Index("idx_export_fmt", "fmt", "created_at"),
    )


class Upload(db.Model):
    __tablename__ = "uploads"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(128), nullable=False, index=True)
    filename = db.Column(db.String(256), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    file_type = db.Column(db.String(16), nullable=False)
    status = db.Column(db.String(32), default="processed")
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (Index("idx_upload_session", "session_id", "created_at"),)


class ApiUsage(db.Model):
    __tablename__ = "api_usage"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip_address = db.Column(db.String(64), nullable=False, index=True)
    endpoint = db.Column(db.String(128), nullable=False, index=True)
    session_id = db.Column(db.String(128), nullable=True, index=True)
    status_code = db.Column(db.Integer, nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_api_usage_ip", "ip_address", "created_at"),
        Index("idx_api_usage_endpoint", "endpoint", "created_at"),
    )


def init_db(app):
    db_url = os.getenv("DATABASE_URL", "sqlite:///aidoc.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    engine_opts = {
        "pool_pre_ping": True,
    }
    is_sqlite = db_url.startswith("sqlite")
    if not is_sqlite:
        engine_opts["pool_size"] = int(os.getenv("DB_POOL_SIZE", "10"))
        engine_opts["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_opts
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
    return db
