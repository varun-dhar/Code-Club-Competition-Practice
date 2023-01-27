import sanic

bp = sanic.Blueprint('account-private')


@bp.get('/logout')
async def logout(request: sanic.Request):
	res = sanic.response.redirect('/login')
	await request.app.ctx.db['sessions'].delete_one({'token': request.cookies['session_token']})
	del res.cookies['session_token']
	return res
