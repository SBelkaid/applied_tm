from sqlalchemy import ForeignKey, Text
from sqlalchemy import create_engine, Table, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import Column, Integer, String, JSON, BLOB
import flask_login
import json

Base = declarative_base()
DATABASE_URI = 'sqlite.db'
engine = create_engine('sqlite:///' + DATABASE_URI)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base.query = db_session.query_property()


class User(flask_login.UserMixin):
    pass


class Perspective(Base):
    __tablename__ = 'perspectives'
    id = Column(Integer, primary_key=True)
    statement = Column(String)
    statement_span = Column(JSON)
    opinion_info = Column(JSON)
    cue = Column(String)
    frame = Column(String)
    roles_span = Column(JSON)
    roles_text = Column(JSON)
    order = Column(String)
    term_to_word = Column(JSON)
    source_entity = Column(String)
    target_entity = Column(String)
    sentiment = Column(String)
    doc_id = Column(Integer, ForeignKey('documents.id'))
    doc = relationship("Document", backref=backref("perspectives     ", lazy="dynamic"))

    @property
    def serialize(self):
        return {
            'statement': self.statement,
            'statement_span': self.statement_span,
            'cue': self.cue,
            'opinion_info': self.opinion_info,
            'roles_span': self.roles_span,
            'roles_text': self.roles_text,
            'term_to_word': self.term_to_word,
            'source_entity': self.source_entity,
            'target_entity': self.target_entity,
            'doc_id': self.doc_id,
            'sentiment': self.sentiment,
            'frame': self.frame
        }


class Entity(Base):
    __tablename__ = 'entities'
    id = Column(Integer, primary_key=True)
    value = Column(String)
    type = Column(String)
    sent_id = Column(Integer)
    span = Column(JSON)
    doc_id = Column(Integer, ForeignKey('documents.id'))
    doc = relationship("Document", backref=backref("entities", lazy="dynamic"))

    @property
    def serialize(self):
        return {
            'id': self.id,
            'value': self.value,
            'type': self.type,
            'sent_id': self.sent_id
        }


class Claim(Base):
    __tablename__ = 'claims'
    id = Column(Integer, primary_key=True)
    value = Column(String)
    sent_id = Column(Integer)
    token_ids = Column(JSON)
    doc_id = Column(Integer, ForeignKey('documents.id'))
    doc = relationship("Document", backref=backref("claims", lazy="dynamic"))

    @property
    def serialize(self):
        return {
            'id': self.id,
            'value': self.value,
            'sent_id': self.sent_id,
            'doc_id': self.doc_id
        }


class Attribution(Base):
    __tablename__ = 'attributions'
    id = Column(Integer, primary_key=True)
    source = Column(String)
    cue = Column(String)
    content = Column(String)
    sent_id = Column(Integer)
    doc_id = Column(Integer, ForeignKey('documents.id'))
    doc = relationship("Document", backref=backref("attributions", lazy="dynamic"))

    @property
    def serialize(self):
        return {
            'id': self.id,
            'doc_id': self.doc_id,
            'source': self.source,
            'cue': self.cue,
            'content': self.content,
            'sent_id': self.sent_id
        }


class Document(Base):
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    text = Column(Text)
    url = Column(String)
    publisher = Column(String)
    author = Column(String)

    @property
    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'text': self.text
        }


Base.metadata.create_all(engine)
