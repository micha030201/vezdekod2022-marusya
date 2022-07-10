import random


def grouper(iterable, n):
    "Collect data into non-overlapping fixed-length chunks or blocks"
    args = [iter(iterable)] * n
    return zip(*args)


M = 22
N = 10


class TetrisField:
    SHAPES = [
        [
            [0, 0, 2, 0],
            [0, 0, 2, 0],
            [0, 0, 2, 0],
            [0, 0, 2, 0],
        ],
        [
            [0, 3, 0],
            [3, 3, 3],
            [0, 0, 0],
        ],
        [
            [4, 0, 0],
            [4, 4, 4],
            [0, 0, 0],
        ],
        [
            [0, 0, 0],
            [5, 5, 5],
            [5, 0, 0],
        ],
        [
            [0, 0, 0],
            [0, 6, 6],
            [6, 6, 0],
        ],
        [
            [0, 0, 0],
            [7, 7, 0],
            [0, 7, 7],
        ],
        [
            [8, 8],
            [8, 8],
        ],
    ]

    def __init__(self):
        self._table = [[0 for _ in range(N)] for _ in range(M)]
        self.shape = random.choice(self.SHAPES)
        self.shape_i = 0
        self.shape_j = 3
        self.emoji_ = ['⬜', '⬛', '🟥', '🟧', '🟨', '🟩', '🟦', '🟪', '🟫']

    def check_fit(self, shape, shape_i, shape_j):
        for i, row in enumerate(shape):
            for j, el in enumerate(row):
                global_i = i + shape_i
                global_j = j + shape_j

                if (shape[i][j] and (
                        (not (0 <= global_i < M and 0 <= global_j < N))
                        or self._table[global_i][global_j])):
                    return False
        return True

    def apply(self):
        for i in range(M):
            for j in range(N):
                shapelocal_i = i - self.shape_i
                shapelocal_j = j - self.shape_j

                if (0 <= shapelocal_i < len(self.shape)) and (0 <= shapelocal_j < len(self.shape[0])):
                    assert not (self._table[i][j] and self.shape[shapelocal_i][shapelocal_j])
                    self._table[i][j] = self._table[i][j] or self.shape[shapelocal_i][shapelocal_j]

    def table(self):
        ret = [[0 for _ in range(N)] for _ in range(M)]
        for i in range(M):
            for j in range(N):
                #print('g', i, j, self._table[i][j])
                shapelocal_i = i - self.shape_i
                shapelocal_j = j - self.shape_j

                if (0 <= shapelocal_i < len(self.shape)) and (0 <= shapelocal_j < len(self.shape[0])):
                    #print('l', shapelocal_i, shapelocal_j, self.shape[shapelocal_i][shapelocal_j])
                    assert not (self._table[i][j] and self.shape[shapelocal_i][shapelocal_j])
                    ret[i][j] = ret[i][j] or self.shape[shapelocal_i][shapelocal_j]

                ret[i][j] = ret[i][j] or self._table[i][j]

        return ret

    def _gravitate(self):
        for i in range(M):
            if all(self._table[i]):
                self._table = (
                    [[0 for _ in range(N)]]
                    + self._table[:i]
                    + self._table[i+1:]
                )

    def step(self):
        self._gravitate()

        if not self.check_fit(self.shape, self.shape_i + 1, self.shape_j):
            self.apply()

            self._gravitate()

            self.shape = random.choice(self.SHAPES)
            self.shape_i = 0
            self.shape_j = 3
        else:
            self.shape_i += 1

    def multistep(self):
        while True:
            self._gravitate()

            if not self.check_fit(self.shape, self.shape_i + 1, self.shape_j):
                self.apply()

                self._gravitate()

                self.shape = random.choice(self.SHAPES)
                self.shape_i = 0
                self.shape_j = 3
                break
            else:
                self.shape_i += 1

    def rotate(self):
        rotated_shape = list(list(x) for x in zip(*self.shape))[::-1]
        if self.check_fit(rotated_shape, self.shape_i, self.shape_j):
            self.shape = rotated_shape

    def left(self):
        if self.check_fit(self.shape, self.shape_i, self.shape_j - 1):
            self.shape_j -= 1

    def right(self):
        if self.check_fit(self.shape, self.shape_i, self.shape_j + 1):
            self.shape_j += 1

    def loss(self):
        return any(self._table[3]) or any(self._table[2])

    def print(self):
        for row in self.table():
            print('|' + ''.join('#' if e else ' ' for e in row) + '|')

    def braille(self):
        top = '⠉'
        top2 = '⠛'
        bot = '⠤'
        bot2 = '⠶'
        full = '⠿'
        empty = '⠀'

        table = [[True] * N] + self.table() + [[True] * N]

        def genchar(t, b, even):
            if even:
                if t and b:
                    return full
                if t and not b:
                    return top2
                if b and not t:
                    return bot
                else:
                    return empty
            else:
                if t and b:
                    return full
                if t and not b:
                    return top
                if b and not t:
                    return bot2
                else:
                    return empty

        return '\n'.join(
            [''.join(
                [full]
                + list(genchar(t, b, True) for t, b in zip(topline, midline))
                + [full]
            ) + '\n'
            + ''.join(
                [full]
                + list(genchar(t, b, False) for t, b in zip(midline, bottomline))
                + [full]
            ) for topline, midline, bottomline in grouper(table, 3)]
        )

    def emoji(self):
        table = [[1] * N] + self.table() + [[1] * N]

        return '\n'.join(
            [''.join(
                [self.emoji_[1]]
                + list(self.emoji_[el] for el in row)
                + [self.emoji_[1]]
            ) for row in table]
        )
