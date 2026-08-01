# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Links the CAS BACnet Stack through the `CASBACnetStack::Adapter` CMake target
  instead of compiling its `source/*.cpp` into this project directly.** `main.cpp`
  and `common/CASExampleHelper.cpp` now include `CASBACnetStackAdapter.h` and call
  `LoadBACnetFunctions()` once at the top of `main()`; **every `BACnetStack_*` call
  site is unchanged** — the adapter exposes the same export names in every link
  mode. `CAS_BACNET_STACK_LINK` (`SOURCE` default, or `STATIC`/`DLL`) now picks the
  link mode, so switching is a CMake flag rather than a code change. See the
  README's new "Link modes" section.
  - Stack pinned to `6.x-TestTool` @ `756371c1`, which carries the adapter
    (cas-bacnet-stack PRs #267 and #268).
  - `common/` bumped to **v1.5.1** (see `common/CHANGELOG.md`), byte-identical to
    the other migrated examples. The `LoadBACnetFunctions()` requirement is a
    contract change shared by every example in the series.
  - Release CI now passes `-DCAS_BACNET_STACK_LINK=SOURCE` **explicitly** and
    asserts it back out of `CMakeCache.txt`, so a published artifact stays a
    single self-contained executable even if the CMake default ever moves.
  - README: added parallel-build guidance for the ~600-file first compile, and
    refreshed the Versions table.

## [1.0.0] - unreleased

> Not tagged yet: this repository has no tags at all. `release.yml` publishes binaries on a `v*.*.*`
> tag, so until that tag exists this section describes what is on the
> branch, not what shipped.

First release: a complete B-BBMD (BACnet Broadcast Management Device) tutorial.

### Added

- `main.cpp` implementing the **B-BBMD** profile and nothing more. It is the
  [B-ASC](https://github.com/chipkin/BACnetProfileExample-B-ASC-CPP) example plus
  the one capability the profile exists for:
  - **NM-BBMDC-B** — this device *is* a BBMD: `BACnetStack_SetBBMD` hands
    Network Port 1 over to the stack's BBMD machinery, and a seeded Broadcast
    Distribution Table lists the peer BBMDs to forward local broadcasts to. The
    stack owns the Forwarded-NPDU work, the BDT/FDT reads, and FDT ageing; the
    application only configures the tables.
  - `Network Port 1` reports **`BACnet_IP_Mode` = `bbmd`** (2) — every other
    example in the series reports `normal` (0). This is how a client discovers
    that the port performs the BBMD function.
  - **DS-RP-B / DS-WP-B / DM-DDB-B / DM-DOB-B / DM-DCC-B** — carried over from
    B-ASC unchanged (the series through-line rule: code demonstrating a shared
    BIBB is identical in every example that has it).
- Start-up prints the BDT read back through the stack's own getter, so what is
  shown is what the BBMD will really use, with this device as entry [0].
- Peer addresses are placeholders from the documentation range (RFC 5737
  TEST-NET-1), deliberately unreachable so the example cannot disturb a real
  network if run as-is; `bdtSeeds` in `main.cpp` is the one place to edit.
- `README.md` (human tutorial), `AGENTS.md` (agent guidance), `LICENSE` (CC0-1.0),
  the three BBMD Network Port table properties enabled explicitly (SetBBMD
  does not do it, so ReadProperty would otherwise return unknown-property), and
  the vendored `common/` helper (v1.3.0), and a CMake build that compiles the CAS
  BACnet Stack from source.

### Notes

- **Two BBMD API traps are documented in the code, the README, and AGENTS.md**,
  because both were hit while writing this example and both fail misleadingly:
  1. A BDT entry address is **6 octets** (IP[4] + UDP port, high byte first), not
     the bare 4-octet IP — despite `AddBDTEntry` taking a length argument that
     makes `4` look reasonable.
  2. The BDT must be populated **before** `SetBBMD`, and must already contain this
     device's own entry — the stack does **not** add the self-entry for you.
     `SetBBMD` builds the host's B/IP address from the Network Port's `IP_Address`
     + `BACnet_IP_UDP_Port` and fails if no BDT entry matches it.

  Either mistake produces the same unhelpful pair of errors:
  `Broadcast Distribution Table is not configured with host device entry` /
  `Failed to UpdateHostBDTIndex, aborting BBMD setup`.
- Deliberately **not** implemented, because B-BBMD does not require them:
  ReadPropertyMultiple, SubscribeCOV, alarms/events, scheduling, trending.
- A true end-to-end NM-BBMDC-B test needs **two subnets and two BBMDs**, which is
  inherent to the profile and beyond a single-host example.
- Verified against **CAS BACnet Stack 6.0.0.0** at **Protocol_Revision 24** (the
  stack default). Built and run on Windows (MSVC 2022, C++17): the device starts,
  registers all eight objects, configures the BBMD, reads its BDT back with itself
  as entry [0], and broadcasts its I-Am.

[1.0.0]: https://github.com/chipkin/BACnetProfileExample-B-BBMD-CPP/commits/llm-auto-2026-july
