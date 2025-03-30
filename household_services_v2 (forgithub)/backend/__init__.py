import os
from flask import Flask, jsonify, current_app, send_from_directory 
from werkzeug.exceptions import HTTPException
from .config import Config
from .extensions import db, migrate, login_manager, cache, make_celery, celery_app
from .models import User


def create_app(config_class=Config):
    
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'household_services_v2/frontend'))

    app = Flask(__name__,
                instance_relative_config=True,
                instance_path=Config.INSTANCE_FOLDER_PATH,
                static_folder=static_dir, 
                static_url_path=''        
               )
    app.config.from_object(config_class)

    #extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    cache.init_app(app)
    

    #Celery
    global celery_app
    celery_app = make_celery(app)
    app.celery = celery_app

    # API Blueprints
    from .auth import auth_bp
    from .admin import admin_bp
    from .customer import customer_bp
    from .professional import professional_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(customer_bp, url_prefix='/api/customer')
    app.register_blueprint(professional_bp, url_prefix='/api/professional')

    # make tables and admin
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(role='admin').first():
             admin_user = User(username=app.config['ADMIN_USERNAME'], email='admin@household.com', role='admin', name='Admin User', is_active=True)
             admin_user.set_password(app.config['ADMIN_PASSWORD'])
             db.session.add(admin_user)
             db.session.commit()
             print(f"Admin user '{app.config['ADMIN_USERNAME']}' created.")

    # API error handling
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        response = e.get_response()
        response.data = jsonify({"code": e.code, "name": e.name, "description": e.description})
        response.content_type = "application/json"
        return response

    @app.errorhandler(Exception)
    def handle_generic_exception(e):
        current_app.logger.error(f"Unhandled exception: {e}", exc_info=True)
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500

    # Check Auth Status endpoint
    @app.route('/api/check_auth')
    def check_auth_status():
         from flask_login import current_user
         if current_user.is_authenticated:
             user_data = {'id': current_user.id, 'username': current_user.username, 'role': current_user.role, 'name': current_user.name, 'is_active': current_user.is_active}
             if current_user.is_professional() and current_user.professional_profile:
                  user_data['is_approved'] = current_user.professional_profile.is_approved
             return jsonify({'logged_in': True, 'user': user_data})
         else:
             return jsonify({'logged_in': False, 'user': None})

    # serving index.html
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_vue_app(path):
        full_path = os.path.join(app.static_folder, path)
        if path == "" or not os.path.exists(full_path) or os.path.isdir(full_path):
             index_path = os.path.join(app.static_folder, 'index.html')
             if not os.path.exists(index_path):
                  return jsonify({"error": "index.html not found in static folder: " + app.static_folder}), 404
             return send_from_directory(app.static_folder, 'index.html')
        else:
             return send_from_directory(app.static_folder, path)

# was giving error
    @app.route('/favicon.ico')
    def favicon():
        return '', 204

    return app
