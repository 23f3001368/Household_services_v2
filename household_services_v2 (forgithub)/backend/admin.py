from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from .models import User, Service, ServiceRequest, ProfessionalProfile, db
from .extensions import cache
from functools import wraps
from .__init__ import celery_app 
admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    @login_required # User must be logged in first
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin():
            return jsonify({"error": "Admin privileges required"}), 403 
        return f(*args, **kwargs)
    return decorated_function



@admin_bp.route('/users', methods=['GET'])
@admin_required
def manage_users():
    """Get a list of users (customers/professionals) with filtering/searching."""
    role_filter = request.args.get('role') 
    search_term = request.args.get('search') 

    query = User.query.filter(User.role != 'admin') 

    if role_filter in ['customer', 'professional']:
        query = query.filter(User.role == role_filter)

    if search_term:
         query = query.filter(
             db.or_(
                 User.username.ilike(f'%{search_term}%'),
                 User.email.ilike(f'%{search_term}%'),
                 User.name.ilike(f'%{search_term}%')
             )
         )

    users = query.order_by(User.date_created.desc()).all()

    user_list = []
    for user in users:
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'name': user.name,
            'role': user.role,
            'is_active': user.is_active, 
            'date_created': user.date_created.isoformat(),
        }
        if user.is_professional() and user.professional_profile:
            user_data['is_approved'] = user.professional_profile.is_approved 
            user_data['service_type'] = user.professional_profile.service_type.name if user.professional_profile.service_type else 'N/A'
        user_list.append(user_data)

    return jsonify(user_list)

@admin_bp.route('/users/<int:user_id>/approve', methods=['POST'])
@admin_required
def approve_professional(user_id):
    """Approve a service professional."""
    user = db.session.get(User, user_id)
    if not user or not user.is_professional() or not user.professional_profile:
        return jsonify({"error": "Professional user not found or profile missing"}), 404

    if user.professional_profile.is_approved:
        return jsonify({"message": "Professional already approved"}), 200 

    user.professional_profile.is_approved = True
    db.session.commit()
    
    return jsonify({"message": "Professional approved successfully"}), 200

@admin_bp.route('/users/<int:user_id>/block', methods=['POST'])
@admin_required
def block_user(user_id):
    """Block a customer or professional."""
    user = db.session.get(User, user_id)
    if not user or user.is_admin(): 
        return jsonify({"error": "User not found or cannot be blocked"}), 404

    if not user.is_active:
         return jsonify({"message": "User already blocked"}), 200

    user.is_active = False
    db.session.commit()
    
    return jsonify({"message": f"User '{user.username}' blocked successfully"}), 200

@admin_bp.route('/users/<int:user_id>/unblock', methods=['POST'])
@admin_required
def unblock_user(user_id):
    """Unblock a customer or professional."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.is_active:
         return jsonify({"message": "User already active"}), 200

    user.is_active = True
    db.session.commit()
    return jsonify({"message": f"User '{user.username}' unblocked successfully"}), 200


#services 
@admin_bp.route('/services', methods=['POST'])
@admin_required
def create_service():
    """Create a new service type."""
    data = request.get_json()
    name = data.get('name')
    base_price = data.get('base_price')
    description = data.get('description')
    time_required = data.get('time_required')

    if not name or base_price is None: 
        return jsonify({"error": "Missing required fields (name, base_price)"}), 400

    if Service.query.filter_by(name=name).first():
        return jsonify({"error": "Service with this name already exists"}), 409 

    try:
        price_float = float(base_price)
        if price_float < 0:
             return jsonify({"error": "Base price cannot be negative"}), 400
    except ValueError:
        return jsonify({"error": "Invalid base price format"}), 400

    new_service = Service(
        name=name,
        base_price=price_float,
        description=description,
        time_required=time_required
    )
    db.session.add(new_service)
    db.session.commit()

   
    cache.delete_memoized(get_available_services) 
    cache.delete_memoized(get_services_list_for_registration) 

    return jsonify({"message": "Service created successfully", "service": {"id": new_service.id, "name": new_service.name}}), 201

@admin_bp.route('/services/<int:service_id>', methods=['PUT'])
@admin_required
def update_service(service_id):
    """Update an existing service type."""
    service = db.session.get(Service, service_id)
    if not service:
        return jsonify({"error": "Service not found"}), 404

    data = request.get_json()
    
    if 'name' in data:
       
        existing = Service.query.filter(Service.name == data['name'], Service.id != service_id).first()
        if existing:
            return jsonify({"error": f"Another service with name '{data['name']}' already exists"}), 409
        service.name = data['name']
    if 'base_price' in data:
        try:
            price_float = float(data['base_price'])
            if price_float < 0:
                 return jsonify({"error": "Base price cannot be negative"}), 400
            service.base_price = price_float
        except ValueError:
            return jsonify({"error": "Invalid base price format"}), 400
    if 'description' in data:
        service.description = data['description']
    if 'time_required' in data:
        service.time_required = data['time_required']

    db.session.commit()
    
    cache.delete_memoized(get_available_services)
    cache.delete_memoized(get_services_list_for_registration)
    return jsonify({"message": "Service updated successfully"}), 200

@admin_bp.route('/services/<int:service_id>', methods=['DELETE'])
@admin_required
def delete_service(service_id):
    """Delete a service type."""
    service = db.session.get(Service, service_id)
    if not service:
        return jsonify({"error": "Service not found"}), 404
    if ProfessionalProfile.query.filter_by(service_type_id=service_id).first():
         return jsonify({"error": "Cannot delete service: It is assigned to one or more professionals."}), 400
    if ServiceRequest.query.filter_by(service_id=service_id).filter(ServiceRequest.status != 'closed').first():
         return jsonify({"error": "Cannot delete service: It is part of active or pending service requests."}), 400

    db.session.delete(service)
    db.session.commit()
    
    cache.delete_memoized(get_available_services)
    cache.delete_memoized(get_services_list_for_registration)
    return jsonify({"message": "Service deleted successfully"}), 200



@admin_bp.route('/export/service-requests', methods=['POST'])
@admin_required
def trigger_export_requests_csv():
    """Triggers an asynchronous job to generate and email a CSV export."""
    try:
       
        task = celery_app.send_task('app.tasks.export_service_requests_csv', args=[current_user.email])
        return jsonify({"message": "CSV export task triggered successfully. You will receive an email when complete.", "task_id": task.id}), 202 # Accepted
    except Exception as e:
        current_app.logger.error(f"Failed to trigger CSV export task: {e}", exc_info=True)
        return jsonify({"error": "Failed to trigger export task"}), 500


@admin_bp.route('/requests', methods=['GET'])
@admin_required
def admin_view_all_requests():
    """Provides an overview of all service requests for the admin."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)

        requests_query = ServiceRequest.query.order_by(ServiceRequest.date_of_request.desc())
        paginated_requests = requests_query.paginate(page=page, per_page=per_page, error_out=False)

        request_list = []
        for r in paginated_requests.items:
             request_list.append({
                'id': r.id,
                'customer_name': r.customer.name if r.customer else 'N/A',
                'service_name': r.service.name if r.service else 'N/A',
                'professional_name': r.professional.name if r.professional else 'Not Assigned',
                'status': r.status,
                'date_of_request': r.date_of_request.isoformat(),
                'requested_datetime': r.requested_datetime.isoformat() if r.requested_datetime else None,
                'date_of_completion': r.date_of_completion.isoformat() if r.date_of_completion else None,
                'location_pincode': r.location_pincode,
                'remarks': r.remarks
             })

        return jsonify({
            "requests": request_list,
            "total": paginated_requests.total,
            "pages": paginated_requests.pages,
            "current_page": page
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching all requests for admin: {e}", exc_info=True)
        return jsonify({"error": "Could not retrieve service requests"}), 500


from .customer import get_available_services
from .auth import get_services_list_for_registration