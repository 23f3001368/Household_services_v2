from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from .models import User, CustomerProfile, ProfessionalProfile, Service, db
from .extensions import cache

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register/customer', methods=['POST'])
def register_customer():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')
    pincode = data.get('pincode') 

    if not all([username, email, password, name, pincode]):
        return jsonify({"error": "Missing required fields"}), 400

   
    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({"error": "Username or email already exists"}), 409 

    new_user = User(username=username, email=email, name=name, role='customer')
    new_user.set_password(password) 

   
    customer_profile = CustomerProfile(user=new_user, location_pincode=pincode)

    db.session.add(new_user)
    db.session.add(customer_profile)
    try:
        db.session.commit()
        return jsonify({"message": "Customer registered successfully"}), 201 
    except Exception as e:
        db.session.rollback()
        
        return jsonify({"error": "Registration failed due to server error"}), 500


@auth_bp.route('/register/professional', methods=['POST'])
def register_professional():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')
    service_type_id = data.get('service_type_id')
    experience = data.get('experience')
    prof_description = data.get('description')
    pincode = data.get('pincode') 

    
    if not all([username, email, password, name, service_type_id, pincode]):
        return jsonify({"error": "Missing required fields"}), 400

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({"error": "Username or email already exists"}), 409

   
    service = db.session.get(Service, service_type_id)
    if not service:
         return jsonify({"error": "Invalid service type selected"}), 400

    new_user = User(username=username, email=email, name=name, role='professional')
    new_user.set_password(password)

  
    professional_profile = ProfessionalProfile(
        user=new_user,
        service_type_id=service_type_id,
        experience=experience,
        description=prof_description,
        location_pincode=pincode,
        is_approved=False 
    )

    db.session.add(new_user)
    db.session.add(professional_profile)
    try:
        db.session.commit()
        return jsonify({"message": "Professional registered successfully. Awaiting admin approval."}), 201
    except Exception as e:
        db.session.rollback()
        
        return jsonify({"error": "Registration failed due to server error"}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        if not user.is_active:
             return jsonify({"error": "Account is blocked by administrator"}), 403 
        if user.is_professional():
            if not user.professional_profile or not user.professional_profile.is_approved:
                return jsonify({"error": "Account is awaiting administrator approval"}), 403 

       
        login_user(user, remember=True) 
        user_data = {
            'id': user.id,
            'username': user.username,
            'role': user.role,
            'name': user.name,
            'is_active': user.is_active
        }
        if user.is_professional():
            user_data['is_approved'] = user.professional_profile.is_approved if user.professional_profile else False

        return jsonify({"message": "Login successful", "user": user_data}), 200
    else:
        
        return jsonify({"error": "Invalid username or password"}), 401 


@auth_bp.route('/logout', methods=['POST'])
@login_required 
def logout():
    logout_user() 
    return jsonify({"message": "Logout successful"}), 200


@auth_bp.route('/services', methods=['GET'])
# @cache.cached(timeout=600) 
def get_services_list_for_registration():
    """Returns a list of available service types for professional registration."""
    try:
        services = Service.query.order_by(Service.name).all()
        return jsonify([{'id': s.id, 'name': s.name} for s in services])
    except Exception as e:
        
        return jsonify({"error": "Could not retrieve services list"}), 500