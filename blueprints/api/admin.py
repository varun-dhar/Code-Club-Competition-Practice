import sanic
import pathlib
import aiofiles

bp = sanic.Blueprint('admin-api')


@bp.on_request
async def check_admin(request):
	record = await request.app.ctx.db['user_data'].find_one({'email': request.ctx.session_record['email']})
	if not record['admin']:
		return sanic.response.empty(status=403)


@bp.post('/add_level')
async def add_level(request):
	try:
		level = int(request.form['level'][0])
	except ValueError:
		return sanic.response.text('Level must be an integer', status=400)
	root = pathlib.Path('levels').resolve()
	level_path = root / str(level)
	if root not in level_path.resolve().parents:
		return sanic.response.text('Invalid level name', status=400)
	pathlib.Path(level_path).mkdir(exist_ok=True)
	for file in request.files['tests']:
		path = level_path / file.name
		if root not in path.resolve().parents:
			return sanic.response.text('Invalid filename', status=400)
		async with aiofiles.open(path, 'w') as f:
			await f.write(file.body.decode('utf-8'))

	await request.app.ctx.db['levels'].insert_one(
		{'level': level, 'desc': request.form['desc'][0], 'n_tests': len(request.files['tests']) // 2})
	return sanic.response.empty()


@bp.post('/delete_user')
async def delete_user(request: sanic.Request):
	if (email := request.json.get('email')) is None:
		return sanic.response.text('No email provided', status=400)

	db = request.app.ctx.db
	if (record := await db['user_data'].find_one({'email': email})) is None:
		return sanic.response.text('Account does not exist', status=400)
	if record['admin']:
		return sanic.response.text('Cannot delete admin account', status=400)

	await db['hashes'].delete_one({'email': email})
	await db['leaderboard'].delete_many({'email': email})
	await db['sessions'].delete_many({'email': email})
	await db['user_data'].delete_one({'email': email})
	return sanic.response.empty()
