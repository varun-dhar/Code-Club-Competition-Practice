import os
import pathlib
import re

import aiohttp
import dotenv
import jinja2
import motor.motor_asyncio
import sanic

import blueprints

'''
TODO
- steal challenges from leetcode and usaco
- make this look better
'''

dotenv.load_dotenv()

app = sanic.Sanic('Practicode')
app.blueprint(blueprints.blueprints)

app.ctx.smtp_sender = os.getenv('SENDER_EMAIL')
app.ctx.mailjet_user = os.getenv('MAILJET_USERNAME')
app.ctx.mailjet_pass = os.getenv('MAILJET_PASSWORD')

app.ctx.domain = os.getenv('DOMAIN')

app.ctx.email_re = re.compile(
	'(?:[a-z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&\'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])')
app.ctx.pass_re = re.compile("^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,100}$")

app.ctx.langs = {'Java': 'java1800', 'C++': 'gsnapshot', 'C': 'cgsnapshot', 'Python3': 'python310', 'Go': 'gltip',
				 'Kotlin': 'kotlinc1700', 'Ruby': 'ruby302', 'Rust': 'nightly', 'TypeScript': 'tsc_0_0_20_gc'}
app.ctx.compile_args = {'C++': '-O3', 'C': '-O3', 'Kotlin': '-opt', 'Rust': '-C opt-level=3'}


@app.before_server_start
async def before_start(srv: sanic.Sanic, loop):
	pathlib.Path('levels').mkdir(exist_ok=True)
	srv.ctx.db_client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv('MONGODB_URL'), tls=True,
															   tlsCertificateKeyFile=os.getenv('MONGODB_CERT'),
															   io_loop=loop)
	srv.ctx.db = srv.ctx.db_client['data']
	await srv.ctx.db['sessions'].create_index('last_login', expireAfterSeconds=60 * 60)
	await srv.ctx.db['user_data'].create_index('email', unique=True)
	await srv.ctx.db['hashes'].create_index('email', unique=True)
	srv.ctx.session = aiohttp.ClientSession(loop=loop)
	srv.ctx.environment = jinja2.Environment(loader=jinja2.FileSystemLoader('templates/'), enable_async=True,
											 autoescape=True)


app.run()
