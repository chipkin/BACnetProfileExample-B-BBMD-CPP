# wiretest changelog

The shared Wiretest Harness of the BACnet profile example series. Vendored into each
example; `WIRETEST_VERSION` in `__init__.py` names the version.

## [0.2.0] - 2026-10-14

Added for B-BBMD's wire tests; nothing in it is BBMD-specific, and every 0.1.0 call
behaves as before.

### Added

- `codec`: every Annex J BVLL message - `bvll()` for any function, builders for
  Register-Foreign-Device, Read-/Write-Broadcast-Distribution-Table,
  Read-Foreign-Device-Table, Delete-Foreign-Device-Table-Entry,
  Distribute-Broadcast-To-Network and Forwarded-NPDU, the BVLC function and
  BVLC-Result code constants, `write_property_request`, `context_octet_string`.
- `codec.Frame`: decodes BVLL-only messages too (`ok` True, `has_npdu` False),
  including 4-octet ones such as an empty Read-Foreign-Device-Table-Ack, which 0.1.0
  rejected as too short; adds `bvll_data`, `result_code`, `bdt_entries()`,
  `fdt_entries()` and a Forwarded-NPDU's `originating_mac`; `describe()` shows both.
  A predicate on `invoke_id`, `pdu_type`, `service` or `network_message` sees `None`
  for a BVLL-only message, so 0.1.0 tests behave as before.
- `endpoint.Endpoint`: `ip`, `mac` (the socket's B/IP address) and `clear()`.

### Fixed

- `endpoint.Endpoint` no longer raises on Windows when an earlier send drew an ICMP
  port-unreachable (`ConnectionResetError` on the next receive); the receive goes on.
- `peer.SimulatedDevice` no longer stops answering on Windows for the same reason: its
  receive thread treated `ConnectionResetError` (an `OSError`) as "socket closed" and
  ended silently.

## [0.1.0] - 2026-10-14

First cut, written for B-RTR's wire tests and kept free of anything router-specific.

### Added

- `codec`: BVLC (Original-Unicast/Broadcast, Forwarded-NPDU decode), NPDU encode/decode
  with DNET/DADR, SNET/SADR, hop count and network layer messages, APDU builders
  (ReadProperty request/ComplexACK, Error, Who-Is, I-Am, AddListElement /
  RemoveListElement, ReadAccessSpecification), tag reader and value helpers.
- `endpoint`: `Endpoint` (send, collect, wait_for) and `broadcast_listener` (POSIX).
- `process`: `Program` / `start` for an example binary, `broadcast_address` from
  common/'s TX console line, `default_exe`.
- `peer`: `SimulatedDevice`, a Python BACnet/IP device that answers ReadProperty and
  Who-Is and addresses answers back through a router (DNET/DADR from SNET/SADR).
- `results`: `record`, `known_gap`, `summary`.
