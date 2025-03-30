from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from .models import ServiceRequest, User, ProfessionalProfile, db
from functools import wraps
import datetime

professional_bp = Blueprint('professional', __name__)

# --- Decorator for Approved Professional Role Check ---
def professional_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        # Check role, profile existence, and approval status
        if not current_user.is_professional() or \
           not current_user.professional_profile or \
           not current_user.professional_profile.is_approved:
            return jsonify({"error": "Approved professional access required"}), 403
        # Also ensure the professional user account itself is active
        if not current_user.is_active:
             return jsonify({"error": "Account is blocked"}), 403

        return f(*args, **kwargs)
    return decorated_function

# --- Core Functionality 6: Take Action on Service Request ---

@professional_bp.route('/requests', methods=['GET'])
@professional_required
def get_my_tasks():
    """Get service requests assigned to or accepted by the current professional."""
    # Show requests that need action ('assigned') or are in progress ('accepted')
    # Could also include 'completed' to show recently finished tasks before customer closes.
    relevant_statuses = ['assigned', 'accepted', 'completed']
    try:
        requests = ServiceRequest.query.filter(
                        ServiceRequest.professional_id == current_user.id,
                        ServiceRequest.status.in_(relevant_statuses)
                    ).order_by(ServiceRequest.requested_datetime.asc()).all() # Order by when needed

        request_list = []
        for r in requests:
             request_list.append({
                'id': r.id,
                'customer_name': r.customer.name if r.customer else 'N/A',
                'service_name': r.service.name if r.service else 'N/A',
                'status': r.status,
                'date_of_request': r.date_of_request.isoformat(),
                'requested_datetime': r.requested_datetime.isoformat() if r.requested_datetime else None,
                'location_pincode': r.location_pincode,
                # 'customer_remarks_on_close': r.remarks if r.status == 'closed' else None # Maybe not needed here
            })
        return jsonify(request_list)
    except Exception as e:
        current_app.logger.error(f"Error fetching tasks for professional {current_user.id}: {e}", exc_info=True)
        return jsonify({"error": "Could not retrieve assigned tasks"}), 500


@professional_bp.route('/requests/<int:request_id>/accept', methods=['POST'])
@professional_required
def accept_request(request_id):
    """Accept an assigned service request."""
    service_request = db.session.get(ServiceRequest, request_id)

    # Check if request exists and is assigned to this professional
    if not service_request or service_request.professional_id != current_user.id:
        return jsonify({"error": "Service request not found or not assigned to you"}), 404

    # Can only accept if status is 'assigned'
    if service_request.status != 'assigned':
        return jsonify({"error": f"Cannot accept request with status '{service_request.status}'"}), 400

    service_request.status = 'accepted'
    db.session.commit()
    # TODO (Optional): Notify customer that the request is accepted?
    return jsonify({"message": "Service request accepted"}), 200


@professional_bp.route('/requests/<int:request_id>/reject', methods=['POST'])
@professional_required
def reject_request(request_id):
    """Reject an assigned service request."""
    service_request = db.session.get(ServiceRequest, request_id)

    # Check if request exists and is assigned to this professional
    if not service_request or service_request.professional_id != current_user.id:
        return jsonify({"error": "Service request not found or not assigned to you"}), 404

    # Can only reject if status is 'assigned'
    if service_request.status != 'assigned':
        return jsonify({"error": f"Cannot reject request with status '{service_request.status}'"}), 400

    # Revert status to 'requested' and remove professional assignment
    # This allows admin to potentially re-assign it.
    service_request.status = 'requested'
    # Optionally, add a reason field to the model/request for rejection?
    service_request.professional_id = None # Unassign

    db.session.commit()
    # TODO (Optional): Notify admin about the rejection?
    return jsonify({"message": "Service request rejected and unassigned"}), 200


@professional_bp.route('/requests/<int:request_id>/complete', methods=['POST'])
@professional_required
def complete_request(request_id):
    """Mark a service request as completed (by the professional)."""
    service_request = db.session.get(ServiceRequest, request_id)

    # Check if request exists and is assigned to this professional
    if not service_request or service_request.professional_id != current_user.id:
        return jsonify({"error": "Service request not found or not assigned to you"}), 404

    # Can only complete if status is 'accepted' (i.e., they started the work)
    if service_request.status != 'accepted':
        return jsonify({"error": f"Cannot mark request as completed from status '{service_request.status}'"}), 400

    service_request.status = 'completed'
    service_request.date_of_completion = datetime.datetime.utcnow() # Mark completion time
    db.session.commit()
    # TODO (Optional): Notify customer that service is complete and awaiting closure/review?
    return jsonify({"message": "Service request marked as completed. Awaiting customer closure."}), 200