


from ast import literal_eval
import asyncio
from random import randint
from typing import Callable, Coroutine
from async_sx127x.driver import SX127x_Driver
from async_sx127x.radio_controller import ainput
from async_sx127x.registers import (SX127x_DcFree, SX127x_FSK_SHAPING, SX127x_Mode, SX127x_Modulation,
                                            SX127x_RestartRxMode)


async def init_fsk(ax25_mode: bool = False):
    await lora.interface.reset()
    await asyncio.sleep(0.1)

    await lora.set_modulation(SX127x_Modulation.FSK)
    await lora.set_standby_mode()
    await lora.set_frequency(437_501_400)  # 436_996_300
    # await lora.set_frequency(437_500_000)  # 436_996_300
    await lora.set_tx_power(3)
    await lora.set_pa_select(True)

    await lora.set_fsk_bitrate(9600)
    await lora.set_fsk_deviation(4800)
    await lora.set_fsk_sync_mode(True)
    await lora.set_fsk_payload_length(256)
    await lora.set_fsk_preamble_length(8)
    # await lora.set_fsk_auto_afc(True)
    # await lora.set_fsk_autoclear_afc(True)
    # await lora.set_fsk_afc_bw(2, 7)
    await lora.set_fsk_data_shaping(SX127x_FSK_SHAPING.GAUSSIAN_1)
    await lora.set_fsk_fifo_threshold(48, immediate_tx=True)
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
        await lora.fsk_clear_fifo_on_crc_fail(False)
        await lora.set_fsk_sync_value(b'NSUNET')
        await lora.set_fsk_restart_rx_mode(SX127x_RestartRxMode.NO_WAIT_PLL)
    await lora.set_rx_continuous_mode()
    await lora.interface.write_fsk_read_start()


async def received(data: bytes):
    rssi = await lora.get_fsk_rssi()
    print(f'RX [{len(data)}][{rssi}dBm]: {data.hex(" ").upper()}')
    # afc = await lora.get_fsk_afc()
    # # await lora.add_freq(afc)
    # print(f'AFC: {afc}')
    # await lora.fsk_clear_afc()

on_received: Callable[[bytes], Coroutine] | None = received

async def fsk_receiving():
    await init_fsk(False)
    while True:
        isr: list[str] = await lora.get_fsk_isr_list()
        if 'PAYLOAD_READY' in isr:
            rx_data: bytes = await lora.interface.write_fsk_read()
            if on_received:
                await on_received(rx_data)
            await lora.interface.write_fsk_read_start()
        # if 'SYNC_ADDR_MATCH' in isr:
        #     afc = await lora.get_fsk_afc()
        #     # await lora.add_freq(afc)
        #     print(f'AFC: {afc}')


async def send_single(data: bytes):
    await lora.interface.write_fsk_read()
    await lora.set_standby_mode()
    await lora.fsk_sequencer.start_tx()
    await lora.interface.write_fsk_fifo(data)
    print(f'TX [{len(data)}]: {data.hex(" ").upper()}')
    while await lora.get_operation_mode() == SX127x_Mode.TX:
        pass
    await lora.set_rx_continuous_mode()
    while 'MODE_READY' not in await lora.get_fsk_isr_list():
        pass
    await lora.interface.write_fsk_read_start()



async def user_cli() -> None:
    try:
        while True:
            data: str = await ainput('> ')
            if not data:
                continue
            elif data.upper() == 'MSG':
                msg = bytes.fromhex(f'0E 0A 06 01 CB 01 01 01 01 00 {randint(10, 99)} 00 00 00 01')
                asyncio.create_task(send_single(msg))
                continue
            elif data.upper() == 'ISR':
                print(await lora.get_fsk_isr_list())
                continue
            elif data.upper() == 'AFC':
                print(await lora.get_fsk_afc())
                continue
            elif data.upper() == 'READ':
                print((await lora.interface.write_fsk_read()).hex(' ').upper())
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
    await lora.connect('COM25')
    asyncio.create_task(fsk_receiving())
    await user_cli()

if __name__ == '__main__':
    lora: SX127x_Driver = SX127x_Driver('Serial')
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        asyncio.run(lora.interface.reset())
        lora.disconnect()