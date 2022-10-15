import sanic

import api
import private
import public

__all__ = ['blueprints']

blueprints = sanic.Blueprint.group(api.group, private.group, public.group)
