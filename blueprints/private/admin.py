import sanic

bp = sanic.Blueprint('admin')
bp.static('/admin', 'html/admin.html', name='admin')
bp.static('/admin/add_level', 'html/add-level.html', name='add-level')
bp.static('/assets/scripts/delete-user.js', 'assets/scripts/delete-user.js', name='delete-user-js')


@bp.on_request
async def check_admin(request: sanic.Request):
	record = await request.app.ctx.db['user_data'].find_one({'email': request.ctx.session_record['email']})
	if not record['admin']:
		return sanic.response.redirect('/')


@bp.get('/admin/users')
async def users_pg(request: sanic.Request):
	template = request.app.ctx.environment.get_template('users.html')
	records = [record async for record in request.app.ctx.db['user_data'].find()]
	return sanic.response.html(await template.render_async(users=records))
