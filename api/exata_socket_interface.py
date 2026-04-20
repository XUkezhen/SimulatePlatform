from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
import struct
from typing import Any


class ExataMessageType(IntEnum):
    SIMULATION_STATE = 0
    INITIALIZE_SIMULATION = 1
    PAUSE_SIMULATION = 2
    EXECUTE_SIMULATION = 3
    STOP_SIMULATION = 4
    RESET_SIMULATION = 5
    ADVANCE_TIME = 6
    SIMULATION_IDLE = 7
    DYNAMIC_COMMAND = 8
    DYNAMIC_RESPONSE = 9
    CREATE_PLATFORM = 10
    UPDATE_PLATFORM = 11
    COMM_EFFECTS_REQUEST = 12
    COMM_EFFECTS_RESPONSE = 13
    ERROR = 14
    GET_REQUEST = 15
    GET_RESPONSE = 16
    SET_REQUEST = 17
    GET_NEXT_REQUEST = 18
    GET_BULK_REQUEST = 19
    QUERY_SIMULATION_STATE = 20
    BEGIN_WARMUP = 21
    CUSTOM_LINK_STATE = 22


class ExataSimulationState(IntEnum):
    STANDBY = 1
    INITIALIZED = 2
    PAUSED = 3
    EXECUTING = 4
    RESETTING = 6
    STOPPING = 8
    WARMUP = 10


class ExataRuntimePhase(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    STEPPING = "stepping"
    STOPPING = "stopping"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass(slots=True)
class ExataFrameHeader:
    message_type: int
    num_option_fields: int
    reserved: int
    message_size: int


@dataclass(slots=True)
class ExataParsedMessage:
    header: ExataFrameHeader
    raw: bytes
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    is_standard: bool = True

    @property
    def message_type(self) -> int:
        return self.header.message_type


@dataclass(slots=True)
class ExataRuntimeStateMachine:
    phase: ExataRuntimePhase = ExataRuntimePhase.DISCONNECTED
    last_exata_state: ExataSimulationState | None = None
    last_idle_time: float | None = None
    last_error: str | None = None

    def on_connected(self) -> None:
        self.phase = ExataRuntimePhase.CONNECTED
        self.last_error = None

    def on_disconnected(self) -> None:
        self.phase = ExataRuntimePhase.DISCONNECTED

    def request_pause(self) -> None:
        if self.phase in {
            ExataRuntimePhase.RUNNING,
            ExataRuntimePhase.STEPPING,
            ExataRuntimePhase.INITIALIZED,
        }:
            self.phase = ExataRuntimePhase.PAUSED

    def request_continue(self) -> None:
        if self.phase in {
            ExataRuntimePhase.PAUSED,
            ExataRuntimePhase.CONNECTED,
            ExataRuntimePhase.INITIALIZED,
            ExataRuntimePhase.ERROR,
        }:
            self.phase = ExataRuntimePhase.RUNNING

    def request_step(self) -> None:
        self.phase = ExataRuntimePhase.STEPPING

    def request_stop(self) -> None:
        self.phase = ExataRuntimePhase.STOPPING

    def on_simulation_state(self, state: int) -> None:
        try:
            parsed_state = ExataSimulationState(state)
        except ValueError:
            self.last_error = f"Unknown EXATA simulation state: {state}"
            self.phase = ExataRuntimePhase.ERROR
            return

        self.last_exata_state = parsed_state
        if parsed_state == ExataSimulationState.STANDBY:
            self.phase = ExataRuntimePhase.CONNECTED
        elif parsed_state == ExataSimulationState.INITIALIZED:
            self.phase = ExataRuntimePhase.INITIALIZED
        elif parsed_state == ExataSimulationState.PAUSED:
            self.phase = ExataRuntimePhase.PAUSED
        elif parsed_state in {ExataSimulationState.EXECUTING, ExataSimulationState.WARMUP}:
            if self.phase != ExataRuntimePhase.STEPPING:
                self.phase = ExataRuntimePhase.RUNNING
        elif parsed_state in {ExataSimulationState.RESETTING, ExataSimulationState.STOPPING}:
            self.phase = ExataRuntimePhase.STOPPING

    def on_idle(self, current_time: float) -> None:
        self.last_idle_time = current_time
        if self.phase == ExataRuntimePhase.STEPPING:
            self.phase = ExataRuntimePhase.PAUSED
        elif self.phase in {
            ExataRuntimePhase.CONNECTED,
            ExataRuntimePhase.INITIALIZED,
            ExataRuntimePhase.RUNNING,
        }:
            self.phase = ExataRuntimePhase.RUNNING

    def on_error(self, message: str) -> None:
        self.last_error = message
        self.phase = ExataRuntimePhase.ERROR


def _encode_uint8(value: int) -> bytes:
    return struct.pack(">B", int(value))


def _encode_uint16(value: int) -> bytes:
    return struct.pack(">H", int(value))


def _encode_uint32(value: int) -> bytes:
    return struct.pack(">I", int(value))


def _encode_int8(value: int) -> bytes:
    return struct.pack(">b", int(value))


def _encode_float64(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _encode_string(value: str) -> bytes:
    encoded = str(value).encode("utf-8")
    return _encode_uint16(len(encoded)) + encoded


def _encode_coordinate(x: float, y: float, z: float) -> bytes:
    return _encode_float64(x) + _encode_float64(y) + _encode_float64(z)


def _encode_option(option_type: int, payload: bytes) -> bytes:
    return (
        _encode_uint8(option_type)
        + b"\x00\x00\x00"
        + _encode_uint32(8 + len(payload))
        + payload
    )


def _build_message(message_type: int, required_fields: bytes = b"", options: list[bytes] | None = None) -> bytes:
    options = options or []
    size = 8 + len(required_fields) + sum(len(option) for option in options)
    header = (
        _encode_uint8(message_type)
        + _encode_uint8(len(options))
        + b"\x00\x00"
        + _encode_uint32(size)
    )
    return header + required_fields + b"".join(options)


class ExataProtocolCodec:
    @staticmethod
    def initialize_simulation(
        *,
        time_management_mode: int = 0,
        coordinate_system: int = 1,
    ) -> bytes:
        return _build_message(
            ExataMessageType.INITIALIZE_SIMULATION,
            required_fields=_encode_uint8(time_management_mode),
            options=[_encode_option(0, _encode_uint8(coordinate_system))],
        )

    @staticmethod
    def pause_simulation(pause_time: float | None = None) -> bytes:
        options = []
        if pause_time is not None:
            options.append(_encode_option(2, _encode_float64(pause_time)))
        return _build_message(ExataMessageType.PAUSE_SIMULATION, options=options)

    @staticmethod
    def execute_simulation() -> bytes:
        return _build_message(ExataMessageType.EXECUTE_SIMULATION)

    @staticmethod
    def stop_simulation(stop_time: float | None = None) -> bytes:
        options = []
        if stop_time is not None:
            options.append(_encode_option(2, _encode_float64(stop_time)))
        return _build_message(ExataMessageType.STOP_SIMULATION, options=options)

    @staticmethod
    def query_simulation_state() -> bytes:
        return _build_message(ExataMessageType.QUERY_SIMULATION_STATE)

    @staticmethod
    def advance_time(time_allowance: float) -> bytes:
        return _build_message(
            ExataMessageType.ADVANCE_TIME,
            required_fields=_encode_float64(time_allowance),
        )

    @staticmethod
    def dynamic_command(operation_type: int, path: str, args: str = "") -> bytes:
        return _build_message(
            ExataMessageType.DYNAMIC_COMMAND,
            required_fields=_encode_uint8(operation_type) + _encode_string(path) + _encode_string(args),
        )

    @staticmethod
    def create_platform(
        *,
        entity_id: str,
        lat: float,
        lon: float,
        alt: float,
        damage_state: int = 0,
        create_time: float | None = None,
        platform_type: int | None = None,
    ) -> bytes:
        options: list[bytes] = []
        if create_time is not None:
            options.append(_encode_option(2, _encode_float64(create_time)))
        if platform_type is not None:
            options.append(_encode_option(4, _encode_uint8(platform_type)))
        return _build_message(
            ExataMessageType.CREATE_PLATFORM,
            required_fields=(
                _encode_string(entity_id)
                + _encode_coordinate(lat, lon, alt)
                + _encode_uint8(damage_state)
            ),
            options=options,
        )

    @staticmethod
    def update_platform(
        *,
        entity_id: str,
        update_time: float | None = None,
        position: tuple[float, float, float] | None = None,
        damage_state: int | None = None,
    ) -> bytes:
        options: list[bytes] = []
        if update_time is not None:
            options.append(_encode_option(2, _encode_float64(update_time)))
        if position is not None:
            options.append(_encode_option(6, _encode_coordinate(*position)))
        if damage_state is not None:
            options.append(_encode_option(7, _encode_uint8(damage_state)))
        return _build_message(
            ExataMessageType.UPDATE_PLATFORM,
            required_fields=_encode_string(entity_id),
            options=options,
        )


class _ByteReader:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def remaining(self) -> int:
        return len(self.data) - self.offset

    def read_bytes(self, size: int) -> bytes:
        if self.offset + size > len(self.data):
            raise ValueError(f"Need {size} bytes, only {self.remaining()} available")
        value = self.data[self.offset:self.offset + size]
        self.offset += size
        return value

    def read_uint8(self) -> int:
        return struct.unpack(">B", self.read_bytes(1))[0]

    def read_int8(self) -> int:
        return struct.unpack(">b", self.read_bytes(1))[0]

    def read_uint16(self) -> int:
        return struct.unpack(">H", self.read_bytes(2))[0]

    def read_uint32(self) -> int:
        return struct.unpack(">I", self.read_bytes(4))[0]

    def read_uint64(self) -> int:
        return struct.unpack(">Q", self.read_bytes(8))[0]

    def read_float64(self) -> float:
        return struct.unpack(">d", self.read_bytes(8))[0]

    def read_string(self) -> str:
        size = self.read_uint16()
        return self.read_bytes(size).decode("utf-8")

    def read_string_list(self, count: int) -> list[str]:
        return [self.read_string() for _ in range(count)]


def parse_exata_stream(buffer: bytes) -> tuple[list[bytes], bytes]:
    messages: list[bytes] = []
    offset = 0
    while len(buffer) - offset >= 8:
        message_size = struct.unpack(">I", buffer[offset + 4: offset + 8])[0]
        if message_size < 8:
            raise ValueError(f"Invalid EXATA message size: {message_size}")
        if len(buffer) - offset < message_size:
            break
        messages.append(buffer[offset: offset + message_size])
        offset += message_size
    return messages, buffer[offset:]


def decode_exata_message(raw: bytes) -> ExataParsedMessage:
    if len(raw) < 8:
        raise ValueError("EXATA message is shorter than header size")

    header = ExataFrameHeader(
        message_type=raw[0],
        num_option_fields=raw[1],
        reserved=struct.unpack(">H", raw[2:4])[0],
        message_size=struct.unpack(">I", raw[4:8])[0],
    )
    body = raw[8:]
    if header.message_size != len(raw):
        raise ValueError(
            f"EXATA header size mismatch: header={header.message_size}, actual={len(raw)}"
        )

    if header.message_type == ExataMessageType.CUSTOM_LINK_STATE:
        return _decode_custom_link_state(header, raw, body)

    decoded = ExataParsedMessage(
        header=header,
        raw=raw,
        name=ExataMessageType(header.message_type).name
        if header.message_type in ExataMessageType._value2member_map_
        else f"UNKNOWN_{header.message_type}",
        payload={},
        errors=[],
        is_standard=header.message_type in ExataMessageType._value2member_map_,
    )

    if not decoded.is_standard:
        decoded.payload["body_hex"] = body.hex()
        return decoded

    reader = _ByteReader(body)
    try:
        if header.message_type == ExataMessageType.SIMULATION_STATE:
            decoded.payload["state"] = reader.read_uint8()
            decoded.payload["old_state"] = reader.read_uint8()
        elif header.message_type == ExataMessageType.SIMULATION_IDLE:
            decoded.payload["current_time"] = reader.read_float64()
        elif header.message_type == ExataMessageType.DYNAMIC_RESPONSE:
            decoded.payload["operation_type"] = reader.read_uint8()
            decoded.payload["path"] = reader.read_string()
            decoded.payload["args"] = reader.read_string()
            decoded.payload["output"] = reader.read_string()
        elif header.message_type == ExataMessageType.COMM_EFFECTS_RESPONSE:
            decoded.payload["id1"] = reader.read_uint64()
            decoded.payload["id2"] = reader.read_uint64()
            decoded.payload["sender_id"] = reader.read_string()
            decoded.payload["receiver_id"] = reader.read_string()
            decoded.payload["status"] = reader.read_int8()
            decoded.payload["receive_time"] = reader.read_float64()
            decoded.payload["latency"] = reader.read_float64()
        elif header.message_type == ExataMessageType.ERROR:
            decoded.payload["code"] = reader.read_uint8()
            decoded.payload["error"] = reader.read_string()
            decoded.payload["remaining_bytes_hex"] = reader.read_bytes(reader.remaining()).hex()
        elif header.message_type == ExataMessageType.GET_RESPONSE:
            decoded.payload["entity_id"] = reader.read_string()
            num_oids = reader.read_uint16()
            decoded.payload["num_oids"] = num_oids
            decoded.payload["oids"] = reader.read_string_list(num_oids)
            decoded.payload["outputs"] = reader.read_string_list(num_oids)
            decoded.payload["error_status"] = list(reader.read_bytes(num_oids))
        else:
            decoded.payload["body_hex"] = body.hex()
    except Exception as exc:  # pragma: no cover
        decoded.errors.append(str(exc))
        decoded.payload["body_hex"] = body.hex()

    return decoded


def _decode_custom_link_state(
    header: ExataFrameHeader,
    raw: bytes,
    body: bytes,
) -> ExataParsedMessage:
    decoded = ExataParsedMessage(
        header=header,
        raw=raw,
        name="CUSTOM_LINK_STATE",
        payload={},
        errors=[],
        is_standard=False,
    )
    reader = _ByteReader(body)
    try:
        text = reader.read_string()
        decoded.payload["text"] = text
        split_values = text.split()
        decoded.payload["fields"] = split_values
        if len(split_values) < 6:
            decoded.errors.append(
                f"Incomplete link-state payload, expected at least 6 fields but got {len(split_values)}"
            )
            return decoded

        base_payload = {
            "source_satellite_id": split_values[0],
            "destination_satellite_id": split_values[1],
            "source_satellite_interface": split_values[2],
            "destination_satellite_interface": split_values[3],
            "time": split_values[4],
        }

        if split_values[5] == "0":
            decoded.payload["link_state"] = {
                **base_payload,
                "type": "network_layer",
            }
        else:
            app_metadata_missing = len(split_values) < 9
            if app_metadata_missing:
                decoded.errors.append(
                    f"Application-layer payload missing app metadata, got {len(split_values)} fields"
                )
            decoded.payload["link_state"] = {
                **base_payload,
                "type": "application_layer",
                "app_id": split_values[6] if len(split_values) > 6 else None,
                "app_source_id": split_values[7] if len(split_values) > 7 else None,
                "app_des_id": split_values[8] if len(split_values) > 8 else None,
                "app_metadata_missing": app_metadata_missing,
            }
    except Exception as exc:
        decoded.errors.append(str(exc))
        decoded.payload["body_hex"] = body.hex()
    return decoded
