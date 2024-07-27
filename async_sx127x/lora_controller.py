from __future__ import annotations
import asyncio
from asyncio import Lock
from datetime import datetime, UTC
from ast import literal_eval
from typing import Awaitable, Callable, Iterable
from loguru import logger
from event import Event
from async_sx127x.driver import SX127x_Driver
from async_sx127x.models import (LoRaModel, LoRaRxPacket, LoRaTxPacket,
                                 RadioModel)
from async_sx127x.registers import (SX127x_BW, SX127x_CR, SX127x_HeaderMode,
                                    SX127x_Modulation, SX127x_Registers)


async def ainput(prompt: str = "") -> str:
    return await asyncio.to_thread(input, prompt)

lock = Lock()

class LoRa_Controller:
    freq_hz: int
    crc_mode: bool
    tx_power: int
    coding_rate: SX127x_CR
    bandwidth: SX127x_BW
    spread_factor: int
    sync_word: int
    preamble_length: int
    auto_gain_control: bool
    payload_length: int
    lna_val: int
    lna_boost: bool
    header_mode: SX127x_HeaderMode
    ldro: bool
    def __init__(self, driver: SX127x_Driver, **kwargs) -> None:
        self.driver: SX127x_Driver = driver
        self.freq_hz = kwargs.get('frequency', 433_000_000)   # 436700000
        self.crc_mode = kwargs.get('crc_mode', True)  # check crc
        self.tx_power = kwargs.get('tx_power', 17)  # dBm
        self.coding_rate = kwargs.get('ecr', SX127x_CR.CR5)  # error coding rate
        self.bandwidth = kwargs.get('bw', SX127x_BW.BW250)  # bandwidth  BW250
        self.spread_factor = kwargs.get('sf', 10)  # spreading factor  SF10
        self.sync_word = kwargs.get('sync_word', 0x12)
        self.preamble_length = kwargs.get('preamble_length', 8)
        self.auto_gain_control = kwargs.get('agc', True)  # auto gain control
        self.payload_length = kwargs.get('payload_size', 10)  # for implicit mode
        self.lna_val = kwargs.get('low_noize_amplifier', 5)  # 1 - min; 6 - max
        self.lna_boost = kwargs.get('lna_boost', False)  # 150% LNA current
        self.header_mode = kwargs.get('header_mode', SX127x_HeaderMode.EXPLICIT)
        self.ldro = kwargs.get('low_data_rate_optimize', True)
        self._only_tx: bool = kwargs.get('only_tx', False)
        self.label: str = kwargs.get('label', '')
        self._transmited: Event = Event(LoRaTxPacket)
        self._last_caller: str = ''

    async def init(self) -> bool:
        await self.driver.reset()
        await asyncio.sleep(0.1)
        await self.driver.set_modulation(SX127x_Modulation.LORA)
        await self.driver.set_lora_header_mode(self.header_mode)
        if self.header_mode == SX127x_HeaderMode.IMPLICIT:
            await self.driver.set_lora_payload_length(self.payload_length)
        await self.driver.set_lora_coding_rate(self.coding_rate)
        await self.driver.set_lora_bandwidth(self.bandwidth)
        await self.driver.set_lora_sf(self.spread_factor)
        await self.driver.set_lora_crc_mode(self.crc_mode)
        await self.driver.set_tx_power(self.tx_power)
        await self.driver.set_lora_sync_word(self.sync_word)
        await self.driver.set_lora_preamble_length(self.preamble_length)
        await self.driver.set_lora_auto_gain_control(self.auto_gain_control)
        # if not self.auto_gain_control:
        await self.driver.set_low_noize_amplifier(self.lna_val,
                                                  self.lna_boost)
        await self.driver.set_lora_rx_tx_fifo_base_addr(0, 0)
        await self.driver.set_frequency(self.freq_hz)
        await self.driver.set_low_data_rate_optimize(self.ldro)
        if not self._only_tx:
            await self.driver.set_rx_continuous_mode()
        return True

    async def to_model(self) -> RadioModel:
        model = LoRaModel(spreading_factor=self.spread_factor,
                            bandwidth=self.bandwidth.name,
                            sync_word=self.sync_word,
                            coding_rate=self.coding_rate.name,
                            lna_boost=self.lna_boost,
                            lna_gain=self.lna_val,
                            header_mode=self.header_mode.name,
                            autogain_control=self.auto_gain_control,
                            ldro=self.ldro)
        return RadioModel(mode=model,
                          frequency=self.freq_hz,
                          pa_select=self.driver.pa_boost,
                          check_crc=self.crc_mode,
                          tx_power=self.tx_power)

    async def read_config(self) -> RadioModel:
        bw: str = (await self.driver.get_lora_bandwidth()).name
        cr: str = (await self.driver.get_lora_coding_rate()).name
        header_mode: str = (await self.driver.get_lora_header_mode()).name
        crc: bool = await self.driver.get_lora_crc_mode()
        sf: int = await self.driver.get_lora_sf()
        sync_word: int = await self.driver.get_lora_sync_word()
        agc: bool = await self.driver.get_lora_auto_gain_control()
        ldro: bool = await self.driver.get_low_data_rate_optimize()
        lna_boost: bool = await self.driver.get_lna_boost()
        lna_gain: int = await self.driver.get_lna_gain()
        model = LoRaModel(spreading_factor=sf,
                            bandwidth=bw,
                            sync_word=sync_word,
                            coding_rate=cr,
                            autogain_control=agc,
                            lna_boost=lna_boost,
                            lna_gain=lna_gain,
                            header_mode=header_mode,
                            ldro=ldro)
        freq: int = await self.driver.get_freq()
        tx_power: float = await self.driver.get_tx_power_dbm()
        radio_model = RadioModel(mode=model,
                           frequency=freq,
                           pa_select=self.driver.pa_boost,
                           check_crc=crc,
                           tx_power=tx_power)
        return radio_model

    async def _send_chunks(self, data: bytes, chunk_size: int) -> None:
        chunks: list[bytes] = [data[i:i + chunk_size]
                               for i in range(0, len(data), chunk_size)]
        logger.debug(f'{self.label} big parcel: {len(data)=}')
        is_implicit: bool = (self.header_mode == SX127x_HeaderMode.IMPLICIT)
        for chunk in chunks:
            tx_chunk: LoRaTxPacket = self.calculate_packet(chunk)
            logger.debug(tx_chunk)
            await self.driver.write_fifo(chunk, is_implicit)
            await self.driver.interface.run_tx_then_rx_cont()
            await self._transmited.aemit(tx_chunk)
            await asyncio.sleep((tx_chunk.Tpkt + 10) / 1000)

    async def send_single(self, data: bytes,
                          caller_name: str = '') -> LoRaTxPacket:
        buffer_size: int = 255
        tx_pkt: LoRaTxPacket = self.calculate_packet(data)
        tx_pkt.caller = caller_name
        self._last_caller = caller_name
        logger.debug(f'{self.label} {tx_pkt}')
        if len(data) > buffer_size:
            await self._send_chunks(data, buffer_size)
        else:
            is_implicit: bool = (self.header_mode == SX127x_HeaderMode.IMPLICIT)
            await self.driver.write_fifo(data, is_implicit)
            await self.driver.interface.run_tx_then_rx_cont()
            await self._transmited.aemit(tx_pkt)
            await asyncio.sleep((tx_pkt.Tpkt) / 1000)
            await self.driver.reset_irq_flags()
        return tx_pkt

    def calculate_packet(self, packet: bytes,
                         force_optimization=True) -> LoRaTxPacket:
        sf: int = self.spread_factor
        _str_bw: str = self.bandwidth.name.replace('BW', '').replace('_', '.')
        bw: int | float = literal_eval(_str_bw)
        cr: int = self.coding_rate.value >> 1
        if self.header_mode == SX127x_HeaderMode.IMPLICIT:
            payload_size = self.payload_length
        else:
            payload_size: int = len(packet)
        t_sym: float = 2 ** sf / bw  # ms
        optimization_flag: bool = True if force_optimization else t_sym > 16
        preamble_time: float = (self.preamble_length + 4.25) * t_sym
        _tmp_1: int = 8 * payload_size - 4 * sf + 28
        _tmp_2: int = 16 * self.crc_mode - 20 * self.header_mode.value
        tmp_poly: int = max((_tmp_1 + _tmp_2), 0)
        _devider = (4 * (sf - 2 * optimization_flag))
        payload_symbol_nb: float = 8 + (tmp_poly / _devider) * (4 + cr)
        payload_time: float = payload_symbol_nb * t_sym
        packet_time: float = payload_time + preamble_time
        timestamp: datetime = datetime.now().astimezone()

        return LoRaTxPacket(timestamp=timestamp.isoformat(' ', 'seconds'),
                            data=packet,
                            data_len=len(packet),
                            frequency=self.freq_hz,
                            Tpkt=packet_time,
                            low_datarate_opt_flag=optimization_flag)

    async def send_repeat(self, data: bytes | Callable[..., bytes],
                          period_sec: float,
                          untill_answer: bool = True,
                          max_retries: int = 50,
                          handler: Callable[[LoRaRxPacket, Iterable],
                                            Awaitable[bool]] | None = None,
                          handler_args: Iterable = (),
                          caller_name: str = '') -> LoRaRxPacket | None:
        last_rx_packet: LoRaRxPacket | None = None
        if self._only_tx:
            while max_retries:
                bdata: bytes = data() if isinstance(data, Callable) else data
                tx_packet: LoRaTxPacket = await self.send_single(bdata,
                                                                 caller_name)
                timeout: float = period_sec - tx_packet.Tpkt / 1000
                await asyncio.sleep(timeout)
                max_retries -= 1
            return None

        while max_retries:
            bdata: bytes = data() if isinstance(data, Callable) else data
            tx_packet: LoRaTxPacket = await self.send_single(bdata, caller_name)
            timeout: float = period_sec - tx_packet.Tpkt / 1000
            try:
                rx_packet: LoRaRxPacket = await asyncio.wait_for(self._wait_rx(),
                                                                 timeout)
                last_rx_packet = rx_packet
                if rx_packet.crc_correct and untill_answer:
                    if handler:
                        if handler(rx_packet, *handler_args):
                            break
                    else:
                        break
            except asyncio.TimeoutError:
                logger.debug('LoRa Rx timeout')
            max_retries -= 1
        return last_rx_packet

    async def _wait_rx(self) -> LoRaRxPacket:
        while True:
            if rx := await self.check_rx_input():
                return rx

    async def check_rx_input(self) -> LoRaRxPacket | None:
        if not await self.driver.get_rx_done_flag():
            return None
        curr_addr: int = await self.driver.get_lora_fifo_ptr()
        addr = SX127x_Registers.LORA_FIFO_ADDR_PTR.value
        await self.driver.interface.write(addr, [curr_addr])
        if self.header_mode == SX127x_HeaderMode.IMPLICIT:
            data: bytes = await self.driver.read_lora_fifo(self.payload_length)
        else:
            rx_size_addr = SX127x_Registers.LORA_RX_NB_BYTES.value
            rx_amount: int = await self.driver.interface.read(rx_size_addr)
            data = await self.driver.read_lora_fifo(rx_amount)
        crc: bool = await self.driver.get_crc_flag()
        await self.driver.reset_irq_flags()
        bw: float = await self.driver.get_lora_bw_khz()
        fei: int = await self.driver.get_lora_fei(bw)
        timestamp: str = datetime.now(UTC).isoformat(' ', 'seconds')
        snr, rssi = await self.driver.get_snr_and_rssi(self.freq_hz)
        return LoRaRxPacket(timestamp=timestamp,
                            data=bytes(data),
                            data_len=len(data),
                            frequency=self.freq_hz,
                            snr=snr,
                            rssi_pkt=rssi,
                            crc_correct=crc,
                            fei=fei,
                            caller=self._last_caller)
