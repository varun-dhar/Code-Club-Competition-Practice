import sanic

bp = sanic.Blueprint('admin')
bp.static('/admin', 'html/admin.html')
bp.static('/add-level', 'html/add-level.html')


@bp.middleware('request')
async def check_admin(request):
	record = await request.app.ctx.db['user_data'].find_one({'email': request.ctx.session_record['email']})
	if not record['admin']:
		return sanic.response.redirect('/')


@bp.get('/admin/users')
async def users_pg(request):
	template = request.app.ctx.environment.get_template('users.html')
	records = [record async for record in request.app.ctx.db['user_data'].find()]
	return sanic.response.html(await template.render_async(users=records))
