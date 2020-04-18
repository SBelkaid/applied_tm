import urllib
from models import db_session, User
from flask import Flask, request, url_for, redirect, render_template
from flask_graphql import GraphQLView
from schema import schema
import flask_login
from models import Claim
from models import Document
from models import Attribution
from models import Predicate
from models import Opinion
from models import Entity
from flask_login import current_user
import requests
import sqlalchemy
from fuzzywuzzy import process
from collections import defaultdict


login_manager = flask_login.LoginManager()
app = Flask(__name__)
login_manager.init_app(app)
app.secret_key = 'AGhauch3woo5xee'
client = app.test_client()
app.add_url_rule(
    '/graphql',
    view_func=GraphQLView.as_view('graphql', schema=schema, graphiql=True))
users = {'soufyan@isda.xyz': {'password': 'cJH!X9VB16!'}, 'p.t.j.m.vossen@vu.nl': {'password': 'Eep9thoo'}}
session = db_session()
CLAIMS_ATTRIBUTIONS = { doc_id:sent_id for sent_id, doc_id in
                       session.query(Claim.sent_id, Claim.doc_id).filter(Attribution.sent_id == Claim.sent_id,
                                                                         Attribution.doc_id == Claim.doc_id).all()}

ENTITIES = {e[0].lower(): e[1] for e in set(session.query(Entity.value, Entity.type).all())}

QUERY = """
query perspectives($sentence: Int = %s, $documentId: Int = %s) {
  claimList(sentence: $sentence, documentId: $documentId) {
    edges {
      node {
        value
        doc {
          name
          attributions(sentence: $sentence, documentId: $documentId) {
            sentId
            source
            cue
            content
          }
          propositions(sentence: $sentence, documentId: $documentId) {
            sentId
            predicate
            roles
          }
          opinions(sentence: $sentence, documentId: $documentId) {
            sentId
            expression
            target
          }
          entities(sentence: $sentence, documentId: $documentId) {
            type
            value
          }
        }
      }
    }
  }
}
"""


@login_manager.user_loader
def user_loader(email):
    if email not in users:
        return

    user = User()
    user.id = email
    return user


@login_manager.request_loader
def request_loader(request):
    email = request.form.get('email')
    if email not in users:
        return

    user = User()
    user.id = email

    # DO NOT ever store passwords in plaintext and always compare password
    # hashes using constant-time comparison!
    user.is_authenticated = request.form['password'] == users[email]['password']

    return user


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        if request.form['password'] == users[email]['password']:
            user = User()
            user.id = email
            flask_login.login_user(user)
            return redirect(url_for('viewer'))
    if request.method == 'GET' and current_user.is_authenticated is False:
        return render_template('login.html')
    return redirect(url_for('viewer'))


def create_gq_request(q, connection_list, item):
    r = requests.post("http://127.0.0.1:8999/graphql", json={'query': q})
    if r.status_code == 200:
        return [node['node'][item] for node in r.json()['data'][connection_list]['edges']]


def fuzzy_match(l1,l2, value1, value2, th=90):
    matching = []
    faulty = ['|', '>', '-', '"', '', "'", None]
    for e in l1:
        search_val = e[value1]
        if search_val not in faulty:
            values = [other_el[value2] for other_el in l2 if other_el[value2] not in faulty]
            searched = process.extract(search_val, values)
            best_match = list(filter(lambda x: x[1] > th, searched))
            if not best_match:
                continue
            index = values.index(best_match[0][0])
            matching.append({value1:search_val, value2:l2[index]})
    return matching


def get_all_data(doc_id):
    claims = [c.serialize for c in Claim.query.filter_by(doc_id=doc_id).all()]
    attributions = [a.serialize for a in Attribution.query.filter_by(doc_id=doc_id).all()]
    props = [p.serialize for p in Predicate.query.filter_by(doc_id=doc_id)]
    entities = [a.serialize for a in Entity.query.filter_by(doc_id=doc_id).all()]
    raw_text = Document.query.filter_by(id=doc_id).one().serialize
    opinions = [o.serialize for o in
                filter(lambda x: x.target is not None, Opinion.query.filter_by(doc_id=doc_id).all())]
    perspectives = create_perspectives(claims, attributions, props, opinions, entities)


def create_perspectives(claims, attributions, propositions, opinions, entities):
    perspectives = {}
    matching_c_a = fuzzy_match(claims, attributions, 'value', 'content')
    matching_a_p = fuzzy_match(attributions, propositions, 'cue', 'predicate')
    matching_a_e = fuzzy_match(attributions, entities, 'source', 'value')
    # matching_a_o = fuzzy_match(attributions, opinions, 'content', 'expression', 95)
    matching_p_o = fuzzy_match(matching_a_p, opinions, 'cue', 'expression')
    matching_c_o = fuzzy_match(matching_c_a, opinions, 'value', 'expression')
    for i, e in enumerate(matching_c_a):
        perspectives[i] = {'source': e['content']['source'], 'cue': e['content']['cue'], 'argument': e['value']}
        try:
            perspectives[i]['sentiment_cue'] = matching_p_o[[a['cue'] for a in matching_p_o].index(perspectives[i]['cue'])]['expression']['polarity']
            perspectives[i]['roles'] = matching_a_p[[a['cue'] for a in matching_p_o].index(perspectives[i]['argument'])]['predicate']['roles']
            perspectives[i]['sentiment_argument'] = \
                matching_c_o[[a['value'] for a in matching_c_o].index(perspectives[i]['argument'])]['expression']['polarity']
            perspectives[i]['source_entity'] = ENTITIES.get(perspectives[i]['source'].lower())
        except ValueError:
            continue
    print(matching_p_o)
    print(perspectives)
    return perspectives




@app.route('/viewer/<int:doc_id>', methods=['GET'])
@app.route('/viewer', methods=['GET'])
@flask_login.login_required
def viewer(doc_id=None):
    all_docs = ([doc.id, doc.name] for doc in Document.query.all())

    try:
        if doc_id:
            # graphql_url = urllib.parse.urljoin(request.url_root, url_for('graphql'))
            # print(CLAIMS_ATTRIBUTIONS[doc_id])
            # q_with_vars = QUERY % (doc_id, CLAIMS_ATTRIBUTIONS[doc_id])
            # r = requests.post(graphql_url, json={'query': q_with_vars})
            # if r.status_code == 200:
                # print(r.text)
            claims = [c.serialize for c in Claim.query.filter_by(doc_id=doc_id).all()]
            attributions = [a.serialize for a in Attribution.query.filter_by(doc_id=doc_id).all()]
            props = [p.serialize for p in Predicate.query.filter_by(doc_id=doc_id)]
            entities = [a.serialize for a in Entity.query.filter_by(doc_id=doc_id).all()]
            raw_text = Document.query.filter_by(id=doc_id).one().serialize
            opinions = [o.serialize for o in filter(lambda x: x.target is not None, Opinion.query.filter_by(doc_id=doc_id).all())]
            perspectives = create_perspectives(claims, attributions, props, opinions, entities)
            return render_template('viewer.html', raw_text=raw_text, claims=claims, perspectives=perspectives,
                                   attributions=attributions, props=props, opinions=opinions, doc_nav=all_docs)
    except sqlalchemy.orm.exc.NoResultFound as e:
        return render_template('404.html'), 404
    return render_template('viewer.html', doc_nav=all_docs)


@app.route('/logout')
def logout():
    flask_login.logout_user()
    return redirect(url_for('login'))


@app.route('/')
def index():
    return redirect(url_for('login'))


class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


@login_manager.unauthorized_handler
def unauthorized_handler():
    return render_template('403.html')
    # raise AuthError({"code": "unathorized",
    #                  "description": "Not allowed"}, 403)


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


if __name__ == '__main__':
    app.run(threaded=True, debug=True, port=8999)
