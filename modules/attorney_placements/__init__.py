from flask import Blueprint

bp = Blueprint('placements', __name__,
               template_folder='templates',
               url_prefix='/placements')

from . import routes  # noqa: E402, F401
