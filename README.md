# BACnet B-BBMD (BACnet Broadcast Management Device) — C++ example

A complete, self-contained C++ tutorial that implements the **B-BBMD (BACnet
Broadcast Management Device)** profile from ASHRAE 135 Annex L using the
[CAS BACnet Stack](https://store.chipkin.com/products/stacks/cas-bacnet-stack).

Part of the CAS BACnet Stack **BACnet profile example series** — one repository
per BACnet device profile. This example claims **only** B-BBMD.

## Why BBMDs exist

BACnet/IP leans on broadcasts — Who-Is, I-Am, and Who-Has are all broadcast to the
local subnet. But **IP routers do not forward subnet broadcasts**, so a plain
BACnet/IP device can only ever discover peers on its *own* subnet. That would make
BACnet/IP useless across a real building network.

A **BBMD** fixes this. One BBMD sits on each subnet; they all know about each other
through a **Broadcast Distribution Table (BDT)**. When a BBMD sees a local
broadcast, it forwards it as a **unicast** to every other BBMD in its BDT, and each
of those re-broadcasts it onto its own subnet. The result is a BACnet internetwork
that behaves as though every device were on one wire.

A BBMD also keeps a **Foreign Device Table (FDT)** for remote devices that register
with it directly (`Register-Foreign-Device`) instead of sitting behind a BBMD of
their own — e.g. a laptop running a tool from another subnet.

## What this example supports

| Required BIBB | What it means | How this example does it |
|---|---|---|
| **DS-RP-B** | Execute ReadProperty | `SERVICE_READ_PROPERTY` enabled; `GetProperty*` callbacks |
| **DS-WP-B** | Execute WriteProperty | `SERVICE_WRITE_PROPERTY` enabled; commandable outputs (same as B-SA/B-ASC) |
| **DM-DDB-B** | Answer Who-Is with I-Am | Handled by the stack; plus an unsolicited I-Am on start-up |
| **DM-DOB-B** | Answer Who-Has with I-Have | Handled by the stack |
| **DM-DCC-B** | Execute DeviceCommunicationControl | `SERVICE_DEVICE_COMMUNICATION_CONTROL` + one callback (identical to B-ASC) |
| **NM-BBMDC-B** | **Be a BBMD** | `BACnetStack_SetBBMD` + a seeded BDT; `BACnet_IP_Mode` reports `bbmd` |

**Deliberately NOT included** — a B-BBMD does not require them: ReadPropertyMultiple,
SubscribeCOV, alarms and events, scheduling, and trending.

> Annex L allows a **Miscellaneous** profile like B-BBMD to be **combined** with one
> other family — a real product is often "B-BC + B-BBMD". This example claims only
> B-BBMD, demonstrating the BBMD function on the smallest device that can carry it.

## The BBMD function is the stack's job

This is the main thing to take away. **You do not write forwarding logic.** You:

1. build the BDT (`BACnetStack_AddBDTEntry`), then
2. hand the port over (`BACnetStack_SetBBMD`).

From then on the stack does the Forwarded-NPDU work, answers
Read-Broadcast-Distribution-Table / Read-Foreign-Device-Table, and adds, ages out,
and removes FDT entries as foreign devices register and expire. The application's
only other job is reporting `BACnet_IP_Mode` = `bbmd` — which is how a client
discovers that this port performs the BBMD function.

## Two traps worth knowing before you copy this

Both cost real debugging time, and both fail in misleading ways:

**1. A BDT entry address is 6 octets, not 4.** It is a BACnet/IP ("B/IP") address:
the 4 IP octets followed by the **UDP port, high byte first** — the same layout the
Network Port's `MAC_Address` uses. `AddBDTEntry` takes a length argument, which
makes passing `4` look reasonable. It is not.

**2. Populate the BDT *before* `SetBBMD`, and include this device's own entry.**
Per Annex J a BBMD's BDT includes itself, and `SetBBMD` **requires** that entry to
already exist: it reads this Network Port's `IP_Address` + `BACnet_IP_UDP_Port`
through your Get callbacks, builds the host's 6-octet B/IP address, and looks for a
matching BDT entry. **The stack does not add the self-entry for you.** Get either
trap wrong and you get the same unhelpful pair of errors:

```
Error: Broadcast Distribution Table is not configured with host device entry
Error: Failed to UpdateHostBDTIndex, aborting BBMD setup
```

## Objects

Identical to [B-ASC](https://github.com/chipkin/BACnetProfileExample-B-ASC-CPP) —
a BBMD is a network function, not a new object model:

| Object | Instance | Name | Notes |
|---|---|---|---|
| Device | 389020 | Rainbow | Configurable with `--deviceID` |
| Analog Input | 1 | Bronze | REAL, °C; read-only; starts at 21.5 |
| Binary Input | 1 | Emerald | active / inactive; read-only |
| Multi-State Input | 1 | Hot Pink | state 1..3; read-only |
| Analog Output | 1 | Chartreuse | REAL setpoint; WRITABLE, commandable |
| Binary Output | 1 | Fuchsia | active / inactive; WRITABLE, commandable |
| Multi-State Output | 1 | Indigo | state 1..3; WRITABLE, commandable |
| Network Port | 1 | Vermilion | The BACnet/IP port — **reports `BACnet_IP_Mode` = `bbmd`** |

## Configure it for your site

The peer addresses in `main.cpp` are **placeholders** from the documentation range
(RFC 5737 TEST-NET-1), deliberately chosen so they cannot collide with a real device
if you run the example as-is — they are unreachable, so the stack simply logs the
failed forwards rather than disturbing anyone's network.

Edit `bdtSeeds` in `main.cpp` to list your real peer BBMDs — one entry per remote
subnet. A real product would load this table from its configuration, and/or let a
client write it over BACnet with `Write-Broadcast-Distribution-Table`.

## Build

```bash
git clone --recursive https://github.com/chipkin/BACnetProfileExample-B-BBMD-CPP.git
cd BACnetProfileExample-B-BBMD-CPP
cmake -B build -S .
cmake --build build --config Release
```

If you cloned without `--recursive`, run `git submodule update --init --recursive`
first. The first build compiles the whole CAS BACnet Stack (~460 source files) and
takes a few minutes; later incremental builds are fast.

## Run

```bash
./build/BACnetExampleBBBMD                       # Linux/macOS
.\build\Release\BACnetExampleBBBMD.exe           # Windows
```

Options: `--help`, `--version`, `--deviceID <n>` (default 389020), `--port <n>`
(default 47808). Interactive keys: `h` help, `q` quit, up/down nudge Analog Input 1.

Start-up prints the BDT the stack is actually holding — read back through the
stack's own getter, so what you see is what the BBMD will really use:

```
FYI: Device 389020 ("Rainbow") ready. Vendor ID 389. Press 'h' for help.
FYI: this device is a BBMD. Broadcast Distribution Table:
      [0] 192.168.3.73:47808  mask 255.255.255.0   <- this device
      [1] 192.0.2.10:47808  mask 255.255.255.255
      [2] 192.0.2.20:47808  mask 255.255.255.255
      (the Foreign Device Table starts empty and fills in as remote
       devices send Register-Foreign-Device to this BBMD.)
```

## Try it

With a BACnet client (e.g. the
[CAS BACnet Explorer](https://store.chipkin.com/products/tools/cas-bacnet-explorer)):

1. **Who-Is** → an I-Am from device **389020**, vendor **389**.
2. **ReadProperty** `Network Port 1` `BACnet_IP_Mode` → `bbmd` (2). Every other
   example in this series reports `normal` (0) here; this is the difference.
3. **ReadProperty** `Network Port 1` `BBMD_Broadcast_Distribution_Table` → the same
   three entries printed at start-up.
4. **WriteProperty** the outputs, exactly as in
   [B-SA](https://github.com/chipkin/BACnetProfileExample-B-SA-CPP).
5. **DeviceCommunicationControl** `disable-initiation` → accepted; the device stops
   initiating but still answers reads. (The plain `disable` is answered
   `service-request-denied` at Protocol_Revision ≥ 20 — a deprecation the stack
   applies, not a quirk of this example.)

**A true end-to-end test needs two subnets and two BBMDs** — that is inherent to
the profile and beyond what one host can show. Point two real BBMDs at each other
via `bdtSeeds`, then confirm that a Who-Is broadcast on subnet A produces an I-Am
from a device on subnet B.

## Versions

| | |
|---|---|
| Example version | 1.0.0 |
| `common/` helper | 1.2.0 |
| CAS BACnet Stack | 6.0.0.0 (submodule pinned at the series-wide commit) |
| Protocol_Revision | 24 (the stack default — the highest it supports) |
| Verified on | Windows (MSVC 2022, C++17) |

## License

The example source code is dedicated to the public domain under
[CC0-1.0](LICENSE) — copy it into your project freely. The **CAS BACnet Stack is
a separate, commercially licensed product** and is not covered by that
dedication; contact [Chipkin](https://store.chipkin.com/) for licensing.
