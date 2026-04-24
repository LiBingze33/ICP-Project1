import sqlalchemy as db
from sqlalchemy.orm import declarative_base, sessionmaker

#Use SQLite
#store the database in a file called app.db
#place it in the current project folder

engine = db.create_engine('sqlite:///./database.db', echo=True)
#Create a Session Object to initiate query in database
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
