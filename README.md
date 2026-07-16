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

## Three traps worth knowing before you copy this

All three cost real debugging time and fail in misleading ways:

**1. A BDT entry address is 6 octets, not 4 — and nothing checks this for you.**
It is a BACnet/IP ("B/IP") address: the 4 IP octets followed by the **UDP port,
high byte first** — the same layout the Network Port's `MAC_Address` uses.
`AddBDTEntry` takes a length argument, but **the stack ignores it** and always
copies 6 octets from your buffer; `AddBDTEntry` returns `true` even for a malformed
entry. So the length argument protects nothing — the guarantee *you* must provide
is that the buffer actually holds 6 octets (IP + port). Pass a 4-octet buffer and
the stack reads 2 bytes of adjacent memory as the port and silently forwards
broadcasts to that garbage address. The safe habit: always build the address with
a helper like `MakeBip` below that lays out all 6 octets.

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

**3. `SetBBMD` does not make the BBMD tables readable — you must enable them.**
The `BBMD_Broadcast_Distribution_Table`, `BBMD_Foreign_Device_Table`, and
`BBMD_Accept_FD_Registrations` properties on the Network Port are *optional*, so
they are not enabled automatically and `SetBBMD` does not enable them. Without an
explicit `SetPropertyEnabled` for each, a client's `ReadProperty` of them returns
`unknown-property` even though the BBMD is fully functional — the same "serving a
value is not enough, you must enable the property" trap the Description property
hits. This example enables all three right after `SetBBMD`.

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
subnet. **You do not list this device in `bdtSeeds`:** the example computes this
BBMD's own entry from its live interface and adds it as entry `[0]` automatically
(Trap #2 above explains why the self-entry must exist).

Each entry carries a **broadcast-distribution mask** alongside the IP + port, and
it is a real per-entry decision:

- `255.255.255.255` = **two-hop**: you unicast the broadcast to the peer BBMD and it
  re-broadcasts onto its own subnet. This is the normal, router-friendly choice, and
  what `bdtSeeds` uses for every peer. Use this unless you have a specific reason not to.
- *the peer's real subnet mask* = **one-hop**: you send a directed broadcast straight
  onto the peer's subnet. It needs the intervening routers to forward directed
  broadcasts, which most are configured **not** to do — so this usually fails silently.

A real product would load this table from its configuration, and/or let a client
write it over BACnet with `Write-Broadcast-Distribution-Table`.

## Before you ship

This example is a tutorial, and it identifies itself as one. Everything in this
table is read by clients and shown to the operator in **every discovery tool on
the network**. Left as-is, your product appears on a real site announcing itself
as a Chipkin demo. None of it is cosmetic.

| Constant (`main.cpp`) | Ships as | Change it to |
|---|---|---|
| `VENDOR_IDENTIFIER` | `389` (Chipkin) | **Your** company's vendor ID. Assigned by ASHRAE, free: <https://bacnet.org/assigned-vendor-ids/> |
| `VENDOR_NAME` | `Chipkin Automation Systems` | Your company name - must match the vendor ID above. |
| `DEVICE_NAME` | `"Rainbow"` | Your device's `Object_Name`. **Must be unique across the BACnet internetwork** - see the note below. |
| `MODEL_NAME` | `CAS BACnet Stack Example - B-BBMD` | Your model designation - what a building operator reads to identify your device. |
| `DEVICE_DESCRIPTION` | a description of *this example* | What your device actually is. |
| `FIRMWARE_REVISION` / `APPLICATION_SOFTWARE_VERSION` | `1.0.0` | Your real versions - wire them to your build. |
| `DCC_PASSWORD` | `""` (no password) | Set your device's secret, or leave empty to accept any DeviceCommunicationControl. It crosses the wire in **plaintext** - a guard against accidents, not a security boundary. |
| Device instance | `389020` (`--deviceID` overrides) | Must be unique on the internetwork. BACnet requires this to be configurable; keep it so. |

> **`Object_Name` uniqueness is the one that will bite you.** The device instance
> is runtime-configurable via `--deviceID`, but `DEVICE_NAME` is a compile-time
> constant. Ship two units and configure their instances correctly, and **both
> still announce `Object_Name "Rainbow"`** - a spec violation. In a real product,
> `Object_Name` must be per-unit configurable too (serial number, DIP switches,
> a config file, or a `--deviceName` argument).

`main.cpp` marks this block with a `CHANGE ALL OF THIS BEFORE YOU SHIP` banner.

## Build

```bash
git clone --recursive https://github.com/chipkin/BACnetProfileExample-B-BBMD-CPP.git
cd BACnetProfileExample-B-BBMD-CPP
cmake -B build -S .
cmake --build build --config Release
```

If you cloned without `--recursive`, run `git submodule update --init --recursive`
first. The first build compiles the whole CAS BACnet Stack (~600 source files) and
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

Entry `[0]`'s mask is this device's own subnet mask (`255.255.255.0` here), not
`255.255.255.255` like the peers. That is fine and intentional: a BBMD never
forwards a broadcast to *itself*, so the self-entry's mask is never used — only
the peer entries' masks matter for forwarding.

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
| `common/` helper | 1.3.0 |
| CAS BACnet Stack | 6.0.0.0 (submodule pinned at the 6.x series commit) |
| Protocol_Revision | 24 (the stack default — the highest it supports) |
| Verified on | Windows (MSVC 2022, C++17) |

## License

The example source code is dedicated to the public domain under
[CC0-1.0](LICENSE) — copy it into your project freely. The **CAS BACnet Stack is
a separate, commercially licensed product** and is not covered by that
dedication; contact [Chipkin](https://store.chipkin.com/) for licensing.
