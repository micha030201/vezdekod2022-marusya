import logging
from typing import Dict, Any, List

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel


logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)


class Nlu(BaseModel):
    tokens: List[str]


class Request(BaseModel):
    command: str
    original_utterance: str
    type: str
    #payload: Dict[Any, Any]
    nlu: Nlu


class Session(BaseModel):
    session_id: str
    user_id: str
    skill_id: str
    new: bool
    message_id: int


class Item(BaseModel):
    meta: Dict[Any, Any]
    request: Request
    session: Session
    version: str


###

def is_similar(cls, a, b):
    def collate(s):
        return cls._collate.get(s, s)
    return collate(a.casefold()) == collate(b.casefold())


class StateMachine:
    _collate = {}

    @classmethod
    def similar(cls, best, good):
        for alias in good:
            cls._collate[alias] = best

    def input(match_spec=None):
        def matches(cls, request: Request):
            if match_spec is None:
                return True
            elif isinstance(match_spec, list):
                return len(match_spec) == len(request.nlu.tokens) and all(
                    is_similar(cls, a, b)
                    for a, b in zip(match_spec, request.nlu.tokens)
                )
            elif isinstance(match_spec, str):
                return is_similar(cls, match_spec, request.command)
            elif isinstance(match_spec, set):
                return all(
                    any(
                        is_similar(cls, required, present)
                        for present in request.nlu.tokens)
                    for required in match_spec
                )

        def decorator(func):
            if not hasattr(func, '_matches'):
                func._matches = []
            func._matches.append(matches)
            return func

        return decorator

    def need_state(*state):
        def decorator(func):
            func._need_state = state
            return func

        return decorator

    def parse(self, request: Request):
        for name, method in type(self).__dict__.items():
            if (
                    hasattr(method, '_matches')
                    and any(
                        matches(type(self), request)
                        for matches in method._matches)
                    and ((not hasattr(method, '_need_state'))
                        or self.state in method._need_state)):
                return method(self)

    def __init__(self):
        self.state = None


class Greeter(StateMachine):
    @StateMachine.input(['soft', 'squad', 'вездеход'])
    def greet_good(self):
        return 'Привет вездекодерам!'

    @StateMachine.input()
    def greet_bad(self):
        return 'Фу, уходи.'


app = FastAPI()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(str(exc))
    return PlainTextResponse('', status_code=400)


@app.post('/marusya')
async def read_root(req: Item):
    sm = Greeter()
    resp = sm.parse(req.request)

    return {
        'response': {
            'text': resp,
            'end_session': False
        },
        'session': req.session,
        'version': req.version,
    }
