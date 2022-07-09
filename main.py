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
    message_id: int
    skill_id: str
    #auth_token: str
    #new: bool


class Item(BaseModel):
    meta: Dict[Any, Any]
    request: Request
    session: Session
    version: str


###

class Response:
    def __init__(self, text, tts=None, buttons=[], cards={}):
        self.text = text
        self.tts = to_tts(tts or text)
        self.buttons = buttons
        self.cards = cards

    def json(self):
        ret = {
            'text': self.text,
            'tts': self.tts,
            'end_session': False
        }
        if self.buttons:
            ret['buttons'] = [{'title': b} for b in self.buttons]
        if self.cards:
            ret['commands'] = self.cards
        return ret


def to_tts(s):
    return re.sub('{.*?}{(.*?)}', r'\1', s.replace('`', ''))


class EndSession(Exception):
    def __init__(self, *args, **kwargs):
        self.resp = Response(*args, **kwargs)


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
                return e.resp
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
        state_machine.inhabitor = self
        self._inhabited_by = state_machine

    def __init__(self):
        self.state = None


class Card:
    def __init__(self, suit, number):
        self.suit = suit
        self.number = number

    def __repr__(self):
        tts_number = {
            6: 'шестёрка',
            7: 'семёрка',
            8: 'восьмёрка',
            9: 'девятка',
            10: 'десятка',
            'J': 'валет',
            'Q': 'дама',
            'K': 'король',
            'A': 'туз',
        }[self.number]

        tts_suit = {
            '♠️': 'пик',
            '♦️': 'бубен',
            '♣️': 'крестей',
            '♥️': 'червей'
        }[self.suit]

        return f'{{{self.number}{self.suit}}}{{{tts_number} {tts_suit}}}'

    def value(self):
        return self.number if isinstance(self.number, int) else {
            'J': 2,
            'Q': 3,
            'K': 4,
            'A': 11
        }[self.number]


class Game21(StateMachine):
    similar = {
        'ещё': ['еще'],
    }

    DECK = [
        Card(suit, number)
        for suit in ['♠️', '♦️', '♣️', '♥️']
        for number in list(range(6, 11)) + ['J', 'Q', 'K', 'A']
    ]

    def __init__(self):
        self.deck = self.DECK.copy()
        random.shuffle(self.deck)
        self.hand = []

    def get_card(self):
        card = self.deck.pop()
        self.hand.append(card)
        return card

    def hand_value(self, hand=None):
        if hand is None:
            hand = self.hand
        return sum(card.value() for card in hand)

    def hand_str(self, hand=None):
        if hand is None:
            hand = self.hand
        return " ".join(repr(card) for card in hand)

    def start(self):
        self.state = ''
        return Response(
            'Играем в двадцать одно!'
            ' Чтобы взять карту, {напишите}{скажите} "Ещё!".'
            ' Чтобы закончить брать карты, {напишите}{скажите} "Хватит!".'
            '\n\n'
            'К сожалению, у этого отладчика есть незадокументированная'
            ' фича, которая автоматически закрывает его при команде "хватит".'
            ' Чтобы сессия отладчика не рвалась, вы можете использовать'
            ' команду "достаточно" вместо команды "хватит". Возможно,'
            ' авторам заданий следовало бы при их составлении учесть то, как'
            ' работает ^отладчик^, не ^считаете^?'
            '\n\n'
            f'В любом случае, ваша первая карта: {self.get_card()}.\n'
            f'Количество очков: {self.hand_value()}\n\n'
            'Ещё или хватит?'
        )

    @StateMachine.input({'ещё'})
    def pick(self):
        assert self.hand_value() < 21
        card = self.get_card()
        message = f'Вы вытянули карту {card}.\n\n'
        if self.hand_value() == 21:
            message += 'Вы набрали ровно {21}{двадцать одно} очко и выиграли!'
            raise EndSession(message)
        elif self.hand_value() > 21:
            if self.hand_value() < 25:
                message += f'Перебор! У вас оказалось {self.hand_value()} очка.'
            else:
                message += f'Перебор! У вас оказалось {self.hand_value()} очков.'
            raise EndSession(message)
        else:
            message += f'Ваша рука: {self.hand_str()}\n'
            message += f'Количество очков: {self.hand_value()}\n\n'
            message += 'Ещё или хватит?'
            return message

    @StateMachine.input({'достаточно'})
    @StateMachine.input({'хватит'})
    def enough(self):
        dealer_hand = []
        while self.hand_value(dealer_hand) <= 17:
            dealer_hand.append(self.deck.pop())

        dealer_value = self.hand_value(dealer_hand)
        if dealer_value > 21 or dealer_value < self.hand_value():
            message = 'Вы выиграли!\n\n'
        else:
            message = 'Вы проиграли.\n\n'
        message += f'Рука банкира: {self.hand_str(dealer_hand)}\n'
        message += f'Количество очков банкира: {dealer_value}'
        raise EndSession(message)


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
            cards=[{'type': 'BigImage', 'image_id': 457239017}]
        )

    @StateMachine.input({'очко'})
    def start_quiz(self):
        self.state = 'help_seen'
        game = Game21()
        self.inhabit(game)
        return game.start()

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
                 ' Или напиши "очко" чтобы сыграть в двадцать одно.',
            tts='Привет!! Мы команда SOFT SQUAD!!'
                ' <speaker audio=marusia-sounds/things-sword-1> '
                ' <speaker audio=marusia-sounds/things-gun-1> '
                ' Напиши SOFT SQUAD вездекод чтобы поздороваться с нами!'
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
