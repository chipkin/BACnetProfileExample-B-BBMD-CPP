# TODO / known gaps

Every gap below is outside this example - in the CAS BACnet Stack or in the series' shared
`common/` helper. The one the Wire Tests can see is reported on every run as a
`[KNOWN GAP]` line (`tests/`), so the day it is fixed the test says `[GAP CLOSED]`.
None of them stops the Profile Function: `tests/forwarding_test.py` proves a Who-Is from
a foreign device registered with one BBMD reaches a foreign device registered with
another, and the second BBMD's I-Am comes back.

Verified 2026-10-15 against the pinned stack, `6.x` @ `64b2cfac5` (6.0.23), with
`common/` 3.4.0. `common/` 3.4.0 closed the two-hop local re-broadcast gap (stack
[#3933](https://github.com/chipkin/cas-bacnet-stack/issues/3933)): a broadcast the stack
addresses to this BBMD's own B/IP address now goes to the subnet broadcast, and
`forwarding_test.py` counts it.

## Stack: a BDT write takes effect at once, not on ReinitializeDevice

Cl. 12.56.38 (135-2024): "Writing to this property shall set the Changes_Pending property
to TRUE. A value written to this property shall become effective when the device receives
a ReinitializeDevice service request with a 'Reinitialized State of Device' of
ACTIVATE_CHANGES or WARMSTART." At `64b2cfac5`
`BACnetBusinessLogic::SetGeneratedBBMDPropertyValueToDataLink` still replaces the live BDT
while it answers the WriteProperty, and `Changes_Pending` stays FALSE - unlike
`BBMD_Accept_FD_Registrations`, which since stack #3321 is held pending exactly as the
clause says (the Wire Tests check that one).

- Wire Test: `tables_test.py`, `[KNOWN GAP] ... the written BDT waits for
  ReinitializeDevice`. The example already registers a ReinitializeDevice callback for
  ACTIVATE_CHANGES / WARMSTART, and the test already sends ACTIVATE_CHANGES before it
  expects the new peer to be served, so the test needs no change when the stack is fixed.
- Filed as [#3930](https://github.com/chipkin/cas-bacnet-stack/issues/3930); still open at
  `64b2cfac5`.

## `common/` on Windows: the example's socket misses incoming datagrams

Measured 2026-10-14 (Windows 11, this example built static with MSVC 14.51): of 30
requests sent one at a time to an idle instance over loopback, 20-28 reached the
example's `RX` log line; the rest never arrived at the application. Linux (WSL2) loses
none. `SimpleUDP::Connect` gives the socket a 10 ms `SO_RCVTIMEO` and the tick loop
calls a blocking `recvfrom` every pass; a datagram that arrives as the timeout fires
appears to be dropped. It affects every example in the series on Windows, not only this
one.

- Wire Tests: not a gap - they repeat any request that gets no answer (`tests/bbmd_setup.py`,
  `ATTEMPTS`), so they pass on Windows, more slowly.
- Fix belongs in `BACnetProfileExample-B-SS-CPP` `common/` (e.g. `select()` with a
  timeout, or a non-blocking socket, instead of `SO_RCVTIMEO`).
