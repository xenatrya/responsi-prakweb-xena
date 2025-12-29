from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text
import os

app = Flask(__name__)
app.secret_key = "secret-key-grooming"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    duration = db.Column(db.String(50), nullable=True)


class Pet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    jenis = db.Column(db.String(50), nullable=False)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_hewan = db.Column(db.String(100), nullable=False)
    jenis = db.Column(db.String(100), nullable=False)
    owner_name = db.Column(db.String(100), nullable=True)
    tanggal = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), nullable=False, default='pending')
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'))
    price = db.Column(db.Float, nullable=False, default=0.0)
    jam = db.Column(db.String(20), nullable=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


with app.app_context():
    db.create_all()

    # Lightweight migration: if `booking` table existed before adding new columns,
    # add missing columns so the app won't crash. SQLite supports ADD COLUMN.
    try:
        existing = [row[1] for row in db.session.execute(text("PRAGMA table_info('booking')")).fetchall()]
        if 'status' not in existing:
            db.session.execute(text("ALTER TABLE booking ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending'"))
        if 'service_id' not in existing:
            db.session.execute(text("ALTER TABLE booking ADD COLUMN service_id INTEGER"))
        if 'price' not in existing:
            db.session.execute(text("ALTER TABLE booking ADD COLUMN price REAL NOT NULL DEFAULT 0.0"))
        if 'jam' not in existing:
            db.session.execute(text("ALTER TABLE booking ADD COLUMN jam VARCHAR(20)"))
        if 'owner_name' not in existing:
            db.session.execute(text("ALTER TABLE booking ADD COLUMN owner_name VARCHAR(100)"))
        # ensure service table has new columns before any Service.query runs
        svc_info = [row[1] for row in db.session.execute(text("PRAGMA table_info('service')")).fetchall()]
        if 'description' not in svc_info:
            db.session.execute(text("ALTER TABLE service ADD COLUMN description VARCHAR(255)"))
        if 'duration' not in svc_info:
            db.session.execute(text("ALTER TABLE service ADD COLUMN duration VARCHAR(50)"))
        db.session.commit()
    except Exception:
        db.session.rollback()

    # seed users
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", role="admin")
        admin.set_password("admin123")

        staff = User(username="staff", role="staff")
        staff.set_password("staff123")

        db.session.add_all([admin, staff])
        db.session.commit()

    # seed services
    if not Service.query.first():
        services = [
            Service(name='Basic Grooming', price=100000, description='Perawatan dasar meliputi mandi, pengeringan, pembersihan telinga, dan potong kuku.', duration='1 jam'),
            Service(name='Full Grooming', price=200000, description='Perawatan lengkap termasuk mandi, grooming menyeluruh, dan perapihan bulu.', duration='2 jam'),
            Service(name='Nail Trim', price=30000, description='Pemotongan kuku hewan agar tetap rapi, aman, dan nyaman.', duration='15 menit'),
        ]
        db.session.add_all(services)
        db.session.commit()

    # seed pets
    if not Pet.query.first():
        pets = [
            Pet(nama='Mimi', jenis='Kucing'),
            Pet(nama='Bobby', jenis='Anjing')
        ]
        db.session.add_all(pets)
        db.session.commit()
    

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # authenticate by username only; role is determined from the user record
        user = User.query.filter_by(username=request.form['username']).first()

        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Login gagal — periksa username dan password', 'danger')
        return render_template('login.html')

    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        data = Booking.query.order_by(Booking.tanggal).all()
        total_revenue = db.session.query(db.func.sum(Booking.price)).filter(Booking.status == 'done').scalar() or 0
    else:
        data = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.tanggal).all()
        total_revenue = None

    services = {s.id: s for s in Service.query.all()}
    services_list = Service.query.all()
    return render_template('dashboard.html', data=data, services=services, services_list=services_list, total_revenue=total_revenue)


@app.route('/services')
@login_required
def services_page():
    services = Service.query.order_by(Service.price).all()
    return render_template('services.html', services=services)


@app.route('/services/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_service(id):
    if current_user.role != 'admin':
        return redirect(url_for('services_page'))

    svc = Service.query.get_or_404(id)
    if request.method == 'POST':
        svc.name = request.form.get('name')
        svc.price = float(request.form.get('price') or 0)
        svc.description = request.form.get('description')
        svc.duration = request.form.get('duration')
        db.session.commit()
        flash('Layanan berhasil diperbarui.', 'success')
        return redirect(url_for('services_page'))

    return render_template('edit_service.html', service=svc)


@app.route('/services/add', methods=['GET', 'POST'])
@login_required
def add_service():
    if current_user.role != 'admin':
        return redirect(url_for('services_page'))

    if request.method == 'POST':
        name = request.form.get('name')
        price = float(request.form.get('price') or 0)
        description = request.form.get('description')
        duration = request.form.get('duration')
        svc = Service(name=name, price=price, description=description, duration=duration)
        db.session.add(svc)
        db.session.commit()
        flash('Layanan berhasil ditambahkan.', 'success')
        return redirect(url_for('services_page'))

    # render template-based form
    return render_template('add_service.html')


@app.route('/manage_bookings')
@login_required
def manage_bookings():
    if current_user.role == 'admin':
        data = Booking.query.order_by(Booking.tanggal).all()
    else:
        data = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.tanggal).all()
    services = {s.id: s for s in Service.query.all()}
    return render_template('manage_bookings.html', data=data, services=services)


@app.route('/booking', methods=['GET', 'POST'])
@login_required
def booking():
    if current_user.role != 'staff':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        pet_id = request.form.get('pet_id')
        if pet_id:
            pet = Pet.query.get(int(pet_id))
            nama = pet.nama
            jenis = pet.jenis
        else:
            nama = request.form.get('nama')
            jenis = request.form.get('jenis')
            # optional: create pet
            if nama and jenis:
                new_pet = Pet(nama=nama, jenis=jenis)
                db.session.add(new_pet)
                db.session.commit()

        service_id = int(request.form.get('service_id'))
        service = Service.query.get(service_id)
        price = service.price if service else 0
        jam = request.form.get('jam')
        owner = request.form.get('owner')

        booking = Booking(
            nama_hewan=nama,
            jenis=jenis,
            tanggal=request.form['tanggal'],
            jam=jam,
            user_id=current_user.id,
            status='pending',
            service_id=service_id,
            price=price,
            owner_name=owner
        )
        db.session.add(booking)
        db.session.commit()
        flash('Booking berhasil disimpan.', 'success')
        return redirect(url_for('dashboard'))

    pets = Pet.query.all()
    services = Service.query.all()
    return render_template('booking.html', pets=pets, services=services)


@app.route('/update_status/<int:id>', methods=['POST'])
@login_required
def update_status(id):
    if current_user.role != 'staff':
        return redirect(url_for('dashboard'))

    booking = Booking.query.get_or_404(id)
    new_status = request.form.get('status')
    if new_status in ['pending', 'in_progress', 'done', 'canceled']:
        booking.status = new_status
        db.session.commit()
        flash('Status booking diperbarui.', 'info')

    return redirect(url_for('dashboard'))


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_booking(id):
    booking = Booking.query.get_or_404(id)

    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        booking.nama_hewan = request.form['nama']
        booking.jenis = request.form['jenis']
        booking.owner_name = request.form.get('owner')
        booking.tanggal = request.form['tanggal']
        service_id = int(request.form.get('service_id'))
        service = Service.query.get(service_id)
        booking.service_id = service_id
        booking.price = service.price if service else booking.price
        booking.jam = request.form.get('jam')
        db.session.commit()
        flash('Data booking berhasil diubah.', 'success')
        return redirect(url_for('dashboard'))

    services = Service.query.all()
    return render_template('edit_booking.html', booking=booking, services=services)


@app.route('/delete/<int:id>')
@login_required
def delete(id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))

    booking = Booking.query.get_or_404(id)
    db.session.delete(booking)
    db.session.commit()
    flash('Data booking telah dihapus.', 'warning')
    return redirect(url_for('dashboard'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
