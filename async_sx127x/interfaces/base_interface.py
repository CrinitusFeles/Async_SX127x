from __future__ import annotations
import asyncio
from typing import Any, Callable, Coroutine
from loguru import logger


def check_connection(func: Callable):
    def _wrapper(*args, **kwargs):
        if not args[0].connection_status:
            raise RuntimeError('Radio is not connected')
        return func(*args, **kwargs)
    return _wrapper

async def retry(func: Callable[..., Coroutine], counter: int):
    data = b''
    while counter > 0:
        data = await func()
        if data != b'':
            break
        await asyncio.sleep(0.15)
        logger.error('read empty bytes')
        counter -= 1
    return data


lock = asyncio.Lock()

class BaseInterface:
    _write: Callable[..., Coroutine]
    _read: Callable[..., Coroutine]
    _interface: Any
    connection_status: bool = False

    async def connect(self, _: str):
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError

    @check_connection
    async def read(self, address: int) -> int:
        async with lock:
            await self._write(bytes([1, address]))
            data: bytes = await retry(self._try_read, 5)
            return int.from_bytes(data, "big")

    @check_connection
    async def write(self, address: int, data: list[int]) -> int:
        async with lock:
            if len(data) == 1:
                await self._write(bytes([2, address, data[0]]))
            else:
                await self._write(bytes([8, address, len(data), *data]))
            answer: bytes = await self._try_read()
            return int.from_bytes(answer, "big")

    @check_connection
    async def run_tx_then_rx_cont(self) -> int:
        async with lock:
            await self._write(bytes([21]))
            answer: bytes = await self._try_read()
            return int.from_bytes(answer, "big")

    @check_connection
    async def run_tx_then_rx_single(self) -> int:
        async with lock:
            await self._write(bytes([22]))
            answer: bytes = await self._try_read()
            return int.from_bytes(answer, "big")

    @check_connection
    async def read_several(self, address: int, amount: int) -> list[int]:
        async with lock:
            await self._write(bytes([7, address, amount]))
            answer: bytes = await self._try_read(amount)
            return list(answer)

    @check_connection
    async def reset(self) -> int:
        async with lock:
            await self._write(bytes([6]))
            answer: bytes = await self._try_read()
            return int.from_bytes(answer, "big")

    @check_connection
    async def write_fsk_fifo(self, data: bytes) -> int:
        """ В пакете FSK, в отличие от пакета LoRa *НЕ* передается первым байтом
        последущий размер пакета. Но для совместимости верхнего  уровня будем
        его добавлять, а убирать в этой функции.
        """
        async with lock:
            send_data = [31, len(data) - 1, *data[1:]]
            await self._write(bytes(send_data))
            answer: bytes = await self._try_read()
            return int.from_bytes(answer, "big")  # 31

    @check_connection
    async def write_fsk_read_start(self) -> int:
        """
        Запускает на микроконтроллере процесс перекладывания данных из FIFO приемопередатчика
        в FIFO микроконтроллера. Параллельно небходимо вычитывать статусный регистр, пока
        пакет не придет полностью. После окончания пакета нужно вызвать функцию write_fsk_read.
        Для остановки процесса перекладывания данных можно вызвать функцию write_fsk_read до
        окончания пакета.
        """
        async with lock:
            await self._write(bytes([32]))
            answer: bytes = await self._try_read()
            return int.from_bytes(answer, "big")

    @check_connection
    async def write_fsk_read(self) -> bytes:
        """
        Первым байтом возвращает количество следующих байт, а потом последующие байты из
        FIFO микроконтроллера.
        """
        async with lock:
            await self._write(bytes([33]))
            answer: bytes = await self._try_read()
            data_len: int = int.from_bytes(answer, "big")
            if data_len > 0:
                answer = await self._try_read(data_len)
                return int.to_bytes(data_len) + answer
            return b''

    async def _try_read(self, amount: int = 1) -> bytes:
        try:
            data: bytes = await self._read(amount)
            if data == b'':
                raise RuntimeError('Radio read empty data')
            return data
        except TimeoutError as exc:
            raise TimeoutError(f'Radio reading timeout: {exc}') from exc
        except TypeError as exc:
            logger.error('serial interface can not read None data', exc)
            raise exc