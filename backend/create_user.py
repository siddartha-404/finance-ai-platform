from database.database import SessionLocal
from database import models
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_admin():
    db = SessionLocal()
    username = "Admin" 
    password = "finance2026"
    
    # Check if this specific Admin exists
    user = db.query(models.User).filter(models.User.username == username).first()
    
    hashed_pwd = pwd_context.hash(password)
    
    if not user:
        new_user = models.User(username=username, hashed_password=hashed_pwd, role="advisor")
        db.add(new_user)
        print(f"✅ User '{username}' created!")
    else:
        # Force update the password just in case it was different
        user.hashed_password = hashed_pwd
        print(f"🔄 User '{username}' password updated!")
        
    db.commit()
    db.close()

if __name__ == "__main__":
    create_admin()