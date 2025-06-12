import os
import unittest
import sys
import qemu.qmp
import signal
import asyncio


class Tests(unittest.IsolatedAsyncioTestCase):
    res_score = 0

    class Qemu:
        def __init__(self):
            self.p: asyncio.subprocess.Process | None = None
            self.client: qemu.qmp.QMPClient | None = None

        async def __aenter__(self):
            self.p = await asyncio.create_subprocess_exec('make', 'run-nox' if sys.argv[-1] == '--nox' else 'run')
            while not os.path.exists('qemu-monitor-socket'):
                await asyncio.sleep(0.01)
            self.client = qemu.qmp.QMPClient('yabloko')
            await self.client.connect('qemu-monitor-socket')
            await asyncio.sleep(1)  # Time to init OS
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await asyncio.sleep(1)
            await self.client.disconnect()
            if self.p is None:
                raise RuntimeError("Unexpected")
            try:
                os.kill(self.p.pid, signal.SIGTERM)
            except:
                pass
            await self.p.wait()

        async def key_press(self, keys: str, ms: int = 50):
            res = await self.client.execute('send-key', {
                'keys': [{"type": "qcode", "data": key} for key in keys.split('-')],
                'hold-time': ms
            })
            await asyncio.sleep(ms / 1000)
            return res

        async def key_press_release(self, seq: list[str]):
            # Auto release all pressed keys.
            seq = seq.copy()
            pressed = set()
            for key in seq:
                if key[0] == '-':
                    if key[1:] not in pressed:
                        raise RuntimeError("Internal error: key release before press " + key)
                    pressed.remove(key[1:])
                else:
                    if key in pressed:
                        raise RuntimeError("Internal error: double key press " + key)
                    pressed.add(key)
            for key in pressed:
                seq.append('-' + key)

            for key in seq:
                await self.client.execute('input-send-event', {
                    'events': [
                        {'type': 'key', 'data': {
                            'down': not key[0] == '-',
                            'key': {"type": "qcode", "data": key.lstrip('-')},
                        }}
                    ]
                })
                await asyncio.sleep(50 / 1000)

        async def run(self, name: str):
            await self.key_press('r')
            await self.key_press('u')
            await self.key_press('n')
            await self.key_press('spc')
            for c in name:
                await self.key_press(c)
            await self.key_press('ret')

        async def dump_screen(self) -> bytes:
            if os.path.exists('mem.bin'):
                p = await asyncio.create_subprocess_exec('rm', '-rf', 'mem.bin')
                await p.wait()

            # Скорость оставляет желать лучшего
            await asyncio.sleep(1)

            await self.client.execute('pmemsave', {
                'val': 0xb8000,
                'size': 25 * 80 * 2,
                'filename': 'mem.bin',
            })
            await asyncio.sleep(0.1)
            with open('mem.bin', 'rb') as f:
                return f.read()

    @classmethod
    def tearDownClass(cls):
        print()
        print('Score:', cls.res_score)
        with open('res.txt', 'w') as f:
            f.write(str(cls.res_score))

    @staticmethod
    def score(score):
        def decorator(func):
            async def inner(self, *args, **kwargs):
                try:
                    res = await func(self, *args, **kwargs)
                except Exception as e:
                    raise
                else:
                    Tests.res_score += score
                    return res
            return inner
        return decorator

    def check_screen_content(self, dump: bytes, lines: list[str]):
        dump = dump[:79*2] + b' \x07' + dump[80*2:]  # ignore arrow

        self.assertEqual(len(dump), 2 * 80 * 25)
        for i in range(25):
            for j in range(80):
                self.assertEqual(dump[(j + i * 80) * 2 + 1], 0x07)

            cur_line = b''.join(chr(dump[(j + i * 80) * 2]).encode() for j in range(80))

            line = lines[i].encode() if i < len(lines) else b''
            line = line.ljust(80, b' ')

            self.assertEqual(line, cur_line)

    @score(20)
    async def test_shift(self):
        async with Tests.Qemu() as q:

            await q.key_press('a')
            await q.key_press('b')
            await q.key_press('c')

            await q.key_press('shift-a')
            await q.key_press('shift-b')
            await q.key_press('shift-c')

            await q.key_press('shift-a-b-c')

            await q.key_press('ret')

            dump = await q.dump_screen()

            self.check_screen_content(dump, [
                'YABLOKO',
                '',
                '> abcABCABC',
                'unknown command, try: halt | run CMD',
                '>',
            ])

        async with Tests.Qemu() as q:

            await q.key_press('shift-shift_r-a')
            await q.key_press('a')

            await q.key_press('shift_r-shift-b')
            await q.key_press('b')

            await q.key_press('shift_r-c')
            await q.key_press('c')

            await q.key_press('ret')

            await asyncio.sleep(1)

            await q.key_press_release(['a', '-a'])
            await q.key_press('b')

            await q.key_press('ret')

            await asyncio.sleep(1)

            await q.key_press_release(['shift', 'a', '-a', '-shift'])
            await q.key_press('b')
            await q.key_press_release(['shift', 'a', '-shift', '-a'])
            await q.key_press('b')
            await q.key_press_release(['shift', 'shift_r', 'a', '-a', '-shift', 'a'])
            await q.key_press('b')
            await q.key_press_release(['shift', 'shift_r', 'a', '-a', '-shift_r', 'a'])
            await q.key_press('b')
            await q.key_press_release(['shift_r', 'shift', 'a', '-a', '-shift', 'a'])
            await q.key_press('b')
            await q.key_press_release(['shift_r', 'shift', 'a', '-a', '-shift_r', 'a'])
            await q.key_press('b')

            await asyncio.sleep(1)

            dump = await q.dump_screen()

            self.check_screen_content(dump, [
                'YABLOKO',
                '',
                '> AaBbCc',
                'unknown command, try: halt | run CMD',
                '> ab',
                'unknown command, try: halt | run CMD',
                '> AbAbAAbAAbAAbAAb',
            ])

        async with Tests.Qemu() as q:
            keys = '0123456789' + ''.join(chr(i) for i in range(ord('a'), ord('z') + 1))

            for key in keys:
                await q.key_press(key)

            await q.key_press('ret')

            await asyncio.sleep(5)

            for key in keys:
                await q.key_press(f'shift-{key}')

            await q.key_press('ret')

            await asyncio.sleep(5)

            dump = await q.dump_screen()

            self.check_screen_content(dump, [
                'YABLOKO',
                '',
                '> 0123456789abcdefghijklmnopqrstuvwxyz',
                'unknown command, try: halt | run CMD',
                '> )!@#$%^&*(ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                'unknown command, try: halt | run CMD',
                '>',
            ])

    @score(20)
    async def test_backspace(self):
        async with Tests.Qemu() as q:

            await q.key_press('a')
            await q.key_press('b')
            await q.key_press('c')

            await q.key_press('backspace')

            await q.key_press('d')

            await q.key_press('ret')

            dump = await q.dump_screen()

            self.check_screen_content(dump, [
                'YABLOKO',
                '',
                '> abd',
                'unknown command, try: halt | run CMD',
                '>',
            ])

        async with Tests.Qemu() as q:
            await q.key_press('backspace')
            await q.key_press('backspace')

            await q.key_press('a')
            await q.key_press('b')
            await q.key_press('c')

            await q.key_press('backspace')
            await q.key_press('backspace')

            await q.key_press('a')
            await q.key_press('b')
            await q.key_press('c')

            await q.key_press('backspace')
            await q.key_press('backspace')

            dump = await q.dump_screen()

            self.check_screen_content(dump, [
                'YABLOKO',
                '',
                '> aa',
            ])

            await q.key_press('backspace')
            await q.key_press('backspace')
            await q.key_press('backspace')
            await q.key_press('backspace')

            await q.key_press('ret')

            dump = await q.dump_screen()

            self.check_screen_content(dump, [
                'YABLOKO',
                '',
                '> ',
                'unknown command, try: halt | run CMD',
                '>',
            ])

    @score(20)
    async def test_spin(self):
        async with Tests.Qemu() as q:
            found = set()

            for i in range(10):
                dump = await q.dump_screen()

                self.assertEqual(dump[79*2+1], 15)
                self.assertIn(dump[79*2], [0x18 + i for i in range(4)] + [ord('/'), ord('\\')])

                found.add(dump[79*2])

                self.check_screen_content(dump, [
                    'YABLOKO',
                    '',
                    '>',
                ])

            self.assertGreaterEqual(len(found), 3)

    @score(60)
    async def test_bss(self):
        async with Tests.Qemu() as q:

            await q.run('greet')

            await q.run('bss')

            await q.run('bss')

            await q.run('greet')

            await asyncio.sleep(1)

            dump = await q.dump_screen()

            self.check_screen_content(dump, [
                'YABLOKO',
                '',
                '> run greet',
                'Hello world!',
                'Hello world!',
                '* success',
                '',
                '> run bss',
                '* success',
                '',
                '> run bss',
                '* success',
                '',
                '> run greet',
                'Hello world!',
                'Hello world!',
                '* success',
                '',
                '>',
            ])

    @score(100)
    async def test_puts(self):
        async with Tests.Qemu() as q:

            await q.run('greet')

            await q.run('shout')

            await q.run('shout')

            await q.run('greet')

            await asyncio.sleep(2)

            dump = await q.dump_screen()

            self.check_screen_content(dump, [
                'YABLOKO',
                '',
                '> run greet',
                'Hello world!',
                'Hello world!',
                '* success',
                '',
                '> run shout',
                'cra cra trif traf not sgnieflet',
                'cra cra trif traf not sgnieflet',
                '* success',
                '',
                '> run shout',
                'cra cra trif traf not sgnieflet',
                'cra cra trif traf not sgnieflet',
                '* success',
                '',
                '> run greet',
                'Hello world!',
                'Hello world!',
                '* success',
                '',
                '>',
            ])

        async with Tests.Qemu() as q:

            await q.run('greet')

            await q.run('badputs')

            await q.run('badputs')

            await q.run('greet')

            await asyncio.sleep(2)

            dump = await q.dump_screen()

            self.check_screen_content(dump, [
                'YABLOKO',
                '',
                '> run greet',
                'Hello world!',
                'Hello world!',
                '* success',
                '',
                '> run badputs',
                'I hope the kernel does not panic...',
                '* success',
                '',
                '> run badputs',
                'I hope the kernel does not panic...',
                '* success',
                '',
                '> run greet',
                'Hello world!',
                'Hello world!',
                '* success',
                '',
                '>',
            ])


if __name__ == '__main__':
    test_suite = unittest.defaultTestLoader.discover('.', 'tests.py')
    test_runner = unittest.TextTestRunner(resultclass=unittest.TextTestResult)
    result = test_runner.run(test_suite)
    try:
        with open('res.txt', 'r') as f:
            res_score = int(f.read())
    except:
        res_score = 0
    if result.wasSuccessful() or res_score != 0:
        sys.exit(0)
    sys.exit(1)
