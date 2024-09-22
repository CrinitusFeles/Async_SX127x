


from ast import literal_eval
import asyncio
from typing import Callable, Coroutine
from async_sx127x.driver import SX127x_Driver
from async_sx127x.radio_controller import ainput
from async_sx127x.registers import (SX127x_DcFree, SX127x_FSK_SHAPING, SX127x_Modulation,
                                            SX127x_RestartRxMode)

lock = asyncio.Lock()

async def init_fsk(ax25_mode: bool = False):
    async with lock:
        await lora.interface.reset()
        await asyncio.sleep(0.1)

        await lora.set_modulation(SX127x_Modulation.FSK)
        await lora.set_standby_mode()
        await lora.set_frequency(437_496_500)  # 436_996_300
        # await lora.set_frequency(437_500_000)  # 436_996_300
        await lora.set_tx_power(3)
        await lora.set_pa_select(True)

        await lora.set_fsk_bitrate(9600)
        await lora.set_fsk_deviation(4800)
        await lora.set_fsk_sync_mode(True)
        await lora.set_fsk_payload_length(256)
        await lora.set_fsk_preamble_length(8)
        await lora.set_fsk_data_shaping(SX127x_FSK_SHAPING.GAUSSIAN_1)
        await lora.set_fsk_fifo_threshold(15, immediate_tx=True)
        if ax25_mode:
            await lora.set_fsK_packet_format(False)
            await lora.set_fsk_dc_free_mode(SX127x_DcFree.OFF)
            await lora.set_fsk_crc(False)
            await lora.set_fsk_sync_value(bytes([0xFE, 0xFB, 0x91, 0xC5, 0xD5, 0xBE]))
            await lora.set_fsk_restart_rx_mode(SX127x_RestartRxMode.WAIT_PLL)
        else:
            await lora.set_fsK_packet_format(True)
            await lora.set_fsk_dc_free_mode(SX127x_DcFree.WHITENING)
            await lora.set_fsk_crc(True)
            await lora.set_fsk_sync_value(b'NSUNET')
            await lora.set_fsk_restart_rx_mode(SX127x_RestartRxMode.NO_WAIT_PLL)
        await lora.set_rx_continuous_mode()
        await lora.interface.write_fsk_read_start()

msg = bytes.fromhex('0E 0A 06 01 CB 01 01 01 01 00 07 00 00 00 01')


async def received(data: bytes):
    # freq_error = await lora.get_fsk_fei()
    # print(f'{freq_error=}')
    print(f'RX [{len(data)}]: {data.hex(" ").upper()}')
    # await asyncio.sleep(1)
    # await send_single(data)

on_received: Callable[[bytes], Coroutine] | None = received

async def fsk_receiving():
    await init_fsk(False)
    while True:
        isr: list[str] = await lora.get_fsk_isr_list()
        if 'PAYLOAD_READY' in isr:
            print(isr)
            rx_data: bytes = await lora.interface.write_fsk_read()
            if on_received:
                await lora.interface.write_fsk_read_start()
                await on_received(rx_data)


async def send_single(data: bytes):
    await lora.interface.write_fsk_read()
    await lora.set_standby_mode()
    await lora.set_fsk_fifo_threshold(len(data) - 1, immediate_tx=False)
    await lora.fsk_sequencer.start_tx()
    await lora.interface.write_fsk_fifo(data)
    await lora.set_rx_continuous_mode()
    await lora.interface.write_fsk_read_start()
    print(f'TX [{len(data)}]: {data.hex(" ").upper()}')


async def user_cli() -> None:
    try:
        while True:
            data: str = await ainput('> ')
            if not data:
                continue
            elif data.upper() == 'MSG':
                await send_single(msg)
                continue
            elif data.upper() == 'AX25':
                await init_fsk(True)
                print('inited ax25 mode')
                continue
            elif data.upper() == 'NORMAL':
                await init_fsk(False)
                print('inited normal mode')
                continue
            elif data.split(':')[0] == 'freq':
                freq = data.split(':')[1]
                print(freq)
                await lora.set_standby_mode()
                await lora.set_frequency(int(literal_eval(freq)))
                await lora.set_rx_continuous_mode()
                continue
            try:
                list_data: list = literal_eval(data)
                bdata = bytes(list_data)
                await send_single(bdata)
            except (SyntaxError, ValueError):
                await send_single(data.encode())
    except EOFError:
        ...


async def main():
    await lora.connect('COM7')
    asyncio.create_task(user_cli())
    await fsk_receiving()

if __name__ == '__main__':
    lora: SX127x_Driver = SX127x_Driver('Serial')
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        asyncio.run(lora.interface.reset())
        asyncio.run(lora.disconnect())