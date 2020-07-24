"""
Examples of usages.
"""
from trinket import Trinket, Response
from trinket.response import file_iterator
from trinket.extensions import logger
from trinket.http import HTTPError


class MyTrinket(Trinket):

    async def on_error(self, http_code, message):
        if http_code == 404:
            message = "This route does not exist, i'm so sorry."
        return await super().on_error(http_code, message)


bauble = logger(MyTrinket())


@bauble.route('/')
async def hello(request):
    return Response.raw(b'Hello World !')


@bauble.route('/raw', methods=['POST'])
async def raw(request):
    return Response.raw(b'You got here')


@bauble.route('/read', methods=['POST'])
async def feed(request):
    await request.parse_body()
    files = list(request.files.keys())
    return Response.raw("You got here and it's all read: {}".format(files))


@bauble.route('/ignore', methods=['POST'])
async def ignore(request):
    # A post where we ignore the body
    return Response.raw("You got here and all was ignored.")


@bauble.route('/hello/full/with/{one}/and/{two}')
async def json(request, one, two):
    response = Response.json({
        'parameters': f'{one} and {two}',
        'query': request.query.get('query'),
        'cookie': request.cookies['test'],
    })
    response.cookies.set(name='bench', value='value')
    return response


@bauble.route('/websocket')
async def serve_websocket(request):
    return Response.streamer(
        file_iterator('websocket.html'),
        content_type="text/html")


@bauble.websocket('/chat')
async def chat(request, websocket):
    async for msg in websocket:
        for ws in bauble.websockets:
            if ws is not websocket:
                await ws.send(msg)

bauble.start()
