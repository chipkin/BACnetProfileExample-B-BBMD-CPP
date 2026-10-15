# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""What B-BBMD's wire tests share: this example's numbers, starting it, and the
BBMD-specific encodings the shared harness does not know about.

Everything runs on one host. Each example instance is a BBMD on its own UDP port; its
own BDT entry is the host's LAN address (the address the example reads from the
network adapter and reports as its Network Port IP_Address). Python Peers - foreign
devices and stand-in peer BBMDs - are plain UDP sockets (wiretest.Endpoint).

    foreign device F1   LAN-IP : ephemeral   registered with A
    BBMD A              LAN-IP : --port       BACnetExampleBBBMD  BDT: A, B (+ Python peers)
    BBMD B              LAN-IP : --port + 1   BACnetExampleBBBMD  BDT: B, A
    foreign device F2   LAN-IP : ephemeral   registered with B

WHY THE PEER ENTRIES SAY 127.0.0.1. Annex J.4.5 tells a BBMD that a Forwarded-NPDU
from a source "on the same IP subnet" was already heard by every device there, and the
stack decides "same subnet" from the sender's IP alone (its own BDT mask, all 1's here).
Two BBMDs on one host share one IP, so an A -> B Forwarded-NPDU sent to the LAN address
would look local to B. Listing each peer at 127.0.0.1:<its port> makes the datagram
arrive from 127.0.0.1 - a genuinely different source address on the same machine - so
B handles it exactly as it would a peer on another subnet. See README "Wire Tests".
"""
import argparse
import re
import socket
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))

import wiretest  # noqa: E402  (the vendored harness at the repository root)

# Match main.cpp.
NETWORK_PORT_INSTANCE = 1
PROPERTY_BACNET_IP_MODE = 408
PROPERTY_BBMD_BROADCAST_DISTRIBUTION_TABLE = 414
PROPERTY_CHANGES_PENDING = 416
BACNET_IP_MODE_NORMAL = 0
BACNET_IP_MODE_BBMD = 2
TWO_HOP_MASK = "255.255.255.255"
LOOPBACK = "127.0.0.1"

# The example prints its BDT at start-up; entry [0] is itself, e.g.
#       [0] 192.168.3.64:47900  mask 255.255.255.255   <- this device
OWN_ENTRY = re.compile(r"\[0\] (\d+\.\d+\.\d+\.\d+):(\d+)\s+mask (\S+)\s+<- this device")

# Foreign-device registration lifetime used unless a test needs another one: well inside
# the 30 s - 9 h range K.6.6 requires a BBMD to support.
TIME_TO_LIVE = 300


def parser(description):
    arguments = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    arguments.add_argument("--exe", default=str(wiretest.default_exe(REPOSITORY, "BACnetExampleBBBMD")),
                           help="path to BACnetExampleBBBMD (default: build/BACnetExampleBBBMD)")
    arguments.add_argument("--port", type=int, default=47900,
                           help="first UDP port; each script uses a few above it (default 47900)")
    return arguments


class Bbmd:
    """One running BACnetExampleBBBMD and the address it says it has."""

    def __init__(self, program, port):
        self.program = program
        self.port = port
        found = OWN_ENTRY.search(program.output())
        self.ip = found.group(1) if found else None

    @property
    def mac(self):
        return wiretest.mac(self.ip, self.port)

    def stop(self):
        self.program.stop()


def start_bbmd(args, port, device_instance, peers=(), label="bbmd", extra=()):
    """Start the example on `port` with one --bdt per (ip, port) in `peers` (two-hop)."""
    arguments = ["--port", port, "--deviceID", device_instance]
    for peer_ip, peer_port in peers:
        arguments += ["--bdt", f"{peer_ip}:{peer_port}"]
    arguments += list(extra)
    bbmd = Bbmd(wiretest.start(args.exe, arguments, label), port)
    if bbmd.ip is None:
        # Not a BBMD (--no-bbmd, or a broken build): carry on with the address the OS would
        # use, so the wire checks themselves report what is missing.
        bbmd.ip = outbound_ipv4()
        if "--no-bbmd" not in extra:
            print(f"      ({label} printed no '<- this device' BDT line; using {bbmd.ip})")
    return bbmd


def outbound_ipv4():
    """The local IPv4 address the OS picks for an outbound datagram (connect() on UDP sends nothing)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 47808))   # RFC 5737 TEST-NET-1: never reached
        return probe.getsockname()[0]
    finally:
        probe.close()


def foreign_device(bbmd):
    """A Python foreign device: a UDP socket on the host's LAN address, ephemeral port. It is a
    wiretest.Client, so it can also send confirmed requests (ReadProperty, WriteProperty,
    ReinitializeDevice), retried with the same invoke id while unanswered."""
    return client_on(bbmd.ip)


def client_on(ip):
    return wiretest.Client(bind_ip=ip, retries=ATTEMPTS - 1)


# UDP is lossy, and on Windows the example's own socket misses a fifth or more of what it
# is sent (measured; common/'s receive loop polls with a 10 ms SO_RCVTIMEO - see TODO.md).
# So a request that gets NO answer is asked again, as a real client would; every message
# asked more than once here is harmless to repeat. A check that
# something does NOT arrive always has a positive control in the same exchange, so a lost
# datagram cannot make it pass.
ATTEMPTS = 5


def exchange(endpoint, bbmd, message, predicate, seconds=1):
    """Send `message` to `bbmd` and return the first answer matching `predicate`, asking up to
    ATTEMPTS times while nothing comes back; None if it never does."""
    for _ in range(ATTEMPTS):
        endpoint.clear()
        endpoint.send(message, bbmd.port, ip=bbmd.ip)
        answer = endpoint.wait_for(predicate, seconds)
        if answer:
            return answer
    return None


def request_result(endpoint, bbmd, message):
    """The BVLC-Result code (Annex J.2.1) `bbmd` answers `message` with, or None."""
    answer = exchange(endpoint, bbmd, message,
                      lambda frame: frame.result_code is not None and frame.source[1] == bbmd.port)
    return answer.result_code if answer else None


def register(endpoint, bbmd, time_to_live=TIME_TO_LIVE):
    """Register-Foreign-Device (J.5.2.2); the BVLC-Result code, or None. Registering again is
    harmless - J.5.2.3 just restarts the timer."""
    return request_result(endpoint, bbmd, wiretest.register_foreign_device(time_to_live))


def read_fdt(endpoint, bbmd):
    """Read-Foreign-Device-Table (J.5.2.1.1): [(address, TTL, remaining)], or the answer frame if not an Ack."""
    answer = exchange(endpoint, bbmd, wiretest.read_foreign_device_table(),
                      lambda frame: frame.source[1] == bbmd.port and not frame.has_npdu)
    return answer.fdt_entries() if answer and answer.fdt_entries() is not None else answer


def read_bdt(endpoint, bbmd):
    """Read-Broadcast-Distribution-Table (J.4.4.1): [(address, mask)], or the answer frame if not an Ack."""
    answer = exchange(endpoint, bbmd, wiretest.read_broadcast_distribution_table(),
                      lambda frame: frame.source[1] == bbmd.port and not frame.has_npdu)
    return answer.bdt_entries() if answer and answer.bdt_entries() is not None else answer


def broadcast(sender, bbmd, receivers, seconds=2):
    """`sender` (a registered foreign device) broadcasts a Who-Is through `bbmd`
    (Distribute-Broadcast-To-Network, J.2.10). Returns, for each of `receivers`, the
    Forwarded-NPDU it got carrying that Who-Is, or None. Sent again (up to ATTEMPTS times)
    while any receiver is still waiting - a repeated Who-Is is harmless."""
    for receiver in receivers:
        receiver.clear()
    found = [None] * len(receivers)
    for _ in range(ATTEMPTS):
        sender.send(wiretest.distribute_broadcast_to_network(who_is_npdu()), bbmd.port, ip=bbmd.ip)
        for index, receiver in enumerate(receivers):
            if found[index] is None:
                found[index] = receiver.wait_for(lambda frame: is_forwarded_who_is(frame, sender.mac),
                                                 seconds if index == 0 else 0.5)
        if all(found):
            break
    return found


def who_is_npdu():
    return wiretest.npdu(wiretest.who_is())


def is_forwarded_who_is(frame, originating_mac):
    """A Forwarded-NPDU (J.2.5) carrying a Who-Is that `originating_mac` broadcast."""
    return (frame.bvlc_function == wiretest.BVLC_FORWARDED_NPDU and frame.originating_mac == originating_mac
            and frame.pdu_type == wiretest.PDU_UNCONFIRMED_REQUEST and frame.service == wiretest.SERVICE_WHO_IS)


def i_am_instance(frame):
    """The device instance an I-Am announces, else None."""
    return wiretest.i_am_device_instance(frame.payload) if frame.has_npdu else None


def bdt_entry(ip, port, mask=TWO_HOP_MASK):
    """One BACnetBDTEntry (cl. 21) for a WriteProperty of BBMD_Broadcast_Distribution_Table:
    bbmd-address [0] BACnetHostNPort { host [0] { ip-address [1] }, port [1] }, broadcast-mask [1]."""
    return (wiretest.opening(0) +
            wiretest.opening(0) + wiretest.context_octet_string(1, socket.inet_aton(ip)) + wiretest.closing(0) +
            wiretest.context_unsigned(1, port) +
            wiretest.closing(0) +
            wiretest.context_octet_string(1, socket.inet_aton(mask)))


def parse_bdt_property(value):
    """A BBMD_Broadcast_Distribution_Table value (BACnetLIST of BACnetBDTEntry) as [(address, mask)]."""
    entries = []
    depth = 0
    ip = port = None
    position = 0
    while position < len(value):
        number, is_context, kind, body, position = wiretest.read_tag(value, position)
        if kind == "open":
            depth += 1
        elif kind == "close":
            depth -= 1
        elif is_context and number == 1 and depth == 2 and len(body) == 4:
            ip = socket.inet_ntoa(body)
        elif is_context and number == 1 and depth == 1:
            port = int.from_bytes(body, "big")
        elif is_context and number == 1 and depth == 0:
            entries.append((f"{ip}:{port}", socket.inet_ntoa(body)))
    return entries


def read_property(client, bbmd, property_identifier):
    """ReadProperty of Network Port 1 (a wiretest.Client); returns (value octets or None, the answer frame or None)."""
    answer = client.read_property(bbmd.port, wiretest.OBJECT_TYPE_NETWORK_PORT, NETWORK_PORT_INSTANCE,
                                  property_identifier, ip=bbmd.ip, timeout=1)
    return answer.value_octets, answer.frame


def write_property(client, bbmd, property_identifier, value_octets):
    """WriteProperty of Network Port 1 (a wiretest.Client); returns the answer frame or None."""
    return client.write_property(bbmd.port, wiretest.OBJECT_TYPE_NETWORK_PORT, NETWORK_PORT_INSTANCE,
                                 property_identifier, value_octets, ip=bbmd.ip, timeout=1).frame


def reinitialize_device(client, bbmd, state):
    """ReinitializeDevice (cl. 16.4) with no password; returns the answer frame or None."""
    return client.request(lambda invoke_id: wiretest.reinitialize_device_request(invoke_id, state),
                          bbmd.port, ip=bbmd.ip, timeout=1).frame


def show(answer):
    """Text for a check's detail: a table as itself, a frame described, None as 'no answer'."""
    if answer is None:
        return "no answer"
    return answer.describe() if isinstance(answer, wiretest.codec.Frame) else f"{answer}"
