from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import server_config

engine = create_engine(
    server_config.value.sqlAlchemyDatabaseUrl, 
    connect_args={"check_same_thread": False}
)

# 起名为 SessionLocal，与 sqlalchemy 的 Session 类所区分
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
