# TODO / known gaps

Every gap below is outside this example - in the CAS BACnet Stack or in the series' shared
`common/` helper. The three the Wire Tests can see are reported on every run as a
`[KNOWN GAP]` line (`tests/`), so the day one is fixed the test says `[GAP CLOSED]`.
None of them stops the Profile Function: `tests/forwarding_test.py` proves a Who-Is from
a foreign device registered with one BBMD reaches a foreign device registered with
another, and the second BBMD's I-Am comes back.

Verified 2026-10-14 against the pinned stack, `6.x` @ `e6de4ffd` (6.0.23), with
`common/` 3.3.0.

## Stack: a Forwarded-NPDU from a same-subnet peer is not passed to foreign devices

Annex J.4.5 (135-2024): "If the message arrived via directed broadcast, or if the source
is a device located on the same IP subnet, a situation which can occur if two or more
BBMDs are installed on the same IP subnet, it was also received by the other devices on
the BBMD's subnet. In this case the BBMD merely retransmits the message directly to each
foreign device currently in the BBMD's FDT."

`BACnetBBMD::ProcessOutgoingMessageBBMD` (`source/BACnetBBMD.cpp`, the #467 loop guard)
returns before any distribution when the sender is on its own subnet - so it skips the
local re-broadcast (correct) **and** the foreign-device retransmission (not correct).
The stack's own tests cover only the first half
(`tests/BACnetBBMDTests.cpp`, `ForwardedNPDUFromSameSubnetDifferentPortPeer_IsNotReBroadcastLocally`).

- Wire Test: `forwarding_test.py`, `[KNOWN GAP] peers at the same IP ...` - two instances
  peered at the shared LAN address; F2 (registered with B) never receives F1's Who-Is.
- Effect here: on one host the peers must be named at `127.0.0.1` (README "Two BBMDs on
  one host"). On a real site, two BBMDs on one IP subnet would not pass each other's
  broadcasts to their foreign devices.
- Not filed yet - needs the owner's OK.

## Stack: a BDT write takes effect at once, not on ReinitializeDevice

Cl. 12.56.38 (135-2024): "Writing to this property shall set the Changes_Pending property
to TRUE. A value written to this property shall become effective when the device receives
a ReinitializeDevice service request with a 'Reinitialized State of Device' of
ACTIVATE_CHANGES or WARMSTART." At `e6de4ffd`
`BACnetBusinessLogic::SetGeneratedBBMDPropertyValueToDataLink` replaces the live BDT while
it answers the WriteProperty, and `Changes_Pending` stays FALSE.

- Wire Test: `tables_test.py`, `[KNOWN GAP] ... the written BDT waits for
  ReinitializeDevice`. The example already registers a ReinitializeDevice callback for
  ACTIVATE_CHANGES / WARMSTART, and the test already sends ACTIVATE_CHANGES before it
  expects the new peer to be served, so the test needs no change when the stack is fixed.
- Check whether `6.x` after `e6de4ffd` (#2866 `BACnetStack_ActivateNetworkPortPendingChanges`,
  #3321) already makes the BDT a pending change; if not, it is a stack issue to file
  (owner's OK first).

## `common/`: the stack's `broadcast` flag is ignored when it comes with an address

For a two-hop BBMD's local re-broadcast (J.4.5) the stack calls the send callback with
its **own** B/IP address and `broadcast = true`. `HelperSendMessage` (`common/` 3.0.0 up to
and including 3.3.0, vendored here) sends to the address it is given whenever there are 6
octets, so the re-broadcast goes to this BBMD's own unicast address
(`TX 14 bytes to 172.17.136.75:47901 (broadcast)`) and the devices on its subnet never see
it.

- Wire Test: `forwarding_test.py`, `[KNOWN GAP] B re-broadcasts it on its own subnet`
  (Linux/macOS only - Windows cannot open the capture socket).
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

## Stack pin: what this example waits for in a later `6.x`

The `6.x` tip `4b27bd56` does not link outside a test-tool build
([stack #3850](https://github.com/chipkin/cas-bacnet-stack/issues/3850), fixed on
`issues/runbook`, not yet promoted), so this example stays on `e6de4ffd`. When the pin
moves past these, change the example as listed:

- **#3321 - `BBMD_Accept_FD_Registrations` writable** (as a pending change, cl.
  12.56.39). Today it is generated as a constant TRUE, so "a BBMD ... that is not
  configured to accept foreign device registrations" (J.5.2.2) cannot be shown. Add a
  Failure Mode Wire Test: write it FALSE, ReinitializeDevice ACTIVATE_CHANGES (the
  callback is already there), and a Register-Foreign-Device gets NAK X'0030'; write it
  TRUE again and registration works - the route back.
- **#2866 - `BACnetStack_ActivateNetworkPortPendingChanges`.** Read its contract: if the
  application must call it from the ReinitializeDevice callback, add the call there.
- **#2548 - `SetBBMD` sets `BACnet_IP_Mode`**, and **#3317 - `SetBBMD` enables the three
  BBMD table properties.** The example's own `BACnet_IP_Mode` branch and its
  `SetPropertyEnabled` calls then become redundant (they say so in `main.cpp`).
