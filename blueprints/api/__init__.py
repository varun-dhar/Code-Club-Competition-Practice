import sanic
import datetime

from . import admin
from . import user

__all__ = ['group']

group = sanic.Blueprint.group(admin.bp, user.bp)


@group.middleware('request', priority=1)
async def check_login(request: sanic.Request):
	if 'session_token' not in request.cookies:
		return sanic.response.empty(status=401)
	record = await request.app.ctx.db['sessions'].find_one({'token': request.cookies['session_token']})
	if not record:
		res = sanic.response.empty(status=401)
		del res.cookies['session_token']
		return res
	await request.app.ctx.db['sessions'].update_one({'token': request.cookies['session_token']},
													[{'$set': {'last_login': datetime.datetime.utcnow()}}])
	request.ctx.session_record = record
