from flask import Blueprint

bp = Blueprint('legal', __name__,
               template_folder='templates',
               url_prefix='/legal')

from . import routes  # noqa: E402, F401
