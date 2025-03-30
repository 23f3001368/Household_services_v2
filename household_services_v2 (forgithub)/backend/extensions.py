# File: backend/app/extensions.py (Updated)

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_caching import Cache
from celery import Celery
# REMOVE: from bcrypt import Bcrypt # No longer using bcrypt directly

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
cache = Cache()
# REMOVE: bcrypt = Bcrypt() # No longer need an instance

# Configure Flask-Login (remains the same)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
login_manager.login_message = 'Please log in to access this page.'

# Celery Initialization Function (remains the same)
def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config['CELERY_CONFIG'])

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

# Celery instance placeholder (remains the same)
celery_app = None