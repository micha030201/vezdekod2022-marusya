from typing import Union, Dict, Any

from fastapi import FastAPI
from pydantic import BaseModel


class Item(BaseModel):
    meta: Dict[Any, Any]
    request: Dict[Any, Any]
    session: Dict[Any, Any]
    version: str


app = FastAPI()


@app.post('/')
async def read_root(req: Item):
    return {
        'response': {
            'text': 'sdfhsfjsrgm',
            'end_session': False
        },
        'session': req.session,
        'version': req.version,
    }
