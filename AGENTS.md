# AGENTS.md

Guidance for AI coding agents working in this repository. See
<https://agents.md/> for the format. Human contributors should read
[README.md](README.md) first.

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
- `submodules/cas-bacnet-stack/` - the **CAS BACnet Stack** as a git submodule
  (private; compiled from source). After cloning, run
  `git submodule update --init --recursive`.

## Build

```bash
git submodule update --init --recursive   # once, if not cloned with --recursive
cmake -B build -S .
cmake --build build --config Release
```

The first build compiles the whole stack (~600 files) and takes a few minutes;
later incremental builds are fast. Use `-D CAS_STACK_DIR=...` only if your stack
lives outside the bundled submodule.

## Run

```bash
./build/BACnetExampleBBBMD [--port 47808] [--deviceID 389020]   # Linux/macOS
.\build\Release\BACnetExampleBBBMD.exe [--port 47808] [--deviceID 389020]   # Windows
```

Interactive keys while running: `h` help, `q` quit, up/down nudge Analog Input 1.

## Conventions

- Device is named "Rainbow"; objects use the series' colour names; vendor id 389;
  device instance **389020**.
- Implement **only** what B-BBMD requires — DS-RP-B, DS-WP-B, DM-DDB-B, DM-DOB-B,
  DM-DCC-B, NM-BBMDC-B — but expose **every required property** of each object for
  Protocol_Revision 24. Do not add COV, alarms, scheduling, or trending.
- The objects and the DS-WP-B / DM-DCC-B code are **identical to B-ASC** on
  purpose (the series' through-line rule: code demonstrating a shared BIBB is the
  same in every example that has it). If you change them here, they must change in
  every example that shares them — prefer not to.
- **The BBMD function is the stack's job.** Do not write forwarding logic. The
  application only configures the tables and reports `BACnet_IP_Mode` = `bbmd`.
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

## How to verify a change

There are no unit tests; verification is behavioural:

1. Build, then run one instance on a clear UDP port.
2. Confirm start-up prints the BDT with **this device as entry [0]** and no stack
   errors. If `SetBBMD` failed the process exits non-zero — that alone catches
   both traps above.
3. With a BACnet client (e.g. the CAS BACnet Explorer), send **Who-Is** and
   confirm **I-Am** from device 389020.
4. **ReadProperty** `Network Port 1` `BACnet_IP_Mode` → must be `bbmd` (2), not
   `normal`. This is what tells a client the port performs the BBMD function.
5. **ReadProperty** every required property of every object; confirm
   `Protocol_Revision` is 24 and `Object_List` lists all eight objects.
6. Exercise DM-DCC-B: DeviceCommunicationControl `disable-initiation` is accepted;
   the plain `disable` is answered `service-request-denied` at Protocol_Revision
   ≥ 20 (a deprecation the stack applies, not a bug here).
7. A true end-to-end NM-BBMDC-B test needs **two subnets and two BBMDs**, which is
   beyond a single-host example. Point real peer BBMDs at each other by editing
   `bdtSeeds`, then confirm a Who-Is broadcast on one subnet produces an I-Am from
   a device on the other.

## Releasing

Bump `APP_VERSION` in `main.cpp` and add an entry to [CHANGELOG.md](CHANGELOG.md),
then tag `vX.Y.Z`. The GitHub Actions workflow builds and publishes the release.

## License

The example source code is dedicated to the public domain under
[CC0-1.0](LICENSE). The CAS BACnet Stack is a separate, commercially licensed
product and is not covered by that dedication.
