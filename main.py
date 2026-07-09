from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from passlib.context import CryptContext
from pathlib import Path
import uvicorn
from datetime import datetime

# --- Database Configuration ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./flappybird.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# --- SQLAlchemy Models ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class Score(Base):
    __tablename__ = "scores"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    score = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# --- Dependencies ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

security = HTTPBasic()

def get_current_user(
    credentials: HTTPBasicCredentials = Depends(security), 
    db: Session = Depends(get_db)
):
    """
    Validates user credentials. Creates user if new, verifies password if existing.
    """
    username = credentials.username
    password = credentials.password
    
    if not password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password required",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        # Create new user
        user = User(username=username, hashed_password=get_password_hash(password))
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Verify password
        if not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password",
                headers={"WWW-Authenticate": "Basic"},
            )
    
    return user

# --- FastAPI Application ---
app = FastAPI(title="Flappy Bird with Persistence")

@app.get("/", response_class=HTMLResponse)
async def serve_game():
    """Serves the main game interface."""
    html_file = Path(__file__).parent / "index.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return html_file.read_text(encoding="utf-8")

@app.get("/api/stats")
def get_user_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves the user's personal record and last result."""
    record = db.query(func.max(Score.score)).filter(Score.user_id == user.id).scalar() or 0
    last_score_obj = db.query(Score.score).filter(Score.user_id == user.id).order_by(Score.created_at.desc()).first()
    last_result = last_score_obj[0] if last_score_obj else 0
    
    return {"username": user.username, "record": record, "last_result": last_result}

@app.post("/api/score")
def save_score(score: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Records a new score for the authenticated user."""
    new_score = Score(user_id=user.id, score=score)
    db.add(new_score)
    db.commit()
    return {"status": "success", "score": score}

@app.get("/api/leaderboard")
def get_leaderboard(db: Session = Depends(get_db)):
    """Retrieves the top 10 highest scores across all users."""
    results = db.query(User.username, func.max(Score.score).label('max_score'))\
        .join(Score, User.id == Score.user_id)\
        .group_by(User.username)\
        .order_by(func.max(Score.score).desc())\
        .limit(10).all()
        
    return [{"username": r[0], "score": r[1]} for r in results]

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)