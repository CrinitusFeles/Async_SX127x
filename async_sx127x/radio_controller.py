import asyncio
from random import randint
from typing import Awaitable, Callable, Coroutine, Iterable, Literal

from loguru import logger
from event import Event
from async_sx127x.driver import SX127x_Driver
from async_sx127x.fsk_controller import FSK_Controller
from async_sx127x.lora_controller import LoRa_Controller
from async_sx127x.models import (FSK_RX_Packet, FSK_TX_Packet, LoRaRxPacket,
                                 LoRaTxPacket, RadioModel)


async def ainput(prompt: str = "") -> str:
    return await asyncio.to_thread(input, prompt)


ANSWER_CALLBACK = Callable[[LoRaRxPacket | FSK_RX_Packet, Iterable],
                           Awaitable[bool] | bool]

class RadioController:
    def __init__(self, mode: Literal['lora', 'fsk'] = 'lora', **kwargs) -> None:
        self.label: str = kwargs.get('label', '')
        self.driver = SX127x_Driver(**kwargs)
        self.lora = LoRa_Controller(self.driver, **kwargs)
        self.fsk = FSK_Controller(self.driver, **kwargs)
        if mode == 'lora':
            self.current_mode: LoRa_Controller | FSK_Controller = self.lora
        else:
            self.current_mode = self.fsk
        self.lora._transmited.subscribe(self._on_transmited)
        self.fsk._transmited.subscribe(self._on_transmited)
        self.received: Event = Event(LoRaRxPacket | FSK_RX_Packet)
        self.transmited: Event = Event(LoRaTxPacket | FSK_TX_Packet)
        self._tx_buffer: list[LoRaTxPacket | FSK_TX_Packet] = []
        self._rx_buffer: list[LoRaRxPacket | FSK_RX_Packet] = []
        self.tx_task: asyncio.Task | None = None

    def connection_status(self) -> bool:
        return self.driver.interface.connection_status

    async def connect(self, port_or_ip: str) -> bool:
        if await self.driver.connect(port_or_ip):
            await asyncio.sleep(0.1)
            logger.success(f'Radio {self.label} connected.\n'
                           f'Start initialization...')
            await self.current_mode.init()
            logger.success(f'Radio {self.label} inited.')
            return True
        logger.warning(f'Radio {self.label} is not connected!')
        return False

    async def disconnect(self) -> bool:
        await self.driver.reset()
        return await self.driver.disconnect()

    async def _on_transmited(self, pkt: LoRaTxPacket | FSK_TX_Packet):
        self._tx_buffer.append(pkt)
        self.transmited.emit(pkt)

    def clear_buffers(self) -> None:
        self._rx_buffer.clear()
        self._tx_buffer.clear()

    def get_tx_buffer(self) -> list[LoRaTxPacket | FSK_TX_Packet]:
        return self._tx_buffer

    def get_rx_buffer(self) -> list[LoRaRxPacket | FSK_RX_Packet]:
        return self._rx_buffer

    async def read_config(self) -> RadioModel:
        return await self.current_mode.read_config()

    async def to_model(self) -> RadioModel:
        return await self.current_mode.to_model()

    async def init_lora(self, sf: int | None = None,
                        bw: int | float | None = None,
                        freq: int | None = None,
                        cr: int | None = None,
                        ldro: bool | None = None,
                        crc_en: bool | None = None,
                        sync_word: int | None = None,
                        preamble_length: int | None = None,
                        tx_power: int | None = None
                        ) -> None:
        if sf is not None:
            self.lora.spread_factor = sf
        if bw is not None:
            self.lora.bandwidth = bw
        if freq is not None:
            self.lora.freq_hz = freq
        if cr is not None:
            self.lora.coding_rate = cr
        if ldro is not None:
            self.lora.ldro = ldro
        if crc_en is not None:
            self.lora.crc_mode = crc_en
        if sync_word is not None:
            self.lora.sync_word = sync_word
        if preamble_length is not None:
            self.lora.preamble_length = preamble_length
        if tx_power is not None:
            self.lora.tx_power = tx_power
        await self.lora.init()
        self.current_mode = self.lora

    async def init_fsk(self, ax25_mode: bool = False) -> None:
        await self.fsk.init(ax25_mode)
        self.current_mode = self.fsk

    async def send_repeat(self, data: bytes | Callable,
                          period_sec: float,
                          untill_answer: bool = True,
                          max_retries: int = 50,
                          answer_handler: ANSWER_CALLBACK | None = None,
                          handler_args: Iterable = (),
                          caller_name: str = '') -> LoRaRxPacket | FSK_RX_Packet | None:
        coro: Coroutine = self.current_mode.send_repeat(data, period_sec,
                                                        untill_answer,
                                                        max_retries,
                                                        answer_handler,
                                                        handler_args,
                                                        caller_name)
        self.tx_task = asyncio.create_task(coro)
        try:
            result = await self.tx_task
            self.tx_task = None
        except asyncio.CancelledError as err:
            logger.debug('TX task was cancelled')
            self.tx_task = None
            result = None
            raise err
        return result

    async def cancel_tx(self) -> bool:
        if self.tx_task:
            return self.tx_task.cancel()
        return False

    async def send_single(self, data: bytes,
                          caller_name: str = '') -> LoRaTxPacket | FSK_TX_Packet:
        return await self.current_mode.send_single(data, caller_name)

    async def check_rx_input(self) -> LoRaRxPacket | FSK_RX_Packet | None:
        return await self.current_mode.check_rx_input()

    async def rx_routine(self) -> None:
        pkt: LoRaRxPacket | FSK_RX_Packet | None = None
        try:
            while True:
                pkt = await self.current_mode.check_rx_input()
                self.current_mode._last_caller_name = ''
                if pkt:
                    logger.debug(pkt)
                    self._rx_buffer.append(pkt)
                    self.received.emit(pkt)
        except (RuntimeError, ConnectionResetError) as err:
            logger.error(err)
        except asyncio.CancelledError:
            logger.debug('Radio RX task cancelled')

    async def set_frequency(self, new_freq_hz: int) -> None:
        await self.current_mode.driver.set_frequency(new_freq_hz)
        self.lora.freq_hz = new_freq_hz
        self.fsk.freq_hz = new_freq_hz

    async def add_freq(self, freq_hz: int) -> int:
        new_freq: int = await self.current_mode.driver.add_freq(freq_hz)
        self.lora.freq_hz = new_freq
        self.fsk.freq_hz = new_freq
        return new_freq

    async def user_cli(self) -> None:
        while True:
            data: str = await ainput('> ')
            if not data:
                continue
            elif data.upper() == 'TMI':
                msg = bytes.fromhex(f'0E 0A 06 01 CB 01 01 01 01 00 {randint(10, 99)} 00 00 00 01')
                # asyncio.create_task(self.send_single(msg))
                asyncio.create_task(self.send_single(msg))
                continue
            elif data.upper() == 'AX25':
                await self.init_fsk(True)
                print('inited ax25 mode')
                continue
            elif data.upper() == 'FSK':
                await self.init_fsk(False)
                print('inited normal mode')
                continue
            elif data.upper() == 'LORA':
                await self.init_lora()
                print('inited lora mode')
                continue
            elif data.upper() == 'CONFIG':
                print(await self.read_config())
                continue
            elif data.upper() == 'TASKS':
                for task in asyncio.all_tasks():
                    print(task)
                continue
            try:
                bdata: bytes = bytes.fromhex(data)
                await self.send_single(bdata)
            except (SyntaxError, ValueError):
                await self.send_single(data.encode())


def on_received(data: LoRaRxPacket | FSK_RX_Packet):
    print(data)

async def on_transmited(data: LoRaTxPacket | FSK_TX_Packet):
    print(data)

async def test():
    if await device.connect(port_or_ip='COM25'):  # 192.168.0.5
        print(await device.read_config())
        asyncio.create_task(device.rx_routine())
        await device.user_cli()


if __name__ == '__main__':
    device: RadioController = RadioController('lora',
                                              interface='Serial',
                                              frequency=401_500_000,
                                              tx_power=3)
    device.received.subscribe(on_received)
    device.transmited.subscribe(on_transmited)
    try:
        asyncio.run(test())
    except KeyboardInterrupt:
        asyncio.run(device.disconnect())
        print('Shutdown')