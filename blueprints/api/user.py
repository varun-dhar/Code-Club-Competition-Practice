import sanic
import statistics
import aiofiles

bp = sanic.Blueprint('user-api')


@bp.post('/levels/<level:int>')
async def run_test(request, level: int):
	if not request.form or 'lang' not in request.form or not request.files or 'file' not in request.files:
		return sanic.response.text('Missing fields', status=400)
	if (level_info := await request.app.ctx.db['levels'].find_one({'level': level})) is None:
		return sanic.response.text('No such level', status=400)

	lang = request.form['lang'][0]
	if (lang_id := request.app.ctx.langs.get(lang)) is None:
		return sanic.response.text('Invalid language', status=400)

	email = request.ctx.session_record['email']

	try:
		file = request.files['file'][0].body.decode('utf-8')
	except UnicodeDecodeError:
		return sanic.response.text('Invalid file', status=400)

	exec_times = []
	for i in range(1, level_info['n_tests'] + 1):
		async with aiofiles.open(f'levels/{level}/{i}.in', 'r') as f:
			test_input = await f.read()
		async with request.app.ctx.session.post(
				f'https://godbolt.org/api/compiler/{lang_id}/compile',
				json={'source': file, 'options': {
					'userArguments': request.app.ctx.compile_args.get(lang, ''),
					'executeParameters': {
						'stdin': test_input}, 'compilerOptions': {'executorRequest': True},
					'filters': {'execute': True}}},
				headers={'Accept': 'application/json'}) as res:
			result = await res.json()
		if result['buildResult']['code'] != 0:
			return sanic.response.text('\n'.join(map(lambda x: x['text'], result['stderr'])), status=400)

		output = '\n'.join(map(lambda x: x['text'], result['stdout'])).strip()
		async with aiofiles.open(f'levels/{level}/{i}.out', 'r') as f:
			ans = (await f.read()).strip()
		if output != ans:
			return sanic.response.text('Test failed', status=400)
		exec_times.append(int(result['execTime']))

	mean = statistics.mean(exec_times)
	median = statistics.median(exec_times)
	rank_data = await request.app.ctx.db['leaderboard'].find_one({'email': email, 'level': level})
	if not rank_data or rank_data['mean'] > mean or rank_data['median'] > median:
		await request.app.ctx.db['leaderboard'].update_one({'email': email, 'level': level},
														   [{'$set': {'median': median, 'mean': mean, 'code': file}}],
														   upsert=True)
	return sanic.response.empty()
