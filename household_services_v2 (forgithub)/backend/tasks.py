import datetime
import csv
import io
from flask import current_app
from .extensions import db # Assuming db is initialized in extensions
from .models import ServiceRequest, User, ProfessionalProfile, Service
from .__init__ import celery_app # Import the celery instance created in app factory

# --- Helper Functions for Notifications (Placeholders) ---
def send_email_notification(to, subject, html_body):
    # In a real app, use Flask-Mail or another library configured in create_app
    print("-" * 20)
    print(f"SIMULATING EMAIL to: {to}")
    print(f"Subject: {subject}")
    print(f"Body:\n{html_body}")
    print("-" * 20)
    # Check if mail is configured before attempting to send
    # if current_app.config.get('MAIL_SERVER'):
    #     try:
    #         # mail.send_message(subject=subject, recipients=[to], html=html_body)
    #         pass # Replace with actual mail sending call
    #     except Exception as e:
    #         current_app.logger.error(f"Failed to send email to {to}: {e}")
    # else:
    #      current_app.logger.warning("Mail server not configured. Skipping email send.")


def send_gchat_notification(webhook_url, message):
    if not webhook_url:
        current_app.logger.warning("GCHAT_WEBHOOK_URL not configured. Skipping GChat send.")
        print("SIMULATING GCHAT (Webhook URL missing)")
        return

    print("-" * 20)
    print(f"SIMULATING GCHAT to webhook: {webhook_url}")
    print(f"Message: {message}")
    print("-" * 20)
    # In a real app, use the 'requests' library
    # import requests
    # try:
    #     response = requests.post(webhook_url, json={'text': message})
    #     response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
    # except requests.exceptions.RequestException as e:
    #     current_app.logger.error(f"Failed to send GChat message: {e}")


# --- Core Functionality 7a: Daily Reminders (Scheduled Job) ---
@celery_app.task(name='app.tasks.send_daily_reminders')
def send_daily_reminders():
    """Sends reminders to professionals about pending assigned requests."""
    current_app.logger.info("Running Daily Reminder Task...")
    try:
        # Find requests that are 'assigned' but not yet 'accepted'
        # Optionally filter by age (e.g., assigned more than 24 hours ago)
        pending_requests = ServiceRequest.query.filter(
            ServiceRequest.status == 'assigned',
            ServiceRequest.professional_id != None
        ).all()

        reminders_sent = 0
        # Group reminders by professional to avoid spamming
        reminders_by_professional = {} # {professional_id: [request1, request2]}

        for req in pending_requests:
            if req.professional_id not in reminders_by_professional:
                reminders_by_professional[req.professional_id] = []
            reminders_by_professional[req.professional_id].append(
                f"- Request #{req.id} for '{req.service.name}' (Needed: {req.requested_datetime.strftime('%Y-%m-%d %H:%M') if req.requested_datetime else 'ASAP'})"
            )

        for professional_id, request_details in reminders_by_professional.items():
            professional = db.session.get(User, professional_id)
            if professional and professional.email: # Check if professional exists and has email
                num_requests = len(request_details)
                subject = f"Reminder: You have {num_requests} assigned service request(s) requiring action"
                request_list_html = "<ul>" + "".join([f"<li>{detail}</li>" for detail in request_details]) + "</ul>"
                body_html = f"""
                <p>Hello {professional.name},</p>
                <p>This is a reminder to please review and accept or reject the following assigned service request(s):</p>
                {request_list_html}
                <p>Thank you,</p>
                <p>Household Services Team</p>
                """
                gchat_message = f"Reminder for {professional.name}: You have {num_requests} pending assigned requests. Please check the platform."

                # Send Email
                send_email_notification(professional.email, subject, body_html)
                # Send GChat (if configured)
                gchat_url = current_app.config.get('GCHAT_WEBHOOK_URL')
                send_gchat_notification(gchat_url, gchat_message) # Simplified message for chat

                reminders_sent += 1

        current_app.logger.info(f"Daily Reminder Task finished. Sent reminders to {reminders_sent} professionals.")
        return f"Sent reminders to {reminders_sent} professionals."

    except Exception as e:
        current_app.logger.error(f"Error in daily reminder task: {e}", exc_info=True)
        # Raise exception so Celery knows the task failed
        raise e


# --- Core Functionality 7b: Monthly Activity Report (Scheduled Job) ---
@celery_app.task(name='app.tasks.generate_monthly_reports_task')
def generate_monthly_reports_task():
    """Generates and sends monthly activity reports (HTML format) to customers."""
    current_app.logger.info("Running Monthly Report Task...")
    try:
        # Calculate date range for the *previous* month
        today = datetime.date.today()
        first_day_current_month = today.replace(day=1)
        last_day_prev_month = first_day_current_month - datetime.timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)
        month_name = first_day_prev_month.strftime('%B %Y')

        # Get all active customers
        customers = User.query.filter_by(role='customer', is_active=True).all()
        reports_sent = 0

        for customer in customers:
            # Find requests created or completed within the previous month for this customer
            requests_last_month = ServiceRequest.query.filter(
                ServiceRequest.customer_id == customer.id,
                db.or_(
                    # Consider requests created in the month OR completed in the month
                     ServiceRequest.date_of_request.between(first_day_prev_month, last_day_prev_month.replace(hour=23, minute=59, second=59)),
                     ServiceRequest.date_of_completion.between(first_day_prev_month, last_day_prev_month.replace(hour=23, minute=59, second=59))
                )
            ).order_by(ServiceRequest.date_of_request.desc()).all()

            if not requests_last_month:
                continue # Skip customer if no activity in the period

            # Basic HTML Report Generation
            report_html = f"<html><head><title>Monthly Report</title></head><body>"
            report_html += f"<h1>Monthly Activity Report - {month_name}</h1>"
            report_html += f"<p>Dear {customer.name},</p>"
            report_html += f"<p>Here's a summary of your service activity for {month_name}:</p>"
            report_html += f"<p>Total Requests in Period: {len(requests_last_month)}</p>"

            # Simple Table
            report_html += "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>"
            report_html += "<thead style='background-color: #f2f2f2;'><tr><th>Request ID</th><th>Service</th><th>Date Requested</th><th>Status</th><th>Completion Date</th><th>Professional</th></tr></thead>"
            report_html += "<tbody>"
            for req in requests_last_month:
                completion_date = req.date_of_completion.strftime('%Y-%m-%d') if req.date_of_completion else 'N/A'
                professional_name = req.professional.name if req.professional else 'N/A'
                report_html += f"<tr><td>{req.id}</td><td>{req.service.name if req.service else 'N/A'}</td><td>{req.date_of_request.strftime('%Y-%m-%d')}</td><td>{req.status}</td><td>{completion_date}</td><td>{professional_name}</td></tr>"
            report_html += "</tbody></table>"

            report_html += "<p style='margin-top: 20px;'>Thank you for using our services!</p>"
            report_html += "</body></html>"

            # Send email
            if customer.email:
                subject = f"Your Household Services Monthly Report - {month_name}"
                send_email_notification(customer.email, subject, report_html)
                reports_sent += 1
            else:
                 current_app.logger.warning(f"Customer {customer.id} has no email address. Skipping report.")


        current_app.logger.info(f"Monthly Report Task finished. Sent {reports_sent} reports.")
        return f"Sent {reports_sent} reports."

    except Exception as e:
        current_app.logger.error(f"Error in monthly report task: {e}", exc_info=True)
        raise e


# --- Core Functionality 7c: Export as CSV (User Triggered Async Job) ---
@celery_app.task(name='app.tasks.export_service_requests_csv')
def export_service_requests_csv(admin_email):
    """Exports closed service requests to CSV and notifies the admin."""
    current_app.logger.info(f"Running CSV Export Task for admin: {admin_email}...")
    if not admin_email:
         current_app.logger.error("Admin email not provided for CSV export notification.")
         return "Error: Admin email missing."

    try:
        # Fetch all 'closed' service requests
        closed_requests = ServiceRequest.query.filter_by(status='closed')\
                                            .order_by(ServiceRequest.date_of_completion.desc()).all()

        if not closed_requests:
            message = "No closed service requests found to export."
            send_email_notification(admin_email, "CSV Export Result", f"<p>{message}</p>")
            current_app.logger.info(message)
            return message

        # Use StringIO to build CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write Header Row
        header = [
            'Request ID', 'Service ID', 'Service Name', 'Customer ID', 'Customer Name',
            'Professional ID', 'Professional Name', 'Date Requested',
            'Date Completed', 'Status', 'Remarks', 'Location Pincode'
        ]
        writer.writerow(header)

        # Write Data Rows
        for req in closed_requests:
            row = [
                req.id,
                req.service_id,
                req.service.name if req.service else 'N/A',
                req.customer_id,
                req.customer.name if req.customer else 'N/A',
                req.professional_id if req.professional else 'N/A',
                req.professional.name if req.professional else 'N/A',
                req.date_of_request.isoformat(),
                req.date_of_completion.isoformat() if req.date_of_completion else 'N/A',
                req.status,
                req.remarks,
                req.location_pincode
            ]
            writer.writerow(row)

        csv_content = output.getvalue()
        output.close()

        # Send Notification Email (In real app, might attach CSV or provide download link)
        num_requests = len(closed_requests)
        subject = "Service Request Export Completed"

        
        ####look at dis again
        #body = f
        #<p>Your export of {num_requests} closed service requests is complete.</p>
        #<p>The CSV data is attached (simulation - in a real app, this would be an attachment or download link).</p>
        #<hr>
        #<pre>{csv_content[:1000]}...</pre> {/* Displaying first 1000 chars as example */}
        
        # TODO: Actually attach the file or upload and send link
        send_email_notification(admin_email, subject, body)

        current_app.logger.info(f"CSV Export Task finished for {admin_email}. Exported {num_requests} requests.")
        return f"Exported {num_requests} requests. Notification sent to {admin_email}."

    except Exception as e:
        current_app.logger.error(f"Error in CSV export task: {e}", exc_info=True)
        # Notify admin about the failure
        send_email_notification(admin_email, "CSV Export Failed", f"<p>An error occurred during the CSV export: {e}</p>")
        # Raising exception marks task as failed in Celery
        raise e