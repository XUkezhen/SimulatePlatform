import struct
import unittest

from api.exata_socket_interface import (
    ExataMessageType,
    ExataProtocolCodec,
    decode_exata_message,
    parse_exata_stream,
)


def build_custom_link_state_message(text: str) -> bytes:
    payload = text.encode("utf-8")
    body = struct.pack(">H", len(payload)) + payload
    size = 8 + len(body)
    header = struct.pack(">BBHI", ExataMessageType.CUSTOM_LINK_STATE, 0, 0, size)
    return header + body


class ExataSocketInterfaceTests(unittest.TestCase):
    def test_parse_exata_stream_handles_single_frame(self):
        raw = ExataProtocolCodec.execute_simulation()
        frames, remaining = parse_exata_stream(raw)

        self.assertEqual(frames, [raw])
        self.assertEqual(remaining, b"")

    def test_parse_exata_stream_handles_sticky_and_partial_frames(self):
        first = ExataProtocolCodec.execute_simulation()
        second = ExataProtocolCodec.query_simulation_state()
        combined = first + second[:-2]

        frames, remaining = parse_exata_stream(combined)

        self.assertEqual(frames, [first])
        self.assertEqual(remaining, second[:-2])

        replay_frames, replay_remaining = parse_exata_stream(remaining + second[-2:])
        self.assertEqual(replay_frames, [second])
        self.assertEqual(replay_remaining, b"")

    def test_decode_simulation_idle(self):
        body = struct.pack(">d", 12.5)
        raw = struct.pack(">BBHI", ExataMessageType.SIMULATION_IDLE, 0, 0, 8 + len(body)) + body

        message = decode_exata_message(raw)

        self.assertEqual(message.message_type, ExataMessageType.SIMULATION_IDLE)
        self.assertEqual(message.payload["current_time"], 12.5)

    def test_decode_simulation_state(self):
        body = struct.pack(">BB", 2, 1)
        raw = struct.pack(">BBHI", ExataMessageType.SIMULATION_STATE, 0, 0, 8 + len(body)) + body

        message = decode_exata_message(raw)

        self.assertEqual(message.message_type, ExataMessageType.SIMULATION_STATE)
        self.assertEqual(message.payload["state"], 2)
        self.assertEqual(message.payload["old_state"], 1)

    def test_decode_network_layer_custom_link_state(self):
        raw = build_custom_link_state_message("1 2 3 4 5 0")

        message = decode_exata_message(raw)

        self.assertEqual(message.payload["link_state"]["type"], "network_layer")
        self.assertFalse(message.errors)

    def test_decode_application_layer_custom_link_state_with_full_metadata(self):
        raw = build_custom_link_state_message("1 2 3 4 5 1 app src dst")

        message = decode_exata_message(raw)
        link_state = message.payload["link_state"]

        self.assertEqual(link_state["type"], "application_layer")
        self.assertEqual(link_state["app_id"], "app")
        self.assertEqual(link_state["app_source_id"], "src")
        self.assertEqual(link_state["app_des_id"], "dst")
        self.assertFalse(link_state["app_metadata_missing"])

    def test_decode_application_layer_custom_link_state_with_missing_metadata(self):
        raw = build_custom_link_state_message("1 2 3 4 5 1")

        message = decode_exata_message(raw)
        link_state = message.payload["link_state"]

        self.assertEqual(link_state["type"], "application_layer")
        self.assertIsNone(link_state["app_id"])
        self.assertIsNone(link_state["app_source_id"])
        self.assertIsNone(link_state["app_des_id"])
        self.assertTrue(link_state["app_metadata_missing"])
        self.assertTrue(message.errors)


if __name__ == "__main__":
    unittest.main()
