from models import db_session, User
from flask import Flask, request, url_for, redirect, render_template
from models import Claim
from models import Document
from models import Attribution
from models import Entity
from models import Perspective
from flask_login import current_user
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import sqlalchemy
import flask_login


login_manager = flask_login.LoginManager()
app = Flask(__name__)
login_manager.init_app(app)
app.secret_key = 'AGhauch3woo5xee'
client = app.test_client()
users = {'soufyan@isda.xyz': {'password': 'cJH!X9VB16!'}, 'p.t.j.m.vossen@vu.nl': {'password': 'Eep9thoo'}}
session = db_session()
analyser = SentimentIntensityAnalyzer()
CLAIMS_ATTRIBUTIONS = {doc_id:sent_id for sent_id, doc_id in
                       session.query(Claim.sent_id, Claim.doc_id).filter(Attribution.sent_id == Claim.sent_id,
                                                                         Attribution.doc_id == Claim.doc_id).all()}

ENTITIES = {e[0].lower(): e[1] for e in set(session.query(Entity.value, Entity.type).all())}

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


class PerspectiveViewer:
    def __init__(self, serialized_perspective):
        self.mapping = serialized_perspective['term_to_word']
        self.statement = serialized_perspective['statement']
        self.cue = serialized_perspective['cue']
        self.opinion_info = serialized_perspective['opinion_info']
        self.roles_span = serialized_perspective['roles_span']
        self.source_entity = serialized_perspective['source_entity']
        self.doc_id = serialized_perspective['doc_id']
        self.sentiment = serialized_perspective['sentiment']

    def get_key(self, tid):
        roles = [key for (key, value) in self.roles_span.items() if tid in value]
        if not roles:
            if self.mapping[tid] == self.cue:
                return "CUE"
            return None
        return roles.pop()

    def get_opinion_info(self):
        return [f"<p>expression: {opinion['expression']}, target: {opinion['target']}, polarity: {opinion['polarity']}</p>" for opinion in self.opinion_info]

    def construct_statement(self):
        return [(self.mapping[token_id], token_id) for token_id in sorted(self.mapping, key=lambda x: int(x[1:]))]


@app.route('/viewer/<int:doc_id>', methods=['GET'])
@app.route('/viewer', methods=['GET'])
@flask_login.login_required
def viewer(doc_id=None):
    all_docs = ([doc.id, doc.name] for doc in Document.query.all())
    try:
        if doc_id:
            doc = Perspective.query.filter_by(doc_id=doc_id).all()
            article = Document.query.filter_by(id=doc_id).one().name
            claims = [c.serialize for c in Claim.query.filter_by(doc_id=doc_id).all()]
            attributions = [a.serialize for a in doc]
            perspectives = [PerspectiveViewer(pers.serialize) for pers in doc]
            entities = [a.serialize for a in Entity.query.filter_by(doc_id=doc_id).all()]
            raw_text = Document.query.filter_by(id=doc_id).one().serialize
            return render_template('viewer.html', doc_name=article, raw_text=raw_text, claims=claims,
                                   attributions=attributions, doc_nav=all_docs,
                                   perspectives=perspectives)
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
