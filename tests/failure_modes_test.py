#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""Failure Modes: what the BBMD does when a foreign device goes silent, when its Foreign
Device Table is full, when a stranger asks it to forward, and when it is not a BBMD.

  1. A foreign device goes silent (J.5.2.3). It registers with a Time-to-Live of 30 s -
     the shortest lifetime K.6.6 requires a BBMD to support - and never re-registers.
     It is still in the FDT after its TTL (the 30 s grace period), and gone once
     TTL + 30 s have passed. After that the BBMD no longer forwards broadcasts to it, and
     refuses to forward its broadcasts: Distribute-Broadcast-To-Network NAK X'0060' (J.4.5).
  2. A registration is refused (J.5.2.2: "A BBMD that does not have an available table
     entry ... shall return ... 'Register-Foreign-Device NAK'"). The stack's FDT holds
     128 entries: 128 registrations are accepted, the 129th gets X'0030'; once one entry
     is deleted, a new registration is accepted again.
  3. A device that never registered asks the BBMD to distribute a broadcast: NAK X'0060'
     (J.4.5: "the message was not received from a registered foreign device").
  4. Reconfigured as a non-BBMD (--no-bbmd; Annex L.7.3): BACnet_IP_Mode reads normal,
     and every BBMD message gets the NAK Annex J requires of a device that is not a BBMD
     (J.4.4.1 X'0020', J.5.2.1.1 X'0040', J.5.2.1.2 X'0050', J.5.2.2 X'0030').

Check 1 waits out the grace period, so this script takes a little over a minute; checks
2-4 run while it waits.

    python3 tests/failure_modes_test.py [--exe build/BACnetExampleBBBMD] [--port 47900]
"""
import sys
import time

import bbmd_setup as setup
from bbmd_setup import wiretest

DEVICE_EXPIRY = 389025
DEVICE_FULL = 389026
DEVICE_PLAIN = 389027
SHORT_TIME_TO_LIVE = 30      # K.6.6: "lifetimes in the range 30 seconds - 9 hours"
GRACE_PERIOD = 30            # J.5.2.3
FDT_CAPACITY = 128           # STACK_OPTION_MAX_FOREIGN_DEVICE_TABLE_ENTRIES (full target)


def in_fdt(endpoint, bbmd, member):
    table = setup.read_fdt(endpoint, bbmd)
    return isinstance(table, list) and any(entry[0] == wiretest.mac_text(member.mac) for entry in table), table


def table_full(args):
    bbmd = setup.start_bbmd(args, args.port + 21, DEVICE_FULL, (), "bbmd-full")
    devices = [setup.foreign_device(bbmd) for _ in range(FDT_CAPACITY + 1)]
    try:
        # 3. Never registered.
        code = setup.request_result(devices[0], bbmd, wiretest.distribute_broadcast_to_network(setup.who_is_npdu()))
        wiretest.record("an unregistered device's Distribute-Broadcast-To-Network is NAKed X'0060'",
                        code == wiretest.BVLC_RESULT_DISTRIBUTE_BROADCAST_TO_NETWORK_NAK, f"result {code}")

        # 2. The table fills up.
        codes = [setup.register(endpoint, bbmd) for endpoint in devices[:FDT_CAPACITY]]
        accepted = codes.count(wiretest.BVLC_RESULT_SUCCESSFUL_COMPLETION)
        wiretest.record(f"{FDT_CAPACITY} registrations fill the Foreign Device Table", accepted == FDT_CAPACITY,
                        f"{accepted} accepted")
        code = setup.register(devices[FDT_CAPACITY], bbmd)
        wiretest.record("the next registration is refused: Register-Foreign-Device NAK X'0030'",
                        code == wiretest.BVLC_RESULT_REGISTER_FOREIGN_DEVICE_NAK, f"result {code}")
        code = setup.request_result(devices[0], bbmd, wiretest.delete_foreign_device_table_entry(devices[0].mac))
        code_after = setup.register(devices[FDT_CAPACITY], bbmd)
        wiretest.record("... and accepted once an entry is deleted",
                        code == wiretest.BVLC_RESULT_SUCCESSFUL_COMPLETION
                        and code_after == wiretest.BVLC_RESULT_SUCCESSFUL_COMPLETION,
                        f"delete {code}, register {code_after}")
    finally:
        for endpoint in devices:
            endpoint.close()
        bbmd.stop()


def not_a_bbmd(args):
    bbmd = setup.start_bbmd(args, args.port + 22, DEVICE_PLAIN, (), "plain", extra=["--no-bbmd"])
    client = None
    try:
        # A plain device prints no BDT, so reach it on loopback.
        bbmd.ip = setup.LOOPBACK
        client = setup.client_on(setup.LOOPBACK)
        value, answer = setup.read_property(client, bbmd, setup.PROPERTY_BACNET_IP_MODE)
        mode = wiretest.application_values(value) if value is not None else None
        wiretest.record("--no-bbmd: Network Port 1 BACnet_IP_Mode reads normal (0)",
                        mode == [(9, bytes([setup.BACNET_IP_MODE_NORMAL]))],
                        f"{mode}" if value is not None else (answer.describe() if answer else "no answer"))
        expectations = [
            ("Register-Foreign-Device", wiretest.register_foreign_device(setup.TIME_TO_LIVE),
             wiretest.BVLC_RESULT_REGISTER_FOREIGN_DEVICE_NAK),
            ("Read-Broadcast-Distribution-Table", wiretest.read_broadcast_distribution_table(),
             wiretest.BVLC_RESULT_READ_BDT_NAK),
            ("Read-Foreign-Device-Table", wiretest.read_foreign_device_table(), wiretest.BVLC_RESULT_READ_FDT_NAK),
            ("Delete-Foreign-Device-Table-Entry", wiretest.delete_foreign_device_table_entry(client.mac),
             wiretest.BVLC_RESULT_DELETE_FDT_ENTRY_NAK),
        ]
        for name, message, expected in expectations:
            code = setup.request_result(client, bbmd, message)
            wiretest.record(f"--no-bbmd: {name} is NAKed X'{expected:04X}'", code == expected, f"result {code}")
    finally:
        if client:
            client.close()
        bbmd.stop()


def main():
    args = setup.parser(__doc__).parse_args()

    # 1. Start the silent foreign device's clock first; checks 2-4 run while it ticks.
    bbmd = setup.start_bbmd(args, args.port + 20, DEVICE_EXPIRY, (), "bbmd-expiry")
    silent = setup.foreign_device(bbmd)
    watcher = setup.foreign_device(bbmd)
    listener = setup.foreign_device(bbmd)     # the positive control for "no longer forwarded"
    try:
        code = setup.register(silent, bbmd, SHORT_TIME_TO_LIVE)
        registered_at = time.monotonic()
        wiretest.record(f"a foreign device registers with TTL {SHORT_TIME_TO_LIVE} s",
                        code == wiretest.BVLC_RESULT_SUCCESSFUL_COMPLETION, f"result {code}")
        codes = [setup.register(watcher, bbmd), setup.register(listener, bbmd)]
        wiretest.record("two more foreign devices register (TTL 300 s)",
                        codes == [wiretest.BVLC_RESULT_SUCCESSFUL_COMPLETION] * 2, f"results {codes}")

        not_a_bbmd(args)

        # Past its TTL, inside the grace period: still there. (The FDT-full check, which
        # can take a while, runs only after this, so this one happens on time.)
        time.sleep(max(0.0, registered_at + SHORT_TIME_TO_LIVE + 10 - time.monotonic()))
        elapsed = time.monotonic() - registered_at
        present, table = in_fdt(watcher, bbmd, silent)
        wiretest.record(f"{elapsed:.0f} s later (past its TTL, inside TTL + 30 s) it is still in the FDT",
                        present and elapsed < SHORT_TIME_TO_LIVE + GRACE_PERIOD - 5, setup.show(table))
        at_listener, at_silent = setup.broadcast(watcher, bbmd, [listener, silent])
        wiretest.record("... and still receives forwarded broadcasts", at_listener is not None and at_silent is not None,
                        f"listener {at_listener is not None}, silent device {at_silent is not None}")

        table_full(args)

        # Past TTL + grace: purged.
        time.sleep(max(0.0, registered_at + SHORT_TIME_TO_LIVE + GRACE_PERIOD + 3 - time.monotonic()))
        elapsed = time.monotonic() - registered_at
        present, table = in_fdt(watcher, bbmd, silent)
        wiretest.record(f"{elapsed:.0f} s after registering (past TTL + 30 s) it is gone from the FDT",
                        isinstance(table, list) and not present, setup.show(table))
        at_listener, at_silent = setup.broadcast(watcher, bbmd, [listener, silent])
        wiretest.record("... a broadcast still reaches the other foreign device (control) ...", at_listener is not None)
        wiretest.record("... but is no longer forwarded to it", at_silent is None,
                        at_silent.describe() if at_silent else "")
        code = setup.request_result(silent, bbmd, wiretest.distribute_broadcast_to_network(setup.who_is_npdu()))
        wiretest.record("... and its own Distribute-Broadcast-To-Network is NAKed X'0060'",
                        code == wiretest.BVLC_RESULT_DISTRIBUTE_BROADCAST_TO_NETWORK_NAK, f"result {code}")
    finally:
        for endpoint in (silent, watcher, listener):
            endpoint.close()
        bbmd.stop()
    return wiretest.summary()


if __name__ == "__main__":
    sys.exit(main())
