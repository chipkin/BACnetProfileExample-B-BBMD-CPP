# TODO / known gaps

Every gap below is outside this example - in the CAS BACnet Stack or in the series' shared
`common/` helper. The two the Wire Tests can see are reported on every run as a
`[KNOWN GAP]` line (`tests/`), so the day one is fixed the test says `[GAP CLOSED]`.
None of them stops the Profile Function: `tests/forwarding_test.py` proves a Who-Is from
a foreign device registered with one BBMD reaches a foreign device registered with
another, and the second BBMD's I-Am comes back.

Verified 2026-10-15 against the pinned stack, `6.x` @ `64b2cfac5` (6.0.23), with
`common/` 3.3.0.

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

## `common/`: the stack's `broadcast` flag is ignored when it comes with an address

For a two-hop BBMD's local re-broadcast (J.4.5) the stack calls the send callback with
its **own** B/IP address and `broadcast = true`. `HelperSendMessage` (`common/` 3.0.0 up to
and including 3.3.0, vendored here) sends to the address it is given whenever there are 6
octets, so the re-broadcast goes to this BBMD's own unicast address
(`TX 14 bytes to 172.17.136.75:47901 (broadcast)`) and the devices on its subnet never see
it.

- Wire Test: `forwarding_test.py`, `[KNOWN GAP] B re-broadcasts it on its own subnet`
  (Linux/macOS only - Windows cannot open the capture socket).
- Stack side filed as [#3933](https://github.com/chipkin/cas-bacnet-stack/issues/3933): the `broadcast` flag is undocumented, and the
  two-hop re-broadcast passes the BBMD's own address.
- Fix belongs in `BACnetProfileExample-B-SS-CPP` `common/`, then re-copied to every
  example. Careful: the stack also passes `broadcast = true` together with a foreign
  device's address when its device answers a Who-Is that arrived from that foreign
  device (`TX 21 bytes to <foreign device>:<port> (broadcast)`), so "broadcast flag ->
  local broadcast address" is not by itself the whole fix. The stack's
  `RegisterCallbackSendMessageForPort` documentation does not say what `broadcast = true`
  with a connection string means; that may need a stack documentation issue first.

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
