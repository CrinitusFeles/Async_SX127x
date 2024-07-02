from __future__ import annotations
from aioserial import AioSerial
from serial import serialutil
from loguru import logger

from async_sx127x.interfaces.base_interface import BaseInterface


class SerialInterface(BaseInterface):
    async def connect(self, port: str) -> bool:
        if self.connection_status:
            return True
        try:
            self._interface: AioSerial = AioSerial(port=port, baudrate=500000,
                                                   timeout=1, write_timeout=1)
            self._read = self._interface.read_async
            self._write = self._interface.write_async
            self._interface.dtr = False
            await self._interface.write_async(bytes([6]))
            await self._interface.read_async(1)
            if self._interface.is_open:
                self.connection_status = True
                return True
            raise ConnectionError(f"Can\'t connect to {port}. Probably device is busy")
        except serialutil.SerialException as err:
            logger.error(err)
            return False

    def disconnect(self) -> bool:
        if self.connection_status:
            self._interface.close()
            self.connection_status = False
            return not self._interface.is_open
        return True

    async def _try_read(self, amount: int = 1) -> bytes:  # type: ignore
        try:
            return await super()._try_read(amount)
        except serialutil.SerialException as exc:
            logger.error(exc)

if __name__ == '__main__':
    ser: SerialInterface = SerialInterface()
    print(ser.connect('COM3'))
