#!/usr/bin/env python3

import json
import logging
import os
import socketserver
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

try:
    import paho.mqtt.client as mqtt
except ImportError:  # optional dependency
    mqtt = None


HEADER_LEN = 11
FOOTER_LEN = 2
PACKET_MIN_LEN = HEADER_LEN + FOOTER_LEN
MAX_BUFFER_SIZE = 256 * 1024
RECV_BUFFER_SIZE = 4096

REQUEST_TYPE_HANDSHAKE = 0x41
REQUEST_TYPE_DATA = 0x42
REQUEST_TYPE_WIFI = 0x43
REQUEST_TYPE_HEARTBEAT = 0x47

DATA_SCHEMA_MICROINVERTER = 0x08
TOPIC_PREFIX = "deye-dummycloud"


def _truncate_at_null(data: bytes) -> str:
    return data.split(b"\0", 1)[0].decode("ascii", errors="ignore")


def _read_u16_le(buf: bytes, offset: int) -> int:
    if offset + 2 > len(buf):
        return 0
    return int.from_bytes(buf[offset:offset + 2], "little")


def _read_u16_be(buf: bytes, offset: int) -> int:
    if offset + 2 > len(buf):
        return 0
    return int.from_bytes(buf[offset:offset + 2], "big")


def _read_u32_le(buf: bytes, offset: int) -> int:
    if offset + 4 > len(buf):
        return 0
    return int.from_bytes(buf[offset:offset + 4], "little")


def _read_i16_le(buf: bytes, offset: int) -> int:
    if offset + 2 > len(buf):
        return 0
    return int.from_bytes(buf[offset:offset + 2], "little", signed=True)


def packet_checksum(packet: bytes) -> int:
    return sum(packet[1:-2]) & 0xFF


@dataclass
class PacketHeader:
    magic: int
    payload_length: int
    unknown1: int
    msg_type: int
    msg_id_response: int
    msg_id_request: int
    logger_serial: int


def parse_header(packet: bytes) -> PacketHeader:
    if len(packet) < PACKET_MIN_LEN:
        raise ValueError("Packet too short")
    if packet[0] != 0xA5:
        raise ValueError(f"Invalid header magic {packet[0]:#x}")

    payload_length = int.from_bytes(packet[1:3], "little")
    expected_len = HEADER_LEN + payload_length + FOOTER_LEN
    if expected_len != len(packet):
        raise ValueError("Packet length mismatch")

    if packet[-1] != 0x15:
        raise ValueError(f"Invalid footer magic {packet[-1]:#x}")

    expected_checksum = packet_checksum(packet)
    if packet[-2] != expected_checksum:
        raise ValueError(
            f"Invalid checksum {packet[-2]:#x}, expected {expected_checksum:#x}"
        )

    return PacketHeader(
        magic=packet[0],
        payload_length=payload_length,
        unknown1=packet[3],
        msg_type=packet[4],
        msg_id_response=packet[5],
        msg_id_request=packet[6],
        logger_serial=int.from_bytes(packet[7:11], "little"),
    )


def build_time_response(header: PacketHeader, payload: bytes) -> bytes:
    response = bytearray(23)

    response[0] = 0xA5
    response[1:3] = (10).to_bytes(2, "little")
    response[3] = header.unknown1
    response[4] = (header.msg_type - 0x30) & 0xFF
    response[5] = (header.msg_id_response + 1) & 0xFF
    response[6] = header.msg_id_request
    response[7:11] = header.logger_serial.to_bytes(4, "little")

    response[11] = payload[0] if payload else 0
    response[12] = 0x01
    response[13:17] = int(time.time()).to_bytes(4, "little")
    response[17:21] = (0).to_bytes(4, "little")

    response[-2] = packet_checksum(response)
    response[-1] = 0x15

    return bytes(response)


def parse_logger_payload(payload: bytes) -> Dict[str, str]:
    return {
        "fw_ver": _truncate_at_null(payload[19:60]),
        "ip": _truncate_at_null(payload[65:82]),
        "ver": _truncate_at_null(payload[89:130]),
        "ssid": _truncate_at_null(payload[172:210]),
    }


def parse_microinverter_payload(payload: bytes) -> Optional[Dict[str, Any]]:
    if len(payload) < 2:
        return None

    if payload[0] & 0b10000000:
        return None

    pv = {}
    for idx, base in enumerate([85, 89, 93, 97], start=1):
        v = _read_u16_le(payload, base) / 10
        i = _read_u16_le(payload, base + 2) / 10
        pv[str(idx)] = {
            "v": v,
            "i": i,
            "w": round(v * i, 2),
            "kWh_today": _read_u16_le(payload, 134 + idx * 2) / 10,
            "kWh_total": _read_u16_be(payload, 141 + idx * 4) / 10,
        }

    return {
        "pv": pv,
        "grid": {
            "active_power_w": _read_u32_le(payload, 59),
            "kWh_today": _read_u32_le(payload, 33) / 100,
            "kWh_total": _read_u32_le(payload, 37) / 10,
            "v": _read_u16_le(payload, 45) / 10,
            "i": _read_u16_le(payload, 51) / 10,
            "hz": _read_u16_le(payload, 57) / 100,
        },
        "inverter": {
            "radiator_temp_celsius": _read_i16_le(payload, 63) / 100,
        },
        "inverter_meta": {
            "rated_power_w": _read_u16_be(payload, 129) / 10,
            "mppt_count": payload[131] if len(payload) > 131 else 0,
            "phase_count": payload[132] if len(payload) > 132 else 0,
            "protocol_ver": payload[101:109].decode("ascii", errors="ignore"),
            "dc_master_fw_ver": payload[109:117].decode("ascii", errors="ignore"),
            "ac_fw_ver": payload[117:125].decode("ascii", errors="ignore"),
        },
    }


def parse_data_payload(payload: bytes) -> Optional[Dict[str, Any]]:
    if len(payload) < 2:
        return None
    if payload[1] != DATA_SCHEMA_MICROINVERTER:
        return None
    return parse_microinverter_payload(payload)


class MqttPublisher:
    def __init__(self, broker_url: Optional[str], username: Optional[str], password: Optional[str]):
        self._client = None
        if not broker_url:
            return

        if mqtt is None:
            logging.warning("MQTT broker configured but paho-mqtt is not installed")
            return

        client_id = f"deye_dummycloud_{int(time.time())}"
        if hasattr(mqtt, "CallbackAPIVersion"):
            self._client = mqtt.Client(
                client_id=client_id,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
            )
        else:
            self._client = mqtt.Client(client_id=client_id)
        if username:
            self._client.username_pw_set(
                username,
                password,
            )
        self._client.connect(*self._parse_broker_url(broker_url))
        self._client.loop_start()
        logging.info("Connected to MQTT broker %s", broker_url)

    @staticmethod
    def _parse_broker_url(url: str):
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 1883
        return host, port, 60

    def publish_packet(self, logger_serial: int, payload: Dict[str, Any]) -> None:
        if self._client is None:
            return

        base_topic = f"{TOPIC_PREFIX}/{logger_serial}"
        self._client.publish(f"{base_topic}/raw", json.dumps(payload))

        pv = payload.get("pv", {})
        for idx, values in pv.items():
            self._client.publish(f"{base_topic}/pv/{idx}/v", str(values.get("v", 0)))
            self._client.publish(f"{base_topic}/pv/{idx}/i", str(values.get("i", 0)))
            self._client.publish(f"{base_topic}/pv/{idx}/w", str(values.get("w", 0)))
            self._client.publish(f"{base_topic}/pv/{idx}/kWh_today", str(values.get("kWh_today", 0)), retain=True)
            if values.get("kWh_total", 0) > 0:
                self._client.publish(f"{base_topic}/pv/{idx}/kWh_total", str(values["kWh_total"]), retain=True)

        grid = payload.get("grid", {})
        self._client.publish(f"{base_topic}/grid/active_power_w", str(grid.get("active_power_w", 0)))
        self._client.publish(f"{base_topic}/grid/kWh_today", str(grid.get("kWh_today", 0)), retain=True)
        if grid.get("kWh_total", 0) > 0:
            self._client.publish(f"{base_topic}/grid/kWh_total", str(grid["kWh_total"]), retain=True)
        self._client.publish(f"{base_topic}/grid/v", str(grid.get("v", 0)))
        self._client.publish(f"{base_topic}/grid/hz", str(grid.get("hz", 0)))


class DeyeDummyCloudTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, mqtt_publisher: MqttPublisher):
        super().__init__(server_address, handler_class)
        self.mqtt_publisher = mqtt_publisher


class DeyeConnectionHandler(socketserver.BaseRequestHandler):
    def handle(self):
        remote = f"{self.client_address[0]}:{self.client_address[1]}"
        logging.info("New connection from %s", remote)

        buffer = bytearray()
        while True:
            data = self.request.recv(RECV_BUFFER_SIZE)
            if not data:
                break
            buffer.extend(data)
            if len(buffer) > MAX_BUFFER_SIZE:
                logging.warning("Closing connection %s due to buffer overflow", remote)
                return

            while True:
                if len(buffer) < PACKET_MIN_LEN:
                    break

                if buffer[0] != 0xA5:
                    next_magic = buffer.find(0xA5, 1)
                    if next_magic == -1:
                        buffer.clear()
                        break
                    del buffer[:next_magic]
                    continue

                payload_len = int.from_bytes(buffer[1:3], "little")
                packet_len = HEADER_LEN + payload_len + FOOTER_LEN
                if len(buffer) < packet_len:
                    break

                packet = bytes(buffer[:packet_len])
                del buffer[:packet_len]
                self.process_packet(packet, remote)

        logging.info("Connection closed for %s", remote)

    def process_packet(self, packet: bytes, remote: str):
        try:
            header = parse_header(packet)
            payload = packet[HEADER_LEN:-FOOTER_LEN]
            msg_type = header.msg_type

            if msg_type == REQUEST_TYPE_HANDSHAKE:
                logger_data = parse_logger_payload(payload)
                logging.info("Handshake from %s logger=%s data=%s", remote, header.logger_serial, logger_data)
            elif msg_type == REQUEST_TYPE_DATA:
                parsed_data = parse_data_payload(payload)
                if parsed_data:
                    logging.info(
                        "Data from %s logger=%s grid_w=%s",
                        remote,
                        header.logger_serial,
                        parsed_data.get("grid", {}).get("active_power_w"),
                    )
                    self.server.mqtt_publisher.publish_packet(header.logger_serial, parsed_data)
            elif msg_type in (REQUEST_TYPE_WIFI, REQUEST_TYPE_HEARTBEAT):
                logging.debug("Packet type 0x%x from logger=%s", msg_type, header.logger_serial)
            else:
                logging.debug("Unknown packet type 0x%x from logger=%s", msg_type, header.logger_serial)

            self.request.sendall(build_time_response(header, payload))
        except Exception as exc:
            logging.warning("Failed to process packet from %s: %s", remote, exc)


def main():
    valid_levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    configured_loglevel = os.getenv("LOGLEVEL", "INFO").upper()
    warning_message = None
    if configured_loglevel in valid_levels:
        effective_loglevel_name = configured_loglevel
    else:
        effective_loglevel_name = "INFO"
        warning_message = f"Invalid LOGLEVEL '{configured_loglevel}', falling back to INFO"

    loglevel = valid_levels[effective_loglevel_name]
    logging.basicConfig(
        level=loglevel,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
    )
    if warning_message:
        logging.warning(warning_message)

    host = os.getenv("BIND_HOST", "127.0.0.1")
    port_value = os.getenv("PORT", "10000")
    try:
        port = int(port_value)
    except ValueError as exc:
        raise ValueError(f"Invalid PORT value '{port_value}'. Expected an integer.") from exc
    mqtt_publisher = MqttPublisher(
        broker_url=os.getenv("MQTT_BROKER_URL"),
        username=os.getenv("MQTT_USERNAME"),
        password=os.getenv("MQTT_PASSWORD"),
    )

    with DeyeDummyCloudTCPServer((host, port), DeyeConnectionHandler, mqtt_publisher) as server:
        logging.info("Starting deye dummycloud on %s:%s", host, port)
        server.serve_forever()


if __name__ == "__main__":
    main()
