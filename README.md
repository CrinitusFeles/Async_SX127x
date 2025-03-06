# Async_SX127x



## Installation

```bash
poetry add git+https://github.com/CrinitusFeles/Async_SX127x.git
```

or

```bash
pip install git+https://github.com/CrinitusFeles/Async_SX127x.git
```

## Using

```bash
python -m async_sx127x COM25 frequency=436700000 sf=10 bw=250 cr=1 ldro=True
```

After successful initialization you can send data over LoRa:

```
> FF DE 01 AD 99
```

or
```
> hello world!
```

All received frames will be printed to terminal.

## API description

### Constructor

```python
device: RadioController = RadioController(interface='Serial',
                                          frequency=437_501_400,
                                          tx_power=3)
```
Available arguments:
```python
interface: Literal['Ethernet', 'Serial'] # (default value: 'Serial')
frequency: int  # (default value: 433_000_000)
crc_mode: bool  # (default value: True)
tx_power: int  # (default value: 17)  # dBm
cr: int  # (default value: 5)  # coding rate
bw: int  # (default value: 250)  # bandwidth
sf: int  # (default value: 10)  # spreading factor
sync_word: int  # (default value: 0x12)
preamble_length: int  # (default value: 8)
agc: int  # (default value: True)  # auto gain control
payload_size: int  # (default value: 10)  # for implicit mode
low_noize_amplifier: int  # (default value: 5)  # 1 - min; 6 - max
lna_boost: int  # (default value: False)  # 150% LNA current
header_mode: int  # (default value: SX127x_HeaderMode.EXPLICIT)
ldro: int  # (default value: True)
label: int  # (default value: '')
```

### Connection

As argument you need to provide COM port or url of radio device:

```python
await device.connect(port_or_ip='COM25')
```

### Initialization

If you want to change some of transceiver parameter you need to use next method:

```python
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
```
All not provided arguments will not be changed.

If you need read current configuration you can use next method:

```python
async def read_config(self) -> RadioModel:
```

### Events

You can subscribe on next events:

- received -> LoRaRxPacket | FSK_RX_Packet
- transmited -> LoRaTxPacket | FSK_TX_Packet

When you subscribing on event as argument you need to provide a callback
function which takes argument of classes: `LoRaRxPacket`, `LoRaTxPacket`,
`FSK_RX_Packet`, `FSK_TX_Packet` depending on event name.

You can use events like in next example:
```python
async def on_received(data: LoRaRxPacket | FSK_RX_Packet):
    print(data)

async def on_transmited(data: LoRaTxPacket | FSK_TX_Packet):
    print(data)

device: RadioController = RadioController()
device.received.subscribe(on_received)
device.transmited.subscribe(on_transmited)
```

After subscribing you will see in terminal all received and transmitted packages



### Packets structure

```python
class RadioPacket(BaseModel):
    timestamp: str  # the timestamp of received or transmited package
    data: bytes  # raw data of the radio package
    data_len: int  # len of raw data
    frequency: int  # current frequency of radio transceiver
    caller: str = ''  # the name of function which generated radio package


class LoRaRxPacket(RadioPacket):
    snr: int  # signal to noise ratio of received package
    rssi_pkt: int  # received signal strength indicator of received package
    crc_correct: bool  # status of control sum of received package
    fei: int  # frequency error indicator in Hz
    mode: str = 'LoRa'  # current mode of radio transceiver


class LoRaTxPacket(RadioPacket):
    Tpkt: int  # time on air of transmited radio package
    low_datarate_opt_flag: bool  # low datarate optimization flag
    mode: str = 'LoRa'  # current mode of radio transceiver


class FSK_RX_Packet(RadioPacket):
    rssi_pkt: int  # signal to noise ratio of received package
    crc_correct: bool  # status of control sum of received package
    mode: str = 'FSK'  # current mode of radio transceiver


class FSK_TX_Packet(RadioPacket):
    mode: str = 'FSK'  # current mode of radio transceiver
```

### Sending packages

For sending radio packages you can use next methods:

```python
async def send_single(self, data: bytes,
                      caller_name: str = '') -> LoRaTxPacket | FSK_TX_Packet:
```
The next function will be repeat last message every `period_sec` while counter
of retries less then `max_retries` or while `answer_handler` not return _True_ value.
If `untill_answer` is _False_ the function will repeat message `max_retries` times every `period_sec`. If you want to see name of caller function in received radio
package you need to provide `caller_name` argument.
``` python
ANSWER_CALLBACK = Callable[[LoRaRxPacket | FSK_RX_Packet, Iterable],
                           Awaitable[bool] | bool]

async def send_repeat(self, data: bytes | Callable,
                      period_sec: float,
                      untill_answer: bool = True,
                      max_retries: int = 50,
                      answer_handler: ANSWER_CALLBACK | None = None,
                      handler_args: Iterable = (),
                      caller_name: str = '') -> LoRaRxPacket | FSK_RX_Packet | None:
```

## Example

```python
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
```