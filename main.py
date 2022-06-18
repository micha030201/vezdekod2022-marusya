from typing import Union, Dict, Any, List

from fastapi import FastAPI
from pydantic import BaseModel


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
