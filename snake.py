import random
from collections import deque


class SnakeField:
    N = 10

    def __init__(self):
        self.walls = (
            [(0, j) for j in range(self.N)] +
            [(self.N-1, j) for j in range(self.N)] +
            [(i, 0) for i in range(self.N)] +
            [(i, self.N-1) for i in range(self.N)]
        )

        self.snake = deque()
        self.snake = deque([self.random_space()])

        self.food = self.random_space()

        self.emoji_ = ['⬜', '⬛', '🟩', '🟨', '🟥']
        self.lost = False

    def random_space(self):
        try:
            return random.choice(list(
                {(i, j) for i in range(self.N) for j in range(self.N)}
                - set(self.snake)
                - set(self.walls)
            ))
        except IndexError:
            return -5, -5

    def table(self):
        ret = [[0 for _ in range(self.N)] for _ in range(self.N)]

        for i, j in self.walls:
            ret[i][j] = 1

        for i, j in self.snake:
            ret[i][j] = 2

        i, j = self.food
        ret[i][j] = 3

        if self.lost:
            i, j = self.lost
            ret[i][j] = 4

        return ret

    def check_free(self, i, j):
        return not (
            (i, j) in self.snake
            or (i, j) in self.walls
        )

    def move(self, i, j):
        if self.lost:
            return
        if self.check_free(i, j):
            self.snake.appendleft((i, j))
            if (i, j) == self.food:
                self.food = self.random_space()
            else:
                self.snake.pop()
        else:
            self.lost = (i, j)

    def loss(self):
        return self.lost

    def up(self):
        i, j = self.snake[0]
        self.move(i-1, j)

    def down(self):
        i, j = self.snake[0]
        self.move(i+1, j)

    def left(self):
        i, j = self.snake[0]
        self.move(i, j-1)

    def right(self):
        i, j = self.snake[0]
        self.move(i, j+1)

    def print(self):
        for row in self.table():
            print(''.join(str(n) for n in row))

    def emoji(self):
        table = self.table()

        for i in range(self.N):
            for j in range(self.N):
                table[i][j] = self.emoji_[table[i][j]]

        return '\n'.join(''.join(e for e in row) for row in table)
