

import asyncio
from async_sx127x.models import FSK_RX_Packet, FSK_TX_Packet, LoRaRxPacket, LoRaTxPacket
from async_sx127x.radio_controller import RadioController

async def on_received(data: LoRaRxPacket | FSK_RX_Packet):
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
                                              frequency=437_501_400,
                                              tx_power=3)
    device.received.subscribe(on_received)
    device.transmited.subscribe(on_transmited)
    try:
        asyncio.run(test())
    except KeyboardInterrupt:
        asyncio.run(device.disconnect())
        print('Shutdown')