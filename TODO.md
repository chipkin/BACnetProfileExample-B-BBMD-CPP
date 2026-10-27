# TODO / known gaps

The gaps below that name a reference are outside this example - in the CAS BACnet Stack or
in the series' shared `common/` helper. A gap the Wire Tests can see is reported on every run as a
`[KNOWN GAP]` line (`tests/`), so the day it is fixed the test says `[GAP CLOSED]`.
None of them stops the Profile Function: `tests/forwarding_test.py` proves a Who-Is from
a foreign device registered with one BBMD reaches a foreign device registered with
another, and the second BBMD's I-Am comes back.

Verified 2026-10-26 against the pinned stack, `6.x` @ `69b6249f` (6.0.23), with
`common/` 3.5.0. `common/` 3.4.0 closed the two-hop local re-broadcast gap (stack
[#3933](https://github.com/chipkin/cas-bacnet-stack/issues/3933)): a broadcast the stack
addresses to this BBMD's own B/IP address now goes to the subnet broadcast, and
`forwarding_test.py` counts it. The Stack Pin move to `29b83de6` closed the BDT-write gap
(stack [#3930](https://github.com/chipkin/cas-bacnet-stack/issues/3930)): a written
`BBMD_Broadcast_Distribution_Table` now sets `Changes_Pending` and waits for
ReinitializeDevice ACTIVATE_CHANGES or WARMSTART (cl. 12.56.38), and `tables_test.py`
counts it.

## Host names in the Broadcast Distribution Table

`--bdt` takes an IP address, not a host name. A client that writes a host name into
`BBMD_Broadcast_Distribution_Table` (cl. 12.3.11.4) gets Error PROPERTY /
VALUE_OUT_OF_RANGE: the stack does not accept host-name entries and has no resolver for
them. Use the peer's IP address. (ref: chipkin/cas-bacnet-stack#4430)

## Open limits of the example

- The Broadcast Distribution Table and `BBMD_Accept_FD_Registrations` are not kept across
  a restart: the table is rebuilt from `--bdt` and the flag starts TRUE each time.
- Backup and restore are not supported (ReinitializeDevice END_BACKUP and ABORT_RESTORE
  are answered with an Error).
- Write-BDT (the BVLL message) is answered with NAK X'0010' by design; change the table by
  writing the Network Port property.
