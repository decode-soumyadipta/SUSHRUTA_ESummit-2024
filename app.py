from flask import Flask, render_template, redirect, url_for, request, session, flash,jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import json
import re
import io
import logging
import os
from datetime import datetime
from flask_mail import Mail, Message
from flask_bcrypt import Bcrypt
from flask_mysqldb import MySQL




with open('config.json', 'r') as c:
    config_params = json.load(c)["params"]

local_server = True


app =Flask(__name__)
app.secret_key = 'soumo-diamond'
app.config['UPLOAD_FOLDER'] = config_params['upload_location']
app.config['SESSION_TYPE'] = 'filesystem'
app.config.from_object(Config)  
app.config['GOOGLE_OAUTH_CLIENT_ID'] = 'your_google_client_id'
app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = 'your_google_client_secret'
app.config['FACEBOOK_OAUTH_CLIENT_ID'] = 'your_facebook_client_id'
app.config['FACEBOOK_OAUTH_CLIENT_SECRET'] = 'your_facebook_client_secret'




app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT='465',
    MAIL_USE_SSL=True,
    MAIL_USERNAME=config_params['gmail-id'],
    MAIL_PASSWORD=config_params['gmail-password'],
    MYSQL_USER=config_params['mysql_user'],
    MYSQL_PASSWORD=config_params['mysql_password'],
    MYSQL_DB=config_params['mysql_db'],
    MYSQL_HOST=config_params['mysql_host']
)
def truncate_words(s, num):
    if not s:
        return ''
    words = re.findall(r'\w+', s)
    if len(words) > num:
        return ' '.join(words[:num]) + '...'
    return s

app.jinja_env.filters['truncate_words'] = truncate_words








def get_access_token():
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    response = requests.post(ACCESS_TOKEN_URL, data=data)
    token_info = response.json()
    return token_info['access_token']



def generate_checksum(params, merchant_key):
    params_str = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
    params_str += f'&{merchant_key}'
    return hashlib.sha256(params_str.encode()).hexdigest()

def verify_checksum(params, merchant_key, received_checksum):
    params_str = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
    params_str += f'&{merchant_key}'
    return hashlib.sha256(params_str.encode()).hexdigest() == received_checksum



ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov','csv'}  # Add any other allowed extensions here

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


mail = Mail(app)
mysql = MySQL(app) 
bcrypt = Bcrypt(app)
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
google_bp = make_google_blueprint(
    client_id=config_params['google_client_id'],
    client_secret=config_params['google_client_secret'],
    redirect_to='google_login'
)
facebook_bp = make_facebook_blueprint(redirect_to='facebook_login')

app.register_blueprint(google_bp, url_prefix='/login')
app.register_blueprint(facebook_bp, url_prefix='/login')

logging.basicConfig()


login_manager = LoginManager(app)
login_manager.login_view = 'signin'  # Redirect to signin page if unauthorized
login_manager.login_message_category = 'danger'

if local_server:
    app.config['SQLALCHEMY_DATABASE_URI'] = config_params['local_uri']
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = config_params['prod_uri']

db.init_app(app)
