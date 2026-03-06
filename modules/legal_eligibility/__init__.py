from flask import Blueprint

bp = Blueprint('eligibility', __name__,
               url_prefix='/eligibility',
               template_folder='templates')

from . import routes  # noqa: E402,F401
