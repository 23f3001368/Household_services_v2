import os
from .__init__ import create_app, db
from .models import User, Service, ServiceRequest, ProfessionalProfile, CustomerProfile


app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Service': Service,
        'ServiceRequest': ServiceRequest,
        'ProfessionalProfile': ProfessionalProfile,
        'CustomerProfile': CustomerProfile
        }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)