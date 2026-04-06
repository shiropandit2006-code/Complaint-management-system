from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string
import os
import base64
from PIL import Image
from datetime import datetime
from flask import jsonify
from functools import wraps
from sqlalchemy import func

# ------------ Config ------------
# app = Flask(__name__)
# app.config['SECRET_KEY'] = 'your_secret_key_here'  # replace with a secure key in production
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///civiccare.db'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# app.config['SQLALCHEMY_ECHO'] = True

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
# ... baaki saare imports wahi rehne dein ...

# --- YE VALA HISSA UPDATE KAREIN ---
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'civiccare.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = True


# 1. Sabse upar ye import add karein
from flask_mail import Mail, Message

# 2. Config section (SQLAlchemy ke niche) ye add karein
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME') # Apna Gmail yahan likhein
app.config['MAIL_PASSWORD'] =  os.environ.get('MAIL_PASSWORD')    # Gmail ka 16-digit App Password
app.config['MAIL_DEFAULT_SENDER'] = ('CiviCare Team','shristip67.official@gmail.com')

mail = Mail(app)

# 3. Ek Helper Function banayein jo email bhejega
def send_notification(to_email, subject, body):
    try:
        msg = Message(subject, recipients=[to_email])
        msg.body = body
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Mail Error: {e}")
        return False

# uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
UPLOAD_SUBDIR = 'uploads'  # inside /static
db = SQLAlchemy(app)

# Ensure uploads dir exists on boot
def ensure_upload_dir():
    base = app.static_folder or 'static'
    up = os.path.join(base, UPLOAD_SUBDIR)
    os.makedirs(up, exist_ok=True)
    return up

# ------------ Models ------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    email = db.Column(db.String(120), unique=True, index=True)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(256))

    complaints = db.relationship('Complaint', backref='user', lazy=True)

    def set_password(self, plain):
        self.password_hash = generate_password_hash(plain)

    def check_password(self, plain):
        return check_password_hash(self.password_hash, plain)

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_code = db.Column(db.String(20), unique=True, index=True)
    name = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    category = db.Column(db.String(100))
    subcategory = db.Column(db.String(100))
    location = db.Column(db.String(200))
    status = db.Column(db.String(50), default='Received')
    progress = db.Column(db.Integer, default=20)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)
    admin_remark = db.Column(db.Text, default="Your grievance is currently under verification.") # <--- Naya Column

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    images = db.relationship('ComplaintImage', backref='complaint', cascade='all, delete-orphan', lazy=True)
    feedback = db.relationship('Feedback', backref='complaint', uselist=False)

    # --- NAYE COLUMNS FOR AUTHORITY PROOF ---
    authority_photo = db.Column(db.String(255)) # Kaam ke baad ki photo ka path
    authority_note = db.Column(db.Text)         # Dept ka message
    is_verified = db.Column(db.Boolean, default=False)

    # Naye Fields
    department = db.Column(db.String(100))
    dept_email = db.Column(db.String(100))
    priority = db.Column(db.String(20), default="Normal")
    deadline = db.Column(db.Date)
    
 

    

class ComplaintImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300))
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaint.id'))

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.String(10))
    comments = db.Column(db.Text)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaint.id'), unique=True)



# --- YE VALA HISSA ADD KAREIN ---
# with app.app_context():
#     db.create_all()
#     # ensure_upload_dir() agar aapne function banaya hai toh yahan call karein
# -------------------------------

# ------------ Helper functions ------------
def make_complaint_code():
    return 'CMP' + ''.join(random.choices(string.digits, k=6))

def complaint_to_dict(c: Complaint):
    first_image = c.images[0].filename if c.images else None
    return {
        'complaint_code': c.complaint_code,
        'name': c.name,
        'phone': c.phone,
        'address': c.address,
        'category': c.category,
        'subcategory': c.subcategory,
        'location': c.location,
        'status': c.status,
        'progress': c.progress,
        'date': c.date.strftime('%Y-%m-%d') if c.date else '',
        'resolved': c.resolved,
        'remarks': c.admin_remark, # <--- Frontend ko remark bhej rahe hain
        'image_file': first_image,
        'images': [img.filename for img in c.images]
    }

def allowed_ext(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def unique_name(original: str) -> str:
    base, ext = os.path.splitext(secure_filename(original))
    suffix = ''.join(random.choices(string.digits, k=6))
    return f"{base}_{suffix}{ext.lower()}"

def sniff_is_image(path):
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False

def save_upload_file(storage, upload_dir: str) -> str | None:
    """Save a werkzeug FileStorage if valid, return filename or None."""
    if not storage or not storage.filename:
        return None
    if not allowed_ext(storage.filename):
        return None
    filename = unique_name(storage.filename)
    path = os.path.join(upload_dir, filename)
    storage.save(path)
    # sniff to ensure it's actually an image
    if not sniff_is_image(path):
        # remove suspicious file
        try:
            os.remove(path)
        except Exception:
            pass
        return None
    return filename

def save_base64_image(data_uri: str, upload_dir: str) -> str | None:
    """
    Accepts data URI like 'data:image/png;base64,....'
    Saves to PNG filename and returns it if valid. Otherwise None.
    """
    if not data_uri or not data_uri.startswith('data:image'):
        return None
    try:
        header, b64data = data_uri.split(',', 1)
    except ValueError:
        return None

    # pick extension from header (only allow png/jpg/jpeg)
    ext = 'png'
    if 'jpeg' in header or 'jpg' in header:
        ext = 'jpg'
    elif 'png' in header:
        ext = 'png'
    else:
        return None

    filename = f"captured_{''.join(random.choices(string.digits, k=8))}.{ext}"
    path = os.path.join(upload_dir, filename)
    try:
        with open(path, 'wb') as f:
            f.write(base64.b64decode(b64data))
    except Exception:
        return None

    # sniff
    if not sniff_is_image(path):
        try:
            os.remove(path)
        except Exception:
            pass
        return None

    return filename

# ------------ Routes ------------
ADMIN_PASSWORD = 'admin123'  # keep as you had it


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get('user_logged_in'):
            return redirect(url_for('homepage', next=request.path))
        return view_func(*args, **kwargs)
    return wrapper

@app.route('/')
def homepage():
    show_login_modal = request.args.get('show_login') == '1'
    login_failed = request.args.get('login_failed') == '1'
    return render_template(
        'index.html',
        show_login_modal=show_login_modal,
        login_failed=login_failed,
        user_logged_in=session.get('user_logged_in', False)
    )

from flask import Flask, render_template, request, jsonify

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Form se data nikalna
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        # Yahan aap database mein save karne ka logic daal sakte hain
        # e.g., new_msg = Message(name=name, email=email, content=message)
        # db.session.add(new_msg)
        # db.session.commit()

        # AJAX ko success response bhejna
        return jsonify({
            "status": "success", 
            "message": f"Thank you {name}, your message has been sent successfully! We will contact you soon"
        })
    
    # Agar sirf page access ho raha hai (GET request)
    return render_template('contact.html')

@app.route('/status')

def status():
    return render_template('status.html')

@app.route('/get_status/<complaint_id>')
def get_status(complaint_id):
    complaint = Complaint.query.filter_by(complaint_code=complaint_id.upper()).first()
    if not complaint:
        return jsonify({"status": "Not Found"}), 404
    return jsonify(complaint_to_dict(complaint))



# ---------- Complaint ----------
@app.route('/complaint/<category>', methods=['GET', 'POST'])
def show_complaint_form(category):
    # ✅ Require login
    if not session.get('user_logged_in') or not session.get('user_id'):
        if request.method == 'POST':
            flash("⚠️ You must log in before submitting a complaint.", "danger")
            return render_template(
                'complaint_section.html',
                selected_category=category,
                show_login_modal=True,
                form_data=request.form
            )
        else:
            return render_template(
                'complaint_section.html',
                selected_category=category,
                show_login_modal=True,
                form_data={}
            )

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        complaint_category = request.form.get('category', '').strip()
        subcategory = request.form.get('subcategory', '').strip()
        location = request.form.get('location', '').strip()

        import re
        # ✅ Validation logic
        if not re.match(r'^[A-Z][a-z]+(?: [A-Z][a-z]+)+$', name):
           flash("❌ Enter your full name (first and last, each starting with capital letters).", "danger")
           return render_template('complaint_section.html', selected_category=category, form_data=request.form)

        if not re.match(r'^[6-9]\d{9}$', phone):
            flash("❌ Enter a valid 10-digit Indian mobile number.", "danger")
            return render_template('complaint_section.html', selected_category=category, form_data=request.form)

        if not re.match(r'^[A-Za-z0-9\s,.-]{10,}$', address):
            flash("❌ Enter a valid address (Road/Area, City, State, Landmark).", "danger")
            return render_template('complaint_section.html', selected_category=category, form_data=request.form)

        if not re.match(r'^[A-Za-z\s]+,\s*[A-Za-z\s]+$', location):
            flash("❌ Location must be in format: City, State", "danger")
            return render_template('complaint_section.html', selected_category=category, form_data=request.form)

        # ✅ Save complaint to DB
        code = make_complaint_code()
        complaint = Complaint(
            complaint_code=code,
            name=name,
            phone=phone,
            address=address,
            category=complaint_category,
            subcategory=subcategory,
            location=location,
            status='Received',
            progress=20,
            resolved=False,
            user_id=session.get('user_id')
        )
        db.session.add(complaint)
        db.session.flush()

        # ✅ Handle images
        upload_dir = ensure_upload_dir()
        saved_filenames = []

        uploaded_files = request.files.getlist('images') or []
        for file in uploaded_files:
            if len(saved_filenames) >= 5:
                break
            fname = save_upload_file(file, upload_dir)
            if fname:
                db.session.add(ComplaintImage(filename=fname, complaint=complaint))
                saved_filenames.append(fname)

        if len(saved_filenames) < 5:
            captured_data_uri = request.form.get('captured_image', '')
            if captured_data_uri:
                fname = save_base64_image(captured_data_uri, upload_dir)
                if fname:
                    db.session.add(ComplaintImage(filename=fname, complaint=complaint))
                    saved_filenames.append(fname)

        # ✅ Final Database Commit
        db.session.commit()

        # 🔥 MODIFICATION: Send Confirmation Email
        user_email = session.get('user_email') # Fetching email from login session
        if user_email:
            subject = f"CivicCare: Complaint Filed Successfully [ID: {code}]"
            body = f"""
            Dear {name},

            Thank you for reaching out. Your complaint has been successfully registered with CivicCare.

            --- Complaint Details ---
            Complaint ID : {code}
            Category     : {complaint_category}
            Subcategory  : {subcategory}
            Status       : Received / Under Review

            You can monitor the progress of your grievance by visiting the 'Track Status' section on our portal using your Complaint ID.

            Best Regards,
            CivicCare Management Team
            """
            send_notification(user_email, subject, body)

        
        return render_template('success.html', complaint_id=code)

    # ✅ GET request
    return render_template('complaint_section.html', selected_category=category, form_data={})

# ---------- Feedback ----------
@app.route('/submit_feedback/<complaint_id>', methods=['POST'])
def submit_feedback(complaint_id):
    complaint = Complaint.query.filter_by(complaint_code=complaint_id.upper()).first()
    if not complaint:
        return "Complaint not found", 404
    rating = request.form.get('rating')
    comments = request.form.get('comments')
    # upsert feedback
    fb = Feedback.query.filter_by(complaint_id=complaint.id).first()
    if not fb:
        fb = Feedback(rating=rating, comments=comments, complaint=complaint)
        db.session.add(fb)
    else:
        fb.rating = rating
        fb.comments = comments
    db.session.commit()
    return f"✅ Thank you for your feedback on {complaint_id}!"

# ---------- Admin ----------
@app.route('/admin')
def admin_intro():
    # If already logged in, skip intro and go directly to dashboard
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_panel'))
    return render_template('admin_dashboard.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    # If already logged in, skip login page
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_panel'))

    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            return render_template('admin_login.html', error="Invalid password")

    return render_template('admin_login.html')

from flask import render_template, session, redirect, url_for, request, flash
from sqlalchemy import func

# @app.route('/admin/dashboard')
# def admin_panel():
#     if not session.get('admin_logged_in'):
#         return redirect(url_for('admin_login'))

#     # Ye line zaroori hai: Saari complaints aur unka linked feedback fetch hoga
#     all_complaints = Complaint.query.order_by(Complaint.date.desc()).all()
    
#     # Statistics logic...
#     total_count = Complaint.query.count()
#     resolved_count = Complaint.query.filter_by(status='Resolved').count()
#     pending_count = total_count - resolved_count
    
#     cat_stats = db.session.query(Complaint.category, func.count(Complaint.id)).group_by(Complaint.category).all()
#     all_users = User.query.all() 

#     return render_template('admin_complaints.html', 
#                            complaints=all_complaints, # Ye data HTML mein jayega
#                            users=all_users,
#                            cat_labels=[s[0] for s in cat_stats], 
#                            cat_counts=[s[1] for s in cat_stats],
#                            total=total_count,
#                            resolved=resolved_count,
#                            pending=pending_count)

# @app.route('/admin/dashboard')
# def admin_panel():
#     if not session.get('admin_logged_in'):
#         return redirect(url_for('admin_login'))

#     # Sabhi complaints ko fetch karna (feedback ke saath)
#     all_complaints = Complaint.query.order_by(Complaint.date.desc()).all()
#     all_users = User.query.all() 
    
#     total_count = len(all_complaints)
#     resolved_count = len([c for c in all_complaints if c.status == 'Resolved'])
#     forwarded_count = len([c for c in all_complaints if 'Forwarded' in (c.status or '')])
#     pending_count = total_count - resolved_count - forwarded_count

#     cat_stats = db.session.query(Complaint.category, func.count(Complaint.id)).group_by(Complaint.category).all()
    
#     return render_template('admin_complaints.html', 
#                            complaints=all_complaints,
#                            users=all_users,
#                            cat_labels=[s[0] for s in cat_stats], 
#                            cat_counts=[s[1] for s in cat_stats],
#                            total=total_count,
#                            resolved=resolved_count,
#                            forwarded=forwarded_count,
#                            pending=pending_count)



# @app.route('/admin/dashboard')
# def admin_panel():
#     if not session.get('admin_logged_in'):
#         return redirect(url_for('admin_login'))

#     all_complaints = Complaint.query.order_by(Complaint.date.desc()).all()
#     all_users = User.query.all() 
    
#     # Statistics calculations
#     total_count = len(all_complaints)
#     resolved_count = len([c for c in all_complaints if c.status == 'Resolved'])
#     pending_count = total_count - resolved_count
    
#     # Category stats for Charts
#     # Note: 'func' ko sqlalchemy se import karna hoga
#     cat_stats = db.session.query(Complaint.category, db.func.count(Complaint.id)).group_by(Complaint.category).all()

#     return render_template('admin_complaints.html', 
#                            complaints=all_complaints,
#                            users=all_users,
#                            cat_labels=[s[0] for s in cat_stats], 
#                            cat_counts=[s[1] for s in cat_stats],
#                            total=total_count,
#                            resolved=resolved_count,
#                            pending=pending_count)

# from datetime import datetime

# @app.route('/admin/dashboard')
# def admin_panel():
#     if not session.get('admin_logged_in'):
#         return redirect(url_for('admin_login'))

#     all_complaints = Complaint.query.order_by(Complaint.date.desc()).all()
#     all_users = User.query.all() 
    
#     # 1. Counts Calculation
#     total_count = len(all_complaints)
#     resolved_count = Complaint.query.filter_by(status='Resolved').count()
    
#     # Forwarded + Action Taken ko hum 'In Progress' ki tarah dashboard pe dikhayenge
#     forwarded_count = Complaint.query.filter(
#         (Complaint.status.contains('Forwarded')) | (Complaint.status == 'Action Taken')
#     ).count()
    
#     # Pending wahi hain jo bilkul naye hain (Received status)
#     pending_count = Complaint.query.filter_by(status='Received').count()
    
#     cat_stats = db.session.query(Complaint.category, db.func.count(Complaint.id)).group_by(Complaint.category).all()

#     return render_template('admin_complaints.html', 
#                            complaints=all_complaints,
#                            users=all_users,
#                            cat_labels=[s[0] for s in cat_stats], 
#                            cat_counts=[s[1] for s in cat_stats],
#                            total=total_count,
#                            resolved=resolved_count,
#                            pending=pending_count, # Nayi complaints
#                            forwarded=forwarded_count) # Progress waali complaints

# # 2. Naya Route: Forward karne ke liye
# from datetime import datetime
# import os
# from werkzeug.utils import secure_filename

# # 1. Forward Logic (Admin Dashboard se call hoga)
# @app.route('/forward_to_authority/<complaint_code>', methods=['POST'])
# def forward_to_authority(complaint_code):
#     complaint = Complaint.query.filter_by(complaint_code=complaint_code).first()
#     if complaint:
#         complaint.department = request.form.get('department')
#         complaint.priority = request.form.get('priority')
#         deadline_str = request.form.get('deadline')
#         if deadline_str:
#             complaint.deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
        
#         complaint.status = f"Forwarded to {complaint.department}"
#         db.session.commit()
#         return jsonify({"success": True})
#     return jsonify({"error": "Ticket not found"}), 404

# # 2. Authority Submission (Authority Dashboard se call hoga)
# @app.route('/authority/submit_proof/<complaint_code>', methods=['POST'])
# def submit_proof(complaint_code):
#     complaint = Complaint.query.filter_by(complaint_code=complaint_code).first()
#     if 'proof_image' in request.files:
#         file = request.files['proof_image']
#         if file.filename != '':
#             filename = secure_filename(f"resolved_{complaint_code}_{file.filename}")
#             file.save(os.path.join('static/uploads', filename))
            
#             complaint.authority_photo = filename
#             complaint.authority_note = request.form.get('note')
#             complaint.status = "Action Taken" # Admin ko notify karega
#             db.session.commit()
#     return redirect(url_for('authority_dashboard', dept_name=complaint.department))








# @app.route('/admin/dashboard')
# def admin_panel():
#     if not session.get('admin_logged_in'):
#         return redirect(url_for('admin_login'))

#     # 1. Saari complaints fetch karna (Taaki table mein dikhein)
#     all_complaints = Complaint.query.order_by(Complaint.date.desc()).all()
    
#     # 2. Stats calculate karna (Taaki cards mein numbers dikhein)
#     total_count = len(all_complaints)
#     resolved_count = len([c for c in all_complaints if c.status == 'Resolved'])
#     pending_count = total_count - resolved_count
    
#     # 3. Visualization/Charts ke liye data
#     cat_stats = db.session.query(Complaint.category, func.count(Complaint.id)).group_by(Complaint.category).all()
    
#     # 4. Saare users fetch karna (Citizens tab ke liye)
#     all_users = User.query.all() 

#     # 5. Current time (Dashboard par update time dikhane ke liye)
#     now = datetime.now()

#     return render_template('admin_complaints.html', 
#                            complaints=all_complaints,
#                            users=all_users,
#                            cat_labels=[s[0] for s in cat_stats], 
#                            cat_counts=[s[1] for s in cat_stats],
#                            total=total_count,
#                            resolved=resolved_count,
#                            pending=pending_count,
#                            now=now)

@app.route('/admin/dashboard')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    all_complaints = Complaint.query.order_by(Complaint.date.desc()).all()
    
    # Dashboard Counters
    total = len(all_complaints)
    resolved = Complaint.query.filter_by(status='Resolved').count()
    # In Progress = Jo forward ho chuki hain ya jinka action ho chuka hai
    forwarded = Complaint.query.filter(
        (Complaint.status.contains('Forwarded')) | (Complaint.status == 'Action Taken')
    ).count()
    pending = Complaint.query.filter_by(status='Received').count()
    
    # Chart Data
    cat_stats = db.session.query(Complaint.category, db.func.count(Complaint.id)).group_by(Complaint.category).all()

    return render_template('admin_complaints.html', 
                           complaints=all_complaints,
                           users=User.query.all(),
                           cat_labels=[s[0] for s in cat_stats], 
                           cat_counts=[s[1] for s in cat_stats],
                           total=total, resolved=resolved, 
                           pending=pending, forwarded=forwarded)



@app.route('/forward_to_authority/<complaint_code>', methods=['POST'])
def forward_to_authority(complaint_code):
    complaint = Complaint.query.filter_by(complaint_code=complaint_code).first()
    if complaint:
        complaint.department = request.form.get('department')
        complaint.priority = request.form.get('priority')
        deadline_str = request.form.get('deadline')
        if deadline_str:
            complaint.deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
        
        complaint.status = f"Forwarded to {complaint.department}"
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"error": "Ticket not found"}), 404

@app.route('/admin/resolve_final/<complaint_code>', methods=['POST'])
def resolve_final(complaint_code):
    complaint = Complaint.query.filter_by(complaint_code=complaint_code).first()
    if complaint:
        complaint.resolved = True
        complaint.status = "Resolved"
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"error": "Ticket not found"}), 404

# --- AUTHORITY ROUTES ---

# --- AUTHORITY LOGIN ROUTE ---
DEPT_PASSWORDS = {
    "PWD (Roads)": "pwd@123",
    "Electricity Board": "power@786",
    "Jal Nigam": "water@999",
    "Municipal Corporation": "clean@456",
    "Traffic Police": "traffic@111"
}

@app.route('/authority/login', methods=['GET', 'POST'])
def authority_login():
    if request.method == 'POST':
        selected_dept = request.form.get('dept_name')
        entered_password = request.form.get('password')

        # Check if department exists and password matches
        if selected_dept in DEPT_PASSWORDS:
            if DEPT_PASSWORDS[selected_dept] == entered_password:
                session['auth_dept'] = selected_dept
                return redirect(url_for('authority_dashboard', dept_name=selected_dept))
            else:
                return render_template('authority_login.html', error="Invalid Password for " + selected_dept)
        else:
            return render_template('authority_login.html', error="Department not found")
            
    return render_template('authority_login.html')


# --- UPDATED DASHBOARD (With Session Security) ---
@app.route('/authority/dashboard/<dept_name>')
def authority_dashboard(dept_name):
    # Department ke hisaab se saare tickets mangwana
    tickets = Complaint.query.filter_by(department=dept_name).all()
    
    # Stats calculate karna (HTML boxes ke liye)
    t_assigned = len(tickets)
    t_resolved = len([t for t in tickets if t.status == 'Resolved'])
    h_priority = len([t for t in tickets if t.priority == 'High' and t.status != 'Resolved'])
    
    # Ye saare variables render_template mein bhejna zaroori hai
    return render_template('authority_dashboard.html', 
                           tickets=tickets, 
                           dept_name=dept_name,
                           total_assigned=t_assigned,
                           total_resolved=t_resolved,
                           high_priority=h_priority)

@app.route('/authority/logout')
def authority_logout():
    session.pop('auth_dept', None)
    return redirect(url_for('authority_login'))

@app.route('/authority/submit_proof/<complaint_code>', methods=['POST'])
def submit_proof(complaint_code):
    complaint = Complaint.query.filter_by(complaint_code=complaint_code).first()
    
    if complaint and 'proof_image' in request.files:
        file = request.files['proof_image']
        if file.filename != '':
            # Bina config change kiye direct helper function use karein
            upload_dir = ensure_upload_dir() 
            filename = secure_filename(f"proof_{complaint_code}_{file.filename}")
            
            # File save karna
            file.save(os.path.join(upload_dir, filename))
            
            # DB update
            complaint.authority_photo = filename
            complaint.authority_note = request.form.get('note')
            complaint.status = "Action Taken"
            db.session.commit()
            
    return redirect(url_for('authority_dashboard', dept_name=complaint.department))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_intro'))

from flask import jsonify # Ye file ke sabse upar check kar lena

@app.route('/resolve/<complaint_id>', methods=['POST'])
def resolve_complaint(complaint_id):
    if not session.get('admin_logged_in'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    # Aapka original remark logic
    admin_action_text = request.form.get('admin_remark', 'The issue has been successfully resolved by our department.')

    complaint = Complaint.query.filter_by(complaint_code=complaint_id.upper()).first()
    
    if complaint:
        # 1. DB Updates (Same as yours)
        complaint.status = 'Resolved'
        complaint.progress = 100
        complaint.resolved = True
        complaint.admin_remark = admin_action_text
        db.session.commit()

        # 2. Aapka Professional Notification logic
        if complaint.user and complaint.user.email:
            user_email = complaint.user.email
            subject = f"ACTION TAKEN: Complaint #{complaint_id.upper()}"
            body = f"""
Dear {complaint.name},

Greetings from CivicCare Administration.

Your grievance regarding '{complaint.category}' has been officially addressed.

--- OFFICIAL RESOLUTION REPORT ---
Ticket ID: {complaint_id.upper()}
Action Taken: {admin_action_text}
Final Status: CLOSED / RESOLVED

We thank you for bringing this matter to our attention and helping us improve our community.

Regards,
CivicCare Team
            """
            send_notification(user_email, subject, body)

        # Flash ki jagah JSON message
        return jsonify({"status": "success", "message": f"✅ Ticket #{complaint_id} updated and citizen notified."})
    
    return jsonify({"status": "error", "message": "❌ Error: Complaint ID not found."}), 404


@app.route('/reject_proof/<complaint_code>', methods=['POST'])
def reject_proof(complaint_code):
    complaint = Complaint.query.filter_by(complaint_code=complaint_code).first()
    if complaint:
        # Ticket wapas department ke paas chala jayega
        complaint.status = "Forwarded to " + complaint.assigned_dept 
        # Purani proof details clear kar sakte hain (Optional)
        complaint.authority_photo = None 
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Not found"})

# ---------- Past complaints (search by phone) ----------
@app.route('/past', methods=['GET', 'POST'])
def past_complaints():
    if request.method == 'POST':
        phone = request.form.get('phone')
        qs = Complaint.query.filter_by(phone=phone).order_by(Complaint.date.desc()).all()
        complaints_map = {c.complaint_code: complaint_to_dict(c) for c in qs}
        return render_template('past_complaints.html', complaints=complaints_map, no_data=not bool(complaints_map))
    return render_template('past_complaints.html', complaints=None, no_data=False)

# ---------- User auth ----------
from flask import jsonify

@app.route('/user/register', methods=['POST'])
def user_register():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '')

    if not email or not password:
        return jsonify({
            "status": "error",
            "message": "Email and Password are required"
        })

    existing = User.query.filter_by(email=email).first()

    if existing:
        return jsonify({
            "status": "error",
            "message": "Account already exists. Please login."
        })

    user = User(name=name, email=email, phone=phone)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Registration successful! Please login."
    })



@app.route('/user/login', methods=['POST'])
def user_login():
    contact = request.form.get('contact', '').strip().lower()
    password = request.form.get('password', '')

    user = None
    if '@' in contact:
        user = User.query.filter_by(email=contact).first()
    else:
        user = User.query.filter_by(phone=contact).first()

    if user and user.check_password(password):
        session['user_logged_in'] = True
        session['user_id'] = user.id
        session['user_name'] = user.name or user.email or user.phone
        session['user_email'] = user.email
        session['user_phone'] = user.phone

        # 🔥 IMPORTANT PART
        next_page = request.args.get('next') or url_for('homepage')

        return jsonify({
            "status": "success",
            "message": f"Welcome {session['user_name']}!",
            "redirect": next_page
        })

    return jsonify({
        "status": "error",
        "message": "Invalid email/phone or password"
    })

# @app.route('/forward_to_authority/<complaint_id>', methods=['POST'])
# def forward_to_authority(complaint_id):
#     if not session.get('admin_logged_in'):
#         return jsonify({"status": "error", "message": "Unauthorized"}), 401

#     dept_name = request.form.get('department')
#     dept_email = request.form.get('dept_email')
    
#     complaint = Complaint.query.filter_by(complaint_code=complaint_id.upper()).first()
    
#     if complaint:
#         complaint.status = f"Forwarded to {dept_name}"
#         complaint.progress = 50 
#         db.session.commit()

#         # Authority Email Notification
#         subject = f"URGENT: Complaint Assigned #{complaint_id}"
#         body = f"Dear {dept_name},\n\nA new complaint has been assigned to you.\nID: {complaint_id}\nCategory: {complaint.category}\nLocation: {complaint.location}\n\nPlease take action.\n\nRegards,\nCivicCare Admin"
#         send_notification(dept_email, subject, body)
        
#         return jsonify({"status": "success", "message": f"Forwarded to {dept_name}"})
#     return jsonify({"status": "error", "message": "Not found"}), 404

# @app.route('/authority/update/<complaint_code>', methods=['GET', 'POST'])
# def authority_update(complaint_code):
#     complaint = Complaint.query.filter_by(complaint_code=complaint_code).first_or_404()
    
#     if request.method == 'POST':
#         file = request.files.get('proof_img')
#         note = request.form.get('note')
        
#         if file:
#             filename = f"resolved_{complaint_code}.jpg"
#             file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
#             complaint.authority_photo = filename
            
#         complaint.authority_note = note
#         complaint.status = "Action Taken" # Admin ko signal dene ke liye status change
#         complaint.progress = 80           # Progress bar badha dein
#         db.session.commit()
#         return "<h3>Success! Proof submitted to Admin for verification.</h3>"

#     return render_template('authority_form.html', complaint=complaint)

@app.route('/logout')
def logout():
    session.clear()   # clears all user data
    return redirect(url_for('homepage'))

# ------------ Startup (create tables) ------------
with app.app_context():
    ensure_upload_dir()
    db.create_all()

# ------------ Run ------------
if __name__ == '__main__':
    ensure_upload_dir()
    app.run(host='0.0.0.0', port=5000, debug=True)
