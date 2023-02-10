import asyncio
from typing import Union

import aiohttp
import sanic
import statistics
import aiofiles

bp = sanic.Blueprint('user-api')


async def test_solution(session: aiohttp.ClientSession, level: int, test_no: int, lang_id: str, code: str,
						compile_args: str) -> tuple[bool, Union[str, int]]:
	async with aiofiles.open(f'levels/{level}/{test_no}.in', 'r') as f:
		test_input = await f.read()
	async with session.post(
			f'https://godbolt.org/api/compiler/{lang_id}/compile',
			json={'source': code, 'options': {
				'userArguments': compile_args,
				'executeParameters': {
					'stdin': test_input}, 'compilerOptions': {'executorRequest': True},
				'filters': {'execute': True}}},
			headers={'Accept': 'application/json'}) as res:
		result = await res.json()
	if result['buildResult']['code'] != 0:
		return False, '\n'.join(map(lambda x: x['text'], result['stderr']))

	output = '\n'.join(map(lambda x: x['text'], result['stdout'])).strip()
	async with aiofiles.open(f'levels/{level}/{test_no}.out', 'r') as f:
		ans = (await f.read()).strip()
	if output != ans:
		return False, 'Test failed.'

	return True, int(result['execTime'])


@bp.post('/levels/<level:int>')
async def run_test(request: sanic.Request, level: int):
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

	compile_args = request.app.ctx.compile_args.get(lang, '')

	exec_times = []
	results = [asyncio.create_task(test_solution(request.app.ctx.session, level, i, lang_id, file, compile_args)) for i in
			   range(1, level_info['n_tests'] + 1)]
	for coro in asyncio.as_completed(results):
		success, output = await coro
		if success:
			exec_times.append(output)
		else:
			for closed_coro in results:
				closed_coro.cancel()
			return sanic.response.text(output, status=400)

	mean = statistics.mean(exec_times)
	median = statistics.median(exec_times)
	rank_data = await request.app.ctx.db['leaderboard'].find_one({'email': email, 'level': level})
	if not rank_data or rank_data['mean'] > mean or rank_data['median'] > median:
		await request.app.ctx.db['leaderboard'].update_one({'email': email, 'level': level},
														   [{'$set': {'median': median, 'mean': mean, 'code': file}}],
														   upsert=True)
	return sanic.response.empty()
