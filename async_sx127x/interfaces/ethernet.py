from __future__ import annotations
import socket
from loguru import logger

from async_sx127x.interfaces.base_interface import BaseInterface


class EthernetInterface(BaseInterface):
    def connect(self, ip: str) -> bool:
        if self.connection_status:
            return True
        try:
            self._interface: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._read = self._interface.recv
            self._write = self._interface.send
            self._interface.settimeout(2)
            try:
                self._interface.connect((ip, 80))
            except ConnectionRefusedError:
                logger.error('Radio connected in another thread! Connection refused')
                return False
            self.connection_status = True
            return True
        except TimeoutError:
            logger.error('Radio connectoin timeout!')
            return False

    def disconnect(self) -> bool:
        if self.connection_status:
            self._interface.close()
            self.connection_status = False
            return True
        return False


if __name__ == '__main__':
    ser: EthernetInterface = EthernetInterface()
    logger.debug(ser.connect('10.6.1.99'))
