import sanic
import bisect

bp = sanic.Blueprint('misc')
bp.static('/assets/styles/index.css', 'assets/styles/index.css', name='index-css')
bp.static('/assets/styles/level.css', 'assets/styles/level.css', name='level-css')
bp.static('/assets/styles/leaderboard.css', 'assets/styles/leaderboard.css', name='leaderboard-css')
bp.static('/assets/scripts/level.js', 'assets/scripts/level.js', name='level-js')
bp.static('/assets/images/check.svg', 'assets/images/check.svg', name='check-svg')
bp.static('/assets/images/x.svg', 'assets/images/x.svg', name='x-svg')


@bp.get('/')
async def home(request):
	template = request.app.ctx.environment.get_template('index.html')
	email = request.ctx.session_record['email']
	user_data = await request.app.ctx.db['user_data'].find_one({'email': email})
	name = user_data['name']
	solved = {record['level']: record['median'] async for record in
			  request.app.ctx.db['leaderboard'].find({'email': email}).sort('level', 1)}
	levels = []
	async for level in request.app.ctx.db['levels'].find().sort('level', 1):
		rank = 0
		if level['level'] in solved:
			ranks = [record async for record in
					 request.app.ctx.db['leaderboard'].find({'level': level['level']}).sort('median')]
			rank = bisect.bisect_left(ranks, solved[level['level']], key=lambda x: x['median'])
			while ranks[rank]['email'] != email and rank < len(ranks):
				rank += 1
			rank += 1
		levels.append({'name': level['level'], 'desc': level['desc'], 'rank': rank})
	return sanic.response.html(await template.render_async(
		levels=levels, name=name))


@bp.get('/levels/<level:int>')
async def level_pg(request, level: int):
	record = await request.app.ctx.db['levels'].find_one({'level': level})
	if not record:
		return sanic.response.empty(status=404)
	email = request.ctx.session_record['email']
	user_data = await request.app.ctx.db['user_data'].find_one({'email': email})
	name = user_data['name']
	template = request.app.ctx.environment.get_template('level.html')
	return sanic.response.html(
		await template.render_async(langs=request.app.ctx.langs.keys(), level=level, desc=record['desc'], name=name))


@bp.get('/leaderboards/<level:int>')
async def leaderboard_pg(request, level: int):
	if not (await request.app.ctx.db['levels'].find_one({'level': level})):
		return sanic.response.empty(status=404)
	entries = []
	async for record in request.app.ctx.db['leaderboard'].find({'level': level}).sort('median'):
		user_data = await request.app.ctx.db['user_data'].find_one({'email': record['email']})
		entries.append({'name': user_data['name'], 'mean': record['mean'], 'median': record['median']})

	email = request.ctx.session_record['email']
	user_data = await request.app.ctx.db['user_data'].find_one({'email': email})
	name = user_data['name']

	template = request.app.ctx.environment.get_template('leaderboard.html')
	return sanic.response.html(await template.render_async(level=level, entries=entries, name=name))
