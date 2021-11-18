import sanic,sanic.response
import os
import sys
import resource
import prctl
import signal
import tempfile
import asyncio
import aiofiles
import pwd

uid = pwd.getpwnam('jrunner')[2]
os.setreuid(uid,uid)

async def check_test(ctx):
	pid,_ = os.waitpid(-1,os.WNOHANG)
	if pid != 0:
		rdata = ctx.procinfo[pid]
		async with aiofiles.open(f"{rdata['level']}{rdata['test_no']}a",'r') as f:
			ans = (await f.read()).strip()
		output = os.read(rdata['fd'],len(ans)).decode('utf-8')
		os.close(rdata['fd'])
		ctx.stats[rdata['email']]['levels'][rdata['level']][rdata['test_no']]['success'] = output == ans
		ctx.stats[rdata['email']]['levels'][rdata['level']][rdata['test_no']]['running'] = False
		del ctx.procinfo[pid]
		ctx.proc_count -= 1

	if ctx.proc_count > 0:
		loop = asyncio.get_event_loop()
		loop.call_later(0.1,loop.create_task,check_test(ctx))

async def run_check(ctx):
	if ctx.proc_count == 0:
		ctx.proc_count += 1
		await check_test(ctx)
		return
	ctx.proc_count += 1

app = sanic.Sanic('runner')
with open('index.html') as f:
	app.ctx.home = f.read()

app.ctx.stats = {}
app.ctx.procinfo = {}
app.ctx.N_TESTS = app.ctx.N_LEVELS = 10
app.ctx.proc_count = 0

@app.get('/')
async def home(request):
	return sanic.response.html(request.app.ctx.home)

@app.post('/test')
async def run_test(request):
	if not request.form or not request.files or any(i not in request.form for i in ('email','level')) or (level:=int(request.form['level'][0])) not in range(request.app.ctx.N_LEVELS+1):
		return sanic.response.json({'success':False,'error':'invalid form'},status=400)

	email = request.form['email'][0]
	file = request.files['file'][0].body.decode('utf-8')
	filename = request.files['file'][0].name

	for i in range(request.app.ctx.N_TESTS):
		pgm_dir = tempfile.TemporaryDirectory()
		async with aiofiles.open((pgm_file:=f'{pgm_dir.name}/{filename}'),'w') as f:
			await f.write(file)
		pipefds = os.pipe()
		pid = os.fork()
		if pid == 0:
			os.close(pipefds[0])
			test_file = os.open(f"{level}{i}",os.O_RDONLY)
			# attach input data to stdin, attach stdout to pipe
			os.dup2(test_file,sys.stdin.fileno())
			os.dup2(pipefds[1],sys.stdout.fileno())
			resource.setrlimit(resource.RLIMIT_CORE,(0,0))
			# no creating/accessing files/sockets
			resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
			resource.setrlimit(resource.RLIMIT_NOFILE,(8,8))
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
	return sanic.response.json({'success':True,'tests_passed':sum(request.app.ctx.stats[email]['levels'][level][i]['success'] for i in range(request.app.ctx.N_TESTS))})

app.run(host='0.0.0.0',port=8080)
