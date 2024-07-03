from __future__ import annotations
import asyncio
from datetime import datetime, UTC
import time
from ast import literal_eval
from loguru import logger
from event import Event
from async_sx127x.driver import SX127x_Driver
from async_sx127x.models import LoRaRxPacket, LoRaTxPacket, RadioModel
from async_sx127x.registers_and_params import (SX127x_BW, SX127x_CR,
                                            SX127x_HeaderMode, SX127x_Mode,
                                            SX127x_Modulation)


async def sleep(timeout: float):
    counter = 0
    while counter < timeout:
        await asyncio.sleep(0.01)
        counter += 0.01

async def ainput(prompt: str = "") -> str:
    return await asyncio.to_thread(input, prompt)

class RadioController(SX127x_Driver):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)  # super(LoRa_Controller, self).__init__(**kwargs)
        self.modulation: SX127x_Modulation = kwargs.get('modulation', SX127x_Modulation.LORA)
        self.coding_rate: SX127x_CR = kwargs.get('ecr', self.cr.CR5)  # error coding rate
        self.bandwidth: SX127x_BW = kwargs.get('bw', self.bw.BW250)  # bandwidth  BW250
        self.spread_factor: int = kwargs.get('sf', 10)  # spreading factor  SF10
        self.frequency: int = kwargs.get('frequency', 433_000_000)   # 436700000
        self.crc_mode: bool = kwargs.get('crc_mode', True)  # check crc
        self.tx_power: int = kwargs.get('tx_power', 17)  # dBm
        self.sync_word: int = kwargs.get('sync_word', 0x12)
        self.preamble_length: int = kwargs.get('preamble_length', 8)
        self.auto_gain_control: bool = kwargs.get('agc', True)  # auto gain control
        self.payload_length: int = kwargs.get('payload_size', 10)  # for implicit mode
        self.low_noize_amplifier: int = kwargs.get('low_noize_amplifier', 5)  # 1 - min; 6 - max
        self.lna_boost: bool = kwargs.get('lna_boost', False)  # 150% LNA current
        self.header_mode: SX127x_HeaderMode = kwargs.get('header_mode', SX127x_HeaderMode.EXPLICIT) # fixed payload size
        self.low_data_rate_optimize: bool = kwargs.get('low_data_rate_optimize', True)
        self.only_tx: bool = kwargs.get('only_tx', False)
        self.label: str = kwargs.get('label', '')
        self.transmited: Event = Event(LoRaTxPacket)
        self.received: Event = Event(LoRaRxPacket)
        self.received_raw: Event = Event(bytes)
        self.tx_timeout: Event = Event(str)
        self.on_rx_timeout: Event = Event(str)

        self._last_caller: str = ''
        self._repeating_flag: bool = True
        self._keep_running: bool = False

    def stop_repeating(self) -> None:
        self._repeating_flag = False

    def clear_subscribers(self) -> None:
        self.received.subscribers[:] = self.received.subscribers[:2]
        self.transmited.subscribers[:] = self.transmited.subscribers[:2]
        self.on_rx_timeout.subscribers.clear()
        self.tx_timeout.subscribers.clear()
        self._last_caller: str = ''

    async def init(self) -> None:
        await self.interface.reset()
        await asyncio.sleep(0.1)
        await self.set_modulation(self.modulation)
        await self.set_lora_header_mode(self.header_mode)
        if self.header_mode == SX127x_HeaderMode.IMPLICIT:
            await self.set_lora_payload_length(self.payload_length)
        await self.set_lora_coding_rate(self.coding_rate)
        await self.set_lora_bandwidth(self.bandwidth)
        await self.set_lora_sf(self.spread_factor)
        await self.set_lora_crc_mode(self.crc_mode)
        await self.set_tx_power(self.tx_power)
        await self.set_lora_sync_word(self.sync_word)
        await self.set_lora_preamble_length(self.preamble_length)
        await self.set_lora_auto_gain_control(self.auto_gain_control)
        # if not self.auto_gain_control:
        await self.set_low_noize_amplifier(self.low_noize_amplifier, self.lna_boost)
        await self.set_lora_rx_tx_fifo_base_addr(0, 0)
        await self.set_frequency(self.frequency)
        await self.set_low_data_rate_optimize(self.low_data_rate_optimize)
        if not self.only_tx:
            await self.to_receive_mode()

    async def to_model(self) -> RadioModel:
        if self.interface.connection_status:
            result: SX127x_Mode = await self.get_operation_mode()
            op_mode: str = result.name
        else:
            op_mode = 'SLEEP'
        return RadioModel(mode=self.modulation.name,
                          frequency=self.frequency,
                          spreading_factor=self.spread_factor,
                          bandwidth=self.bandwidth.name,
                          check_crc=self.crc_mode,
                          sync_word=self.sync_word,
                          coding_rate=self.coding_rate.name,
                          tx_power=self.tx_power,
                          lna_boost=self.lna_boost,
                          lna_gain=self.low_noize_amplifier,
                          header_mode=self.header_mode.name,
                          autogain_control=self.auto_gain_control,
                          ldro=self.low_data_rate_optimize,
                          op_mode=op_mode)

    async def read_config(self) -> RadioModel:
        modulation = await self.get_modulation()
        bw = await self.get_lora_bandwidth()
        op_mode = await self.get_operation_mode()
        cr = await self.get_lora_coding_rate()
        header_mode = await self.get_lora_header_mode()
        model = RadioModel(mode=modulation.name if modulation else '',
                          op_mode=op_mode.name if op_mode else '',
                          frequency=await self.get_freq(),
                          spreading_factor=await self.get_lora_sf(),
                          bandwidth=bw.name if bw else '',
                          check_crc=await self.get_lora_crc_mode(),
                          sync_word=await self.get_lora_sync_word(),
                          coding_rate=cr.name if cr else '',
                          tx_power=await self.get_tx_power_dbm(),
                          autogain_control=await self.get_lora_auto_gain_control(),
                          lna_boost=await self.get_lna_boost(),
                          lna_gain=await self.get_lna_gain(),
                          header_mode=header_mode.name if header_mode else '',
                          ldro=await self.get_low_data_rate_optimize())
        return model


    async def connect(self, port_or_ip: str) -> bool:
        if await super().connect(port_or_ip):
            await asyncio.sleep(0.1)
            logger.success(f'Radio {self.label} connected.\nStart initialization...')
            await self.init()
            logger.success(f'Radio {self.label} inited.')
            return True
        logger.warning(f'Radio {self.label} is not connected!')
        return False
            # raise Exception("Can't connect to radio.")

    def disconnect(self) -> bool:
        return super().disconnect()

    async def _send_chunks(self, data: bytes, chunk_size: int) -> None:
        chunks: list[bytes] = [data[i:i + chunk_size]
                               for i in range(0, len(data), chunk_size)]
        logger.debug(f'{self.label} big parcel: {len(data)=}')
        is_implicit: bool = (self.header_mode == SX127x_HeaderMode.IMPLICIT)
        for chunk in chunks:
            tx_chunk: LoRaTxPacket = self.calculate_packet(chunk)
            logger.debug(tx_chunk)
            await self.write_fifo(chunk, is_implicit)
            await self.interface.run_tx_then_rx_cont()
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
            await self.write_fifo(data, is_implicit)
            # print(await self.interface.read(0x0D))
            # print(await self.interface.read_several(0, 15))
            await self.interface.run_tx_then_rx_cont()
            await asyncio.sleep((tx_pkt.Tpkt) / 1000)
            await self.reset_irq_flags()

        self.transmited.emit(tx_pkt)
        return tx_pkt

    async def to_receive_mode(self) -> None:
        mode: SX127x_Mode = await self.get_operation_mode()
        if mode != self.mode.RXCONT:
            if mode != self.mode.STDBY:
                await self.set_standby_mode()
            await self.set_rx_continuous_mode()

    def calculate_freq_error(self) -> int:
        # if self.sat_path:
        #     light_speed = 299_792_458  # m/s
        #     range_rate = int(self.sat_path.find_nearest(self.sat_path.dist_rate, datetime.now().astimezone(utc)) * 1000)
        #     return self.frequency - int((1 + range_rate / light_speed) * self.frequency)
        return 0

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

        return LoRaTxPacket(timestamp.isoformat(' ', 'seconds'),
                            packet.hex(' ').upper(), len(packet),
                            self.calculate_freq_error(), self.frequency,
                            packet_time, optimization_flag)

    async def get_rssi_packet(self) -> int:
        raw_val: int = await self.interface.read(self.reg.LORA_PKT_RSSI_VALUE.value)
        return raw_val - (164 if self.frequency < 0x779E6 else 157)

    async def get_rssi_value(self) -> int:
        raw_val: int = await self.interface.read(self.reg.LORA_RSSI_VALUE.value)
        return raw_val - (164 if self.frequency < 0x779E6 else 157)

    async def get_snr(self) -> int:
        return await self.interface.read(self.reg.LORA_PKT_SNR_VALUE.value) // 4

    async def get_snr_and_rssi(self) -> tuple[int, int]:
        data: list[int] = await self.interface.read_several(self.reg.LORA_PKT_SNR_VALUE.value, 2)
        if len(data) >= 2:
            snr, rssi = data[0], data[1]
            return snr // 4, rssi - (164 if self.frequency < 0x779E6 else 157)
        logger.warning(f'{self.label} get_snr_and_rssi ERROR!')
        return 0, 0

    # async def send_repeat(self, data: bytes | Callable,
    #                       period_sec: float,
    #                       untill_answer: bool = True,
    #                       max_retries: int = 50,
    #                       answer_handler: Callable[[LoRaRxPacket, Iterable], bool] | None = None,
    #                       handler_args: Iterable = (),
    #                       caller_name: str = '') -> LoRaRxPacket | None:
    #     last_rx_packet: LoRaRxPacket | None = None
    #     if self.only_tx:
    #         while max_retries:
    #             bdata: bytes = data() if isinstance(data, Callable) else data
    #             tx_packet: LoRaTxPacket = await self.send_single(bdata, caller_name)
    #             timeout: float = period_sec - tx_packet.Tpkt / 1000
    #             sleep(timeout)
    #             max_retries -= 1
    #         return None

    #     while max_retries and self._repeating_flag:
    #         bdata: bytes = data() if isinstance(data, Callable) else data
    #         tx_packet: LoRaTxPacket = await self.send_single(bdata, caller_name)
    #         timeout: float = period_sec - tx_packet.Tpkt / 1000

    #         rx_packet: LoRaRxPacket = self._rx_queue.get(timeout=timeout)
    #         last_rx_packet = rx_packet
    #         if not rx_packet.is_crc_error and untill_answer:
    #             if answer_handler:
    #                 if answer_handler(rx_packet, *handler_args):
    #                     break
    #             else:
    #                 break
    #         max_retries -= 1
    #     self._repeating_flag = True
    #     return last_rx_packet


    async def check_rx_input(self) -> LoRaRxPacket | None:
        if not await self.get_rx_done_flag():
            return None

        curr_addr: int = await self.interface.read(self.reg.LORA_FIFO_RX_CURRENT_ADDR.value)
        # TODO: remember previous address to minimize tcp packet (do not need to set fifo address ptr every time)
        await self.interface.write(self.reg.LORA_FIFO_ADDR_PTR.value, [curr_addr])
        freq_error: int = self.calculate_freq_error()
        if self.header_mode == SX127x_HeaderMode.IMPLICIT:
            data: list[int] = await self.interface.read_several(self.reg.FIFO.value,
                                                          self.payload_length)
        else:
            rx_amount: int = await self.interface.read(self.reg.LORA_RX_NB_BYTES.value)
            data = await self.interface.read_several(self.reg.FIFO.value, rx_amount)
        crc: bool = await self.get_crc_flag()
        await self.reset_irq_flags()
        bw: float = await self.get_lora_bw_khz()
        fei: int = await self.get_lora_fei(bw)
        timestamp: str = datetime.now().astimezone(UTC).isoformat(' ', 'seconds')
        snr, rssi = await self.get_snr_and_rssi()
        return LoRaRxPacket(timestamp=timestamp,
                            data=' '.join(f'{val:02X}' for val in data),
                            data_len=len(data),
                            freq_error_hz=freq_error,
                            frequency=self.frequency,
                            snr=snr,
                            rssi_pkt=rssi,
                            is_crc_error=crc,
                            fei=fei,
                            caller=self._last_caller)

    # def dump_memory(self) -> SX127x_Registers:
    #     dump_mem: list[int] = self.get_all_registers()
    #     mem = {k: dump_mem[v - 1] for k, v in self.reg.items()}
    #     return SX127x_Registers(mem)

    def clear(self) -> None:
        self.sat_path = None
        self.clear_subscribers()

    async def rx_routine(self) -> None:
        self._keep_running = True
        while self._keep_running:
            pkt: LoRaRxPacket | None = await self.check_rx_input()
            if pkt is not None:
                logger.debug(pkt)
                self.received.emit(pkt)
                self.received_raw.emit(pkt.to_bytes())
            await asyncio.sleep(0.01)

    async def set_frequency(self, new_freq_hz: int) -> None:
        await super().set_frequency(new_freq_hz)
        self.frequency = new_freq_hz

    async def user_cli(self) -> None:
        try:
            while True:
                data: str = await ainput('> ')
                if not data:
                    continue
                try:
                    list_data: list = literal_eval(data)
                    bdata = bytes(list_data)
                    await self.send_single(bdata)
                except (SyntaxError, ValueError):
                    await self.send_single(data.encode())

        except KeyboardInterrupt:
            self.disconnect()
            logger.debug('Shutdown radio driver')

def on_received(data: LoRaRxPacket):
    # for b in bytes.fromhex(data.data):
    try:
        print(bytes.fromhex(data.data).decode()[:-2])
    except Exception as err:
        print(err)

async def test():
    lora: RadioController = RadioController(interface='Serial', tx_power=18)
    if await lora.connect(port_or_ip='COM25'):  # 192.168.0.5
        print(await lora.read_config())
        rx_task = lora.rx_routine()
        cli_task = lora.user_cli()
        fut = await asyncio.gather(rx_task, cli_task)
        print(fut)

if __name__ == '__main__':
    asyncio.run(test())
    # logger.disable('__main__')


        # lora.received.subscribe(on_received)

        # lora.user_cli()
        # is_868 = True
        # try:
        #     while True:

        #         if is_868:
        #             lora.set_frequency(868_000_000)
        #         else:
        #             lora.set_frequency(915_000_000)
        #         time.sleep(0.5)
        #         lora.init()
        #         time.sleep(1)

        #         lora.send_single([i for i in range(100)])
        #         time.sleep(2)
        #         is_868 = not is_868
        # except KeyboardInterrupt:
        #     pass



# FSK mode:
# RegBitrate(0x02, 0x03): x = 9600;
# RegPreambleLsb(0x26) = 3;
# RegSyncValue(0x28) = NSUNET\0\0;
# RegSyncConfig(0x27) AutoRestartRxMode = 01 -> On, without waiting for the PLL to re-lock
# RegSyncConfig(0x27) SyncSize = 5 (sizeof(NSUNET) - 1)
# RegPacketConfig1(0x30) DcFree = Whitening