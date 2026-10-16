#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""The Profile Function: a broadcast crosses two BBMDs (NM-BBMDC-B, Annex J.4.5).

Starts two example instances, BBMD A (--port) and BBMD B (--port + 1), each listing the
other in its BDT (two-hop, mask 255.255.255.255), and Python foreign devices F1 (registered
with A) and F2 (registered with B). Then:

  0. Read-Broadcast-Distribution-Table: each BBMD lists itself and its peer, both two-hop.
  1. Both registrations are accepted (BVLC-Result X'0000', J.5.2.2).
  2. F1 sends a Who-Is as Distribute-Broadcast-To-Network to A (J.2.10). F2 must receive
     it from B as a Forwarded-NPDU whose originating address is F1's (J.2.5) - the
     broadcast went F1 -> A -> B -> F2.
  3. B's own device answers that Who-Is with an I-Am, which reaches F2 (from B) and F1
     (B -> A -> F1): discovery works across the two BBMDs in both directions.
  4. F1 does not get its own broadcast back (J.4.5: "except the originating node").
  5. Linux/macOS, where the broadcast can be captured: B re-broadcasts the
     Forwarded-NPDU on its own subnet (J.4.5, two-hop). The stack hands it to common/
     addressed to B's own B/IP address with broadcast=true; common/ 3.4.0 sends that to
     the subnet broadcast (up to 3.3.0 it went to B itself - stack #3933).
  6. K.6.6 minimums, on a third instance C: five peer BBMDs (Python sockets) each get the
     Forwarded-NPDU, and with five foreign devices registered, a broadcast from one
     reaches the other four.
  7. Two BBMDs on one IP subnet: with the peers listed at the LAN address (the same IP
     as B), B still retransmits A's Forwarded-NPDU to its foreign devices (J.4.5: "the
     BBMD merely retransmits the message directly to each foreign device currently in
     the BBMD's FDT"). Stack #3651; 6.x @ e6de4ffd dropped it.

    python3 tests/forwarding_test.py [--exe build/BACnetExampleBBBMD] [--port 47900]
"""
import os
import sys
import time

import bbmd_setup as setup
from bbmd_setup import wiretest

DEVICE_A = 389021
DEVICE_B = 389022
DEVICE_C = 389023
K66_MINIMUM = 5      # K.6.6: "a minimum of five peer BBMDs" / "five simultaneous foreign device connections"


def forwarded_who_is(endpoint, originating_mac, seconds):
    return endpoint.wait_for(lambda frame: setup.is_forwarded_who_is(frame, originating_mac), seconds)


def i_am_from(endpoint, device_instance, seconds):
    return endpoint.wait_for(lambda frame: setup.i_am_instance(frame) == device_instance, seconds)


def two_bbmds(args):
    port_a, port_b = args.port, args.port + 1
    bbmd_a = setup.start_bbmd(args, port_a, DEVICE_A, [(setup.LOOPBACK, port_b)], "bbmd-A")
    bbmd_b = setup.start_bbmd(args, port_b, DEVICE_B, [(setup.LOOPBACK, port_a)], "bbmd-B")
    foreign_1, foreign_2 = setup.foreign_device(bbmd_a), setup.foreign_device(bbmd_b)
    b_broadcasts = None
    try:
        # 0. The tables each BBMD reports (Read-BDT): itself and its peer, both two-hop.
        #    Its OWN entry's mask is what tells the stack to re-broadcast a peer's
        #    Forwarded-NPDU locally (J.4.5), so it must be all 1's like the peer's.
        table_a, table_b = setup.read_bdt(foreign_1, bbmd_a), setup.read_bdt(foreign_2, bbmd_b)
        wiretest.record("A's BDT: A and B, both two-hop (255.255.255.255)",
                        table_a == [(f"{bbmd_a.ip}:{port_a}", setup.TWO_HOP_MASK),
                                    (f"{setup.LOOPBACK}:{port_b}", setup.TWO_HOP_MASK)], setup.show(table_a))
        wiretest.record("B's BDT: B and A, both two-hop (255.255.255.255)",
                        table_b == [(f"{bbmd_b.ip}:{port_b}", setup.TWO_HOP_MASK),
                                    (f"{setup.LOOPBACK}:{port_a}", setup.TWO_HOP_MASK)], setup.show(table_b))
        broadcast_ip = wiretest.broadcast_address(bbmd_b.program.output(), port_b)
        if os.name == "posix" and broadcast_ip:
            b_broadcasts = wiretest.broadcast_listener(broadcast_ip, port_b)

        # 1. Registrations.
        code_1, code_2 = setup.register(foreign_1, bbmd_a), setup.register(foreign_2, bbmd_b)
        wiretest.record("F1's Register-Foreign-Device is accepted by A", code_1 == wiretest.BVLC_RESULT_SUCCESSFUL_COMPLETION,
                        f"result {code_1}")
        wiretest.record("F2's Register-Foreign-Device is accepted by B", code_2 == wiretest.BVLC_RESULT_SUCCESSFUL_COMPLETION,
                        f"result {code_2}")
        time.sleep(0.5)
        foreign_1.clear()
        foreign_2.clear()
        if b_broadcasts:
            b_broadcasts.clear()

        # 2. F1's broadcast reaches F2 through A and B.
        crossed, = setup.broadcast(foreign_1, bbmd_a, [foreign_2], 3)
        wiretest.record("F1's Who-Is (Distribute-Broadcast-To-Network to A) reaches F2 via B",
                        crossed is not None, crossed.describe() if crossed else "F2 received nothing")
        if crossed:
            wiretest.record("... as a Forwarded-NPDU sent by B", crossed.source[1] == bbmd_b.port, f"UDP {crossed.source[1]}")

        # 3. B's device answers; the I-Am comes back both ways.
        answer_at_2 = i_am_from(foreign_2, DEVICE_B, 3)
        wiretest.record("B's device answers the Who-Is: its I-Am reaches F2", answer_at_2 is not None,
                        answer_at_2.describe() if answer_at_2 else "no I-Am from device B at F2")
        # B's stack may also unicast the I-Am straight to F1 (the originating address of the
        # Who-Is it answered, J.2.5); the copy that proves the B -> A -> F1 path is the
        # Forwarded-NPDU that A sends.
        answer_at_1 = foreign_1.wait_for(lambda frame: setup.i_am_instance(frame) == DEVICE_B
                                         and frame.source[1] == bbmd_a.port
                                         and frame.bvlc_function == wiretest.BVLC_FORWARDED_NPDU, 3)
        wiretest.record("... and reaches F1 as a Forwarded-NPDU from A (B -> A -> F1)", answer_at_1 is not None,
                        answer_at_1.describe() if answer_at_1 else
                        "not forwarded by A; F1 got: " + "; ".join(frame.describe() for frame in foreign_1.frames))

        # 4. Not echoed to the originator.
        foreign_1.collect(0.5)
        echoed = [frame for frame in foreign_1.frames if setup.is_forwarded_who_is(frame, foreign_1.mac)]
        wiretest.record("F1 does not get its own broadcast back", not echoed,
                        f"{len(echoed)} copies" if echoed else "")

        # 5. B's local re-broadcast (two-hop). The stack hands it to common/ addressed to B's
        #    own B/IP address with broadcast=true; common/ 3.4.0 HelperSendMessage sends a
        #    broadcast addressed to its own socket to the subnet broadcast address (up to
        #    3.3.0 it unicast it to B itself and this check failed - stack #3933).
        if b_broadcasts:
            local = forwarded_who_is(b_broadcasts, foreign_1.mac, 2)
            wiretest.record(f"B re-broadcasts it on its own subnet ({broadcast_ip}:{port_b}, J.4.5)", local is not None,
                            local.describe() if local else
                            "nothing reached the subnet broadcast address (common/ older than 3.4.0 sends B's "
                            "re-broadcast to B's own unicast address - stack #3933)")
        else:
            print("      (B's local re-broadcast is captured on Linux/macOS only: Windows refuses a second "
                  "socket on B's port)")
    finally:
        for endpoint in (foreign_1, foreign_2, b_broadcasts):
            if endpoint:
                endpoint.close()
        bbmd_a.stop()
        bbmd_b.stop()


def k66_minimums(args):
    port_c = args.port + 2
    peers = [wiretest.Endpoint(bind_ip=setup.LOOPBACK) for _ in range(K66_MINIMUM)]
    bbmd_c = setup.start_bbmd(args, port_c, DEVICE_C, [(setup.LOOPBACK, peer.port) for peer in peers], "bbmd-C")
    foreign = [setup.foreign_device(bbmd_c) for _ in range(K66_MINIMUM)]
    try:
        codes = [setup.register(endpoint, bbmd_c) for endpoint in foreign]
        wiretest.record(f"{K66_MINIMUM} foreign devices register with one BBMD (K.6.6)",
                        codes == [wiretest.BVLC_RESULT_SUCCESSFUL_COMPLETION] * K66_MINIMUM, f"results {codes}")
        time.sleep(0.5)
        for endpoint in peers + foreign:
            endpoint.clear()

        originator = foreign[0]
        hits = [frame is not None for frame in setup.broadcast(originator, bbmd_c, peers + foreign[1:])]
        peer_hits, device_hits = hits[:K66_MINIMUM], hits[K66_MINIMUM:]
        wiretest.record(f"all {K66_MINIMUM} peer BBMDs in the BDT get the Forwarded-NPDU (K.6.6)", all(peer_hits),
                        f"received: {peer_hits}")
        wiretest.record(f"the other {K66_MINIMUM - 1} foreign devices get it too", all(device_hits),
                        f"received: {device_hits}")
    finally:
        for endpoint in peers + foreign:
            endpoint.close()
        bbmd_c.stop()


def same_ip_peers(args):
    """The same topology with the peers listed at the shared LAN address: two BBMDs on one IP subnet."""
    port_a, port_b = args.port + 3, args.port + 4
    probe = setup.start_bbmd(args, port_a, DEVICE_A, (), "bbmd-A-probe")
    lan_ip = probe.ip
    probe.stop()
    time.sleep(0.5)
    bbmd_a = setup.start_bbmd(args, port_a, DEVICE_A, [(lan_ip, port_b)], "bbmd-A-same-ip")
    bbmd_b = setup.start_bbmd(args, port_b, DEVICE_B, [(lan_ip, port_a)], "bbmd-B-same-ip")
    foreign_1, foreign_2 = setup.foreign_device(bbmd_a), setup.foreign_device(bbmd_b)
    try:
        codes = [setup.register(foreign_1, bbmd_a), setup.register(foreign_2, bbmd_b)]
        wiretest.record("peers at the same IP: F1 and F2 register with A and B",
                        codes == [wiretest.BVLC_RESULT_SUCCESSFUL_COMPLETION] * 2, f"results {codes}")
        time.sleep(0.5)
        crossed, = setup.broadcast(foreign_1, bbmd_a, [foreign_2], 3)
        wiretest.record("... B still retransmits A's Forwarded-NPDU to its foreign device F2 "
                        "(J.4.5 'merely retransmits the message directly to each foreign device')",
                        crossed is not None and crossed.source[1] == bbmd_b.port,
                        crossed.describe() if crossed else "F2 received nothing")
    finally:
        foreign_1.close()
        foreign_2.close()
        bbmd_a.stop()
        bbmd_b.stop()


def main():
    args = setup.parser(__doc__).parse_args()
    two_bbmds(args)
    k66_minimums(args)
    same_ip_peers(args)
    return wiretest.summary()


if __name__ == "__main__":
    sys.exit(main())
