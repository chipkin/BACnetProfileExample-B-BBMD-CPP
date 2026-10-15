#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""Managing the BBMD's tables over the wire (NM-BBMDC-B, Annex J.4.4 / J.5.2).

Starts one example instance (--port + 10) with one Python peer BBMD in its BDT, then:

  1. ReadProperty Network Port 1 BACnet_IP_Mode = bbmd (2).
  2. Read-Broadcast-Distribution-Table-Ack lists this BBMD (two-hop) and the peer (J.4.4.1).
  3. ReadProperty BBMD_Broadcast_Distribution_Table carries the same two entries.
  4. Write-Broadcast-Distribution-Table is NAKed X'0010' and changes nothing (J.4.4.2).
  5. A foreign device registers (TTL 300); Read-Foreign-Device-Table-Ack lists it with
     TTL 300 and about 330 s remaining - TTL plus the 30 s grace period (J.5.2.1).
  6. Delete-Foreign-Device-Table-Entry removes it (X'0000'; J.5.2.1.2); the table is
     empty afterwards; deleting it again is NAKed X'0050'.
  7. WriteProperty BBMD_Broadcast_Distribution_Table adding a second peer (J.4.4) gets a
     SimpleACK and reads back as written. Cl. 12.56.38: the write sets Changes_Pending
     and becomes effective on ReinitializeDevice ACTIVATE_CHANGES or WARMSTART - so
     until then the second peer must not be served (KNOWN GAP: the pinned stack applies
     the write at once, TODO.md). ReinitializeDevice ACTIVATE_CHANGES gets a SimpleACK;
     after it Read-BDT lists the second peer and a foreign device's broadcast reaches
     it - it did not before the write.
  8. A WriteProperty that drops this BBMD's own entry is refused (Error) and the table
     keeps the second peer.

    python3 tests/tables_test.py [--exe build/BACnetExampleBBBMD] [--port 47900]
"""
import sys
import time

import bbmd_setup as setup
from bbmd_setup import wiretest

DEVICE = 389024
GRACE_PERIOD = 30    # J.5.2.3: "a fixed grace period of 30 seconds"


def main():
    args = setup.parser(__doc__).parse_args()
    peer_1 = wiretest.Endpoint(bind_ip=setup.LOOPBACK)
    peer_2 = wiretest.Endpoint(bind_ip=setup.LOOPBACK)
    bbmd = setup.start_bbmd(args, args.port + 10, DEVICE, [(setup.LOOPBACK, peer_1.port)], "bbmd-tables")
    client = setup.foreign_device(bbmd)
    own_entry = (f"{bbmd.ip}:{bbmd.port}", setup.TWO_HOP_MASK)
    peer_1_entry = (f"{setup.LOOPBACK}:{peer_1.port}", setup.TWO_HOP_MASK)
    peer_2_entry = (f"{setup.LOOPBACK}:{peer_2.port}", setup.TWO_HOP_MASK)
    try:
        # 1. BACnet_IP_Mode.
        value, answer = setup.read_property(client, bbmd, setup.PROPERTY_BACNET_IP_MODE)
        mode = wiretest.application_values(value) if value is not None else None
        wiretest.record("Network Port 1 BACnet_IP_Mode reads bbmd (2)",
                        mode == [(9, bytes([setup.BACNET_IP_MODE_BBMD]))],
                        f"{mode}" if value is not None else (answer.describe() if answer else "no answer"))

        # 2. Read-BDT.
        table = setup.read_bdt(client, bbmd)
        wiretest.record("Read-Broadcast-Distribution-Table-Ack lists this BBMD and its peer",
                        table == [own_entry, peer_1_entry], setup.show(table))

        # 3. The same table as a property.
        value, answer = setup.read_property(client, bbmd, setup.PROPERTY_BBMD_BROADCAST_DISTRIBUTION_TABLE)
        property_table = setup.parse_bdt_property(value) if value is not None else None
        wiretest.record("ReadProperty BBMD_Broadcast_Distribution_Table carries the same entries",
                        property_table == [own_entry, peer_1_entry],
                        f"{property_table}" if value is not None else (answer.describe() if answer else "no answer"))

        # 4. Write-BDT (the BVLL message) is not the way to configure a BBMD.
        code = setup.request_result(client, bbmd, wiretest.write_broadcast_distribution_table(
            [(bbmd.mac, bytes([255] * 4)), (wiretest.mac(setup.LOOPBACK, peer_2.port), bytes([255] * 4))]))
        wiretest.record("Write-Broadcast-Distribution-Table is NAKed X'0010'", code == wiretest.BVLC_RESULT_WRITE_BDT_NAK,
                        f"result {code}")
        wiretest.record("... and the BDT is unchanged", setup.read_bdt(client, bbmd) == [own_entry, peer_1_entry])

        # 5. Register, then read the FDT.
        code = setup.register(client, bbmd, setup.TIME_TO_LIVE)
        wiretest.record("Register-Foreign-Device (TTL 300) is accepted", code == wiretest.BVLC_RESULT_SUCCESSFUL_COMPLETION,
                        f"result {code}")
        fdt = setup.read_fdt(client, bbmd)
        listed = [entry for entry in fdt if entry[0] == wiretest.mac_text(client.mac)] if isinstance(fdt, list) else []
        wiretest.record("Read-Foreign-Device-Table-Ack lists it with its TTL", len(listed) == 1 and listed[0][1] == setup.TIME_TO_LIVE,
                        f"{fdt}" if isinstance(fdt, list) else (fdt.describe() if fdt else "no answer"))
        if listed:
            remaining = listed[0][2]
            wiretest.record("... and TTL + 30 s grace remaining (J.5.2.1)",
                            setup.TIME_TO_LIVE + GRACE_PERIOD - 5 <= remaining <= setup.TIME_TO_LIVE + GRACE_PERIOD,
                            f"{remaining} s")

        # 6. Delete-FDT-Entry.
        code = setup.request_result(client, bbmd, wiretest.delete_foreign_device_table_entry(client.mac))
        wiretest.record("Delete-Foreign-Device-Table-Entry is acknowledged X'0000'",
                        code == wiretest.BVLC_RESULT_SUCCESSFUL_COMPLETION, f"result {code}")
        fdt = setup.read_fdt(client, bbmd)
        wiretest.record("... and the FDT is empty afterwards", fdt == [],
                        f"{fdt}" if isinstance(fdt, list) else (fdt.describe() if fdt else "no answer"))
        code = setup.request_result(client, bbmd, wiretest.delete_foreign_device_table_entry(client.mac))
        wiretest.record("deleting an entry that is not there is NAKed X'0050'",
                        code == wiretest.BVLC_RESULT_DELETE_FDT_ENTRY_NAK, f"result {code}")

        # 7. WriteProperty of the BDT takes effect.
        setup.register(client, bbmd)
        at_peer_1, at_peer_2 = setup.broadcast(client, bbmd, [peer_1, peer_2])
        wiretest.record("before the write, a foreign device's broadcast reaches the first peer (control) ...",
                        at_peer_1 is not None)
        wiretest.record("... but not the second", at_peer_2 is None, at_peer_2.describe() if at_peer_2 else "")

        answer = setup.write_property(client, bbmd, setup.PROPERTY_BBMD_BROADCAST_DISTRIBUTION_TABLE,
                                      setup.bdt_entry(bbmd.ip, bbmd.port) + setup.bdt_entry(setup.LOOPBACK, peer_1.port) +
                                      setup.bdt_entry(setup.LOOPBACK, peer_2.port))
        wiretest.record("WriteProperty BBMD_Broadcast_Distribution_Table (adding a second peer) gets a SimpleACK",
                        answer is not None and answer.pdu_type == wiretest.PDU_SIMPLE_ACK,
                        answer.describe() if answer else "no answer")
        value, answer = setup.read_property(client, bbmd, setup.PROPERTY_BBMD_BROADCAST_DISTRIBUTION_TABLE)
        written = setup.parse_bdt_property(value) if value is not None else None
        wiretest.record("... and reads back as written (cl. 12.56.38 (b)/(c))",
                        written == [own_entry, peer_1_entry, peer_2_entry],
                        f"{written}" if value is not None else (answer.describe() if answer else "no answer"))

        # Cl. 12.56.38: pending until ReinitializeDevice. The first peer is the control.
        value, _ = setup.read_property(client, bbmd, setup.PROPERTY_CHANGES_PENDING)
        changes_pending = wiretest.application_values(value) if value is not None else None
        at_peer_1, at_peer_2 = setup.broadcast(client, bbmd, [peer_1, peer_2])
        wiretest.record("before ReinitializeDevice, a broadcast still reaches the first peer (control)",
                        at_peer_1 is not None)
        wiretest.known_gap("... the written BDT waits for ReinitializeDevice (cl. 12.56.38): Changes_Pending is "
                           "TRUE and the second peer is not served yet",
                           at_peer_2 is None and changes_pending == [(1, b"\x01")],
                           f"stack 6.x @ e6de4ffd applies a BDT write at once (second peer served: "
                           f"{at_peer_2 is not None}; Changes_Pending {changes_pending})")

        answer = setup.reinitialize_device(client, bbmd, wiretest.REINITIALIZE_ACTIVATE_CHANGES)
        wiretest.record("ReinitializeDevice ACTIVATE_CHANGES gets a SimpleACK",
                        answer is not None and answer.pdu_type == wiretest.PDU_SIMPLE_ACK,
                        answer.describe() if answer else "no answer")
        wiretest.record("... Read-BDT now lists the second peer",
                        setup.read_bdt(client, bbmd) == [own_entry, peer_1_entry, peer_2_entry])
        after, = setup.broadcast(client, bbmd, [peer_2])
        wiretest.record("... and a foreign device's broadcast now reaches it", after is not None,
                        after.describe() if after else "the second peer received nothing")

        # 8. A replacement without this BBMD's own entry is refused.
        answer = setup.write_property(client, bbmd, setup.PROPERTY_BBMD_BROADCAST_DISTRIBUTION_TABLE,
                                      setup.bdt_entry(setup.LOOPBACK, peer_1.port))
        wiretest.record("a BDT write that drops this BBMD's own entry is refused (Error)",
                        answer is not None and answer.pdu_type == wiretest.PDU_ERROR,
                        answer.describe() if answer else "no answer")
        time.sleep(0.2)
        wiretest.record("... and the table keeps both peers",
                        setup.read_bdt(client, bbmd) == [own_entry, peer_1_entry, peer_2_entry])
    finally:
        for endpoint in (client, peer_1, peer_2):
            endpoint.close()
        bbmd.stop()
    return wiretest.summary()


if __name__ == "__main__":
    sys.exit(main())
