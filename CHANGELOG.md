# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_No changes yet._

## [1.3.0] - 2026-10-27

Built on CAS BACnet Stack 6.x (69b6249f).

### Added

- **`--deviceName <text>`**: sets the Device's Object_Name at start-up, like
  `--deviceID` sets its instance. Object_Name must be unique on a BACnet
  internetwork, so two units no longer have to share the built-in name. The
  default is unchanged (`Chipkin Example B-BBMD`). A name must be 1 to 255
  bytes with no control characters, otherwise the example warns and keeps the
  default. The name cannot be changed over the network.
- **Automated self-test** `tests/configuration_test.py` checks `--deviceID` and `--deviceName`.

### Changed

- **A written Broadcast Distribution Table now waits for ReinitializeDevice.**
  `Changes_Pending` reads TRUE and the old table stays in force until
  ACTIVATE_CHANGES or WARMSTART, as cl. 12.56.38 requires. README, TUTORIAL and
  PICS describe this.
- **ReinitializeDevice END_BACKUP and ABORT_RESTORE** (backup and restore are not
  supported) are answered with an Error (OPTIONAL_FUNCTIONALITY_NOT_SUPPORTED)
  instead of an Abort, per cl. 16.4.
- **`--help` lists only the options the example reads.** It no longer lists
  `--dcc-password` (the password is `DCC_PASSWORD` in `main.cpp`). `--xml`, which
  was listed but did nothing, now prints each received and sent frame as XML.
- **Self-tests** default to UDP port 47837 (was 47900).
- **Documentation**: PICS now claims segmentation in both directions
  (`Max_Segments_Accepted` 16) and lists Database_Revision as 8 in both run
  modes. Binary Input 1 "Emerald" is documented as fixed at active. The PICS
  objects tables cite the stack's property profiles.
- Vendored `common/` updated to 3.5.0 (see `common/CHANGELOG.md`).

### Fixed

- **Requests no longer go unanswered on Windows.** A request that arrived just as
  the socket's short receive timeout expired could be silently dropped. The
  receive loop now waits with `select()` (vendored `common/` 3.4.1).

## [1.2.0] - 2026-10-16

The example now carries broadcasts between the BBMDs it is told about. It has two
run modes: the default BBMD mode, and `--no-bbmd`, which runs a plain BACnet/IP
device. Built on CAS BACnet Stack 6.x (64b2cfac5, reports 6.0.23).

### Added

- **`--bdt <ip>[:<port>][/<mask>]`** (repeatable) lists the peer BBMDs of the
  Broadcast Distribution Table. Port defaults to 47808 and mask to
  255.255.255.255 (two-hop). Listing this device's own address sets the mask of
  its own entry.
- **`--no-bbmd`** starts the example as a plain BACnet/IP device:
  `BACnet_IP_Mode` is `normal` and every BBMD message is refused (Annex L.7.3).
- **ReinitializeDevice** (ACTIVATE_CHANGES and WARMSTART; other states refused)
  is supported and listed in `Protocol_Services_Supported`. A written
  `BBMD_Broadcast_Distribution_Table` takes effect on these two states (cl. 12.56.38).
- **`BBMD_Accept_FD_Registrations` is writable** (cl. 12.56.39). Writing FALSE
  and activating the change makes the BBMD refuse foreign-device registrations
  with NAK X'0030'.
- **Automated self-tests** under `tests/` (Python standard library only), run with
  `python3 tests/run_wire_tests.py --exe build/BACnetExampleBBBMD`. They cover
  broadcast forwarding between BBMDs, table reads and writes, foreign-device
  expiry and refusal, and `--no-bbmd`.
- `TODO.md` lists the known gaps and what to re-check when the stack changes.

### Changed

- **Device renamed** from the placeholder "Rainbow" to "Chipkin Example B-BBMD",
  so examples in this series can be told apart on one network. Sub-object names
  are unchanged.
- **This device's own BDT entry is two-hop (255.255.255.255)**, not the subnet
  mask, so Forwarded-NPDUs from peers are re-broadcast on the local subnet
  (Annex J.4.5).
- **Two BBMDs on one IP subnet** now pass a peer's Forwarded-NPDU to their foreign devices.
- The unreachable placeholder peers (192.0.2.10 and 192.0.2.20) are gone. The
  table holds this device plus the `--bdt` peers, and is printed before the
  `ready` line.
- **`BACnet_IP_Mode` is set by the stack.** The three BBMD Network Port properties
  are enabled when the BBMD is set up.
- **Protocol_Revision is 30** (docs said 24). `Application_Software_Version`
  and `Firmware_Revision` now report the running build and linked stack version
  instead of a fixed "1.0.0".
- **Build**: the documented and released build compiles the stack from source
  with two commands (`cmake -B build -S .`, `cmake --build build --config Release`)
  on every platform. The prebuilt static library step is gone.
- **Documentation**: README is now this example only; configuration guidance
  and troubleshooting moved to a new `TUTORIAL.md`; a new `docs/PICS.md` lists
  the objects and properties.
- Vendored `common/` updated to 3.4.0 (see `common/CHANGELOG.md`).

### Compatibility

- Peers are now given with `--bdt`; the built-in placeholder peers no longer exist.

## [1.1.0] - 2026-09-15

First tagged release: a B-BBMD (BACnet Broadcast Management Device) example. It is
the B-ASC example plus the BBMD function: Network Port 1 reports `BACnet_IP_Mode`
= `bbmd`, a seeded Broadcast Distribution Table lists the peer BBMDs, and the
stack handles forwarding, table reads and foreign-device registration. Built on
CAS BACnet Stack 6.x (abd4cee1, reports 6.0.21).

### Changed

- The released build links a prebuilt static stack library
  (`tools/build-stack-static.sh`, `-DCAS_BACNET_STACK_LINK=STATIC`); see the
  README's "Link mode" section.
- Updated for the 6.0.21 stack API (network port and BDT function signatures;
  Get callbacks can name a specific BACnet error).
- Vendored `common/` updated to 2.1.0.

### Documentation

- README documents two API traps: a BDT entry address is 6 octets (IP and UDP
  port), and the BDT, including this device's own entry, must be filled in before
  the BBMD is enabled.
