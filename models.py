from sqlalchemy import ForeignKey, Text
from sqlalchemy import create_engine, Table, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import Column, Integer, String, JSON
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


class Entity(Base):
    __tablename__ = 'entities'
    id = Column(Integer, primary_key=True)
    value = Column(String)
    type = Column(String)
    sent_id = Column(Integer)
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


class Predicate(Base):
    __tablename__ = 'predicates'
    id = Column(Integer, primary_key=True)
    predicate = Column(String)
    sent_id = Column(Integer)
    doc_id = Column(Integer, ForeignKey('documents.id'))
    term_id = Column(String)
    roles = Column(JSON)
    doc = relationship("Document", backref=backref("propositions", lazy="dynamic"))

    @property
    def serialize(self):
        return {
            'id': self.id,
            'doc_id': self.doc_id,
            'predicate': self.predicate,
            'roles': json.loads(self.roles),
            'tid_predicate': self.term_id,
            'sent_id': self.sent_id
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


class Opinion(Base):
    __tablename__ = 'opinions'
    id = Column(Integer, primary_key=True)
    expression = Column(String)
    sent_id = Column(Integer)
    target = Column(String)
    holder = Column(String)
    polarity = Column(String)
    doc_id = Column(Integer, ForeignKey('documents.id'))
    doc = relationship("Document", backref=backref("opinions", lazy="dynamic"))

    @property
    def serialize(self):
        return {
            'id': self.id,
            'doc_id': self.doc_id,
            'expression': self.expression,
            'target': self.target,
            'sent_id': self.sent_id,
            'polarity': self.polarity
        }

class Document(Base):
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    text = Column(Text)

    @property
    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'text': self.text
        }


Base.metadata.create_all(engine)
