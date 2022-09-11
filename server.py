import datetime

import motor.motor_asyncio
import sanic, sanic.response
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


@app.before_server_start
async def before_start(app, loop):
	pathlib.Path('levels').mkdir(exist_ok=True)
	app.ctx.db_client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv('MONGODB_URL'), tls=True,
															   tlsCertificateKeyFile=os.getenv('MONGODB_CERT'),
															   io_loop=loop)
	app.ctx.db = app.ctx.db_client['data']
	await app.ctx.db['sessions'].create_index('last_login', expireAfterSeconds=60 * 60)
	await app.ctx.db['user_data'].create_index('email', unique=True)
	await app.ctx.db['hashes'].create_index('email', unique=True)
	app.ctx.session = aiohttp.ClientSession(loop=loop)
	app.ctx.registrants = set()
	app.ctx.environment = jinja2.Environment(loader=jinja2.FileSystemLoader('templates/'), enable_async=True)


async def check_login(request):
	if 'session_token' not in request.cookies:
		return sanic.response.redirect('/login')

	record = await request.app.ctx.db['sessions'].find_one({'token': request.cookies['session_token']})
	if not record:
		res = sanic.response.redirect('/login')
		del res.cookies['session_token']
		return res
	await request.app.ctx.db['sessions'].update_one({'token': request.cookies['session_token']},
													[{'$set': {'last_login': datetime.datetime.utcnow()}}])
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
	if 'session_token' not in request.cookies:
		return sanic.response.redirect('/login')

	record = await request.app.ctx.db['sessions'].find_one({'token': request.cookies['session_token']})
	if not record:
		res = sanic.response.redirect('/login')
		del res.cookies['session_token']
		return res
	record = await request.app.ctx.db['user_data'].find_one({'email': record['email']})
	if not record['admin']:
		return sanic.response.redirect('/')
	return await sanic.response.file('admin.html')


@app.post('/add_level')
async def add_level(request):
	if 'session_token' not in request.cookies:
		return sanic.response.json({'success': False, 'error': 'Unauthorized'}, status=401)

	record = await request.app.ctx.db['sessions'].find_one({'token': request.cookies['session_token']})
	if not record:
		res = sanic.response.json({'success': False, 'error': 'Unauthorized'}, status=401)
		del res.cookies['session_token']
		return res
	record = await request.app.ctx.db['user_data'].find_one({'email': record['email']})
	if not record['admin']:
		return sanic.response.json({'success': False, 'error': 'Forbidden'}, status=403)
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


@app.post('/test/<level:int>')
async def run_test(request, level: int):
	if not request.form or 'lang' not in request.form or not request.files or 'file' not in request.files or \
			(await request.app.ctx.db['levels'].find_one({'level': level})) is None \
			or (lang_id := request.app.ctx.langs.get(request.form['lang'][0])) is None:
		return sanic.response.json({'success': False, 'error': 'Invalid form'}, status=400)

	if 'session_token' not in request.cookies:
		return sanic.response.json({'success': False, 'error': 'Not logged in'}, status=400)

	record = await request.app.ctx.db['sessions'].find_one({'token': request.cookies['session_token']})
	if not record:
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
														   [{'$set': {'median': median, 'mean': mean}}], upsert=True)
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
	if await request.app.ctx.db['user_data'].find_one({'email': email}) or (
			await request.app.ctx.db['unverified'].update_one({'email': email},
															  {'$setOnInsert': {'email': email,
																				'verification': verification}},
															  upsert=True)).matched_count >= 1:
		return sanic.response.json({'success': False, 'error': 'account exists'}, status=400)

	loop = asyncio.get_event_loop()
	with concurrent.futures.ThreadPoolExecutor() as pool:
		hasher = argon2.PasswordHasher()
		pwd_hash = await loop.run_in_executor(pool, hasher.hash, request.form['password'][0])
		del request.form['password'][0]

	async with request.app.ctx.session.post('https://api.mailjet.com/v3.1/send',
											auth=aiohttp.BasicAuth(request.app.ctx.mailjet_user,
																   request.app.ctx.mailjet_pass),
											json={'Messages':
												[{'From':
													{
														'Email': request.app.ctx.smtp_sender,
														'Name': 'EBHS Code Club Competition'
													},
													'To':
														[{
															'Email': email,
															'Name': request.form['name'][0]
														}],
													'Subject': 'Verify your HOC Code Competition Account',
													'HTMLPart': f'''<a href="https://{request.app.ctx.domain}/verify/{verification}">Verify your email</a>
															<br/>
														  <p>You will not be able to log in or submit entries until your email is verified.</p>
														  <br/>
														  <br/>
														  <p>Do not reply to this email; this inbox is not monitored.</p>
														  '''
												}]}) as res:
		data = await res.json()
		if data['Messages'][0]['Status'] != 'success':
			request.app.ctx.registrants.remove(email)
			return sanic.response.json(
				{'success': False, 'error': 'Failed to send verification email. Please try again later.'})

	del verification

	await request.app.ctx.db['hashes'].insert_one({'email': email, 'hash': pwd_hash})
	del pwd_hash
	await request.app.ctx.db['user_data'].insert_one(
		{'email': email, 'name': request.form['name'][0], 'verified': False, 'admin': False})
	request.app.ctx.registrants.remove(email)
	return sanic.response.json({'success': True})


@app.get('/verify/<verification:str>')
async def verify(request, verification: str):
	record = await request.app.ctx.db['unverified'].find_one_and_delete({'verification': verification})
	if not record:
		return sanic.response.html('<p>Unknown or already verified account</p>', status=400)
	await request.app.ctx.db['user_data'].update_one({'email': record['email']}, {'$set': {'verified': True}})
	return sanic.response.redirect('/login')


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
	res.cookies['session_token']['max-age'] = 60 * 60
	res.cookies['session_token']['secure'] = True
	res.cookies['session_token']['httponly'] = True
	res.cookies['session_token']['domain'] = request.app.ctx.domain
	return res


@app.get('/logout')
async def logout(request):
	res = sanic.response.redirect('/login')
	if 'session_token' in request.cookies:
		await request.app.ctx.db['sessions'].delete_one({'token': request.cookies['session_token']})
		del res.cookies['session_token']
	return res


app.run(host='0.0.0.0', port=443, ssl=os.getenv('CERT_DIR'))
