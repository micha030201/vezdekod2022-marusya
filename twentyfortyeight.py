import random


class TwentyFourtyEightField:
    N = 4

    def __init__(self):
        self._table = [[0 for _ in range(self.N)] for _ in range(self.N)]
        self.spawn()
        self.emoji_ = ['*️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟', '#️⃣']

    def free(self):
        for i in range(self.N):
            for j in range(self.N):
                if not self._table[i][j]:
                    yield i, j

    def random_space(self):
        return random.choice(list(
            self.free()
        ))

    def loss(self):
        return not self.free()

    def win(self):
        return any([11 in row for row in self._table])

    def spawn(self):
        n = random.choice([1, 2])
        i, j = self.random_space()
        self._table[i][j] = n


    def collapse(self, l):
        out_l = []

        l = list(reversed(list(filter(None, l))))
        while len(l) > 1:
            if l[-1] == l[-2]:
                out_l.append(l.pop() + 1)
                l.pop()
            else:
                out_l.append(l.pop())
        while len(l):
            out_l.append(l.pop())

        return out_l + [0] * (self.N - len(out_l))

    def up(self):
        table = [[0 for _ in range(self.N)] for _ in range(self.N)]

        for i in range(self.N):
            for j in range(self.N):
                table[j][i] = self._table[i][j]

        for i in range(self.N):
            table[i] = self.collapse(table[i])

        for i in range(self.N):
            for j in range(self.N):
                self._table[i][j] = table[j][i]

        self.spawn()

    def down(self):
        table = [[0 for _ in range(self.N)] for _ in range(self.N)]

        for i in range(self.N):
            for j in range(self.N):
                table[j][i] = self._table[i][j]

        for i in range(self.N):
            table[i] = list(reversed(self.collapse(list(reversed(table[i])))))

        for i in range(self.N):
            for j in range(self.N):
                self._table[i][j] = table[j][i]

        self.spawn()

    def left(self):
        for i in range(self.N):
            self._table[i] = self.collapse(self._table[i])
        self.spawn()

    def right(self):
        for i in range(self.N):
            self._table[i] = list(reversed(self.collapse(list(reversed(self._table[i])))))
        self.spawn()

    def print(self):
        for row in self._table:
            print(''.join(str(n) for n in row))

    def emoji(self):
        table = [[0 for _ in range(self.N)] for _ in range(self.N)]

        for i in range(self.N):
            for j in range(self.N):
                table[i][j] = self.emoji_[self._table[i][j]]

        return '\n'.join(''.join(e for e in row) for row in table)
