import sanic,sanic.response
import os
import sys
import resource
import prctl
import signal
import tempfile
import asyncio
import aiofiles
#import pwd
#import dotenv
import motor.motor_asyncio
import argon2
import secrets
import concurrent.futures
import aiosmtplib
import re

'''
TODO
- steal challenges from leetcode and usaco
- make this look better
'''

#uid = pwd.getpwnam('jrunner')[2]
#os.setreuid(uid,uid)

app = sanic.Sanic('runner')

#app.static('/','index.html')
app.static('/login','login.html')
#app.static('/register','register.html')

app.ctx.stats = {}
app.ctx.procinfo = {}
app.ctx.N_TESTS = app.ctx.N_LEVELS = 10

#dotenv.load_dotenv()

@app.before_server_start
async def before_start(app,loop):
	app.ctx.db_client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv('MONGODB_URL'),tls=True,tlsCertificateKeyFile=os.getenv('MONGODB_CERT'),io_loop=loop)
	app.ctx.db = app.ctx.db_client['users']
	app.ctx.smtp = aiosmtplib.SMTP(os.getenv('MAILJET_SRV'),os.getenv('MAILJET_PORT'))
	await app.ctx.smtp.connect()
	await app.ctx.smtp.starttls()
	await app.ctx.smtp.login(os.getenv('MAILJET_USERNAME'),os.getenv('MAILJET_PASSWORD'))

app.ctx.smtp_sender = os.getenv('SENDER_EMAIL')

app.ctx.domain = os.getenv('DOMAIN')

app.ctx.email_re = re.compile('(?:[a-z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&\'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])')
app.ctx.pass_re = re.compile("^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,100}$")

@app.get('/')
async def home(request):
	if 'session_token' not in request.cookies:
		return sanic.response.redirect('/login')

	if not (await request.app.ctx.db['sessions'].find_one({'token':request.cookies['session_token']})):
		res = sanic.response.redirect('/login')
		del res.cookies['session_token']
		return res
	return await sanic.response.file('index.html')

async def check_test(ctx):
	pid,_ = os.waitpid(-1,os.WNOHANG)
	if pid != 0:
		rdata = ctx.procinfo[pid]
		async with aiofiles.open(f"tests/{rdata['level']}/{rdata['test_no']}a",'r') as f:
			ans = (await f.read()).strip()
		output = os.read(rdata['fd'],len(ans)).decode('utf-8')
		os.close(rdata['fd'])
		ctx.stats[rdata['email']]['levels'][rdata['level']][rdata['test_no']]['success'] = output == ans
		ctx.stats[rdata['email']]['levels'][rdata['level']][rdata['test_no']]['running'] = False
		del ctx.procinfo[pid]

	if len(ctx.procinfo) > 0:
		loop = asyncio.get_event_loop()
		loop.call_later(0.1,loop.create_task,check_test(ctx))

async def run_check(ctx):
	if len(ctx.procinfo) == 1:
		await check_test(ctx)

@app.post('/test')
async def run_test(request):
	if not request.form or not request.files or 'level' not in request.form or not (level:=request.form['level'][0]).isdigit() or (level:=int(level)) not in range(1,request.app.ctx.N_LEVELS+1) or not request.files['file'][0].name.endswith('.java') or len(request.files['file'][0].body) > 100*1000:
		return sanic.response.json({'success':False,'error':'invalid form'},status=400)

	if 'session_token' not in request.cookies:
		return sanic.response.redirect('/login')

	record = await request.app.ctx.db['sessions'].find_one({'token':request.cookies['session_token']})
	if not record:
		res = sanic.response.redirect('/login')
		del res.cookies['session_token']
		return res

	email = record['email']

	file = request.files['file'][0].body.decode('utf-8')
	filename = request.files['file'][0].name

	for i in range(request.app.ctx.N_TESTS):
		pgm_dir = tempfile.TemporaryDirectory()
		async with aiofiles.open((pgm_file:=f'{pgm_dir.name}/{filename}'),'w') as f:
			await f.write(file)
		pipefds = os.pipe()
		pid = os.fork()
		if pid == 0:
			os.close(sys.stderr.fileno())
			os.close(pipefds[0])
			test_file = os.open(f"tests/{level}/{i}",os.O_RDONLY)
			# attach input data to stdin, attach stdout to pipe
			os.dup2(test_file,sys.stdin.fileno())
			os.dup2(pipefds[1],sys.stdout.fileno())
			resource.setrlimit(resource.RLIMIT_CORE,(0,0))
			# no creating/accessing files/sockets
			resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
			resource.setrlimit(resource.RLIMIT_NOFILE,(7,7))
			# limit memory to 1350MB
			resource.setrlimit(resource.RLIMIT_AS,(int(1350*1e6),)*2)
			# 5 seconds of CPU time
			resource.setrlimit(resource.RLIMIT_CPU,(5,5))
			# reap children if srv dies
			prctl.set_pdeathsig(signal.SIGKILL)
			os.execlp('java','java','-Xmx100m','-XX:MaxMetaspaceSize=100m',pgm_file)

		os.close(pipefds[1])

		if email in request.app.ctx.stats and request.app.ctx.stats[email]['levels'][level][i]['running']:
			os.kill(request.app.ctx.stats[email]['levels'][level][i]['pid'],signal.SIGKILL)
		elif email not in request.app.ctx.stats:
			request.app.ctx.stats[email] = {'levels':[[{'running':False}]*request.app.ctx.N_TESTS]*request.app.ctx.N_LEVELS}
		request.app.ctx.stats[email]['levels'][level][i] = {'pid':pid,'running':True,'success':False}
		request.app.ctx.procinfo[pid] = {'email':email,'level':level,'test_no':i,'fd':pipefds[0],'file':pgm_dir}
		await run_check(request.app.ctx)

	while any(request.app.ctx.stats[email]['levels'][level][i]['running'] for i in range(request.app.ctx.N_TESTS)):
		await asyncio.sleep(0.1)

	n_tests = sum(request.app.ctx.stats[email]['levels'][level][i]['success'] for i in range(request.app.ctx.N_TESTS))
	await request.app.ctx.db['user_data'].update_one({'email':email},[{'$set':{'levels':{str(level):n_tests == request.app.ctx.N_TESTS}}}])
	return sanic.response.json({'success':True,'tests_passed':n_tests})

@app.get('/register')
async def register_pg(request):
	if 'session_token' in request.cookies and (await request.app.ctx.db['sessions'].find_one({'token':request.cookies['session_token']})):
		return sanic.response.redirect('/')
	res = await sanic.response.file('register.html')
	if 'session_token' in request.cookies:
		del res.cookies['session_token']
	return res

@app.post('/register')
async def register(request):
	if not request.form or any(i not in request.form for i in ('name','email','password')) or not request.app.ctx.email_re.match(request.form['email'][0]) or not request.app.ctx.pass_re.match(request.form['password'][0]):
		return sanic.response.json({'success':False,'error':'invalid form'},status=400)

	email = request.form['email'][0]

	if (await request.app.ctx.db['user_data'].find_one({'email':email})):
		return sanic.response.json({'success':False,'error':'account exists'},status=400)

	loop = asyncio.get_event_loop()
	with concurrent.futures.ThreadPoolExecutor() as pool:
		hasher = argon2.PasswordHasher()
		pwd_hash = await loop.run_in_executor(pool,hasher.hash,request.form['password'][0])
		del request.form['password'][0]

	verification = secrets.token_urlsafe(16)
	await request.app.ctx.smtp.sendmail(request.app.ctx.smtp_sender,email,f'Subject: Verify your HOC Code Competition Account\n\nVerify your email at https://{request.app.ctx.domain}/verify/{verification}\nYou will not be able to log in or submit entries until your email is verified.\n\nDo not reply to this email; this inbox is not monitored.')
	await request.app.ctx.db['hashes'].insert_one({'email':email,'hash':pwd_hash})
	del pwd_hash
	await request.app.ctx.db['unverified'].insert_one({'email':email,'verification':verification})
	del verification
	await request.app.ctx.db['user_data'].insert_one({'email':email,'name':request.form['name'][0],'verified':False})
	return sanic.response.json({'success':True})

@app.get('/verify/<verification:str>')
async def verify(request,verification: str):
	record = await request.app.ctx.db['unverified'].find_one_and_delete({'verification':verification})
	if not record:
		return sanic.response.html('<p>Unknown or already verified account</p>',status=400)
	await request.app.ctx.db['user_data'].update_one({'email':record['email']},{'$set':{'verified':True}})
	return sanic.response.html('<p>Successfully verified</p><a href="/login">Login</a>')

@app.post('/login')
async def login(request):
	if not request.form or any(i not in request.form for i in ('email','password')):
		return sanic.response.json({'success':False,'error':'invalid form'},status=400)

	email = request.form['email'][0]

	record = await request.app.ctx.db['user_data'].find_one({'email':email})
	if not record or not record['verified']:
		return sanic.response.json({'success':False,'error':'invalid email/password'},status=400)

	record = await request.app.ctx.db['hashes'].find_one({'email':email})

	loop = asyncio.get_event_loop()
	with concurrent.futures.ThreadPoolExecutor() as pool:
		hasher = argon2.PasswordHasher()
		valid = await loop.run_in_executor(pool,hasher.verify,record['hash'],request.form['password'][0])
		del request.form['password'][0]
		del record

	if valid:
		token = secrets.token_urlsafe(16)
		await request.app.ctx.db['sessions'].insert_one({'email':email,'token':token})
		res = sanic.response.redirect('/')
		res.cookies['session_token'] = token
		res.cookies['session_token']['max-age'] = 60*60
		res.cookies['session_token']['secure'] = True
		res.cookies['session_token']['httponly'] = True
#		res.cookies['session_token']['domain'] = request.app.ctx.domain
		return res
	else:
		return sanic.response.json({'success':False,'error':'invalid email/password'},status=400)

@app.get('/logout')
async def logout(request):
	if 'session_token' in request.cookies and request.app.ctx.db['sessions'].find_one_and_delete({'token':request.cookies['session_token']}):
		res = sanic.response.redirect('/login')
		del res.cookies['session_token']
		return res
	return sanic.response.html('<p>Not logged in</p><br><a href="/login">Login</a>')

app.run(host='0.0.0.0',port=8080)
