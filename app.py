from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required

app = Flask(__name__)
app.config.from_pyfile('config.py')

mongo = PyMongo(app)
db = mongo.db
users = db.users # Koleksi untuk menyimpan data user (termasuk siswa, osis, guru)
aspirasi = db.aspirasi

# --- Hardcoded Credentials (for OSIS and Guru) ---
# Praktik terbaik: Gunakan variabel lingkungan atau file konfigurasi terpisah yang lebih aman
# Daripada langsung di kode, tapi untuk demonstrasi ini, kita hardcode.
OSIS_USERNAME = 'osis_admin'
OSIS_PASSWORD = 'password_osis_rahasia' # Ganti dengan password kuat
GURU_USERNAME = 'guru_pembina'
GURU_PASSWORD = 'password_guru_rahasia' # Ganti dengan password kuat

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Rute tempat user akan dialihkan jika belum login

# Kelas User untuk Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.user_data = user_data
        # ID untuk Flask-Login harus unik dan string
        # Untuk siswa, gunakan NISN. Untuk OSIS/Guru, gunakan _id MongoDB
        if user_data['role'] == 'siswa':
            self.id = user_data.get('nisn') # NISN sebagai ID untuk siswa
            if not self.id:
                raise ValueError("Siswa harus memiliki NISN")
        else:
            self.id = str(user_data['_id'])

        self.username = user_data.get('username') # Username bisa jadi nama siswa atau username OSIS/Guru
        self.role = user_data['role']
        self.nisn = user_data.get('nisn') # Tambahkan atribut NISN

    def get_id(self):
        return self.id

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    # Memungkinkan akses atribut lain dari current_user di template
    def __getattr__(self, name):
        try:
            return self.user_data[name]
        except KeyError:
            raise AttributeError(f"'User' object has no attribute '{name}'")


@login_manager.user_loader
def load_user(user_id):
    # Flask-Login akan memanggil ini dengan ID yang disimpan di sesi
    # Kita perlu tahu apakah itu NISN atau _id MongoDB
    
    # Coba cari berdasarkan NISN (untuk siswa)
    user_data = users.find_one({'nisn': user_id, 'role': 'siswa'})
    if user_data:
        return User(user_data)
    
    # Jika bukan siswa, cari berdasarkan _id MongoDB
    try:
        user_data = users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            return User(user_data)
    except Exception:
        pass # ID mungkin bukan ObjectId yang valid
    
    return None

# ----------------------------
# ROUTES
# ----------------------------

@app.route('/')
def home():
    return render_template('home.html')

# ----------------------------
# Register (Hanya untuk OSIS/Guru, Siswa tidak register di sini)
# ----------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password_raw = request.form['password'] # Password akan diverifikasi dengan hardcode, tidak di hash untuk ini
        role = request.form['role']

        if role == 'siswa':
            flash('Siswa tidak dapat mendaftar melalui halaman ini. Silakan hubungi administrator.', 'error')
            return redirect(url_for('register'))

        if users.find_one({'username': username, 'role': role}):
            flash(f'Username {username} untuk role {role} sudah digunakan.', 'error')
            return redirect(url_for('register'))

        # Untuk OSIS dan Guru, kita hanya menyimpan username mereka di DB
        # Verifikasi password akan dilakukan di fungsi login dengan hardcode
        users.insert_one({
            'username': username,
            # Password tidak di-hash di DB jika hardcode. Tapi ini kurang aman.
            # Jika ingin lebih aman, hardcode hash-nya lalu cek dengan check_password_hash.
            # Untuk demo ini, kita tidak simpan password di DB untuk OSIS/Guru.
            'role': role
        })
        flash('Pendaftaran berhasil, silakan login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# ----------------------------
# Login
# ----------------------------
# app.py

# ... (kode di atasnya)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        identifier = request.form['identifier']
        role = request.form['role'] # Role yang dipilih di form

        # Inisialisasi password_input. Hanya ambil jika role bukan siswa
        password_input = None
        if role != 'siswa':
            # Pastikan kunci 'password' ada di form jika role bukan siswa
            # Jika tidak ada, itu indikasi masalah di frontend atau request
            if 'password' not in request.form:
                 flash('Password tidak ditemukan. Harap masukkan password.', 'error')
                 return redirect(url_for('login'))
            password_input = request.form['password'] # Ambil password hanya jika diperlukan

        user_data = None
        user_obj = None

        if role == 'siswa':
            # Login Siswa: Verifikasi NISN
            user_data = users.find_one({'nisn': identifier, 'role': 'siswa'})
            if user_data:
                # Siswa tidak punya password di sistem ini, jadi langsung login jika NISN ditemukan
                user_obj = User(user_data)
                login_user(user_obj)
                flash('Login siswa berhasil!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('NISN siswa tidak ditemukan.', 'error')
        
        elif role == 'osis':
            # Login OSIS: Verifikasi username dan password hardcode
            if password_input is None: # Pastikan password ada untuk OSIS
                flash('Password diperlukan untuk peran OSIS.', 'error')
                return redirect(url_for('login'))

            if identifier == OSIS_USERNAME and password_input == OSIS_PASSWORD:
                user_data = users.find_one({'username': identifier, 'role': 'osis'})
                if not user_data:
                    users.insert_one({'username': identifier, 'role': 'osis'})
                    user_data = users.find_one({'username': identifier, 'role': 'osis'})
                
                if user_data:
                    user_obj = User(user_data)
                    login_user(user_obj)
                    flash('Login OSIS berhasil!', 'success')
                    return redirect(url_for('dashboard'))
            else:
                flash('Username atau password OSIS salah.', 'error')

        elif role == 'guru':
            # Login Guru: Verifikasi username dan password hardcode
            if password_input is None: # Pastikan password ada untuk Guru
                flash('Password diperlukan untuk peran Guru.', 'error')
                return redirect(url_for('login'))

            if identifier == GURU_USERNAME and password_input == GURU_PASSWORD:
                user_data = users.find_one({'username': identifier, 'role': 'guru'})
                if not user_data:
                    users.insert_one({'username': identifier, 'role': 'guru'})
                    user_data = users.find_one({'username': identifier, 'role': 'guru'})
                
                if user_data:
                    user_obj = User(user_data)
                    login_user(user_obj)
                    flash('Login Guru berhasil!', 'success')
                    return redirect(url_for('dashboard'))
            else:
                flash('Username atau password Guru salah.', 'error')
        else:
            flash('Pilihan peran tidak valid.', 'error')

    return render_template('login.html')

# ... (kode di bawahnya)
# ----------------------------
# Logout
# ----------------------------
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('home'))

# ----------------------------
# Dashboard per Role
# ----------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    role = current_user.role

    if role == 'siswa':
        data = aspirasi.find({'pengirim_id': ObjectId(current_user.id)}) # current_user.id sekarang adalah NISN untuk siswa
        return render_template('dashboard/siswa_dashboard.html', aspirasi=data)

    elif role == 'osis':
        data = aspirasi.find()
        return render_template('dashboard/osis_dashboard.html', aspirasi=data)

    elif role == 'guru':
        data = aspirasi.find({'status': {'$in': ['Dikirim', 'Diproses']}})
        return render_template('dashboard/guru_dashboard.html', aspirasi=data)

    flash('Peran pengguna tidak valid.', 'error')
    return redirect(url_for('home'))

# ----------------------------
# Kirim Aspirasi (Siswa)
# ----------------------------
@app.route('/aspirasi/kirim', methods=['GET', 'POST'])
@login_required
def kirim_aspirasi():
    if current_user.role != 'siswa':
        flash('Anda tidak memiliki izin untuk mengakses halaman ini.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        aspirasi.insert_one({
            'judul': request.form['judul'],
            'isi': request.form['isi'],
            'kategori': request.form['kategori'],
            'urgensi': request.form['urgensi'],
            'status': 'Dikirim',
            'tanggal_kirim': datetime.now(),
            'pengirim_id': ObjectId(current_user.id) if current_user.role != 'siswa' else current_user.id, # Gunakan NISN sebagai pengirim_id untuk siswa
            'klasifikasi': None,
            'prioritas': None,
            'tanggapan': None
        })
        flash('Aspirasi berhasil dikirim!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('aspirasi/form.html')

# ----------------------------
# Klasifikasi Aspirasi (OSIS)
# ----------------------------
@app.route('/aspirasi/klasifikasi/<id>', methods=['GET', 'POST'])
@login_required
def klasifikasi_aspirasi(id):
    if current_user.role != 'osis':
        flash('Anda tidak memiliki izin untuk mengakses halaman ini.', 'error')
        return redirect(url_for('dashboard'))

    data = aspirasi.find_one({'_id': ObjectId(id)})
    if not data:
        flash('Aspirasi tidak ditemukan.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        klasifikasi = request.form['klasifikasi']
        prioritas = request.form['prioritas']
        aspirasi.update_one(
            {'_id': ObjectId(id)},
            {'$set': {
                'klasifikasi': klasifikasi,
                'prioritas': prioritas,
                'status': 'Diproses'
            }}
        )
        flash('Aspirasi berhasil diklasifikasi.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('aspirasi/klasifikasi.html', aspirasi=data)

# ----------------------------
# Tanggapi Aspirasi (Guru)
# ----------------------------
@app.route('/aspirasi/tanggapi/<id>', methods=['GET', 'POST'])
@login_required
def tanggapi_aspirasi(id):
    if current_user.role != 'guru':
        flash('Anda tidak memiliki izin untuk mengakses halaman ini.', 'error')
        return redirect(url_for('dashboard'))

    data = aspirasi.find_one({'_id': ObjectId(id)})
    if not data:
        flash('Aspirasi tidak ditemukan.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        tanggapan = request.form['tanggapan']
        aspirasi.update_one(
            {'_id': ObjectId(id)},
            {'$set': {
                'tanggapan': tanggapan,
                'status': 'Selesai'
            }}
        )
        flash('Tanggapan berhasil dikirim.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('aspirasi/tanggapan.html', aspirasi=data)

# ----------------------------
# Statistik (Opsional)
# ----------------------------
@app.route('/statistik')
@login_required
def statistik():
    # Contoh: batasi statistik hanya untuk OSIS/Guru
    if current_user.role not in ['osis', 'guru']:
        flash('Anda tidak memiliki izin untuk mengakses halaman ini.', 'error')
        return redirect(url_for('dashboard'))

    pipeline = [
        {"$group": {"_id": "$kategori", "jumlah": {"$sum": 1}}},
        {"$sort": {"jumlah": -1}}
    ]
    stats = list(aspirasi.aggregate(pipeline))
    return render_template('statistik.html', stats=stats)

# ----------------------------
# Jalankan Aplikasi
# ----------------------------
if __name__ == '__main__':
    app.run(debug=True)