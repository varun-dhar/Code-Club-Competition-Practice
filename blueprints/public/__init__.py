import sanic

from . import account

__all__ = ['group']

group = sanic.Blueprint.group(account.bp)


@group.on_request
async def check_login(request):
	if 'session_token' in request.cookies and \
			(await request.app.ctx.db['sessions'].find_one({'token': request.cookies['session_token']})) is not None:
		return sanic.response.redirect('/')

	del request.cookies['session_token']
