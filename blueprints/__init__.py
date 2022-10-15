import sanic

from . import api
from . import private
from . import public

__all__ = ['blueprints']

blueprints = sanic.Blueprint.group(api.group, private.group, public.group)
