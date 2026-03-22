import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

# Load the hidden password from the .env file
load_dotenv()

# Get the connection string
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Create the engine (the actual connection pipeline)
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create a session factory (how we talk to the DB in our app)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a base class for our data models (Clients, Portfolios, etc.)
Base = declarative_base()

# Dependency to get the DB session in our API routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()