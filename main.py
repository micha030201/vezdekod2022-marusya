import logging
from typing import Union, Dict, Any, List

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
    payload: Dict[Any, Any]
    nlu: Nlu


class Item(BaseModel):
    meta: Dict[Any, Any]
    request: Request
    session: Dict[Any, Any]
    version: str


app = FastAPI()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(str(exc))
    return PlainTextResponse('', status_code=400)


@app.post('/marusya')
async def read_root(req: Item):
    tokens = req.request.nlu.tokens
    if 'soft squad' in req.request.command and 'вездекод' in tokens:
        resp = 'Привет вездекодерам!'
    else:
        resp = 'Фу, уходи.'

    return {
        'response': {
            'text': resp,
            'end_session': False
        },
        'session': req.session,
        'version': req.version,
    }
