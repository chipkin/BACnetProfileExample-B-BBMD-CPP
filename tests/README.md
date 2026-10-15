# B-BBMD Wire Tests

Tests that drive the running example over BACnet/IP from outside it and fail
when its Profile Function - carrying broadcasts between BBMDs - is removed.
They put hand-built Annex J frames on the wire and check the octets that come
back. They are written against the series' shared harness in
[`../wiretest/`](../wiretest/README.md) (vendored, like `common/`, version
0.5.0); everything specific to this BBMD is here. Foreign devices are
`wiretest.Client`s, so the same socket registers, broadcasts and sends
ReadProperty / WriteProperty / ReinitializeDevice. Python 3 standard library only - nothing to
`pip install`.

## Running

Build the example (README "Build"), then from the repository root:

```bash
python3 tests/run_wire_tests.py --exe build/BACnetExampleBBBMD
```

It runs the three scripts below one after another and ends with
`ALL WIRE TESTS PASSED` (exit 0) or the scripts that failed, after about two
minutes. Each script also runs on its own with the same `--exe` / `--port`
options; `--port` (default 47900) moves the whole set of UDP ports (each script
uses a few above it: +0..+4, +10, +20..+23).

A `[KNOWN GAP]` line is a requirement the example does not meet yet because of
a defect outside it (the stack or `common/`). It is reported on every run but
does not fail it; [`../TODO.md`](../TODO.md) says where it has to be fixed. If
one prints `[GAP CLOSED]`, that defect is fixed: make it a counted check.

**Windows.** The tests pass, more slowly: the example's socket misses some
incoming datagrams on Windows (`TODO.md`), so every request that gets no answer
is asked again (`bbmd_setup.ATTEMPTS`). Every check that something does *not*
arrive has a positive control in the same exchange, so a lost datagram cannot
make it pass. B's local re-broadcast is captured on Linux/macOS only.

## The setup

All on one host (`bbmd_setup.py`). Each example instance is a BBMD on its own
UDP port; its own BDT entry is the host's LAN address. Python Peers are plain
UDP sockets:

```
foreign device F1   LAN-IP : ephemeral    registered with A
BBMD A              LAN-IP : --port       BACnetExampleBBBMD --bdt 127.0.0.1:<port + 1>
BBMD B              LAN-IP : --port + 1   BACnetExampleBBBMD --bdt 127.0.0.1:<port>
foreign device F2   LAN-IP : ephemeral    registered with B
```

The peers are named at `127.0.0.1`: two instances on one host share one IP,
and Annex J.4.5 tells a BBMD that a Forwarded-NPDU from its own subnet needs no
local re-broadcast - the stack judges that from the sender's IP. Over
`127.0.0.1` the datagram arrives from a different address, as from a peer on
another subnet. The Peers are Python, never another example's binary.

## `forwarding_test.py` - the Profile Function (NM-BBMDC-B, J.4.5)

- **Tables:** Read-Broadcast-Distribution-Table of A and of B lists itself and
  its peer, both two-hop (`255.255.255.255`).
- **Registration:** F1 is accepted by A and F2 by B (BVLC-Result `X'0000'`).
- **Across two BBMDs:** F1 sends a Who-Is as Distribute-Broadcast-To-Network to
  A; F2 receives it from B as a Forwarded-NPDU whose originating address is
  F1's.
- **And back:** B's own device answers with an I-Am that reaches F2 (from B) and
  F1 (as a Forwarded-NPDU from A: B -> A -> F1).
- **Originator excluded:** F1 does not get its own broadcast back.
- **K.6.6 minimums,** on a third instance: five Python peer BBMDs in its BDT
  each get the Forwarded-NPDU, and five registered foreign devices - a
  broadcast from one reaches the other four.
- **Two BBMDs on one subnet:** with the peers named at the shared LAN address,
  F1 and F2 register, and B still passes A's Forwarded-NPDU to F2 (J.4.5; stack
  #3651 - `6.x` @ `e6de4ffd` dropped it, and this was a known gap until the pin
  moved to `64b2cfac5`).
- KNOWN GAP (Linux/macOS): B re-broadcasts the Forwarded-NPDU on its own subnet
  (`common/` 3.3.0 sends it to B itself; stack #3933).

## `tables_test.py` - managing the tables (J.4.4, J.5.2)

On one instance with one Python peer BBMD: `BACnet_IP_Mode` reads `bbmd`;
Read-Broadcast-Distribution-Table-Ack and ReadProperty
`BBMD_Broadcast_Distribution_Table` both carry this BBMD (two-hop) and the
peer; Write-Broadcast-Distribution-Table gets NAK `X'0010'` and changes
nothing; a foreign device registered with TTL 300 is listed by
Read-Foreign-Device-Table-Ack with TTL 300 and 330 s remaining (TTL + the 30 s
grace period, J.5.2.1); Delete-Foreign-Device-Table-Entry removes it
(`X'0000'`, an empty FDT reads back as an empty Ack) and deleting it again gets
NAK `X'0050'`; before a WriteProperty of `BBMD_Broadcast_Distribution_Table` a
foreign device's broadcast reaches the first peer but not a second; the write
(adding the second) gets a SimpleACK and reads back as written;
ReinitializeDevice ACTIVATE_CHANGES gets a SimpleACK; then Read-BDT lists the
second peer and the next broadcast reaches it; a write that drops this BBMD's
own entry gets an Error and the table is unchanged.

KNOWN GAP: between the write and ReinitializeDevice, cl. 12.56.38 wants
`Changes_Pending` TRUE and the old table still in force; the pinned stack has
already applied the write (stack #3930).

## `failure_modes_test.py` - Failure Modes

- **A foreign device goes silent** (J.5.2.3). It registers with TTL 30 s (the
  shortest K.6.6 requires) and never re-registers. 40 s later it is still in
  the FDT and still receives forwarded broadcasts; once TTL + 30 s have passed
  it is gone, a broadcast still reaches another foreign device but not it, and
  its own Distribute-Broadcast-To-Network gets NAK `X'0060'`.
- **A registration is refused** (J.5.2.2). 128 registrations fill the FDT; the
  129th gets NAK `X'0030'`; after one Delete-FDT-Entry a new registration is
  accepted.
- **A stranger asks to forward:** Distribute-Broadcast-To-Network from a device
  that never registered gets NAK `X'0060'` (J.4.5).
- **Reconfigured as a non-BBMD** (`--no-bbmd`, Annex L.7.3): `BACnet_IP_Mode`
  reads `normal`; Register-Foreign-Device, Read-BDT, Read-FDT and
  Delete-FDT-Entry get NAK `X'0030'`, `X'0020'`, `X'0040'` and `X'0050'`.
- **Configured not to accept foreign devices** (J.5.2.2, cl. 12.56.39), on its
  own instance: `BBMD_Accept_FD_Registrations` reads TRUE; written FALSE it
  gets a SimpleACK and `Changes_Pending` reads TRUE, and a registration is
  still accepted (the write is pending); ReinitializeDevice ACTIVATE_CHANGES
  gets a SimpleACK, `Changes_Pending` reads FALSE, and the next
  Register-Foreign-Device gets NAK `X'0030'`; written TRUE and activated again,
  a registration is accepted.

## Each check fails without its feature

Run 2026-10-14 against stack `6.x` @ `e6de4ffd`, Windows build (static):
`main.cpp` changed as listed, rebuilt, the scripts run, `main.cpp` restored.
Every run exits 1. After the move to `wiretest/` 0.5.0 and `common/` 3.3.0
(2026-10-15) the three mutations whose checks go through `wiretest.Client` -
ReinitializeDevice, the BBMD properties, `BACnet_IP_Mode` - were run again and
gave the same results.

| Without | Script | Result |
|---|---|---|
| The BBMD function: `SetUpBbmd()` not called (the 1.1.2 binary had no peers either) | `forwarding_test.py` | 1/11 - Read-BDT NAKed X'0020', registrations NAKed X'0030', nothing reaches F2, no I-Am crosses, K.6.6 peers and foreign devices get nothing |
| | `tables_test.py` | 6/20 - Read-BDT / ReadProperty BDT / Read-FDT / Delete-FDT-Entry / registration all refused; the BDT write gets an Error; nothing is forwarded |
| | `failure_modes_test.py` | 9/17 - no registration accepted, so no grace period, no purge, no full table (the `--no-bbmd` checks still pass: that device is not a BBMD either way) |
| `--bdt` peers parsed but never added | `forwarding_test.py` | 5/11 - both BDTs hold only themselves; F2 gets nothing; no I-Am crosses; K.6.6 peers get nothing |
| | `tables_test.py` | 17/21 - Read-BDT and the BDT property lack the peer; the first-peer control fails |
| Own BDT entry with the subnet mask (the 1.1.2 behaviour) | `forwarding_test.py` | 10/12 - A's and B's own entries read `255.255.255.0` |
| | `tables_test.py` | 13/21 - the own-entry mask; the two-hop BDT write is refused (value-out-of-range, its own entry no longer matches) |
| ReinitializeDevice callback not registered | `tables_test.py` | 20/21 - ACTIVATE_CHANGES is answered Abort(other) |
| `--no-bbmd` ignored | `failure_modes_test.py` | 12/17 - `--no-bbmd` reads `bbmd` and answers every BBMD message as a BBMD |

Rows dropped at the move to stack `6.x` @ `64b2cfac5`: "the three BBMD table
properties not enabled" and "`BACnet_IP_Mode` always `bbmd`" mutated code
`main.cpp` no longer has - `SetBBMD` does both now (stack #2548, #3317). Those
checks are pinned to the stack instead, below.

Run 2026-10-15 against stack `6.x` @ `64b2cfac5`. The `main.cpp` mutation on the
Windows static build; the stack mutations on the Linux (WSL2) build, which
compiles the stack's sources into the example, so a reverted stack fix is one
rebuild. Each was restored afterwards and the full suite passed again on both.

| Without | Script | Result |
|---|---|---|
| ReinitializeDevice callback not registered (`main.cpp`) | `failure_modes_test.py` | 19/25 - the `BBMD_Accept_FD_Registrations` write is answered Abort, `Changes_Pending` stays FALSE, ACTIVATE_CHANGES is refused, and registrations are still accepted |
| Stack #3321: a FALSE `BBMD_Accept_FD_Registrations` not enforced (`BACnetDataLinkIPv4.cpp`) | `failure_modes_test.py` | 24/25 - the registration after ACTIVATE_CHANGES is accepted (`X'0000'`) instead of NAKed `X'0030'` |
| Stack #3651/#2547: a same-subnet Forwarded-NPDU passed to no foreign device (`BACnetBBMD.cpp`, the old #467 early return) | `forwarding_test.py` | 13/14 - with the peers at the shared LAN address F2 receives nothing |
| Stack #2548: `SetBBMD` leaves `BACnet_IP_Mode` `normal` (`BACnetDBDevice.cpp`) | `tables_test.py` | 20/21 - `BACnet_IP_Mode` reads `normal` (0) |
| Stack #3317: `SetBBMD` does not enable the three BBMD properties (`BACnetDBDevice.cpp`) | `tables_test.py` | 15/21 - ReadProperty and WriteProperty of `BBMD_Broadcast_Distribution_Table` get unknown-property, so the second peer is never added |
| | `failure_modes_test.py` | 20/25 - `BBMD_Accept_FD_Registrations` is unknown-property, so it cannot be read, written or activated |

The B re-broadcast and BDT-pending checks are `[KNOWN GAP]`s, not counted; they
fail today for reasons outside this example (`TODO.md`) and will print
`[GAP CLOSED]` when those are fixed.
