import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import settings

Base = declarative_base()
engine = sa.create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


class Program(Base):
    __tablename__ = 'programs'

    slug = sa.Column(sa.String, primary_key=True)
    id = sa.Column(sa.Integer, nullable=False)
    title = sa.Column(sa.String, nullable=False)
    exam_dates = sa.Column(JSONB, nullable=True)
    admission_quotas = sa.Column(JSONB, nullable=True)
    study_plan_url = sa.Column(sa.String, nullable=False)
    study_plan_file = sa.Column(sa.String, nullable=False)
    study_plan_text = sa.Column(sa.Text, nullable=True)


Base.metadata.create_all(bind=engine)
