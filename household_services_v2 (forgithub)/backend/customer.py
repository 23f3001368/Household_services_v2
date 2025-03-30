from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from .models import Service, ServiceRequest, User, db
from .extensions import cache
from functools import wraps
import datetime

customer_bp = Blueprint('customer', __name__)


def customer_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_customer():
            return jsonify({"error": "Customer privileges required"}), 403
        return f(*args, **kwargs)
    return decorated_function



@customer_bp.route('/services', methods=['GET'])
@login_required 
@cache.cached(timeout=120) 
def get_available_services():
    """Search for available services by name or pincode."""
    name_search = request.args.get('name')
    pincode_search = request.args.get('pincode') 

    query = Service.query

    if name_search:
        query = query.filter(Service.name.ilike(f'%{name_search}%'))

    
    if pincode_search:
        services_in_pincode = db.session.query(ProfessionalProfile.service_type_id)\
            .join(User, User.id == ProfessionalProfile.user_id)\
            .filter(
                ProfessionalProfile.location_pincode == pincode_search,
                ProfessionalProfile.is_approved == True,
                User.is_active == True
            )\
            .distinct() 

        query = query.filter(Service.id.in_(services_in_pincode))

    services = query.order_by(Service.name).all()
    service_list = [{
        'id': s.id,
        'name': s.name,
        'description': s.description,
        'base_price': s.base_price,
        'time_required': s.time_required
    } for s in services]
    return jsonify(service_list)




@customer_bp.route('/requests', methods=['POST'])
@customer_required
def create_service_request():
    """Create a new service request."""
    data = request.get_json()
    service_id = data.get('service_id')
    requested_datetime_str = data.get('requested_datetime') 
    location_pincode = data.get('location_pincode') 

    if not all([service_id, requested_datetime_str, location_pincode]):
        return jsonify({"error": "Missing required fields (service_id, requested_datetime, location_pincode)"}), 400

    service = db.session.get(Service, service_id)
    if not service:
        return jsonify({"error": "Invalid service selected"}), 404 

    try:
        
        requested_dt = datetime.datetime.fromisoformat(requested_datetime_str.replace('Z', '+00:00'))
        
        if requested_dt < datetime.datetime.utcnow():
             return jsonify({"error": "Requested date and time cannot be in the past"}), 400
    except ValueError:
        return jsonify({"error": "Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS or YYYY-MM-DDTHH:MM:SSZ)"}), 400

   
    if not (location_pincode and location_pincode.isdigit() and len(location_pincode) == 6):
         return jsonify({"error": "Invalid location pincode format (should be 6 digits)"}), 400

    new_request = ServiceRequest(
        customer_id=current_user.id,
        service_id=service_id,
        requested_datetime=requested_dt,
        location_pincode=location_pincode,
        status='requested' 
    )
    db.session.add(new_request)
    db.session.commit()

    return jsonify({"message": "Service request created successfully", "request_id": new_request.id}), 201

@customer_bp.route('/requests', methods=['GET'])
@customer_required
def get_my_service_requests():
    """Get all service requests made by the current customer."""
    try:
        requests = ServiceRequest.query.filter_by(customer_id=current_user.id)\
                                    .order_by(ServiceRequest.date_of_request.desc()).all()

        request_list = []
        for r in requests:
             request_list.append({
                'id': r.id,
                'service_name': r.service.name if r.service else 'N/A',
                'professional_name': r.professional.name if r.professional else 'Not Assigned',
                'status': r.status,
                'date_of_request': r.date_of_request.isoformat(),
                'requested_datetime': r.requested_datetime.isoformat() if r.requested_datetime else None,
                'date_of_completion': r.date_of_completion.isoformat() if r.date_of_completion else None,
                'location_pincode': r.location_pincode,
                'remarks': r.remarks
            })
        return jsonify(request_list)
    except Exception as e:
        current_app.logger.error(f"Error fetching requests for customer {current_user.id}: {e}", exc_info=True)
        return jsonify({"error": "Could not retrieve your service requests"}), 500


@customer_bp.route('/requests/<int:request_id>', methods=['PUT'])
@customer_required
def edit_service_request(request_id):
    """Edit details of an existing service request (e.g., date)."""
    service_request = db.session.get(ServiceRequest, request_id)

  
    if not service_request or service_request.customer_id != current_user.id:
        return jsonify({"error": "Service request not found or access denied"}), 404
    editable_statuses = ['requested']
    if service_request.status not in editable_statuses:
         return jsonify({"error": f"Cannot edit request in '{service_request.status}' status"}), 400
    data = request.get_json()
    updated = False

    if 'requested_datetime' in data:
        try:
            new_dt_str = data['requested_datetime']
            new_dt = datetime.datetime.fromisoformat(new_dt_str.replace('Z', '+00:00'))
            if new_dt < datetime.datetime.utcnow():
                return jsonify({"error": "Requested date and time cannot be in the past"}), 400
            service_request.requested_datetime = new_dt
            updated = True
        except ValueError:
            return jsonify({"error": "Invalid datetime format"}), 400
    if 'location_pincode' in data:
         new_pincode = data['location_pincode']
         if not (new_pincode and new_pincode.isdigit() and len(new_pincode) == 6):
             return jsonify({"error": "Invalid location pincode format"}), 400
         service_request.location_pincode = new_pincode
         updated = True
    if updated:
        db.session.commit()
        return jsonify({"message": "Service request updated successfully"}), 200
    else:
        return jsonify({"message": "No valid fields provided for update"}), 400


@customer_bp.route('/requests/<int:request_id>/close', methods=['POST'])
@customer_required
def close_service_request(request_id):
    """Close a 'completed' service request and add remarks."""
    service_request = db.session.get(ServiceRequest, request_id)
    if not service_request or service_request.customer_id != current_user.id:
        return jsonify({"error": "Service request not found or access denied"}), 404
    if service_request.status != 'completed':
        return jsonify({"error": "Request must be marked as 'completed' by the professional before closing"}), 400

    data = request.get_json()
    remarks = data.get('remarks', None) 

    service_request.status = 'closed'
    service_request.remarks = remarks
    
    if not service_request.date_of_completion:
        service_request.date_of_completion = datetime.datetime.utcnow()

    db.session.commit()
    return jsonify({"message": "Service request closed successfully"}), 200
