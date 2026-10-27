# AGENTS.md

Guidance for AI coding agents working in this repository. See
<https://agents.md/> for the format. Human contributors should read
[README.md](README.md) first, then [TUTORIAL.md](TUTORIAL.md).

## What this project is

A **tutorial** C++ example that implements the BACnet **B-BBMD (BACnet Broadcast
Management Device)** profile using the CAS BACnet Stack. It is one of a series -
one git repo per BACnet profile. The top priority is that the code reads like a
tutorial a customer can learn from and copy-paste. Favour clarity over
cleverness.

## Layout

This repository is self-contained:

- `main.cpp` - the example device.
- `common/` - the shared helper (vendored).
- `README.md` - what this example is. Keep it short and about THIS example only.
- `TUTORIAL.md` - how to extend and review the example, and how to configure it
  for a real site (peer BBMDs). Long-form material that would bloat the README
  belongs here.
- `docs/PICS.md` - the Protocol Implementation Conformance Statement. Its
  objects-and-properties section is GENERATED from `docs/objects.json`; do not
  hand-edit between the `OBJECTS-PROPERTIES` markers.
- `docs/objects.json` - the input to that generator. Update it in the same change
  as any `main.cpp` change that adds an object or a `GetProperty*` branch.
- `tests/` - the Wire Tests (Python 3, standard library only) and their
  README, which records the run showing each check fails without its feature.
- `wiretest/` - the series' shared Wiretest Harness (vendored, like `common/`;
  own `WIRETEST_VERSION` and `CHANGELOG.md`). Never put BBMD-specific code in
  it - that belongs in `tests/`. Change it generically, bump its version, and
  re-copy it to every example that vendors it.
- `TODO.md` - known gaps outside this example (stack, `common/`) that the Wire
  Tests report as `[KNOWN GAP]`.
- `submodules/cas-bacnet-stack/` - the **CAS BACnet Stack** as a git submodule
  (private; compiled from source). After cloning, run
  `git submodule update --init --recursive`.

The `PROFILE-TABLE` block in README.md is also generated, from the example-series
repository's `docs/profile-table.md`. Edit it there, not here.

## Build

Plain CMake, identical on every platform, in the adapter's default SOURCE mode
(the stack's sources are compiled into the executable - no prebuilt library, no
DLL, no per-platform pre-step):

```bash
git submodule update --init --recursive   # once, if not cloned with --recursive
cmake -B build -S .
cmake --build build --config Release
```

The first build compiles the whole stack (~600 files) and takes a few minutes;
rebuilds after that are incremental and fast. Use `-D CAS_STACK_DIR=...` only if
your stack lives outside the bundled submodule. Do not reintroduce a link-mode
flag or a series-root build script into the documented build: a customer
downloads this repository on its own and must be able to build it with the two
commands above.

## Run

```bash
./build/BACnetExampleBBBMD [--port 47808] [--deviceID 389020] [--deviceName "Chipkin Example B-BBMD"] [--bdt <ip>[:<port>][/<mask>]]... [--no-bbmd]   # Linux/macOS
.\build\Release\BACnetExampleBBBMD.exe [same options]   # Windows
```

Interactive keys while running: `h` help, `q` quit, up/down nudge Analog Input 1.

## Conventions

- Device is named "Chipkin Example B-BBMD"; objects use the series' colour names; vendor id 389;
  device instance **389020**.
- Implement **only** what B-BBMD requires — DS-RP-B, DS-WP-B, DM-DDB-B, DM-DOB-B,
  DM-DCC-B, NM-BBMDC-B — but expose **every required property** of each object for
  Protocol_Revision 30. Do not add COV, alarms, scheduling, or trending.
- The objects and the DS-WP-B / DM-DCC-B code are **identical to B-ASC** on
  purpose (the series' through-line rule: code demonstrating a shared BIBB is the
  same in every example that has it). If you change them here, they must change in
  every example that shares them — prefer not to.
- **The BBMD function is the stack's job.** Do not write forwarding logic. The
  application only configures the tables (`--bdt`, in `SetUpBbmd()`) and hands
  the port over with `SetBBMD`, which also makes `BACnet_IP_Mode` read `bbmd`
  (`normal` with `--no-bbmd`) and enables the BBMD properties.
- **This device's own BDT entry is two-hop (255.255.255.255).** The stack reads
  its own entry's mask to decide whether to re-broadcast a peer's Forwarded-NPDU
  locally (Annex J.4.5). Do not change it back to the subnet mask.
- **Never edit `common/` in this repo alone** - it is a vendored copy shared by
  every example in the series, with its own version (`COMMON_VERSION`) and
  changelog (`common/CHANGELOG.md`). To change it: edit, bump the version, add
  a changelog entry, then re-copy `common/` into every example repository.

## Two traps in the BBMD API (both cost real time — do not re-learn them)

1. **A BDT entry address is 6 octets, not 4.** It is a BACnet/IP ("B/IP")
   address: `IP[4]` followed by the UDP port, high byte first — the same layout
   as the Network Port's `MAC_Address`. `BACnetStack_AddBDTEntry` takes a length
   argument, which makes passing `4` look reasonable; it is not. Passing 4 does
   not fail at the call — it fails later and confusingly, at `SetBBMD`.
2. **Populate the BDT *before* calling `BACnetStack_SetBBMD`, and include this
   device's own entry.** `SetBBMD` reads this Network Port's `IP_Address` +
   `BACnet_IP_UDP_Port` (through the Get callbacks), builds the host's 6-octet
   B/IP address, and looks for a BDT entry matching it. The stack does **not**
   add the self-entry for you. Get either of these wrong and you get:

   ```
   Error: Broadcast Distribution Table is not configured with host device entry
   Error: Failed to UpdateHostBDTIndex, aborting BBMD setup
   ```

   The self-entry's port must be the port the device is actually listening on, so
   it is built from `--port`, not hardcoded to 47808.

Also: do not probe `GetBDTEntry` upwards until it fails. An out-of-range index is
a genuine error to the stack and it logs one, so a probe loop prints a spurious
error at the end of an otherwise healthy start-up. Iterate a known count.

`GetBDTEntry` returns `uint32_t` (bytes written; `0` = failure), not `bool` -
compare the result to `0` explicitly. Negating it with `!` still gives the right
answer, but forces the `uint32_t` through a `bool` conversion that the strict
build (`/W4`) flags as `C4800`.

## How to verify a change

1. Build, then run the **Wire Tests** - they are the gate:

   ```bash
   python3 tests/run_wire_tests.py --exe build/BACnetExampleBBBMD
   ```

   `ALL WIRE TESTS PASSED` (exit 0) after about two minutes. Linux is the
   reference (it is what `release.yml` runs); on Windows the tests pass more
   slowly because the example's socket misses datagrams there (`TODO.md`).
2. **A behavioural change needs a check that fails without it.** Break the
   feature on purpose, rebuild, and confirm a Wire Test fails; record the run
   in `tests/README.md`'s table. A test that cannot fail proves nothing.
3. A `[KNOWN GAP]` line is a defect outside this example (`TODO.md`). If one
   prints `[GAP CLOSED]`, the defect is fixed: make it a counted `record()`
   check and update `TODO.md`.
4. With a BACnet client (e.g. the CAS BACnet Explorer): Who-Is -> I-Am from
   389020; ReadProperty every required property of every object; confirm
   `Protocol_Revision` is 30 and `Object_List` lists all eight objects.
5. Exercise DM-DCC-B: DeviceCommunicationControl `disable-initiation` is
   accepted; the plain `disable` is answered `service-request-denied` at
   Protocol_Revision >= 20 (a deprecation the stack applies, not a bug here).
6. The local re-broadcast onto a real second subnet is not covered on one host
   (README "Wire Tests"); test it by hand with two BBMDs on two IP subnets when
   the BBMD code changes in a way that could affect it.
7. If you changed the objects or their properties, regenerate `docs/PICS.md`
   (`python tools/gen-objects-properties.py BACnetProfileExample-B-BBMD-CPP` from
   the series root) and confirm no row comes out flagged with ⚠.

## Releasing

Bump `APP_VERSION` in `main.cpp` and add an entry to [CHANGELOG.md](CHANGELOG.md),
then tag `vX.Y.Z`. The GitHub Actions workflow builds and publishes the release.

## License

The example source code is dedicated to the public domain under
[CC0-1.0](LICENSE). The CAS BACnet Stack is a separate, commercially licensed
product and is not covered by that dedication.
