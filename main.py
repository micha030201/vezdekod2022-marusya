from typing import Union

from fastapi import FastAPI
from pydantic import BaseModel


class Item(BaseModel):
    meta: str
    request: str
    session: str
    verson: str


app = FastAPI()


@app.post('/')
async def read_root(req: Item):
    return {
        'response': {
            'text': 'sdfhsfjsrgm'
        },
        'session': req.session,
        'version': req.version,
    }
