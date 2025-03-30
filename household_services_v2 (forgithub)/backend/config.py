import os
from dotenv import load_dotenv

load_dotenv() 

class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    INSTANCE_FOLDER_PATH = os.path.join(BASE_DIR, 'instance')
    os.makedirs(INSTANCE_FOLDER_PATH, exist_ok=True) 
#db
    SECRET_KEY = os.environ.get('SECRET_KEY', 'secret-key') 
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL',
        'sqlite:///' + os.path.join(INSTANCE_FOLDER_PATH, 'app.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
#redis
    CACHE_TYPE = 'RedisCache'
    CACHE_REDIS_URL = os.environ.get('CACHE_REDIS_URL', 'redis://localhost:6379/0')
    CACHE_DEFAULT_TIMEOUT = 300 
#celery
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
    CELERY_CONFIG = {
        'broker_url': CELERY_BROKER_URL,
        'result_backend': CELERY_RESULT_BACKEND,
        'imports': ('app.tasks',),
         'beat_schedule': {
            'daily-reminders': {
                'task': 'app.tasks.send_daily_reminders',
                'schedule': 86400.0,  
                
            },
            'monthly-activity-report': {
                'task': 'app.tasks.generate_monthly_reports_task',
                 'schedule': 2592000.0, 
                
            },
        },
        'timezone': 'UTC',
    }

    
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'password') 

   
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@household.com')

