from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

from multiconfig import getConfig

conf = None
engine = None
Base = None

def init():
    global conf, engine, Base
    conf = getConfig('lunchroom')
    engine = create_engine(conf.get('Database'))
    Base = declarative_base()