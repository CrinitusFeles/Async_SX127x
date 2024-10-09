

import asyncio
from asyncio import Lock, create_task, iscoroutinefunction, wait_for
from datetime import datetime
from typing import Awaitable, Callable, Coroutine, Iterable
from loguru import logger
from async_sx127x.driver import SX127x_Driver
from async_sx127x.models import (FSK_Model, FSK_RX_Packet, FSK_TX_Packet,
                                 RadioModel)
from async_sx127x.registers import (SX127x_FSK_SHAPING, SX127x_RestartRxMode,
                                    SX127x_Mode, SX127x_Modulation,
                                    SX127x_DcFree)


lock = Lock()
CALLBACK = Callable[[FSK_TX_Packet], Coroutine | None]

class FSK_Controller:
    freq_hz: int
    bitrate: int
    tx_power: int
    deviation: int
    sync_mode: bool
    check_crc: bool
    sync_word: bytes
    packet_mode: bool
    preamble_length: int
    max_payload_length: int
    dc_free: SX127x_DcFree
    data_shaping: SX127x_FSK_SHAPING
    rx_restart_mode: SX127x_RestartRxMode
    def __init__(self, driver: SX127x_Driver, **kwargs) -> None:
        self.driver: SX127x_Driver = driver
        self.freq_hz = kwargs.get('frequency', 433_000_000)
        self.bitrate = kwargs.get('bitrate', 9600)
        self.tx_power = kwargs.get('tx_power', 5)
        self.deviation = kwargs.get('deviation', 4800)
        self.sync_mode = kwargs.get('sync_mode', True)
        self.check_crc = kwargs.get('check_crc', True)
        self.sync_word = kwargs.get('sync_word', b'NSUNET')
        self.packet_mode = kwargs.get('packet_mode', True)
        self.preamble_length = kwargs.get('preamble', 8)
        self.max_payload_length = kwargs.get('payload_length', 256)
        self.dc_free = kwargs.get('dc_free', SX127x_DcFree.WHITENING)
        self.data_shaping = kwargs.get('data_shaping',
                                       SX127x_FSK_SHAPING.GAUSSIAN_1)
        self.rx_restart_mode = kwargs.get('rx_restart_mode',
                                          SX127x_RestartRxMode.NO_WAIT_PLL)
        self.label: str = kwargs.get('label', '')
        self._last_caller_name: str = ''
        self._transmited: CALLBACK | None = None

    async def init(self, ax25_mode: bool = False) -> None:
        async with lock:
            await self.driver.interface.reset()
            await asyncio.sleep(0.1)

            await self.driver.set_modulation(SX127x_Modulation.FSK)
            await self.driver.set_standby_mode()
            await self.driver.set_frequency(self.freq_hz)
            await self.driver.set_tx_power(self.tx_power)
            await self.driver.set_pa_select(self.driver.pa_boost)

            await self.driver.set_fsk_bitrate(self.bitrate)
            await self.driver.set_fsk_deviation(self.deviation)
            await self.driver.set_fsk_sync_mode(self.sync_mode)
            await self.driver.set_fsk_payload_length(self.max_payload_length)
            await self.driver.set_fsk_preamble_length(self.preamble_length)
            # await self.set_fsk_auto_afc(True)
            # await self.set_fsk_autoclear_afc(True)
            # await self.set_fsk_afc_bw(2, 7)
            await self.driver.set_fsk_data_shaping(self.data_shaping)
            await self.driver.set_fsk_fifo_threshold(15, immediate_tx=True)
            if ax25_mode:
                await self.driver.set_fsK_packet_format(False)
                await self.driver.set_fsk_dc_free_mode(SX127x_DcFree.OFF)
                await self.driver.set_fsk_crc(False)
                await self.driver.set_fsk_sync_value(bytes([0xFE, 0xFB, 0x91, 0xC5, 0xD5, 0xBE]))
                await self.driver.set_fsk_restart_rx_mode(SX127x_RestartRxMode.WAIT_PLL)
            else:
                await self.driver.set_fsK_packet_format(self.packet_mode)
                await self.driver.set_fsk_dc_free_mode(self.dc_free)
                await self.driver.set_fsk_crc(self.check_crc)
                await self.driver.fsk_clear_fifo_on_crc_fail(False)
                await self.driver.set_fsk_sync_value(self.sync_word)
                await self.driver.set_fsk_restart_rx_mode(self.rx_restart_mode)
            await self.driver.set_rx_continuous_mode()
            await self.driver.interface.write_fsk_read_start()

    async def to_model(self) -> RadioModel:
        model = FSK_Model(bitrate=9600,
                          deviation=4800,
                          sync_word=b'NSUNET',
                          dc_free=SX127x_DcFree.WHITENING.name,
                          packet_format=True)
        return RadioModel(mode=model,
                          frequency=self.freq_hz,
                          pa_select=self.driver.pa_boost,
                          check_crc=self.check_crc,
                          tx_power=self.tx_power)

    async def read_config(self) -> RadioModel:
        bitrate: int = await self.driver.get_fsk_bitrate()
        deviation: int = await self.driver.get_fsk_deviation()
        sync_val: bytes = await self.driver.get_fsk_sync_value(6)
        dc_free: str = (await self.driver.get_fsk_dc_free_mode()).name
        packet_mode: bool = await self.driver.get_fsk_packet_format()
        model = FSK_Model(bitrate=bitrate,
                          deviation=deviation,
                          sync_word=sync_val,
                          dc_free=dc_free,
                          packet_format=packet_mode)
        freq: int = await self.driver.get_freq()
        tx_power: float = await self.driver.get_tx_power_dbm()
        radio_model = RadioModel(mode=model,
                                 frequency=freq,
                                 pa_select=self.driver.pa_boost,
                                 check_crc=self.check_crc,
                                 tx_power=tx_power)
        return radio_model

    def _tx_frame(self, data: bytes, caller_name: str) -> FSK_TX_Packet:
        timestamp: str = datetime.now().isoformat(' ', 'seconds')
        return FSK_TX_Packet(timestamp=timestamp,
                             data = data,
                             data_len=len(data),
                             frequency=self.freq_hz,
                             caller=caller_name)

    async def send_single(self, data: bytes,
                          caller_name: str = '') -> FSK_TX_Packet:
        async with lock:
            await self.driver.interface.write_fsk_read()
            await self.driver.set_standby_mode()
            await self.driver.fsk_sequencer.start_tx()
            await self.driver.interface.write_fsk_fifo(data)
            while await self.driver.get_operation_mode() == SX127x_Mode.TX:
                pass
            tx_frame: FSK_TX_Packet = self._tx_frame(data, caller_name)
            logger.debug(f'{self.label} {tx_frame}')
            await self.driver.set_rx_continuous_mode()
            while 'MODE_READY' not in await self.driver.get_fsk_isr_list():
                pass
            if self._transmited is not None:
                if iscoroutinefunction(self._transmited):
                    create_task(self._transmited(tx_frame))
            await self.driver.interface.write_fsk_read_start()
            return tx_frame

    async def check_rx_input(self) -> FSK_RX_Packet | None:
        async with lock:
            isr: list[str] = await self.driver.get_fsk_isr_list()
            if 'PAYLOAD_READY' in isr:
                timestamp: str = datetime.now().isoformat(' ', 'seconds')
                crc_correct: bool = 'CRC_OK' in isr
                rx_data: bytes = await self.driver.interface.write_fsk_read()
                await self.driver.interface.write_fsk_read_start()
                rssi: int = await self.driver.get_fsk_rssi()
                return FSK_RX_Packet(timestamp=timestamp, data=rx_data,
                                    data_len=len(rx_data),
                                    frequency=self.freq_hz,
                                    crc_correct=crc_correct,
                                    rssi=rssi,
                                    caller=self._last_caller_name)
            return None

    async def _wait_rx(self) -> FSK_RX_Packet:
        while True:
            rx: FSK_RX_Packet | None = await self.check_rx_input()
            if rx:
                return rx

    async def send_repeat(self, data: bytes | Callable[..., bytes],
                          period_sec: float,
                          untill_answer: bool = True,
                          max_retries: int = 50,
                          handler: Callable[[FSK_RX_Packet, Iterable],
                                                   Awaitable[bool]] | None = None,
                          handler_args: Iterable = (),
                          caller_name: str = '') -> FSK_RX_Packet | None:
        last_rx_packet: FSK_RX_Packet | None = None
        async with lock:
            while max_retries:
                bdata: bytes = data() if isinstance(data, Callable) else data
                await self.send_single(bdata, caller_name)
                try:
                    rx_packet: FSK_RX_Packet = await wait_for(self._wait_rx(),
                                                              period_sec)
                    last_rx_packet = rx_packet
                    if rx_packet.crc_correct and untill_answer:
                        if handler:
                            if await handler(rx_packet, *handler_args):
                                break
                        else:
                            break
                except asyncio.TimeoutError:
                    logger.debug('FSK Rx timeout')
                max_retries -= 1
            return last_rx_packet
