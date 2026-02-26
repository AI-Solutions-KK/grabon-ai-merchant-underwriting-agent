from app.db.base import Base
from app.db.session import engine

# Import all models to register them with Base
from app.models.merchant import Merchant
from app.models.risk_score import RiskScore


def init_db():
    """
    Initialize database by creating all tables.
    
    Imports all models and creates tables defined in the Base metadata.
    This function should be called once at application startup.
    """
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
