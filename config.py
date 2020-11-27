# vim: sw=4:ts=4:et
# configuration settings for the GUI

import saq
from saq.util import abs_path

def get_sqlalchemy_database_uri(db_name: str) -> str:
    """Returns the correct uri for the given database based on configuration settings."""
    if saq.CONFIG[f'database_{db_name}']['driver'] == 'mysql':
        if saq.CONFIG[f'database_{db_name}'].get('unix_socket', fallback=None):
            return 'mysql+pymysql://{username}:{password}@localhost/{database}?unix_socket={unix_socket}&charset=utf8mb4'.format(
                username=saq.CONFIG.get(f'database_{db_name}', 'username'),
                password=saq.CONFIG.get(f'database_{db_name}', 'password'),
                unix_socket=saq.CONFIG.get(f'database_{db_name}', 'unix_socket'),
                database=saq.CONFIG.get(f'database_{db_name}', 'database'))
        else:
            SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://{username}:{password}@{hostname}/{database}?charset=utf8mb4'.format(
                username=saq.CONFIG.get(f'database_{db_name}', 'username'),
                password=saq.CONFIG.get(f'database_{db_name}', 'password'),
                hostname=saq.CONFIG.get(f'database_{db_name}', 'hostname'),
                database=saq.CONFIG.get(f'database_{db_name}', 'database'))

    elif saq.CONFIG[f'database_{db_name}']['driver'] == 'sqlite':
        return 'sqlite://'
    else:
        raise ValueError("invalid driver specified for database_{}: {}".format(
            db_name, saq.CONFIG[f'database_{db_name}']['driver']))

def get_sqlalchemy_database_options(db_name: str) -> dict:
    """Returns dict of the kwargs to submit to create_engine()"""
    if saq.CONFIG[f'database_{db_name}']['driver'] == 'mysql':
        return { 
            'isolation_level': 'READ COMMITTED',
            'pool_recycle': 60,
            'pool_size': 5,
            'connect_args': { 'init_command': 'SET NAMES utf8mb4' }
        }
    else:
        return {}

class Config(object):
    SECRET_KEY = saq.CONFIG['gui']['secret_key']
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    INSTANCE_NAME = saq.CONFIG.get('global', 'instance_name')

    # GUI configurations for base template use
    GUI_DISPLAY_METRICS = saq.CONFIG['gui'].getboolean('display_metrics')
    GUI_DISPLAY_EVENTS = saq.CONFIG['gui'].getboolean('display_events')
    AUTHENTICATION_ON = saq.CONFIG['gui'].getboolean('authentication')
    GOOGLE_ANALYTICS = saq.CONFIG['gui'].getboolean('google_analytics')

    # also see lib/saq/database.py:initialize_database
    if saq.CONFIG['database_ace'].get('unix_socket', fallback=None):
        SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://{username}:{password}@localhost/{database}?unix_socket={unix_socket}&charset=utf8mb4'.format(
            username=saq.CONFIG.get('database_ace', 'username'),
            password=saq.CONFIG.get('database_ace', 'password'),
            unix_socket=saq.CONFIG.get('database_ace', 'unix_socket'),
            database=saq.CONFIG.get('database_ace', 'database'))
    else:
        SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://{username}:{password}@{hostname}/{database}?charset=utf8mb4'.format(
            username=saq.CONFIG.get('database_ace', 'username'),
            password=saq.CONFIG.get('database_ace', 'password'),
            hostname=saq.CONFIG.get('database_ace', 'hostname'),
            database=saq.CONFIG.get('database_ace', 'database'))

    SQLALCHEMY_POOL_TIMEOUT = 10
    SQLALCHEMY_POOL_RECYCLE = 60

    # gets passed as **kwargs to create_engine call of SQLAlchemy
    # this is used by the non-flask applications to configure SQLAlchemy db connection
    SQLALCHEMY_DATABASE_OPTIONS = { 
        'pool_recycle': 60,
        'pool_size': 5,
        'connect_args': { 'init_command': 'SET NAMES utf8mb4' }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # are we using SSL for MySQL connections? (you should be)
        if not saq.CONFIG['database_ace'].get('unix_socket', fallback=None):
            if saq.CONFIG['database_ace'].get('ssl_ca', fallback=None) \
            or saq.CONFIG['database_ace'].get('ssl_cert', fallback=None) \
            or saq.CONFIG['database_ace'].get('ssl_key', fallback=None):
                ssl_options = { 'ca': abs_path(saq.CONFIG['database_ace']['ssl_ca']) }
                if saq.CONFIG['database_ace'].get('ssl_cert', fallback=None):
                    ssl_options['cert'] = abs_path(saq.CONFIG['database_ace']['ssl_cert'])
                if saq.CONFIG['database_ace'].get('ssl_key', fallback=None):
                    ssl_options['key'] = abs_path(saq.CONFIG['database_ace']['ssl_key'])
                self.SQLALCHEMY_DATABASE_OPTIONS['connect_args']['ssl'] = ssl_options

    @staticmethod
    def init_app(app):
        pass

class ProductionConfig(Config):
    
    DEBUG = False
    TEMPLATES_AUTO_RELOAD = False

class DevelopmentConfig(Config):

    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True

class UnitTestConfig(Config):

    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True

# the keys for this dict match the instance_type config setting in global section of etc/saq.ini
config = {
    'UNITTEST': UnitTestConfig(),
    'DEV': DevelopmentConfig(),
    'QA': ProductionConfig(),
    'PRODUCTION': ProductionConfig(),
}
