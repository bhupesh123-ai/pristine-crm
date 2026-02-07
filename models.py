from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text, Date, Boolean
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

# 1. User Table (For login later)
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

# 2. Lead Table (Flexible - No Unique Constraint on Phone)
class Lead(Base):
    __tablename__ = 'leads'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    phone = Column(String) 
    email = Column(String)
    
    queries = relationship("Query", back_populates="lead")

# 3. Query Table (The Trips)
class Query(Base):
    __tablename__ = 'queries'
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey('leads.id'))
    destination = Column(String)
    status = Column(String)
    budget = Column(Float)
    notes = Column(Text)
    created_at = Column(Date, default=datetime.utcnow)
    
    lead = relationship("Lead", back_populates="queries")
    itineraries = relationship("Itinerary", back_populates="query")

# 4. Itinerary Table (To Save AI Results)
class Itinerary(Base):
    __tablename__ = 'itineraries'
    id = Column(Integer, primary_key=True)
    query_id = Column(Integer, ForeignKey('queries.id'))
    content = Column(Text) # The full text
    price = Column(String)
    created_at = Column(Date, default=datetime.utcnow)
    
    query = relationship("Query", back_populates="itineraries")

# Database Setup
engine = create_engine('sqlite:///pristine_crm.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)