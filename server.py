import datetime

import motor.motor_asyncio
import sanic, sanic.response, sanic.exceptions
import os
import asyncio
import aiofiles
import aiohttp
import argon2
import secrets
import concurrent.futures
import re
import statistics
import pathlib
import dotenv
import jinja2

'''
TODO
- steal challenges from leetcode and usaco
- make this look better
'''

dotenv.load_dotenv()

app = sanic.Sanic('runner')

app.ctx.smtp_sender = os.getenv('SENDER_EMAIL')
app.ctx.mailjet_user = os.getenv('MAILJET_USERNAME')
app.ctx.mailjet_pass = os.getenv('MAILJET_PASSWORD')

app.ctx.domain = os.getenv('DOMAIN')

app.ctx.email_re = re.compile(
	'(?:[a-z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&\'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])')
app.ctx.pass_re = re.compile("^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,100}$")

app.ctx.langs = {'Java': 'java1800', 'C++': 'gsnapshot', 'C': 'cgsnapshot', 'Python3': 'python310', 'Go': 'gltip',
				 'Kotlin': 'kotlinc1700', 'Ruby': 'ruby302', 'Rust': 'nightly', 'TypeScript': 'tsc_0_0_20_gc'}

redirect = sanic.Sanic('http_redir')
redirect.static('/.well-known', '/var/www/.well-known', resource_type='dir')


@app.before_server_start
async def before_start(app: sanic.Sanic, loop):
	pathlib.Path('levels').mkdir(exist_ok=True)
	app.ctx.db_client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv('MONGODB_URL'), tls=True,
															   tlsCertificateKeyFile=os.getenv('MONGODB_CERT'),
															   io_loop=loop)
	app.ctx.db = app.ctx.db_client['data']
	await app.ctx.db['sessions'].create_index('last_login', expireAfterSeconds=60 * 60)
	await app.ctx.db['user_data'].create_index('email', unique=True)
	await app.ctx.db['hashes'].create_index('email', unique=True)
	app.ctx.session = aiohttp.ClientSession(loop=loop)
	app.ctx.environment = jinja2.Environment(loader=jinja2.FileSystemLoader('templates/'), enable_async=True,
											 autoescape=True)
	app.ctx.redirect = await redirect.create_server(host='0.0.0.0', port=80, return_asyncio_server=True)
	await app.add_task(redirect_runner(redirect, app.ctx.redirect))


@app.before_server_stop
async def stop(app, _):
	await app.ctx.redirect.close()


@redirect.exception(sanic.exceptions.NotFound, sanic.exceptions.MethodNotSupported)
def redirect_everything_else(request, exception):
	server, path = request.server_name, request.path
	if server and path.startswith("/"):
		return sanic.response.redirect(f"https://{server}{path}", status=308)
	return sanic.response.empty(status=400)


async def redirect_runner(redirector: sanic.Sanic, app_server):
	redirector.is_running = True
	try:
		redirector.signalize()
		redirector.finalize()
		redirector.state.is_started = True
		await app_server.serve_forever()
	finally:
		redirector.is_running = False
		redirector.is_stopping = True


async def check_login_rec(request):
	if 'session_token' not in request.cookies:
		return None
	record = await request.app.ctx.db['sessions'].find_one({'token': request.cookies['session_token']})
	if not record:
		return None
	await request.app.ctx.db['sessions'].update_one({'token': request.cookies['session_token']},
													[{'$set': {'last_login': datetime.datetime.utcnow()}}])
	return record


async def check_login(request):
	if (await check_login_rec(request)) is not None:
		return None
	res = sanic.response.redirect('/login')
	del res.cookies['session_token']
	return res


async def check_admin(request):
	if (record := await check_login_rec(request)) is None:
		res = sanic.response.redirect('/login')
		del res.cookies['session_token']
		return res
	record = await request.app.ctx.db['user_data'].find_one({'email': record['email']})
	if not record['admin']:
		return sanic.response.redirect('/')
	return None


async def check_admin_api(request):
	if (record := await check_login_rec(request)) is None:
		res = sanic.response.json({'success': False, 'error': 'Unauthorized'}, status=401)
		del res.cookies['session_token']
		return res
	record = await request.app.ctx.db['user_data'].find_one({'email': record['email']})
	if not record['admin']:
		return sanic.response.json({'success': False, 'error': 'Forbidden'}, status=403)
	return None


@app.get('/')
async def home(request):
	if (resp := await check_login(request)) is not None:
		return resp
	template = request.app.ctx.environment.get_template('index.html')
	return sanic.response.html(await template.render_async(
		levels=[record['level'] async for record in request.app.ctx.db['levels'].find().sort('level', 1)]))


@app.get('/levels/<level:int>')
async def level_pg(request, level: int):
	if (resp := await check_login(request)) is not None:
		return resp
	record = await request.app.ctx.db["levels"].find_one({"level": level})
	if not record:
		return sanic.response.empty(status=404)
	template = request.app.ctx.environment.get_template('level.html')
	return sanic.response.html(
		await template.render_async(langs=request.app.ctx.langs.keys(), level=level, desc=record['desc']))


@app.get('/leaderboards/<level:int>')
async def leaderboard_pg(request, level: int):
	if (resp := await check_login(request)) is not None:
		return resp
	if not (await request.app.ctx.db["levels"].find_one({"level": level})):
		return sanic.response.empty(status=404)
	entries = []
	async for record in request.app.ctx.db['leaderboard'].find({'level': level}).sort('median'):
		user_data = await request.app.ctx.db['user_data'].find_one({'email': record['email']})
		entries.append({'name': user_data['name'], 'mean': record['mean'], 'median': record['median']})

	template = request.app.ctx.environment.get_template('leaderboard.html')
	return sanic.response.html(await template.render_async(level=level, entries=entries))


@app.get('/admin')
async def admin_pg(request):
	if (resp := await check_admin(request)) is not None:
		return resp
	return await sanic.response.file('admin.html')


@app.get('/admin/add_level')
async def add_level_pg(request):
	if (resp := await check_admin(request)) is not None:
		return resp
	return await sanic.response.file('add-level.html')


@app.get('/admin/users')
async def users_pg(request):
	if (resp := await check_admin(request)) is not None:
		return resp
	template = request.app.ctx.environment.get_template('users.html')
	records = [record async for record in request.app.ctx.db['user_data'].find()]
	return sanic.response.html(await template.render_async(users=records))


@app.post('/add_level')
async def add_level(request):
	if (resp := await check_admin_api(request)) is not None:
		return resp
	try:
		level = int(request.form['level'][0])
	except ValueError:
		return sanic.response.json({'success': False, 'error': 'Invalid form'}, status=400)
	root = pathlib.Path('levels')
	level_path = root / str(level)
	if root not in level_path.parents:
		return sanic.response.json({'success': False, 'error': 'Invalid form'}, status=400)
	pathlib.Path(level_path).mkdir(exist_ok=True)
	for file in request.files['tests']:
		path = level_path / file.name
		if root not in path.parents:
			return sanic.response.json({'success': False, 'error': 'Invalid form'}, status=400)
		async with aiofiles.open(path, 'w') as f:
			await f.write(file.body.decode('utf-8'))

	await request.app.ctx.db['levels'].insert_one(
		{'level': level, 'desc': request.form['desc'][0], 'n_tests': len(request.files['tests']) // 2})
	return sanic.response.json({'success': True})


@app.post('/delete_user')
async def delete_user(request: sanic.Request):
	if (resp := await check_admin_api(request)) is not None:
		return resp

	if (email := request.json.get('email')) is None:
		return sanic.response.json({'success': False, 'error': 'No email provided'}, status=400)

	db = request.app.ctx.db
	if (record := await db['user_data'].find_one({'email': email})) is None:
		return sanic.response.json({'success': False, 'error': 'Account does not exist'}, status=400)
	if record['admin']:
		return sanic.response.json({'success': False, 'error': 'Cannot delete admin account'}, status=400)

	await db['hashes'].delete_one({'email': email})
	await db['leaderboard'].delete_many({'email': email})
	await db['sessions'].delete_many({'email': email})
	await db['user_data'].delete_one({'email': email})
	return sanic.response.json({'success': True})


@app.post('/test/<level:int>')
async def run_test(request, level: int):
	if not request.form or 'lang' not in request.form or not request.files or 'file' not in request.files or \
			(await request.app.ctx.db['levels'].find_one({'level': level})) is None \
			or (lang_id := request.app.ctx.langs.get(request.form['lang'][0])) is None:
		return sanic.response.json({'success': False, 'error': 'Invalid form'}, status=400)

	if (record := await check_login_rec(request)) is None:
		res = sanic.response.redirect('/login')
		del res.cookies['session_token']
		return res
	await request.app.ctx.db['sessions'].update_one({'token': request.cookies['session_token']},
													[{'$set': {'last_login': datetime.datetime.utcnow()}}])

	email = record['email']

	try:
		file = request.files['file'][0].body.decode('utf-8')
	except UnicodeDecodeError:
		return sanic.response.json({'success': False, 'error': 'Invalid file'}, status=400)

	level_info = await request.app.ctx.db['levels'].find_one({'level': level})
	exec_times = []
	for i in range(1, level_info['n_tests'] + 1):
		async with aiofiles.open(f'levels/{level}/{i}.in', 'r') as f:
			test_input = await f.read()
		async with request.app.ctx.session.post(
				f'https://godbolt.org/api/compiler/{lang_id}/compile',
				json={'source': file, 'options': {
					'executeParameters': {
						'stdin': test_input}, 'compilerOptions': {'executorRequest': True},
					'filters': {'execute': True}}},
				headers={'Accept': 'application/json'}) as res:
			result = await res.json()
		if result['buildResult']['code'] != 0:
			return sanic.response.json(
				{'success': False, 'error': '\n'.join(map(lambda x: x['text'], result['stderr']))})
		output = '\n'.join(map(lambda x: x['text'], result['stdout'])).strip()
		async with aiofiles.open(f'levels/{level}/{i}.out', 'r') as f:
			ans = (await f.read()).strip()
		if output != ans:
			return sanic.response.json({'success': False, 'error': 'Test failed'})
		exec_times.append(int(result['execTime']))

	mean = statistics.mean(exec_times)
	median = statistics.median(exec_times)
	rank_data = await request.app.ctx.db['leaderboard'].find_one({'email': email, 'level': level})
	if not rank_data or rank_data['mean'] > mean or rank_data['median'] > median:
		await request.app.ctx.db['leaderboard'].update_one({'email': email, 'level': level},
														   [{'$set': {'median': median, 'mean': mean, 'code': file}}],
														   upsert=True)
	return sanic.response.json({'success': True})


@app.get('/register')
async def register_pg(request):
	if 'session_token' in request.cookies and (
			await request.app.ctx.db['sessions'].find_one({'token': request.cookies['session_token']})):
		return sanic.response.redirect('/')
	res = await sanic.response.file('register.html')
	if 'session_token' in request.cookies:
		del res.cookies['session_token']
	return res


@app.post('/register')
async def register(request):
	if not request.form or any(
			i not in request.form for i in
			('name', 'email', 'password', 'confirm_password')) or not request.app.ctx.email_re.match(
		request.form['email'][0]) or not request.app.ctx.pass_re.match(request.form['password'][0]) or \
			request.form['password'][0] != request.form['confirm_password'][0]:
		return sanic.response.json({'success': False, 'error': 'invalid form'}, status=400)

	del request.form['confirm_password'][0]

	email = request.form['email'][0]

	verification = secrets.token_urlsafe(16)
	if await request.app.ctx.db['user_data'].find_one({'email': email}) or (doc := (
			await request.app.ctx.db['unverified'].update_one({'email': email},
															  {'$setOnInsert': {'email': email,
																				'verification': verification}},
															  upsert=True))).matched_count >= 1:
		return sanic.response.json({'success': False, 'error': 'account exists'}, status=400)

	loop = asyncio.get_event_loop()
	with concurrent.futures.ThreadPoolExecutor() as pool:
		hasher = argon2.PasswordHasher()
		pwd_hash = await loop.run_in_executor(pool, hasher.hash, request.form['password'][0])
		del request.form['password'][0]

	template = request.app.ctx.environment.get_template('verify-email.html')
	async with request.app.ctx.session.post('https://api.mailjet.com/v3.1/send',
											auth=aiohttp.BasicAuth(request.app.ctx.mailjet_user,
																   request.app.ctx.mailjet_pass),
											json={'Messages':
												[{'From':
													{
														'Email': request.app.ctx.smtp_sender,
														'Name': 'EBPracticode'
													},
													'To':
														[{
															'Email': email,
															'Name': request.form['name'][0]
														}],
													'Subject': 'Verify your EBPracticode account',
													'HTMLPart': (
															await template.render_async(domain=request.app.ctx.domain,
																						verification=verification))
												}]}) as res:
		data = await res.json()
		if data['Messages'][0]['Status'] != 'success':
			return sanic.response.json(
				{'success': False, 'error': 'Failed to send verification email. Please try again later.'})

	del verification

	await request.app.ctx.db['hashes'].insert_one({'email': email, 'hash': pwd_hash})
	del pwd_hash
	await request.app.ctx.db['user_data'].insert_one(
		{'email': email, 'name': request.form['name'][0], 'verified': False, 'admin': False})
	return sanic.response.json({'success': True})


@app.get('/verify/<verification:str>')
async def verify(request, verification: str):
	record = await request.app.ctx.db['unverified'].find_one_and_delete({'verification': verification})
	template = request.app.ctx.environment.get_template('verify.html')
	if not record:
		return sanic.response.html((await template.render_async(message='Unknown or already verified account')),
								   status=400)
	await request.app.ctx.db['user_data'].update_one({'email': record['email']}, {'$set': {'verified': True}})
	return sanic.response.html(await template.render_async(message='Successfully verified'))


@app.get('/login')
async def login_pg(request):
	if 'session_token' not in request.cookies:
		return await sanic.response.file('login.html')

	record = await request.app.ctx.db['sessions'].find_one({'token': request.cookies['session_token']})
	if not record:
		res = await sanic.response.file('login.html')
		del res.cookies['session_token']
		return res
	return sanic.response.redirect('/')


@app.post('/login')
async def login(request):
	if not request.form or any(i not in request.form for i in ('email', 'password')):
		return sanic.response.json({'success': False, 'error': 'invalid form'}, status=400)

	email = request.form['email'][0]

	record = await request.app.ctx.db['hashes'].find_one({'email': email})
	if not record:
		return sanic.response.json({'success': False, 'error': 'invalid email/password'}, status=400)

	user_data = await request.app.ctx.db['user_data'].find_one({'email': email})
	if not user_data or not user_data['verified']:
		return sanic.response.json({'success': False, 'error': 'unverified account'}, status=400)

	loop = asyncio.get_event_loop()
	with concurrent.futures.ThreadPoolExecutor() as pool:
		hasher = argon2.PasswordHasher()
		try:
			await loop.run_in_executor(pool, hasher.verify, record['hash'], request.form['password'][0])
		except argon2.exceptions.VerifyMismatchError:
			return sanic.response.json({'success': False, 'error': 'invalid email/password'}, status=400)
		finally:
			del request.form['password'][0]
			del record

	token = secrets.token_urlsafe(16)
	await request.app.ctx.db['sessions'].insert_one({'email': email, 'token': token})
	res = sanic.response.json({'success': True})
	res.cookies['session_token'] = token
	# res.cookies['session_token']['max-age'] = 60 * 60
	res.cookies['session_token']['secure'] = True
	res.cookies['session_token']['httponly'] = True
	res.cookies['session_token']['samesite'] = 'Strict'
	return res


@app.get('/logout')
async def logout(request):
	res = sanic.response.redirect('/login')
	if 'session_token' in request.cookies:
		await request.app.ctx.db['sessions'].delete_one({'token': request.cookies['session_token']})
		del res.cookies['session_token']
	return res


app.run(host='0.0.0.0', port=443, ssl=os.getenv('CERT_DIR'))
