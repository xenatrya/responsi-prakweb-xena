from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # admin / staff

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_hewan = db.Column(db.String(100))
    jenis = db.Column(db.String(50))
    tanggal = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))