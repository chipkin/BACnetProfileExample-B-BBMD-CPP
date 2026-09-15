# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - unreleased

### Changed

- **Pinned the CAS BACnet Stack to `6.x` @ `abd4cee1` (reports 6.0.21)** and
  switched this example's shipped build to a prebuilt **STATIC** library:
  `tools/build-stack-static.sh` builds `CASBACnetStack_x64_Release.lib` /
  `libCASBACnetStack_x64_Release.a` from the stack's own project files, and
  `-DCAS_BACNET_STACK_LINK=STATIC` links it. See the README's "Link mode"
  section. The adapter's SOURCE mode still exists but this example is no
  longer built or published that way.
- `common/` synced to **v2.1.0** (see `common/CHANGELOG.md`), byte-identical to
  the other migrated examples.
- Interface changes reaching this example's `main.cpp`:
  - `BACnetStack_AddNetworkPortObjectWithNetworkNumber` → `BACnetStack_AddNetworkPortObject`
    (same argument list).
  - Every `RegisterCallbackGetProperty*` callback gains a trailing
    `uint32_t* errorCode` out-parameter, letting a declining Get callback name
    a specific BACnet error instead of only falling back to the stack's
    decline-and-fabricate default. Ported B-SS's "THE errorCode
    OUT-PARAMETER" documentation and its one real use here: `GetPropertyCharString`
    now sets `ERROR_CODE_INVALID_ARRAY_INDEX` for an out-of-range `State_Text` index.
  - `CASExampleHelper::SetNetworkPortInstance(NETWORK_PORT_INSTANCE)` added
    before `RegisterCommonCallbacks()` — the transport callbacks now dispatch
    per Network Port instance rather than per network type.
  - `BACnetStack_AddBDTEntry` gains a leading `networkPortInstance` parameter
    (both call sites: this device's own entry and each seeded peer).
  - `BACnetStack_GetBDTEntry` gains a leading `networkPortInstance` parameter
    **and now returns `uint32_t`** (the number of bytes written; `0` on
    failure) instead of `bool`. The start-up BDT readback loop now compares
    the result to `0` explicitly rather than negating it with `!`, which
    still worked out logically but forced the `uint32_t` through a `bool`
    conversion the strict build (`/W4`) flags as `C4800`.
- `APP_VERSION` bumped to `1.1.0`.

### Verified

- Builds STATIC with zero warnings from `main.cpp` / `common/`.
- Smoke test (port 47821): `v1.1.0`, `CAS BACnet Stack version: 6.0.21.0`,
  `Common helper (common/) version: 2.1.0`, the device comes up as a BBMD and
  reads back its own seeded 3-entry Broadcast Distribution Table (this
  device + the two documentation-range placeholder peers).
- `--help` / `--version` exit 0; `--deviceID` overrides the announced instance.
- The README's "Three traps" (6-octet BDT address, BDT-before-`SetBBMD` with
  the self-entry, and enabling the BBMD table properties) were re-tested
  against the new signatures and still hold exactly as written.

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
