from flask import Flask, request, jsonify, redirect, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os, pathlib, requests
from pytube import YouTube
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests


#Setup

app=Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['JSON_SORT_KEYS'] = False
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

#db config
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app,db)


#Models

class Videos(db.Model):
    vid = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String, nullable=False)
    author = db.Column(db.String, nullable=False)
    publish_date = db.Column(db.DateTime, nullable=False)
    thumbnail_url = db.Column(db.String, nullable=False)
    length = db.Column(db.Integer, nullable=False)
    size = db.Column(db.BigInteger, nullable=False)
    description = db.Column(db.String, nullable=False)
    url = db.Column(db.String, nullable=False)
    res = db.Column(db.String, nullable=False)
    
    def __init__(self, title, author, publish_date, thumbnail_url, length, size, description, url, res ):
        self.title = title
        self.author = author
        self.publish_date = publish_date
        self.thumbnail_url = thumbnail_url
        self.length = length
        self.size = size
        self.description = description
        self.url = url
        self.res = res
    
    def __repr__(self):
        return f"{self.title}. {self.author}, {self.publish_date}, {self.thumbnail_url}, {self.length}, {self.size}, {self.description}, {self.url}, {self.res}"


#Routes

#Download and Save Data to DB

@app.route('/download', methods=['POST'])
def download():
    link = request.json['link']
    res = request.json['res']
    dvideo = YouTube(link)
    stream = dvideo.streams.filter(res=res).first()
    video = Videos(
        title = dvideo.title,
        author = dvideo.author,
        publish_date = dvideo.publish_date,
        thumbnail_url = dvideo.thumbnail_url,
        length = dvideo.length,
        size = stream.filesize,
        description = dvideo.description,
        url = link,
        res = res[:-1]
    )
    db.session.add(video)
    db.session.commit()
    stream.download()
    return jsonify("Video downloaded")


#view downloads

@app.route('/download', methods=['GET'])
def view_downloads():
    min_length = int(request.json['length'])
    min_res = int((request.json['res'])[:-1])
    page = request.args.get('page', 1, type=int)
    videos = Videos.query.filter(Videos.length>=min_length, Videos.res>=min_res).paginate(page, int(os.environ.get('VIDEOS_PER_PAGE')), False).items
    video_dict = []
    for video in videos:
        vdata = {"title": video.title, "author": video.author, "publish_date": video.publish_date, "thumbnail_url": video.thumbnail_url, "length": video.length, "size": video.size, "description": video.description, "url": video.url, "resolution": video.res}
        video_dict.append(vdata)
    return jsonify(video_dict)

#Sign In

def login_required(function):
    def wrapper(*args, **kwargs):
        if "google_id" not in session:
            return abort(401)
        else:
            return function()

    return wrapper

client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri="http://127.0.0.1:5000/callback"
)

@app.route("/login")
def login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)


@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        abort(500)

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=os.environ.get('GOOGLE_CLIENT_ID')
    )

    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route('/')
def index():
    if session:
        return f"Welcome {session['name']}"
    else:
        return f"Login to see name"


#run
if __name__ == '__main__':
    app.run(debug=True)