import sanic
import secrets
import asyncio
import concurrent.futures
import argon2
import aiohttp

bp = sanic.Blueprint('account-public')
bp.static('/register', 'html/register.html')
bp.static('/login', 'html/login.html')


@bp.post('/register')
async def register(request):
	if not request.form or any(
			field not in request.form for field in ('name', 'email', 'password', 'confirm_password')):
		return sanic.response.text('Missing fields', status=400)

	if not request.app.ctx.email_re.match(request.form['email'][0]):
		return sanic.response.text('Invalid email', status=400)

	if not request.app.ctx.pass_re.match(request.form['password'][0]):
		return sanic.response.text('Password does not meet requirements', status=400)

	if not request.form['password'][0] != request.form['confirm_password'][0]:
		return sanic.response.text('Passwords do not match', status=400)

	del request.form['confirm_password'][0]

	email = request.form['email'][0]

	verification = secrets.token_urlsafe(16)
	if await request.app.ctx.db['user_data'].find_one({'email': email}) or (
			await request.app.ctx.db['unverified'].update_one({'email': email},
															  {'$setOnInsert': {'email': email,
																				'verification': verification}},
															  upsert=True)).matched_count >= 1:
		return sanic.response.text('account exists', status=400)

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
			return sanic.response.text('Failed to send verification email. Please try again later.', status=503)

	del verification

	await request.app.ctx.db['hashes'].insert_one({'email': email, 'hash': pwd_hash})
	del pwd_hash
	await request.app.ctx.db['user_data'].insert_one(
		{'email': email, 'name': request.form['name'][0], 'verified': False, 'admin': False})
	return sanic.response.empty()


@bp.get('/verify/<verification:str>')
async def verify(request, verification: str):
	record = await request.app.ctx.db['unverified'].find_one_and_delete({'verification': verification})
	template = request.app.ctx.environment.get_template('verify.html')
	if not record:
		return sanic.response.html((await template.render_async(message='Unknown or already verified account')),
								   status=400)
	await request.app.ctx.db['user_data'].update_one({'email': record['email']}, {'$set': {'verified': True}})
	return sanic.response.html(await template.render_async(message='Successfully verified'))


@bp.post('/login')
async def login(request):
	if not request.form or any(i not in request.form for i in ('email', 'password')):
		return sanic.response.text('missing fields', status=400)

	email = request.form['email'][0]

	record = await request.app.ctx.db['hashes'].find_one({'email': email})
	if not record:
		return sanic.response.text('invalid email/password', status=400)

	user_data = await request.app.ctx.db['user_data'].find_one({'email': email})
	if not user_data or not user_data['verified']:
		return sanic.response.text('unverified account', status=400)

	loop = asyncio.get_event_loop()
	with concurrent.futures.ThreadPoolExecutor() as pool:
		hasher = argon2.PasswordHasher()
		try:
			await loop.run_in_executor(pool, hasher.verify, record['hash'], request.form['password'][0])
		except argon2.exceptions.VerifyMismatchError:
			return sanic.response.text('invalid email/password', status=400)
		finally:
			del request.form['password'][0]
			del record

	token = secrets.token_urlsafe(16)
	await request.app.ctx.db['sessions'].insert_one({'email': email, 'token': token})
	res = sanic.response.empty()
	res.cookies['session_token'] = token
	res.cookies['session_token']['secure'] = True
	res.cookies['session_token']['httponly'] = True
	res.cookies['session_token']['samesite'] = 'Strict'
	return res
