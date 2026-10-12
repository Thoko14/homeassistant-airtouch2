"""Robust reading of AirTouch 2 status messages.

The airtouch2 library reads status messages as fixed blocks of 395 bytes and
never checks where a message starts. If a single byte is lost or extra (for
example after a reconnect mid-message), every following read is shifted and
the data is garbage. Parsing that garbage can raise an error such as
"72 is not a valid ACMode", which ends the library's listening task. The
connection then stays open, but nothing is read any more: Home Assistant
shows a frozen state and commands seem to do nothing.

According to the protocol notes in the library repository
(re_response/airtouch2_protocol.pdf), every status message starts with the
bytes 0x91 0xFA and ends with a checksum: the sum of the previous 394 bytes
modulo 256.

This module patches At2Client so that:
- reading starts at the next 0x91 0xFA, skipping anything before it, which
  brings a shifted stream back in step;
- a message whose checksum does not match is logged (and still parsed, until
  the checksum rule is confirmed on real hardware);
- a message that cannot be parsed is logged and skipped instead of ending the
  listening task.
"""
from __future__ import annotations

import asyncio
import logging

from airtouch2.at2.At2Client import At2Client
from airtouch2.protocol.at2.constants import MessageLength
from airtouch2.protocol.at2.messages import SystemInfo

_LOGGER = logging.getLogger(__name__)

HEADER = b"\x91\xfa"
_PATCHED_FLAG = "_airtouch2_message_fix_applied"
_warned_checksum = False


def checksum_ok(message: bytes) -> bool:
    """True if the last byte is the sum of the others modulo 256."""
    return sum(message[:-1]) % 256 == message[-1]


async def read_message(client) -> bytes | None:
    """Read one complete status message, starting at the header.

    Returns None when the connection was lost (the library has already
    reconnected by then).
    """
    skipped = 0
    previous = None
    while True:
        byte = await client.read_bytes(1)
        if byte is None:
            return None
        if previous == HEADER[0] and byte[0] == HEADER[1]:
            break
        if previous is not None:
            skipped += 1
        previous = byte[0]
    if skipped:
        _LOGGER.warning(
            "Skipped %d bytes to find the start of the next AirTouch message", skipped
        )
    rest = await client.read_bytes(MessageLength.RESPONSE - len(HEADER))
    if rest is None:
        return None
    return HEADER + rest


def apply() -> None:
    """Patch At2Client once per Home Assistant run."""
    if getattr(At2Client, _PATCHED_FLAG, False):
        return

    original_handle = At2Client._handle_one_message

    async def _read_response(self: At2Client) -> SystemInfo | None:
        global _warned_checksum
        message = await read_message(self._client)
        if message is None:
            return None
        if not checksum_ok(message) and not _warned_checksum:
            _warned_checksum = True
            _LOGGER.warning(
                "AirTouch message checksum does not match (reported once); "
                "parsing it anyway"
            )
        try:
            return SystemInfo.from_bytes(message)
        except Exception as err:  # noqa: BLE001 - keep listening whatever the data
            _LOGGER.warning(
                "Skipped an AirTouch message that could not be read: %s (first bytes %s)",
                err,
                message[:8].hex(":"),
            )
            return None

    async def _handle_one_message(self: At2Client) -> None:
        try:
            await original_handle(self)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - one bad message must not stop the listener
            _LOGGER.exception("Error while handling an AirTouch message; continuing")
            await asyncio.sleep(1)

    At2Client._read_response = _read_response
    At2Client._handle_one_message = _handle_one_message
    setattr(At2Client, _PATCHED_FLAG, True)
    _LOGGER.debug("Applied airtouch2 message fix")
