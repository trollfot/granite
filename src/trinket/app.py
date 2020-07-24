from functools import wraps
from collections import defaultdict

from curio import spawn
from autoroutes import Routes

from trinket.handler import request_handler
from trinket.http import HTTPCode, HTTPStatus, HTTPError
from trinket.lifecycle import handler_events
from trinket.proto import Application
from trinket.request import Request
from trinket.server import Server
from trinket.websockets import Websocket


class Trinket(Application, dict):

    __slots__ = (
        'hooks', 'routes', 'websockets', 'server')

    handle_request = request_handler

    def __init__(self):
        self.routes = Routes()
        self.websockets = set()
        self.hooks = defaultdict(list)

    async def on_error(self, http_code: HTTPCode, message: str=None):
        """This async method allows the customization of errors.
        If you need an async log or report or whatever, this is the
        place to do it.
        """
        raise HTTPError(http_code, message)

    async def lookup(self, request: Request):
        payload, params = self.routes.match(request.path)

        if not payload:
            return await self.on_error(404, request.path)

        # Uppercased in order to only consider HTTP verbs.
        handler = payload.get(request.method.upper(), None)
        if handler is None:
            return await self.on_error(HTTPStatus.METHOD_NOT_ALLOWED)

        # We check if the route is for a websocket handler.
        # If it is, we make sure we were asked for an upgrade.
        if payload.get('websocket', False) and not request.upgrade:
            return await self.on_error(
                HTTPStatus.UPGRADE_REQUIRED,
                'This is a websocket endpoint, please upgrade.')

        return handler, params

    @handler_events
    async def __call__(self, request: Request):
        handler, params = await self.lookup(request)
        return await handler(request, **params)

    def route(self, path: str, methods: list=None, **extras: dict):
        if methods is None:
            methods = ['GET']

        def wrapper(func):
            payload = {method: func for method in methods}
            payload.update(extras)
            self.routes.add(path, **payload)
            return func

        return wrapper

    def websocket(self, path: str, **extras: dict):

        def wrapper(func):
            @wraps(func)
            async def websocket_handler(request, **params):
                websocket = Websocket(request.socket)
                try:
                    await websocket.upgrade(request)
                    self.websockets.add(websocket)
                    task = await spawn(func, request, websocket, **params)
                    await websocket.flow(task)
                finally:
                    self.websockets.discard(websocket)

            payload = {'GET': websocket_handler, 'websocket': True}
            payload.update(extras)
            self.routes.add(path, **payload)
            return func

        return wrapper

    def listen(self, name: str):
        def wrapper(func):
            self.hooks[name].append(func)
        return wrapper

    async def notify(self, name: str, *args, **kwargs):
        if name in self.hooks:
            for hook in self.hooks[name]:
                result = await hook(*args, **kwargs)
                if result is not None:
                    # Allows to shortcut the chain.
                    return result
        return None

    def start(self, host='127.0.0.1', port=5000, debug=True):
        Server.start(self, host, port, debug)
