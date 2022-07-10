import re
import random
import logging
from typing import Dict, Any, List
from collections import defaultdict

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from tetris import TetrisField
from snake import SnakeField


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

def countable(n, one, few, many):
    if n % 10 == 1:
        return f'{n} {one}'
    if n % 10 in {2, 3, 4}:
        return f'{n} {few}'
    return f'{n} {many}'


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
    return re.sub('{.*?}{(.*?)}', r'\1', s)


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


# BLACKJACK:

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


# FOOD OR NOT:

class FoodOrNot(StateMachine):
    FOOD = [
        (True, '{🍇}{виноград}'),
        (True, '{🍉}{арбуз}'),
        (True, '{🍊}{мандарин}'),
        (True, '{🍌}{банан}'),
        (True, '{🍍}{ананас}'),
        (True, '{🥭}{манго}'),
        (True, '{🍎}{яблоко}'),
        (True, '{🍐}{грушу}'),
        (True, '{🍑}{персик}'),
        (True, '{🍒}{вишню}'),
        (True, '{🍓}{клубнику}'),
        (True, '{🫐}{чернику}'),
        (True, '{🥝}{киви}'),
        (True, '{🍅}{помидор}'),
        (True, '{🥥}{кокос}'),
        (True, '{🥑}{авокадо}'),
        (True, '{🍆}{баклажан}'),
        (True, '{🥔}{картошку}'),
        (True, '{🌽}{кукурузу}'),
        (True, '{🌶️}{перец}'),
        (True, '{🥒}{огурец}'),
        (True, '{🍞}{хлеб}'),
        (True, '{🥐}{круассан}'),
        (True, '{🥖}{багет}'),
        (True, '{🧀}{сыр}'),
        (True, '{🍕}{пиццу}'),
        (True, '{🥪}{бутерброд}'),
        (True, '{🍙}{онигири}'),
        (True, '{🍚}{рис}'),
        (True, '{🍝}{спагетти}'),
        (True, '{🍣}{суши}'),
        (True, '{🍨}{мороженое}'),
        (True, '{🥧}{пирог}'),
        (True, '{🍫}{шоколад}'),

        (False, '{🕳️}{дыру}'),
        (False, '{💣}{бомба}'),
        (False, '{🔪}{нож}'),
        (False, '{🧭}{компас}'),
        (False, '{🧱}{стену}'),
        (False, '{🛢️}{нефть}'),
        (False, '{🧳}{чемодан}'),
        (False, '{⏰}{будильник}'),
        (False, '{🌡️}{градусник}'),
        (False, '{🧨}{динамит}'),
        (False, '{🪁}{воздушный змей}'),
        (False, '{🖼️}{картину}'),
        (False, '{💽}{диск}'),
        (False, '{💾}{дискету}'),
        (False, '{📺}{телевизор}'),
        (False, '{📷}{фотоаппарат}'),
        (False, '{📼}{кассету}'),
        (False, '{🔍}{лупу}'),
        (False, '{💡}{лампочку}'),
        (False, '{📖}{книгу}'),
        (False, '{📎}{скрепку}'),
        (False, '{📏}{линейку}'),
        (False, '{🗝️}{ключ}'),
        (False, '{🔨}{молоток}'),
        (False, '{🪓}{топор}'),
        (False, '{🪚}{пила}'),
        (False, '{🗜️}{струбцину}'),
        (False, '{🧲}{магнит}'),
        (False, '{🔭}{телескоп}'),
        (False, '{🪠}{вантуз}'),
        (False, '{🧹}{веник}'),
        (False, '{🧽}{мочалку}'),
    ]

    def start(self):
        self.state = 'playing'
        self.n_correct = 0
        self.current_test = random.choice(self.FOOD)
        return Response(
            'Играем в съедобно-несъед`обно!'
            ' Отвечайте на вопрос либо "съем" либо "выброшу".'
            '\n\n'
            f'Первый вопрос: съели ли бы вы {self.current_test[1]}?'
        )

    @StateMachine.input({'съем'})
    @StateMachine.input({'ем'})
    @StateMachine.input({'да'})
    @StateMachine.need_state('playing')
    def eat(self):
        if self.current_test[0]:
            self.n_correct += 1
            message = f'Правильно! {self.current_test[1]} можно смело кушать.'
            self.current_test = random.choice(self.FOOD)
            message += f' Следующий вопрос: съели ли бы вы {self.current_test[1]}?'
            return Response(message)
        self.state = 'dead'
        return Response(
            f'Нет! {self.current_test[1]} ни в коем случае нельзя есть!'
            ' Вы отравились и умерли.'
            '\n\n'
            'До своей смерти вы успели правильно ответить на'
            f' {countable(self.n_correct, "вопрос", "вопроса", "вопросов")}.'
            ' Чтобы начать снова, {напишите}{скажите} "ожить"{,}{.} чтобы выйти'
            ' {напишите}{скажите} "достаточно".'
        )

    @StateMachine.input({'ожить'})
    @StateMachine.input({'жить'})
    @StateMachine.input({'жить'})
    @StateMachine.need_state('dead')
    def resurrect(self):
        return self.start()

    @StateMachine.input({'выброшу'})
    @StateMachine.input({'нет'})
    @StateMachine.need_state('playing')
    def throw(self):
        if not self.current_test[0]:
            self.n_correct += 1
            message = f'Правильно! {self.current_test[1]} кушать нельзя.'
            self.current_test = random.choice(self.FOOD)
            message += f' Следующий вопрос: съели ли бы вы {self.current_test[1]}?'
            return Response(message)
        self.state = 'wrong'
        return Response(
            f'Как же так! Вы решили выбросить {self.current_test[1]}.'
            ' А в Африке дети от голода умирают. Вы вообще знаете{}{,} как люди'
            ' в блокаду жили?!'
            '\n\n'
            'До этого варварского поступка вы успели правильно ответить на'
            f' {countable(self.n_correct, "вопрос", "вопроса", "вопросов")}.'
            ' Чтобы начать снова, {напишите}{скажите} "извините"{,}{.} чтобы выйти'
            ' {напишите}{скажите} "достаточно".'
        )

    @StateMachine.input({'извините'})
    @StateMachine.need_state('wrong')
    def apologise(self):
        return self.start()

    @StateMachine.input({'достаточно'})
    @StateMachine.input({'выйти'})
    def enough(self):
        raise EndSession('Игра закончена.')


# TETRIS:

class Tetris(StateMachine):
    similar = {
        'налево': ['лево', 'влево'],
        'направо': ['право', 'вправо'],
        'вниз': ['низ'],
    }

    def start(self):
        self.field = TetrisField()
        message = (
            'Играем в тетрис! Доступные команды: "налево", "направо", "вниз",'
            ' "поворот" (против часовой стрелки). Если у вас неправильно'
            ' отображаются плитки, напишите "плитки".\n\n'
        )
        return Response(
            message + self.field.emoji(),
            tts=message
        )

    @StateMachine.input({'плитки'})
    def bw_emoji(self):
        self.field.emoji_ = ['⬜', '⬛', '⬛', '⬛', '⬛', '⬛', '⬛', '⬛', '⬛']
        return self.field.emoji()

    @StateMachine.input({'налево'})
    def left(self):
        if self.field.loss():
            raise EndSession('Вы проиграли.')
        self.field.left()
        self.field.step()
        return self.field.emoji()

    @StateMachine.input({'направо'})
    def right(self):
        if self.field.loss():
            raise EndSession('Вы проиграли.')
        self.field.right()
        self.field.step()
        return self.field.emoji()

    @StateMachine.input({'вниз'})
    def down(self):
        if self.field.loss():
            raise EndSession('Вы проиграли.')
        self.field.multistep()
        return self.field.emoji()

    @StateMachine.input({'поворот'})
    def rotate(self):
        if self.field.loss():
            raise EndSession('Вы проиграли.')
        self.field.rotate()
        self.field.step()
        return self.field.emoji()

    @StateMachine.input({'достаточно'})
    @StateMachine.input({'выйти'})
    def enough(self):
        raise EndSession('Игра закончена.')


# Snake:

class Snake(StateMachine):
    similar = {
        'налево': ['лево', 'влево'],
        'направо': ['право', 'вправо'],
        'вниз': ['низ'],
        'вверх': ['верх'],
    }

    def start(self):
        self.field = SnakeField()
        message = (
            'Играем в змейку! Доступные команды: "налево", "направо", "вниз",'
            ' "вверх". Если у вас неправильно'
            ' отображаются плитки, напишите "плитки".\n\n'
        )
        return Response(
            message + self.field.emoji(),
            tts=message
        )

    @StateMachine.input({'плитки'})
    def bw_emoji(self):
        self.field.emoji_ = ['⬜', '⬛', '🐍', '🔴', '💥']
        return self.field.emoji()

    @StateMachine.input({'налево'})
    def left(self):
        self.field.left()
        ret = self.field.emoji()
        if self.field.loss():
            raise EndSession(f'{ret}\n\nВы проиграли.')
        return ret

    @StateMachine.input({'направо'})
    def right(self):
        self.field.right()
        ret = self.field.emoji()
        if self.field.loss():
            raise EndSession(f'{ret}\n\nВы проиграли.')
        return ret

    @StateMachine.input({'вверх'})
    def up(self):
        self.field.up()
        ret = self.field.emoji()
        if self.field.loss():
            raise EndSession(f'{ret}\n\nВы проиграли.')
        return ret

    @StateMachine.input({'вниз'})
    def down(self):
        self.field.down()
        ret = self.field.emoji()
        if self.field.loss():
            raise EndSession(f'{ret}\n\nВы проиграли.')
        return ret

    @StateMachine.input({'достаточно'})
    @StateMachine.input({'выйти'})
    def enough(self):
        raise EndSession('Игра закончена.')


# GREETER:

class Greeter(StateMachine):
    similar = {
        'съедобно': 'съедобное'
    }

    @StateMachine.input({'очко'})
    def start_quiz(self):
        game = Game21()
        self.inhabit(game)
        return game.start()

    @StateMachine.input({'съедобно'})
    def start_foodornot(self):
        game = FoodOrNot()
        self.inhabit(game)
        return game.start()

    @StateMachine.input({'тетрис'})
    @StateMachine.input({'tetris'})
    def start_tetris(self):
        game = Tetris()
        self.inhabit(game)
        return game.start()

    @StateMachine.input({'змейка'})
    def start_snake(self):
        game = Snake()
        self.inhabit(game)
        return game.start()

    @StateMachine.input()
    def greet(self):
        return Response(
            text=(
                'Привет!!!!! Мы команда SOFT SQUAD!!!!!!!!!'
                ' Выберите одну из игр: "^очк`о^", "^съед`обно^", "тетрис" или "змейка".'),
            tts=(
                'Привет!! Мы команда SOFT SQUAD!!'
                ' <speaker audio=marusia-sounds/things-sword-1> '
                ' <speaker audio=marusia-sounds/things-gun-1> '
                ' Выберите одну из игр: "^очк`о^", "^съед`обно^", "тетрис" или "змейка".'),
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
