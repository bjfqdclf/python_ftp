import os, sys

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

HOST = '127.0.0.1'
PORT = 7700

USER_HOME_DIR = os.path.join(BASE_DIR, 'home')

ACCOUNT_FILE = "%s/conf/accounts.ini" % BASE_DIR

MAX_SOCKET_LISTEN = 5
