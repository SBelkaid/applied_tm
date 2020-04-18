from graphene_sqlalchemy import SQLAlchemyConnectionField
from graphene_sqlalchemy import SQLAlchemyObjectType
from models import Claim as ClaimModel
from models import Attribution as AttribtutionModel
from models import Document as DocumentModel
from models import Opinion as OpinionModel
from models import Entity as EntityModel
from models import Predicate as PropositionModel
import graphene
import json
import flask_login


class ClaimAttribute:
    value = graphene.String(description="Name of the planet.")
    doc_id = graphene.String(description="The id of the document that it was parsed from")


class Claim(SQLAlchemyObjectType, ClaimAttribute):
    """Claim node."""

    class Meta:
        model = ClaimModel
        interfaces = (graphene.relay.Node,)


class AttributionAttribute:
    source = graphene.String(description="Source of the attribution")
    cue = graphene.String(description="Cue of the attribution")
    content = graphene.String(description="Content of the attribution")
    sentiment = graphene.String(description="Sentiment of the attribution")


class Attribution(SQLAlchemyObjectType, AttributionAttribute):
    """Attribution node"""

    class Meta:
        model = AttribtutionModel
        interfaces = (graphene.relay.Node,)


class Proposition(SQLAlchemyObjectType):
    """document node"""

    # role = graphene.Field(Role)
    roles = graphene.List(graphene.types.String)

    class Meta:
        model = PropositionModel
        interfaces = (graphene.relay.Node,)

    def resolve_roles(parent, info, **kwargs):
        return json.loads(parent.roles).items()


class DocAttribute:
    name = graphene.String(description="Article name")
    text = graphene.String(description="Raw text of the document")


class OpinionAttribute:
    target = graphene.String(description="Opinion target")
    holder = graphene.String(description="Raw text of the document")
    expression = graphene.String(description="Raw text of the document")
    polarity = graphene.String(description="Raw text of the document")


class Opinion(SQLAlchemyObjectType, OpinionAttribute):
    """Opinion node"""

    class Meta:
        model = OpinionModel
        interfaces = (graphene.relay.Node,)


class EntityAttribute:
    type = graphene.String(description="Article name")
    value = graphene.String(description="Raw text of the document")


class Entity(SQLAlchemyObjectType, EntityAttribute):
    """Entity node"""

    class Meta:
        model = EntityModel
        interfaces = (graphene.relay.Node,)


class Document(SQLAlchemyObjectType, DocAttribute):
    """document node"""

    attributions = graphene.List(Attribution, document_id=graphene.Int(), sentence=graphene.Int())
    propositions = graphene.List(Proposition, document_id=graphene.Int(), sentence=graphene.Int())
    opinions = graphene.List(Opinion, document_id=graphene.Int(), sentence=graphene.Int())
    entities = graphene.List(Entity, document_id=graphene.Int(), sentence=graphene.Int())

    def resolve_attributions(parent, info, document_id, sentence):
        attributions_in_doc = parent.query.filter_by(id=document_id).one().attributions.all()
        return (attr for attr in attributions_in_doc if attr.sent_id == sentence)

    def resolve_propositions(parent, info, document_id, sentence):
        propositions_in_doc = parent.query.filter_by(id=document_id).one().propositions.all()
        return (prop for prop in propositions_in_doc if prop.sent_id == sentence)

    def resolve_opinions(parent, info, document_id, sentence):
        opinions_in_doc = parent.query.filter_by(id=document_id).one().opinions.all()
        return (opinion for opinion in opinions_in_doc if opinion.sent_id == sentence)

    def resolve_entities(parent, info, document_id, sentence):
        entities_in_doc = parent.query.filter_by(id=document_id).one().entities.all()
        return (entity for entity in entities_in_doc if entity.sent_id == sentence)

    class Meta:
        model = DocumentModel
        interfaces = (graphene.relay.Node,)


class Query(graphene.ObjectType):
    """Query objects for GraphQL API."""

    node = graphene.relay.Node.Field()
    claim = graphene.relay.Node.Field(Claim)
    claimList = SQLAlchemyConnectionField(Claim, sentence=graphene.Int(), document_id=graphene.Int())
    attribution = graphene.relay.Node.Field(Attribution)
    attributionList = SQLAlchemyConnectionField(Attribution, sentence=graphene.Int(), document_id=graphene.Int())
    document = graphene.relay.Node.Field(Document)
    documentList = SQLAlchemyConnectionField(Document, document_id=graphene.Int())
    opinion = graphene.relay.Node.Field(Opinion)
    opinionList = SQLAlchemyConnectionField(Opinion, sentence=graphene.Int(), document_id=graphene.Int())
    entity = graphene.relay.Node.Field(Entity)
    entityList = SQLAlchemyConnectionField(Entity, sentence=graphene.Int(), document_id=graphene.Int())
    proposition = graphene.relay.Node.Field(Proposition)
    propositionList = SQLAlchemyConnectionField(Proposition, sentence=graphene.Int(), document_id=graphene.Int())

    # @flask_login.login_required
    def resolve_claimList(self, info, **kwargs):
        doc_id = kwargs.get('document_id')
        sent_id = kwargs.get('sentence')
        return ClaimModel.query.filter_by(doc_id=doc_id).all()

    # @flask_login.login_required
    def resolve_attributionList(self, info, **kwargs):
        doc_id = kwargs.get('document_id')
        sent_id = kwargs.get('sentence')
        return AttribtutionModel.query.filter_by(doc_id=doc_id, sent_id=sent_id).all()

    def resolve_documentList(self, info, **kwargs):
        doc_id = kwargs.get('document_id')
        return DocumentModel.query.filter_by(id=doc_id).all()

    # @flask_login.login_required
    def resolve_opinionList(self, info, **kwargs):
        doc_id = kwargs.get('document_id')
        sent_id = kwargs.get('sentence')
        return OpinionModel.query.filter_by(doc_id=doc_id, sent_id=sent_id).all()

    # @flask_login.login_required
    def resolve_entityList(self, info, **kwargs):
        doc_id = kwargs.get('document_id')
        sent_id = kwargs.get('sentence')
        return EntityModel.query.filter_by(doc_id=doc_id, sent_id=sent_id).all()

    # @flask_login.login_required
    def resolve_propositionList(self, info, **kwargs):
        doc_id = kwargs.get('document_id')
        sent_id = kwargs.get('sentence')
        return PropositionModel.query.filter_by(doc_id=doc_id, sent_id=sent_id).all()


schema = graphene.Schema(query=Query)
