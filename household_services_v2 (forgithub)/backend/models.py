from .extensions import db, login_manager 
from flask_login import UserMixin
import datetime
from werkzeug.security import generate_password_hash, check_password_hash 


# user 
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False) 
    role = db.Column(db.String(20), nullable=False, default='customer')
    name = db.Column(db.String(100))
    date_created = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    #relationships
    customer_profile = db.relationship('CustomerProfile', back_populates='user', uselist=False, cascade="all, delete-orphan")
    professional_profile = db.relationship('ProfessionalProfile', back_populates='user', uselist=False, cascade="all, delete-orphan")
    customer_requests = db.relationship('ServiceRequest', foreign_keys='ServiceRequest.customer_id', back_populates='customer', lazy='dynamic')
    professional_tasks = db.relationship('ServiceRequest', foreign_keys='ServiceRequest.professional_id', back_populates='professional', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16) 

    def check_password(self, password):
        
        return check_password_hash(self.password_hash, password)

    
    def is_admin(self): return self.role == 'admin'
    def is_professional(self): return self.role == 'professional'
    def is_customer(self): return self.role == 'customer'
    def get_id(self): return str(self.id)
    def __repr__(self): return f'<User {self.username} ({self.role})>'


@login_manager.user_loader
def load_user(user_id):
    try: return db.session.get(User, int(user_id))
    except: return None



class CustomerProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    location_pincode = db.Column(db.String(10))
    user = db.relationship('User', back_populates='customer_profile')

class ProfessionalProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    service_type_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)
    experience = db.Column(db.Integer)
    description = db.Column(db.Text)
    location_pincode = db.Column(db.String(10)) 
    is_approved = db.Column(db.Boolean, default=False)
    user = db.relationship('User', back_populates='professional_profile')
    service_type = db.relationship('Service') 

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    base_price = db.Column(db.Float, nullable=False)
    time_required = db.Column(db.String(50), nullable=True)
    requests = db.relationship('ServiceRequest', back_populates='service', lazy='dynamic')
    def __repr__(self): return f'<Service {self.name}>'

class ServiceRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    professional_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) 
    date_of_request = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    requested_datetime = db.Column(db.DateTime, nullable=True) 
    date_of_completion = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='requested') 
    remarks = db.Column(db.Text, nullable=True) 
    location_pincode = db.Column(db.String(10), nullable=False) 
    customer = db.relationship('User', foreign_keys=[customer_id], back_populates='customer_requests')
    service = db.relationship('Service', back_populates='requests')
    professional = db.relationship('User', foreign_keys=[professional_id], back_populates='professional_tasks')
    def __repr__(self): return f'<ServiceRequest {self.id} ({self.status})>'