# BACnet B-BBMD (Broadcast Management Device) - C++ example

A minimal, copy-paste-friendly example showing how to implement the BACnet
**B-BBMD (Broadcast Management Device)** device profile in C++ using the
[CAS BACnet Stack](https://store.chipkin.com/services/stacks/bacnet-stack).
It listens on **BACnet/IP (UDP 47808)**, answers **ReadProperty** and
**WriteProperty** requests, is discoverable via **Who-Is / I-Am**, and - the
capability the profile exists for - forwards broadcasts between subnets as a
**BBMD**.

**[Download a prebuilt binary](https://github.com/chipkin/BACnetProfileExample-B-BBMD-CPP/releases)**
(Windows and Linux x64) - or build it yourself, see [Build](#build) below.

- **[TUTORIAL.md](TUTORIAL.md)** - how to extend this example, configure it for
  your site, and review it for conformance. Read it when you start turning this
  into your own device.
- **[docs/PICS.md](docs/PICS.md)** - the Protocol Implementation Conformance
  Statement: every object, every property, and who answers it.

> **Versions:** this document describes **example v1.2.0**, built and verified
> against **CAS BACnet Stack 6.0.23** (`6.x` @ `e6de4ffd`), at
> **Protocol_Revision 30**, with the vendored `common/` helper at **v3.3.0**.
> Running the example prints all three - if what it prints disagrees with this
> line, trust the program and check `CHANGELOG.md`.

## Why BBMDs exist

BACnet/IP leans on broadcasts - Who-Is, I-Am, and Who-Has are all broadcast to
the local subnet. But **IP routers do not forward subnet broadcasts**, so a
plain BACnet/IP device can only ever discover peers on its *own* subnet. That
would make BACnet/IP useless across a real building network.

A **BBMD** fixes this. One BBMD sits on each subnet; they all know about each
other through a **Broadcast Distribution Table (BDT)**. When a BBMD sees a
local broadcast, it forwards it as a **unicast** to every other BBMD in its
BDT, and each of those re-broadcasts it onto its own subnet. The result is a
BACnet internetwork that behaves as though every device were on one wire.

A BBMD also keeps a **Foreign Device Table (FDT)** for remote devices that
register with it directly (`Register-Foreign-Device`) instead of sitting
behind a BBMD of their own - e.g. a laptop running a tool from another subnet.

**The BBMD function is the stack's job, not the application's.** You do not
write forwarding logic. You build the BDT (`BACnetStack_AddBDTEntry`), then
hand the port over (`BACnetStack_SetBBMD`). From then on the stack does the
Forwarded-NPDU work, answers Read-Broadcast-Distribution-Table /
Read-Foreign-Device-Table, and adds, ages out, and removes FDT entries as
foreign devices register and expire. The application's only other job is
reporting `BACnet_IP_Mode` = `bbmd` - which is how a client discovers that
this port performs the BBMD function.

## The device this example creates

```
Device 389020  "Chipkin Example B-BBMD"   (Vendor 389 - Chipkin Automation Systems)
    │
    ├── Analog Input 1        "Bronze"      Present_Value  21.5     (REAL, degrees Celsius; read-only)
    ├── Binary Input 1        "Emerald"     Present_Value  active   (0 = inactive / 1 = active; read-only)
    ├── Multi-State Input 1   "Hot Pink"    Present_Value  1        (state, 1..3; read-only)
    ├── Analog Output 1       "Chartreuse"  Present_Value  20.0     (REAL setpoint; WRITABLE, commandable)
    ├── Binary Output 1       "Fuchsia"     Present_Value  inactive (WRITABLE, commandable)
    ├── Multi-State Output 1  "Indigo"      Present_Value  1        (state, 1..3; WRITABLE, commandable)
    └── Network Port 1        "Vermilion"   the BACnet/IP port; BACnet_IP_Mode = bbmd (required on every device)
```

The peer BBMDs come from the command line: one `--bdt <ip>[:<port>][/<mask>]`
per peer (see [Command-line options](#command-line-options)). With none, the
device is a BBMD with no peers - it still accepts foreign devices and passes
their broadcasts to its own subnet and to each other. A client can replace the
table at run time by writing the Network Port's
`BBMD_Broadcast_Distribution_Table` (Annex J.4.4) and sending ReinitializeDevice
ACTIVATE_CHANGES (cl. 12.56.38). `--no-bbmd` starts it as a
plain BACnet/IP device instead (Annex L.7.3 requires a BBMD that also does
other BACnet work to be able to be reconfigured as a non-BBMD).

The sensor values (Analog Input 21.5 degC and the rest) are **Simulation**:
fixed numbers standing in for real hardware. The BBMD function is not simulated
- it is the stack's real BBMD, proven by the [Wire Tests](#wire-tests).

## What this example supports

Annex L allows a **Miscellaneous** profile like B-BBMD to be **combined** with
one other family - a real product is often "B-BC + B-BBMD". This example
claims only B-BBMD, demonstrating the BBMD function on the smallest device
that can carry it.

### BIBBs (BACnet Interoperability Building Blocks)

These six are what the B-BBMD profile requires, and they are what this example
implements. NM-BBMDC-B is the profile's defining BIBB.

| BIBB | Description | Supported |
|------|-------------|:---------:|
| DS-RP-B | Data Sharing - ReadProperty - B | ✅ |
| DS-WP-B | Data Sharing - WriteProperty - B | ✅ |
| DM-DDB-B | Device Management - Dynamic Device Binding - B | ✅ |
| DM-DOB-B | Device Management - Dynamic Object Binding - B | ✅ |
| DM-DCC-B | Device Management - DeviceCommunicationControl - B | ✅ |
| NM-BBMDC-B | Network Management - Broadcast Management Device Configuration - B | ✅ |

**Deliberately NOT included** - a B-BBMD does not require them:
ReadPropertyMultiple, SubscribeCOV, alarms and events, scheduling, and
trending.

### Services (executed / B-side)

| Service | Notes |
|---------|-------|
| ReadProperty | Responds to property reads (DS-RP-B). |
| WriteProperty | Accepts writes to the three commandable outputs (DS-WP-B). |
| Who-Is / I-Am | Answers Who-Is with I-Am, and broadcasts an I-Am on start-up (DM-DDB-B). |
| Who-Has / I-Have | Answers Who-Has with I-Have (DM-DOB-B). |
| DeviceCommunicationControl | Stops/resumes communication, with an optional password (DM-DCC-B). |
| ReinitializeDevice | ACTIVATE_CHANGES and WARMSTART only: what makes a written BDT effective (cl. 12.56.38). Other states are refused. |
| BBMD (Annex J BVLL: Forwarded-NPDU, Distribute-Broadcast-To-Network, Register-Foreign-Device, Read-BDT, Read-FDT, Delete-FDT-Entry; Write-BDT answered with NAK X'0010') | Handled entirely by the stack once the Network Port is handed over with `SetBBMD` (NM-BBMDC-B). The BDT is configured with `--bdt` at start-up, or by WriteProperty of `BBMD_Broadcast_Distribution_Table`. |

### Object types

| Object type | Instance | Name |
|-------------|:--------:|------|
| Device | 389020 | Chipkin Example B-BBMD |
| Analog Input | 1 | Bronze |
| Binary Input | 1 | Emerald |
| Multi-State Input | 1 | Hot Pink |
| Analog Output | 1 | Chartreuse |
| Binary Output | 1 | Fuchsia |
| Multi-State Output | 1 | Indigo |
| Network Port | 1 | Vermilion |

Every required property of every object, and who answers it, is in
[docs/PICS.md](docs/PICS.md).

## Requires the CAS BACnet Stack (licensed product)

This example **builds against the CAS BACnet Stack, which is a commercial
Chipkin product** - it is not free or open source, and there is no
public/trial build. The stack is referenced here as the **private** git
submodule `submodules/cas-bacnet-stack`; you can only fetch and build it once
you have a CAS BACnet Stack license and access to that repository.

**To get the CAS BACnet Stack (and access to build this example), contact
Chipkin:** <https://store.chipkin.com/services/stacks/bacnet-stack> or
sales@chipkin.com.

You do not need a stack licence to *read* this example, or to run a
[prebuilt release binary](https://github.com/chipkin/BACnetProfileExample-B-BBMD-CPP/releases).
The licence is what lets you *build* it - that is the part the stack submodule
gates.

## What's in this repository

This is a **self-contained** project. It ships:

- `main.cpp` - the example device.
- `common/` - the shared helper (UDP, callbacks, CLI, keyboard) vendored in.
- `CMakeLists.txt` - the build, the same on Windows, Linux, and macOS.
- `docs/PICS.md` - the conformance statement.
- `submodules/cas-bacnet-stack/` - the **CAS BACnet Stack as a git submodule**
  (private; requires a license - see above). Its sources are compiled into the
  executable, so there is no library or DLL to build, ship, or install.

## Prerequisites

- A C++17 compiler (MSVC, GCC, or Clang).
- CMake >= 3.15.
- Git (to fetch the stack submodule).

### Windows

- **C++ compiler** - install
  [Visual Studio Community](https://visualstudio.microsoft.com/downloads/)
  (free) and select the **"Desktop development with C++"** workload.
- **CMake** - from <https://cmake.org/download/>, or `winget install Kitware.CMake`.

### Linux / macOS

- Debian/Ubuntu: `sudo apt install build-essential cmake git`
- macOS: `xcode-select --install` and `brew install cmake`

## Build

CMake only, and the same two commands on every platform:

```bash
git clone --recursive https://github.com/chipkin/BACnetProfileExample-B-BBMD-CPP.git
cd BACnetProfileExample-B-BBMD-CPP

cmake -B build -S .
cmake --build build --config Release
```

Already cloned without `--recursive`? Run `git submodule update --init --recursive`
first - the build needs the stack submodule.

> **The first build takes a few minutes** - it compiles the entire CAS BACnet
> Stack (~600 source files) into the executable. Rebuilds after that are
> incremental and take seconds.

If your CAS BACnet Stack lives somewhere other than the bundled submodule, point
CMake at it: `cmake -B build -S . -D CAS_STACK_DIR=/path/to/cas-bacnet-stack`.

## Run

```bash
# Linux / macOS
./build/BACnetExampleBBBMD

# Windows
.\build\Release\BACnetExampleBBBMD.exe
```

Expected output:

```
BACnet B-BBMD (BACnet Broadcast Management Device) Example - C++ v1.2.0
CAS BACnet Stack version: 6.0.23.0
Common helper (common/) version: 3.3.0
FYI: Listening for BACnet/IP on UDP port 47808 (Network Port 1).
FYI: this device is a BBMD. Broadcast Distribution Table:
      [0] 192.168.3.64:47808  mask 255.255.255.255   <- this device
      [1] 192.168.2.10:47808  mask 255.255.255.255
      (the Foreign Device Table starts empty and fills in as remote
       devices send Register-Foreign-Device to this BBMD.)
TX 21 bytes to 192.168.3.255:47808 (broadcast) (Network Port 1) - Unconfirmed: I-Am
TX 27 bytes to 192.168.2.10:47808 (Network Port 1) - Unconfirmed: I-Am
FYI: Device 389020 ("Chipkin Example B-BBMD") ready. Vendor ID 389. Press 'h' for help.
```

(run with `--bdt 192.168.2.10`). The first `TX` line is the start-up I-Am the
device broadcasts to announce itself, on the **local subnet broadcast** address
(here `192.168.3.255`, computed from the Network Port's interface). The second
is the BBMD at work: the same broadcast, forwarded to the peer BBMD as a
Forwarded-NPDU. As clients talk to the device you'll see `RX ... bytes from ...`
and `TX ... bytes to ...` lines showing the traffic.

Entry `[0]` is this device. Its mask is `255.255.255.255` ("two-hop", like the
peers) on purpose: the stack reads its **own** entry's mask to decide whether a
Forwarded-NPDU from a peer must be re-broadcast on this subnet (Annex J.4.5),
and J.4.3.2 requires every BDT to give one subnet the same mask. To use one-hop
for this subnet, list this device's own address with `--bdt` and the subnet
mask.

The device listens on UDP **47808** (BACnet/IP). Allow that port through your
firewall. To use a different port, pass `--port` (see below).

> **Red `Error:` lines while it runs are mostly the stack's own debug logging**,
> for example when a peer BBMD is unreachable or a foreign device's
> registration is refused. [TUTORIAL.md](TUTORIAL.md#troubleshooting) explains
> them.

### Command-line options

| Option | Default | Meaning |
|--------|---------|---------|
| `--port <n>` | `47808` | UDP port to listen on (BACnet/IP). |
| `--deviceID <n>` | `389020` | The device's BACnet instance number (BACnet requires this to be configurable). |
| `--bdt <ip>[:<port>][/<mask>]` | none | A peer BBMD for the Broadcast Distribution Table; repeat once per peer. Port defaults to 47808, mask to `255.255.255.255` (two-hop). This device's own entry is added for you. |
| `--no-bbmd` | off | Start as a plain BACnet/IP device (`BACnet_IP_Mode` = `normal`), not a BBMD. |
| `--help`, `-h` | - | Show usage and exit. |
| `--version` | - | Print the example, stack, and `common/` helper versions, then exit. |

### Interactive commands

While the example runs, these keys are available:

| Key | Action |
|-----|--------|
| `h` | Show the version information and this command list. |
| `q` | Quit. |
| up arrow | Increase Analog Input 1 (`Bronze`) by 1.1. |
| down arrow | Decrease Analog Input 1 (`Bronze`) by 1.1. |

The up/down keys change the live `Present_Value` of the analog input, so a
client re-reading it sees the new value.

## Verify

Use a BACnet client such as the
[**CAS BACnet Explorer**](https://store.chipkin.com/products/tools/cas-bacnet-explorer):

1. **Who-Is** -> an I-Am from device **389020**, vendor **389**. It also
   broadcasts an I-Am at start-up.
2. **ReadProperty** `Network Port 1` `BACnet_IP_Mode` -> `bbmd` (2). Every
   other example in this series reports `normal` (0) here; this is the
   difference.
3. **ReadProperty** `Network Port 1` `BBMD_Broadcast_Distribution_Table` -> the
   same entries printed at start-up.
4. **Read a sensor** - ReadProperty Analog Input `1` -> `Present_Value`
   returns `21.5`; `Units` returns `degrees-Celsius`. Repeat for Binary Input
   `1` and Multi-State Input `1`.
5. **WriteProperty** the outputs - e.g. Analog Output `1`'s `Present_Value` to
   any REAL value at a priority 1-16; ReadProperty it back and confirm it
   changed. Writing `NULL` relinquishes that priority slot.
6. **DeviceCommunicationControl** `disable-initiation` -> accepted; the device
   stops initiating but still answers reads. (The plain `disable` is answered
   `service-request-denied` at Protocol_Revision >= 20 - a deprecation the
   stack applies, not a quirk of this example.)

7. **Read-Broadcast-Distribution-Table** / **Read-Foreign-Device-Table** (the
   BVLL messages; the CAS BACnet Explorer's BBMD tools send them) -> the BDT
   above, and every foreign device registered with it.

For a property-by-property review against the conformance statement, see
[TUTORIAL.md](TUTORIAL.md).

## Two BBMDs on one host

The Profile Function - carrying a broadcast from one BBMD to another - can be
seen on a single machine. Start two instances on different UDP ports, each
listing the other as its peer:

```bash
./build/BACnetExampleBBBMD --port 47900 --deviceID 389021 --bdt 127.0.0.1:47901
./build/BACnetExampleBBBMD --port 47901 --deviceID 389022 --bdt 127.0.0.1:47900
```

Each start-up I-Am now appears twice: once on its own subnet, and once on the
other instance's console as a Forwarded-NPDU it received from its peer. Point a
client at one of them as a **foreign device** (Register-Foreign-Device), send a
Who-Is, and the I-Am from the *other* instance comes back through both BBMDs.

The peers are named at `127.0.0.1`, not the LAN address, for a reason that
only exists on one host. Annex J.4.5 says a Forwarded-NPDU from a sender "on
the same IP subnet" was already heard by every device there, and the stack
judges "same subnet" from the sender's IP. Two instances on one machine share
one IP, so a Forwarded-NPDU between them over the LAN address looks local and
is not passed on. Over `127.0.0.1` it arrives from a different address, exactly
as it would from a peer on another subnet. On a real site, use each peer's own
address.

## Wire Tests

Automated tests drive the running example over BACnet/IP from outside it and
fail when its BBMD function is removed. Their Peers - foreign devices and
stand-in peer BBMDs - are Python, never another example's binary; they put
hand-built Annex J frames on the wire and check the octets that come back.
Python 3 standard library only. Build the example, then from the repository
root:

```bash
python3 tests/run_wire_tests.py --exe build/BACnetExampleBBBMD
```

It ends with `ALL WIRE TESTS PASSED` (exit 0) after about two minutes - one
test waits out a foreign device's 30-second grace period. The `release.yml`
workflow runs the same command on Linux after the smoke test. What each script
proves, and the run that showed each check fails without its feature, is in
[tests/README.md](tests/README.md). In short:

- **The Profile Function** (`forwarding_test.py`): two instances, BBMD A and
  BBMD B, peered two-hop. A Python foreign device F1 registered with A sends a
  Who-Is as Distribute-Broadcast-To-Network; Python foreign device F2,
  registered with B, receives it from B as a Forwarded-NPDU carrying F1's
  address. B's own device answers with an I-Am that reaches F2 and, through A,
  F1. A third instance shows the K.6.6 minimums: five peer BBMDs and five
  foreign devices.
- **Managing the tables** (`tables_test.py`): Read-BDT and Read-FDT replies,
  Delete-FDT-Entry, Write-BDT NAKed X'0010', `BACnet_IP_Mode` = `bbmd`, and a
  WriteProperty of `BBMD_Broadcast_Distribution_Table` followed by
  ReinitializeDevice ACTIVATE_CHANGES, after which the next broadcast reaches
  the new peer.
- **Failure Modes** (`failure_modes_test.py`): a foreign device that stops
  re-registering is purged after its Time-to-Live plus 30 seconds and its
  broadcasts are refused (NAK X'0060'); a full Foreign Device Table refuses the
  next registration (NAK X'0030'); and `--no-bbmd` answers every BBMD message
  with the NAK Annex J requires of a non-BBMD.

What the Wire Tests do **not** show:

- **B re-broadcasting onto its own subnet.** On Linux/macOS the test captures
  it; Windows refuses the second socket on B's port that capturing needs. The
  stack's unit tests (`tests/BACnetBBMDTests.cpp` in the stack) also cover the
  re-broadcast logic. A real two-subnet test - two BBMDs on two IP subnets, a
  device behind each - is done by hand when needed.
- **Peers that share one IP address.** J.4.5 says that a BBMD receiving a
  Forwarded-NPDU from a peer on its own subnet must still pass it to its
  foreign devices. Stack `6.x` @ `e6de4ffd` drops it instead. The test reports
  this as a `[KNOWN GAP]` (see [TODO.md](TODO.md)); it is why the one-host
  setup above names peers at `127.0.0.1`.
- **A BDT write waiting for ReinitializeDevice.** Cl. 12.56.38 says a written
  BDT becomes effective on ReinitializeDevice ACTIVATE_CHANGES or WARMSTART;
  stack `6.x` @ `e6de4ffd` applies it at once. Reported as a `[KNOWN GAP]`
  ([TODO.md](TODO.md)).
- **`BBMD_Accept_FD_Registrations` = FALSE.** At this Stack Pin that property
  always reads TRUE and is not writable, so a BBMD that refuses all
  registrations cannot be configured. Stack `6.x` after `e6de4ffd` makes it
  writable (#3321); see [TODO.md](TODO.md).

On Windows the tests pass, but more slowly: the example's socket misses some
incoming datagrams there (see [TODO.md](TODO.md)), so the tests repeat any
request that gets no answer.


## The BACnet profile example series

<!-- PROFILE-TABLE:BEGIN (generated from cas-bacnet-stack-examples/docs/profile-table.md - do not edit here) -->
There is one example repository per standardized device profile in ASHRAE 135-2024 Annex L. An example marked ⛔ is blocked: the stack cannot yet perform that profile's function through its customer interface, and the example's README says what it does today. Pick the profile your device claims, then the language you build in. "Ask" means the example hasn't been built yet for that language - [contact Chipkin](https://store.chipkin.com/contact-us) if you need one.

### Controllers (Annex L.4)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-SS** Smart Sensor | [B-SS-CPP](https://github.com/chipkin/BACnetProfileExample-B-SS-CPP) | [B-SS-Node](https://github.com/chipkin/BACnetProfileExample-B-SS-Node) | [B-SS-CS](https://github.com/chipkin/BACnetProfileExample-B-SS-CS) | [B-SS-Rust](https://github.com/chipkin/BACnetProfileExample-B-SS-Rust) | [B-SS-Python](https://github.com/chipkin/BACnetProfileExample-B-SS-Python) | [B-SS-Go](https://github.com/chipkin/BACnetProfileExample-B-SS-Go) |
| **B-SA** Smart Actuator | [B-SA-CPP](https://github.com/chipkin/BACnetProfileExample-B-SA-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-ASC** Application Specific Controller | [B-ASC-CPP](https://github.com/chipkin/BACnetProfileExample-B-ASC-CPP) | [B-ASC-Node](https://github.com/chipkin/BACnetProfileExample-B-ASC-Node) | Ask | Ask | Ask | Ask |
| **B-AAC** Advanced Application Controller | [B-AAC-CPP](https://github.com/chipkin/BACnetProfileExample-B-AAC-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-BC** Building Controller | [B-BC-CPP](https://github.com/chipkin/BACnetProfileExample-B-BC-CPP) | Ask | Ask | Ask | Ask | Ask |

### Life safety controllers (Annex L.5)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-LSC** Life Safety Controller | [B-LSC-CPP](https://github.com/chipkin/BACnetProfileExample-B-LSC-CPP) 🚧 | Ask | Ask | Ask | Ask | Ask |
| **B-ALSC** Advanced Life Safety Controller | [B-ALSC-CPP](https://github.com/chipkin/BACnetProfileExample-B-ALSC-CPP) | Ask | Ask | Ask | Ask | Ask |

### Access control controllers (Annex L.6)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-ACC** Access Control Controller | [B-ACC-CPP](https://github.com/chipkin/BACnetProfileExample-B-ACC-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-AACC** Advanced Access Control Controller | [B-AACC-CPP](https://github.com/chipkin/BACnetProfileExample-B-AACC-CPP) | Ask | Ask | Ask | Ask | Ask |

### Lighting controllers (Annex L.11)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-LD** Lighting Device | [B-LD-CPP](https://github.com/chipkin/BACnetProfileExample-B-LD-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-LS** Lighting Supervisor | [B-LS-CPP](https://github.com/chipkin/BACnetProfileExample-B-LS-CPP) | Ask | Ask | Ask | Ask | Ask |

### Elevator controllers (Annex L.13)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-EM** Elevator Monitor | [B-EM-CPP](https://github.com/chipkin/BACnetProfileExample-B-EM-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-EC** Elevator Controller | [B-EC-CPP](https://github.com/chipkin/BACnetProfileExample-B-EC-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-AEC** Advanced Elevator Controller | [B-AEC-CPP](https://github.com/chipkin/BACnetProfileExample-B-AEC-CPP) | Ask | Ask | Ask | Ask | Ask |

### Authentication and authorization (Annex L.14)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-AS** Authorization Server | [B-AS-CPP](https://github.com/chipkin/BACnetProfileExample-B-AS-CPP) | Ask | Ask | Ask | Ask | Ask |

### Miscellaneous (Annex L.7, combinable with any one family)

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-BBMD** Broadcast Management Device | [B-BBMD-CPP](https://github.com/chipkin/BACnetProfileExample-B-BBMD-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-ACDC** Access Control Door Controller | [B-ACDC-CPP](https://github.com/chipkin/BACnetProfileExample-B-ACDC-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-ACCR** Access Control Credential Reader | [B-ACCR-CPP](https://github.com/chipkin/BACnetProfileExample-B-ACCR-CPP) ⛔ blocked: credential format not reportable (no stack issue yet) | Ask | Ask | Ask | Ask | Ask |
| **B-RTR** Router | [B-RTR-CPP](https://github.com/chipkin/BACnetProfileExample-B-RTR-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-GW** Gateway | [B-GW-CPP](https://github.com/chipkin/BACnetProfileExample-B-GW-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-DAP** Device Address Proxy | [B-DAP-CPP](https://github.com/chipkin/BACnetProfileExample-B-DAP-CPP) ⛔ blocked on [stack #2032](https://github.com/chipkin/cas-bacnet-stack/issues/2032) | Ask | Ask | Ask | Ask | Ask |
| **B-SCHUB** BACnet/SC Hub | [B-SCHUB-CPP](https://github.com/chipkin/BACnetProfileExample-B-SCHUB-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-GENERAL** General device (Annex L.8) | *(satisfied by every example above)* | — | — | — | — | — |

### Operator interfaces and workstations (Annex L.1–L.3, L.9–L.10, L.12)

Client-side profiles.

| Profile | C++ | Node.js | C# | Rust | Python | Go |
|---|---|---|---|---|---|---|
| **B-OD** Operator Display | [B-OD-CPP](https://github.com/chipkin/BACnetProfileExample-B-OD-CPP) | Ask | Ask | Ask | Ask | Ask |
| **B-OWS** Operator Workstation | planned | — | — | — | — | — |
| **B-AWS** Advanced Operator Workstation | planned | — | — | — | — | — |
| **B-XAWS** Extended Advanced Operator Workstation | planned | — | — | — | — | — |
| **B-LSAP** Life Safety Annunciator Panel | planned | — | — | — | — | — |
| **B-LSWS** Life Safety Workstation | planned | — | — | — | — | — |
| **B-ALSWS** Advanced Life Safety Workstation | planned | — | — | — | — | — |
| **B-ACSD** Access Control Security Display | planned | — | — | — | — | — |
| **B-ACWS** Access Control Workstation | planned | — | — | — | — | — |
| **B-AACWS** Advanced Access Control Workstation | planned | — | — | — | — | — |
| **B-LOD** Lighting Operator Display | planned | — | — | — | — | — |
| **B-ALWS** Advanced Lighting Workstation | planned | — | — | — | — | — |
| **B-LCS** Lighting Control Station | planned | — | — | — | — | — |
| **B-ALCS** Advanced Lighting Control Station | planned | — | — | — | — | — |
| **B-ED** Elevator Display | planned | — | — | — | — | — |
| **B-EWS** Elevator Workstation | planned | — | — | — | — | — |
| **B-AEWS** Advanced Elevator Workstation | planned | — | — | — | — | — |

🚧 = in progress. ⛔ = Blocked Example (blocked on the named stack gap). "Ask" = not yet built for that language; contact Chipkin if you need it. Profile definitions: ANSI/ASHRAE 135-2024 Annex L. BIBB definitions: Annex K. Get the stack: <https://store.chipkin.com/services/stacks/bacnet-stack>.
<!-- PROFILE-TABLE:END -->

## References

- **ANSI/ASHRAE Standard 135** (BACnet) - the protocol standard. Object model
  (Clause 12), services (Clause 15), BACnet/IP and BBMDs (Annex J), device
  profiles (Annex L). Purchase / preview via the
  [ASHRAE store](https://www.ashrae.org/technical-resources/standards-and-guidelines).
- **What is BACnet?** - Chipkin's introduction:
  <https://docs.chipkin.com/protocols/bacnet/>.
- **CAS BACnet Stack** - product page and documentation:
  <https://store.chipkin.com/services/stacks/bacnet-stack>.
- **CAS BACnet Explorer** - client for testing this device:
  <https://store.chipkin.com/products/tools/cas-bacnet-explorer>.
- **Shared helper used by this example** - [`common/README.md`](common/README.md).

See also [TUTORIAL.md](TUTORIAL.md), [docs/PICS.md](docs/PICS.md),
[CHANGELOG.md](CHANGELOG.md), and [AGENTS.md](AGENTS.md).
