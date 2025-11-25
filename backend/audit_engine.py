# backend/audit_engine.py - FIXED VERSION
import os
import sys
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import hashlib
from urllib.parse import urlparse, urljoin
import json
import re
from enum import Enum
import numpy as np
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Use the same Base from main.py by importing it later
# Remove this line: Base = declarative_base()

# Database setup (use same as main.py)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://seo_user:seo_password@localhost/seo_tool")
from sqlalchemy import create_engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Import Base from main AFTER we define our models
def get_base():
    from main import Base
    return Base

Base = None  # Will be set later
