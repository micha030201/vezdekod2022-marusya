import re
import random
import logging
from typing import Dict, Any, List
from collections import defaultdict

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

class Response:
    def __init__(self, text, tts, buttons=[], image=None):
        self.text = text
        self.tts = to_tts(tts)
        self.buttons = buttons
        self.image = image

    def json(self):
        ret = {
            'text': self.text,
            'tts': self.tts,
            'buttons': [{'title': b} for b in self.buttons],
            'end_session': False,
        }
        if self.image is not None:
            ret['card'] = {
                'type': 'BigImage',
                'image_id': self.image
            }
        return ret


def to_tts(s):
    return re.sub('{.+?}{(.+?)}', r'\1', s)


class EndSession(Exception):
    pass


def is_similar(cls, a, b):
    def collate(s):
        return cls._collate.get(s, s)
    return collate(a.casefold()) == collate(b.casefold())


class StateMachine:
    _collate = {}
    _inhabited_by = None

    similar = {}

    def __init_subclass__(cls, /, **kwargs):
        super().__init_subclass__(**kwargs)
        for best, good in cls.similar.items():
            for alias in good:
                cls._collate[alias] = best

    def input(match_spec=None):
        def matches(cls, request: Request):
            #print(match_spec)
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
        if self._inhabited_by is not None:
            try:
                return self._inhabited_by.parse(request)
            except EndSession as e:
                self._inhabited_by = None
                return str(e)
        logger.info(f'dispatching request {request}')
        for name, method in type(self).__dict__.items():
            if hasattr(method, '_matches'):
                logger.info(f'testing method {name}')
                if any(matches(type(self), request)
                       for matches in method._matches):
                    logger.info('input matches')
                    if ((not hasattr(method, '_need_state'))
                            or self.state in method._need_state):
                        logger.info('state correct. matched.')
                    else:
                        logger.info('state incorrect')
                else:
                    logger.info("input doesn't match")
            if (
                    hasattr(method, '_matches')
                    and any(
                        matches(type(self), request)
                        for matches in method._matches)
                    and ((not hasattr(method, '_need_state'))
                         or self.state in method._need_state)):
                return method(self)
        return 'Команда не распознана'

    def inhabit(self, state_machine):
        assert self._inhabited_by is None
        self._inhabited_by = state_machine

    def __init__(self):
        self.state = None


class Quiz(StateMachine):
    similar = {
        'конец': ['закончить', 'завершить', 'пока']
    }

    def __init__(self):
        self.recs = ['Дизайн']

    @StateMachine.input('начать')
    def start(self):
        self.state = 0
        return ('Если Вы хотите выйти из опроса до окончания,'
                ' напишите "конец". Первый вопрос: что такое {middleware}{мидл вэйр}??'), [
            'сорт яблок',
            'линия в доте',
            'промежуточная функция между запросом и ответом'
        ]

    @StateMachine.input('конец')
    def end(self):
        raise EndSession('ну пока')

    @StateMachine.input('SEAWAYS')
    @StateMachine.need_state(7)
    def correct(self):
        self.recs.append(rec)
        raise EndSession('Правильно!! Опрос закончен. Рекомендуем'
                         f' Вам категорию {random.choice(self.recs)}.')

    @StateMachine.input()
    @StateMachine.need_state(7)
    def incorrect(self):
        raise EndSession('А вот и нет. Опрос закончен. Рекомендуем'
                         f' Вам категорию {random.choice(self.recs)}.')


_quiz_data = [
    (
        'промежуточная функция между запросом и ответом',
        'Веб-разработка, особенно бэкэнд',
        'что такое cv2',
        [
            'резюме второй версии',
            'фреймворк для разработки игр',
            'библиотека для компьютерного зрения'
        ]),
    (
        'библиотека для компьютерного зрения',
        'Компьютерное зрение',
        'что такое {CORS}{корс}',
        [
            'курс типа как в универе',
            'cars может',
            'Cross-Origin Resource Sharing'
        ]),
    (
        'Cross-Origin Resource Sharing',
        'Web',
        'что такое android',
        [
            'роботы такие типа',
            'iphone',
            'операционная система',
        ]),
    (
        'операционная система',
        'Мобильная разработка',
        'что такое feature',
        [
            'ну типа не баг а фича',
            'всё-таки баг',
            'какой-то атрибут объекта',
        ]),
    (
        'какой-то атрибут объекта',
        'Анализ данных',
        'что такое седловая ^точка^',
        [
            'ну типа садиться на неё',
            'не знаю',
            'стационарная точка но не экстремум',
        ]),
    (
        'стационарная точка но не экстремум',
        'Оптимизация',
        'кто такая Маруся',
        [
            'моя еот',
            'машина такая',
            'бот',
        ]),
    (
        'бот',
        'Маруся',
        '^какой^ читкод в {GTA Vice City}{гэ тэ ^а^ вайс сити} позволяет ездить по воде',
        [
            'HESOYAM',
            'ASPIRINE',
            'SEAWAYS'
        ])
]

for i, (answer, rec, next_question, next_options) in enumerate(_quiz_data):
    @StateMachine.input(answer)
    @StateMachine.need_state(i)
    def correct(self, i=i, rec=rec, next_question=next_question, next_options=next_options):
        self.recs.append(rec)
        self.state = i + 1
        return Response(
            text=f'Правильно!! Следующий вопрос: {next_question}??',
            tts=f'Правильно!! <speaker audio=marusia-sounds/game-win-1> Следующий вопрос: {to_tts(next_question)}??',
            buttons=next_options
        )

    setattr(Quiz, f'correct{i}', correct)

    @StateMachine.input()
    @StateMachine.need_state(i)
    def incorrect(self, i=i, rec=rec, next_question=next_question, next_options=next_options):
        self.state = i + 1
        return Response(
            text=f'А вот и нет. Следующий вопрос: {next_question}??',
            tts=f'А вот и нет. <speaker audio=marusia-sounds/game-loss-2> Следующий вопрос: {to_tts(next_question)}??',
            buttons=next_options
        )

    setattr(Quiz, f'incorrect{i}', incorrect)


class Greeter(StateMachine):
    similar = {
        'опрос': ['тест', 'вопрос'],
        'вездекод': ['вездеход', 'бездикод'],
        'код': ['кот'],
        'squad': ['сквад', 'scott']
    }

    @StateMachine.input(['совсквот', 'вездеход'])
    @StateMachine.input(['совсквот', 'везде', 'код'])
    @StateMachine.input(['soft', 'squad', 'вездеход'])
    @StateMachine.input(['soft', 'squad', 'везде', 'кот'])
    def greet_good(self):
        return Response(
            text='Привет вездекодерам!',
            tts='Привет вездек+одерам! <speaker audio=marusia-sounds/game-powerup-1>',
            image=457239017
        )

    @StateMachine.input(['начать', 'опрос'])
    @StateMachine.input({'опрос'})
    def start_quiz(self):
        quiz = Quiz()
        self.inhabit(quiz)
        return quiz.start()

    @StateMachine.input()
    @StateMachine.need_state('help_seen')
    def greet_bad(self):
        return 'Фу, уходи.'

    @StateMachine.input()
    def greet(self):
        self.state = 'help_seen'
        return Response(
            text='Привет!!!!! Мы команда SOFT SQUAD!!!!!!!!!'
                 ' Напиши SOFT SQUAD вездекод чтобы поздороваться с нами!!!!'
                 ' Или напиши "опрос" чтобы пройти опрос',
            tts='Привет!! Мы команда SOFT SQUAD!!'
                ' <speaker audio=marusia-sounds/things-sword-1> '
                ' <speaker audio=marusia-sounds/things-gun-1> '
                ' Напиши SOFT SQUAD вездекод чтобы поздороваться с нами!!!!'
                ' Или напиши "опрос" чтобы пройти опрос',
        )


statemachines = defaultdict(Greeter)


app = FastAPI()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(str(exc))
    return PlainTextResponse('', status_code=400)

@app.post('/marusya')
async def read_root(req: Item):
    resp = statemachines[req.session.session_id].parse(req.request)

    if isinstance(resp, Response):
        resp = resp.json()
    elif isinstance(resp, str):
        resp = {
            'text': resp,
            'end_session': False,
        }
    else:
        text, buttons = resp
        resp = {
            'text': text,
            'buttons': [{'title': b} for b in buttons],
            'end_session': False,
        }

    return {
        'response': resp,
        'session': req.session,
        'version': req.version,
    }
