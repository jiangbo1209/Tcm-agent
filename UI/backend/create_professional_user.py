"""快速创建专业用户用于测试。"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.user import User
from app.auth.service import get_password_hash

Base.metadata.create_all(bind=engine)

USERNAME = os.getenv("PRO_USERNAME", "admin")
EMAIL = os.getenv("PRO_EMAIL", "admin@tcm.com")
PASSWORD = os.getenv("PRO_PASSWORD", "admin123")

db = SessionLocal()
try:
    existing = db.query(User).filter(User.username == USERNAME).first()
    if existing:
        existing.role = "professional"
        existing.hashed_password = get_password_hash(PASSWORD)
        db.commit()
        print(f"已将用户 '{USERNAME}' 升级为专业用户，密码已重置")
    else:
        user = User(
            username=USERNAME,
            email=EMAIL,
            hashed_password=get_password_hash(PASSWORD),
            role="professional",
        )
        db.add(user)
        db.commit()
        print(f"专业用户创建成功: {USERNAME} / {PASSWORD}")
finally:
    db.close()
