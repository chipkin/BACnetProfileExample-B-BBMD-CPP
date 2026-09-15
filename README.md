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

## Who serves what: application or stack?

A BBMD is a network function, so its objects are the ordinary B-ASC set. For the
commandable **Analog Output "Chartreuse"** - the one with the most moving parts:

| Property | Served by | How |
|---|---|---|
| `Object_Identifier`, `Object_Type`, `Object_List`, `Property_List`, `Status_Flags` | **stack** | generated from the object you added |
| `Current_Command_Priority` | **stack** | computed from the Priority_Array (required at Protocol_Revision 24) |
| `Present_Value` | **you (write) / stack (read)** | `SetPropertyReal` accepts a direct write; on read the **stack computes** it from the Priority_Array slots (highest non-null, or `Relinquish_Default`) |
| `Priority_Array`, `Relinquish_Default` | **you** | the typed getters serve each slot; `GetPropertyBool` reports whether a slot is null |
| `Object_Name` | **you** | `GetPropertyCharString` |
| `Units` | **you** | `GetPropertyEnumerated` |
| `Event_State` | **stack**, sort of | no alarming here, so it reads `normal(0)` as a datatype default - correct by coincidence, not computation |

The Network Port additionally reports `BACnet_IP_Mode = bbmd` and, once you enable
them (Trap #3), the three BBMD table properties - which the stack builds from the
live BDT/FDT.

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

This example links the CAS BACnet Stack as a prebuilt **STATIC** library. Build
the library once from the pinned submodule commit, then configure and build the
example against it:

```bash
tools/build-stack-static.sh BACnetProfileExample-B-BBMD-CPP   # from the series root; builds
                                                                # submodules/cas-bacnet-stack/bin/...
cmake -B build -S . -DCAS_BACNET_STACK_LINK=STATIC
cmake --build build --config Release
```

> **The stack library build takes a few minutes** the first time - it compiles
> the entire CAS BACnet Stack (~600 source files) once, via the stack's own
> project files (`msbuild` on Windows, `make` on Linux). The example itself
> (`main.cpp` + `common/`) then builds in seconds against that library, and
> rebuilds after that are incremental.

If you cloned without `--recursive`, run `git submodule update --init --recursive`
first. If your CAS BACnet Stack lives somewhere other than the bundled submodule,
point CMake at it: `cmake -B build -S . -D CAS_STACK_DIR=/path/to/cas-bacnet-stack`.

### Link mode

This example links the stack through the `CASBACnetStack::Adapter` CMake target
(`submodules/cas-bacnet-stack/adapters/cpp`) in **STATIC** mode -
`-DCAS_BACNET_STACK_LINK=STATIC` links the prebuilt
`CASBACnetStack_x64_Release.lib` / `libCASBACnetStack_x64_Release.a` built by
`tools/build-stack-static.sh` above. **Application code is identical
regardless of link mode** - `main.cpp` and `common/` call `BACnetStack_AddDevice(...)`
and friends by the exact export name. Every mode requires calling
`LoadBACnetFunctions()` once at the top of `main()` before any other
`BACnetStack_*` call, which runs a version handshake; if it fails,
`CASBACnetStackAdapter_LastError()` says why and the program exits with a
message rather than crashing.

The adapter also offers a **SOURCE** mode (compiles the stack's `source/*.cpp`
straight into the executable, no library build step) - this example is built
and published in **STATIC** mode only.


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
| Example version | 1.1.0 |
| `common/` helper | 2.1.0 |
| CAS BACnet Stack | 6.0.21 (`6.x` @ `abd4cee1`), linked as a static library |
| Protocol_Revision | 24 (the stack default — the highest it supports) |
| Verified on | Windows (MSVC 2022, C++17) |

## Objects and properties

<!-- OBJECTS-PROPERTIES:BEGIN (generated by tools/gen-objects-properties.py from docs/objects.json - do not edit here) -->
Every object this example creates, and every REQUIRED property of each (per ANSI/ASHRAE 135-2024 clause 12 and the stack's `docs/property-profile-reference.md`), plus the optional properties the example turns on. **Served by** says who answers a ReadProperty: the **stack** generates it, or the **app** serves it from a `GetProperty*` callback in `main.cpp`. A ⚠ row is a required property the app does not serve and the stack would fill with a default - that is a defect, not a feature.

### Device 389020 "Rainbow" - vendor 389 (Chipkin Automation Systems); instance configurable with --deviceID. The properties in 'accepted' are not served from a GetProperty callback because the stack itself is the source of truth for them - Protocol_Revision/Protocol_Version are stack build constants, Protocol_Services_Supported/Protocol_Object_Types_Supported are computed from the BACnetStack_SetServiceEnabled/AddObject calls this example already makes, Object_List and Device_Address_Binding are live stack-maintained tables, System_Status/Database_Revision/Max_APDU_Length_Accepted/Segmentation_Supported/APDU_Timeout/Number_Of_APDU_Retries are the stack's own configuration defaults for a device this example does not override

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| System_Status | BACnetDeviceStatus | stack default, accepted (Generic Enumerated default: `0`) | no |
| Vendor_Name | CharacterString | app | no |
| Vendor_Identifier | Unsigned16 | app | no |
| Model_Name | CharacterString | app | no |
| Firmware_Revision | CharacterString | app | no |
| Application_Software_Version | CharacterString | app | no |
| Description *(optional, enabled)* | CharacterString | app | no |
| Protocol_Version | Unsigned | stack default, accepted (`BACNET_PROTOCOL_VERSION`) | no |
| Protocol_Revision | Unsigned | stack default, accepted (`BACNET_PROTOCOL_REVISION`) | no |
| Protocol_Services_Supported | BACnetServicesSupported | stack default, accepted (computed from which services are enabled) | no |
| Protocol_Object_Types_Supported | BACnetObjectTypesSupported | stack default, accepted (computed from which object types are supported) | no |
| Object_List | BACnetARRAY[N] of BACnetObjectIdentifier | stack default, accepted (None known - a read fails with `unknown-property` or an empt) | no |
| Max_APDU_Length_Accepted | Unsigned | stack default, accepted (`CAS_BACNET_DEVICE_DEFAULT_MAX_APDU_LENGTH_ACCEPTED`) | no |
| Segmentation_Supported | BACnetSegmentation | stack default, accepted (`BACnetSegmentation::noSegmentation`) | no |
| APDU_Timeout | Unsigned | stack default, accepted (`CAS_BACNET_DEVICE_DEFAULT_APDU_TIMEOUT`) | no |
| Number_Of_APDU_Retries | Unsigned | stack default, accepted (`CAS_BACNET_DEVICE_DEFAULT_NUMBER_OF_APDU_RETRIES`) | no |
| Device_Address_Binding | BACnetLIST of BACnetAddressBinding | stack default, accepted (the live Device_Address_Binding (DAB) table) | no |
| Database_Revision | Unsigned | stack default, accepted (Generic UnsignedInteger default: `0`) | no |

### Analog Input 1 "Bronze" - REAL, degrees Celsius; starts at 21.5; read-only

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | Real | app | no |
| Status_Flags | BACnetStatusFlags | stack | no |
| Event_State | BACnetEventState | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Units | BACnetEngineeringUnits | app | no |

### Binary Input 1 "Emerald" - starts inactive; read-only

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | BACnetBinaryPV | app | no |
| Status_Flags | BACnetStatusFlags | stack | no |
| Event_State | BACnetEventState | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Polarity | BACnetPolarity | app | no |

### Multi-state Input 1 "Hot Pink" - state 1 of 3: On, Off, Auto; read-only

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | Unsigned | app | no |
| Status_Flags | BACnetStatusFlags | stack | no |
| Event_State | BACnetEventState | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Number_Of_States | Unsigned | app | no |
| State_Text *(optional, enabled)* | BACnetARRAY[N] of CharacterString | app | no |

### Analog Output 1 "Chartreuse" - REAL setpoint, default 20.0 C; commandable via a 16-slot Priority_Array (WriteProperty, DS-WP-B) - Present_Value/Priority_Array/Current_Command_Priority are resolved by the stack from the slots the app serves through GetPropertyReal/GetPropertyBool

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | Real | stack | yes |
| Status_Flags | BACnetStatusFlags | stack | no |
| Event_State | BACnetEventState | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Units | BACnetEngineeringUnits | app | no |
| Priority_Array | BACnetARRAY[16] of BACnetOptionalReal | stack | no |
| Relinquish_Default | Real | app | no |
| Current_Command_Priority | BACnetOptionalUnsigned | stack | no |

### Binary Output 1 "Fuchsia" - active/inactive, default inactive; commandable via a 16-slot Priority_Array (WriteProperty, DS-WP-B) - Present_Value/Priority_Array/Current_Command_Priority are resolved by the stack from the slots the app serves through GetPropertyEnumerated/GetPropertyBool

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | BACnetBinaryPV | stack | yes |
| Status_Flags | BACnetStatusFlags | stack | no |
| Event_State | BACnetEventState | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Polarity | BACnetPolarity | app | no |
| Priority_Array | BACnetARRAY[16] of BACnetOptionalBinaryPV | stack | no |
| Relinquish_Default | BACnetBinaryPV | app | no |
| Current_Command_Priority | BACnetOptionalUnsigned | stack | no |

### Multi-state Output 1 "Indigo" - state 1 of 3, default state 1; commandable via a 16-slot Priority_Array (WriteProperty, DS-WP-B) - Present_Value/Priority_Array/Current_Command_Priority are resolved by the stack from the slots the app serves through GetPropertyUnsignedInteger/GetPropertyBool

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Present_Value | Unsigned | stack | yes |
| Status_Flags | BACnetStatusFlags | stack | no |
| Event_State | BACnetEventState | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Number_Of_States | Unsigned | app | no |
| Priority_Array | BACnetARRAY[16] of BACnetOptionalUnsigned | stack | no |
| Relinquish_Default | Unsigned | app | no |
| Current_Command_Priority | BACnetOptionalUnsigned | stack | no |

### Network Port 1 "Vermilion" - BACnet/IP, and this Network Port is the BBMD: BACnetStack_SetBBMD makes it one and it reports BACnet_IP_Mode=bbmd instead of normal; the BBMD_Broadcast_Distribution_Table/BBMD_Foreign_Device_Table/BBMD_Accept_FD_Registrations properties are enabled explicitly (not in this table - they are IPv4-BBMD-conditional properties outside property-profile-reference.md's base Network Port set) and are stack-computed from the live BDT/FDT, not app-served. Network_Type and Protocol_Level are set from BACnetStack_AddNetworkPortObject()'s arguments (IPv4, BACnet Application) at start-up, not a GetProperty callback like the object's other app-served rows; Changes_Pending is likewise computed and answered natively by the stack's Network Port object. Reliability has no fault condition this example detects, so it is accepted at the generic default (normal)

| Property | Datatype | Served by | Writable |
|---|---|---|:---:|
| Object_Identifier | BACnetObjectIdentifier | stack | no |
| Object_Name | CharacterString | app | no |
| Object_Type | BACnetObjectType | stack | no |
| Status_Flags | BACnetStatusFlags | stack | no |
| Reliability | BACnetReliability | stack default, accepted (Generic Enumerated default: `0`) | no |
| Out_Of_Service | Boolean | app | no |
| Network_Type | BACnetNetworkType | app | no |
| Protocol_Level | BACnetProtocolLevel | app | no |
| Changes_Pending | Boolean | app | no |

<!-- OBJECTS-PROPERTIES:END -->

## The BACnet profile example series

<!-- PROFILE-TABLE:BEGIN (generated from cas-bacnet-stack-examples/docs/profile-table.md - do not edit here) -->
The CAS BACnet Stack supports every standardized device profile in ASHRAE 135-2024 Annex L. One example repository per profile shows how. ✅ = the required BIBB (service) is supported by the CAS BACnet Stack; the **Example** column is the state of that profile's tutorial repository.

### Controllers (Annex L.4)

| Profile | Example | Required BIBBs (services) |
|---|---|---|
| **B-SS** Smart Sensor | [B-SS-CPP](https://github.com/chipkin/BACnetProfileExample-B-SS-CPP) ✅ | ✅ DS-RP-B · ✅ DM-DDB-B · ✅ DM-DOB-B |
| **B-SA** Smart Actuator | [B-SA-CPP](https://github.com/chipkin/BACnetProfileExample-B-SA-CPP) ✅ | ✅ DS-RP-B · ✅ DS-WP-B · ✅ DM-DDB-B · ✅ DM-DOB-B |
| **B-ASC** Application Specific Controller | [B-ASC-CPP](https://github.com/chipkin/BACnetProfileExample-B-ASC-CPP) ✅ · [B-ASC-Node](https://github.com/chipkin/BACnetProfileExample-B-ASC-Node) ✅ | ✅ DS-RP-B · ✅ DS-WP-B · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B |
| **B-AAC** Advanced Application Controller | [B-AAC-CPP](https://github.com/chipkin/BACnetProfileExample-B-AAC-CPP) ✅ | ✅ DS-RP-B · ✅ DS-RPM-B · ✅ DS-WP-B · ✅ DS-WPM-B · ✅ AE-N-I-B · ✅ AE-ACK-B · ✅ AE-INFO-B · ✅ AE-CRL-B · ✅ SCHED-I-B · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ DM-TS-B / DM-UTC-B · ✅ DM-RD-B |
| **B-BC** Building Controller | [B-BC-CPP](https://github.com/chipkin/BACnetProfileExample-B-BC-CPP) 📝 | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-RPM-A · ✅ DS-RPM-B · ✅ DS-WP-A · ✅ DS-WP-B · ✅ DS-WPM-B · ✅ AE-N-I-B · ✅ AE-ACK-B · ✅ AE-INFO-B · ✅ AE-CRL-B · ✅ SCHED-E-B · ✅ T-VMT-I-B · ✅ T-ATR-B · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ DM-TS-B / DM-UTC-B · ✅ DM-RD-B · ✅ DM-BR-B |

### Life safety controllers (Annex L.5)

| Profile | Example | Required BIBBs (services) |
|---|---|---|
| **B-LSC** Life Safety Controller | [B-LSC-CPP](https://github.com/chipkin/BACnetProfileExample-B-LSC-CPP) 📝 | ✅ DS-RP-B · ✅ DS-RPM-B · ✅ DS-WP-B · ✅ DS-WPM-B · ✅ DS-COV-B · ✅ AE-LS-B · ✅ AE-ACK-B · ✅ AE-INFO-B · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ DM-TS-B / DM-UTC-B · ✅ DM-RD-B |
| **B-ALSC** Advanced Life Safety Controller | [B-ALSC-CPP](https://github.com/chipkin/BACnetProfileExample-B-ALSC-CPP) 📝 | ✅ DS-RP-B · ✅ DS-RPM-B · ✅ DS-WP-B · ✅ DS-WPM-B · ✅ DS-COV-B · ✅ AE-LS-B · ✅ AE-ACK-B · ✅ AE-INFO-B · ✅ AE-EL-I-B · ✅ SCHED-I-B · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ DM-TS-B / DM-UTC-B · ✅ DM-RD-B |

### Access control controllers (Annex L.6)

| Profile | Example | Required BIBBs (services) |
|---|---|---|
| **B-ACC** Access Control Controller | [B-ACC-CPP](https://github.com/chipkin/BACnetProfileExample-B-ACC-CPP) 📝 | ✅ DS-RP-B · ✅ DS-RPM-B · ✅ DS-WP-B · ✅ DS-WPM-B · ✅ DS-COV-B · ✅ DS-ACUC-B · ✅ DS-ACSC-B · ✅ AE-AC-B · ✅ AE-ACK-B · ✅ AE-INFO-B · ✅ AE-EL-I-B · ✅ SCHED-I-B · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ DM-TS-B / DM-UTC-B · ✅ DM-RD-B · ✅ DM-BR-B |
| **B-AACC** Advanced Access Control Controller | [B-AACC-CPP](https://github.com/chipkin/BACnetProfileExample-B-AACC-CPP) 📝 | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-RPM-A · ✅ DS-RPM-B · ✅ DS-WP-A · ✅ DS-WP-B · ✅ DS-WPM-B · ✅ DS-COV-A · ✅ DS-COV-B · ✅ DS-ACAD-A · ☐ DS-ACCDI-A · ✅ DS-ACUC-B · ✅ DS-ACSC-B · ✅ AE-AC-B · ✅ AE-ACK-B · ✅ AE-INFO-B · ✅ AE-EL-I-B · ✅ SCHED-I-B · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ DM-TS-B / DM-UTC-B · ✅ DM-RD-B · ✅ DM-BR-B |

### Lighting controllers (Annex L.11)

| Profile | Example | Required BIBBs (services) |
|---|---|---|
| **B-LD** Lighting Device | [B-LD-CPP](https://github.com/chipkin/BACnetProfileExample-B-LD-CPP) ✅ | ✅ DS-RP-B · ✅ DS-WP-B · ✅ DS-LO-B / DS-BLO-B · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ DM-TS-B / DM-UTC-B |
| **B-LS** Lighting Supervisor | [B-LS-CPP](https://github.com/chipkin/BACnetProfileExample-B-LS-CPP) 📝 | ✅ DS-RP-B · ✅ DS-WP-A · ✅ DS-WP-B · ✅ DS-WG-E-B · ✅ DS-ALO-A · ✅ SCHED-E-B · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ DM-TS-B / DM-UTC-B |

### Elevator controllers (Annex L.13)

| Profile | Example | Required BIBBs (services) |
|---|---|---|
| **B-EM** Elevator Monitor | [B-EM-CPP](https://github.com/chipkin/BACnetProfileExample-B-EM-CPP) 📝 | ✅ DS-RP-B · ✅ DS-RPM-B · ✅ DS-COV-B · ✅ DS-COVM-B · ✅ AE-N-I-B · ✅ AE-ACK-B · ✅ AE-INFO-B · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B |
| **B-EC** Elevator Controller | [B-EC-CPP](https://github.com/chipkin/BACnetProfileExample-B-EC-CPP) 📝 | ✅ DS-RP-B · ✅ DS-RPM-B · ✅ DS-WP-B · ✅ DS-WPM-B · ✅ DS-COV-B · ✅ DS-COVM-B · ✅ AE-N-I-B · ✅ AE-ACK-B · ✅ AE-INFO-B · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ DM-TS-B / DM-UTC-B · ✅ DM-RD-B |
| **B-AEC** Advanced Elevator Controller | [B-AEC-CPP](https://github.com/chipkin/BACnetProfileExample-B-AEC-CPP) 📝 | ✅ DS-RP-B · ✅ DS-RPM-B · ✅ DS-WP-B · ✅ DS-WPM-B · ✅ DS-COV-B · ✅ DS-COVM-B · ✅ AE-N-I-B · ✅ AE-ACK-B · ✅ AE-INFO-B · ✅ AE-EL-I-B · ✅ SCHED-I-B · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ DM-TS-B / DM-UTC-B · ✅ DM-OCD-B · ✅ DM-RD-B · ✅ DM-BR-B |

### Authentication and authorization (Annex L.14)

| Profile | Example | Required BIBBs (services) |
|---|---|---|
| **B-AS** Authorization Server | [B-AS-CPP](https://github.com/chipkin/BACnetProfileExample-B-AS-CPP) 📝 | ✅ DS-RP-B · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ AA-AS-B |

### Miscellaneous (Annex L.7, combinable with any one family)

| Profile | Example | Required BIBBs (services) |
|---|---|---|
| **B-BBMD** Broadcast Management Device | [B-BBMD-CPP](https://github.com/chipkin/BACnetProfileExample-B-BBMD-CPP) ✅ | ✅ DS-RP-B · ✅ DS-WP-B · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ NM-BBMDC-B |
| **B-ACDC** Access Control Door Controller | [B-ACDC-CPP](https://github.com/chipkin/BACnetProfileExample-B-ACDC-CPP) ✅ | ✅ DS-RP-B · ✅ DS-WP-B · ✅ DS-ACAD-B · ✅ DM-DDB-B · ✅ DM-DOB-B |
| **B-ACCR** Access Control Credential Reader | [B-ACCR-CPP](https://github.com/chipkin/BACnetProfileExample-B-ACCR-CPP) 📝 | ✅ DS-RP-B · ✅ DS-WP-B · ✅ DS-COV-B · ✅ DS-ACCDI-B · ✅ DM-DDB-B · ✅ DM-DOB-B |
| **B-RTR** Router | [B-RTR-CPP](https://github.com/chipkin/BACnetProfileExample-B-RTR-CPP) 📝 | ✅ DS-RP-B · ✅ DS-WP-B · ✅ DM-DDB-A · ✅ DM-DOB-B · ✅ DM-LM-B · ✅ NM-RC-B |
| **B-GW** Gateway | [B-GW-CPP](https://github.com/chipkin/BACnetProfileExample-B-GW-CPP) 📝 | ✅ DS-RP-B · ✅ DS-WP-B · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ GW-EO-B / GW-VN-B |
| **B-DAP** Device Address Proxy | [B-DAP-CPP](https://github.com/chipkin/BACnetProfileExample-B-DAP-CPP) 📝 | ✅ DS-RP-B · ✅ DS-WP-B · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DAB-B |
| **B-SCHUB** BACnet/SC Hub | [B-SCHUB-CPP](https://github.com/chipkin/BACnetProfileExample-B-SCHUB-CPP) 📝 | ✅ DS-RP-B · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ NM-SCH-B |
| **B-GENERAL** General device (Annex L.8) | *(satisfied by every example above)* | ✅ DS-RP-B · ✅ DM-DDB-B · ✅ DM-DOB-B |

### Operator interfaces and workstations (Annex L.1–L.3, L.9–L.10, L.12) — client-side profiles

| Profile | Example | Required BIBBs (services) |
|---|---|---|
| **B-OD** Operator Display | [B-OD-CPP](https://github.com/chipkin/BACnetProfileExample-B-OD-CPP) ✅ | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-WP-A · ✅ DS-V-A · ✅ DS-M-A · ✅ AE-N-A · ✅ AE-VN-A · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B |
| **B-OWS** Operator Workstation | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-WP-A · ✅ DS-V-A · ✅ DS-M-A · ✅ AE-N-A · ✅ AE-ACK-A · ✅ AE-AS-A · ✅ AE-VM-A · ✅ AE-VN-A · ✅ SCHED-VM-A · ✅ T-V-A · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-MTS-A |
| **B-AWS** Advanced Operator Workstation | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-RPM-A · ✅ DS-WP-A · ✅ DS-WPM-A · ✅ DS-AV-A · ✅ DS-AM-A · ✅ AE-N-A · ✅ AE-ACK-A · ✅ AE-AS-A · ✅ AE-AVM-A · ✅ AE-AVN-A · ✅ AE-ELVM-A · ✅ SCHED-AVM-A · ✅ T-AVM-A · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-ANM-A · ✅ DM-ADM-A · ✅ DM-DOB-B · ✅ DM-DCC-A · ✅ DM-MTS-A · ✅ DM-OCD-A · ✅ DM-RD-A · ✅ DM-BR-A · ✅ DM-DDA-A · ✅ NM-CC-A · ✅ AR-AVM-A |
| **B-XAWS** Extended Advanced Operator Workstation | planned | ✅ union of B-AWS + B-AACWS + B-ALWS + B-AEWS |
| **B-LSAP** Life Safety Annunciator Panel | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-WP-A · ✅ DS-LSV-A · ✅ AE-N-A · ✅ AE-LS-A · ✅ AE-ACK-A · ✅ AE-LSVN-A |
| **B-LSWS** Life Safety Workstation | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-RPM-A · ✅ DS-WP-A · ✅ DS-WPM-A · ✅ DS-LSV-A · ✅ DS-LSM-A · ✅ AE-N-A · ✅ AE-LS-A · ✅ AE-ACK-A · ✅ AE-AS-A · ✅ AE-LSVM-A · ✅ AE-LSAVN-A · ✅ AE-ELV-A · ✅ SCHED-VM-A · ✅ T-V-A · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-ANM-A · ✅ DM-ADM-A · ✅ DM-DOB-B · ✅ DM-DCC-A · ✅ DM-MTS-A · ✅ DM-OCD-A · ✅ DM-RD-A · ✅ DM-BR-A |
| **B-ALSWS** Advanced Life Safety Workstation | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-RPM-A · ✅ DS-WP-A · ✅ DS-WPM-A · ✅ DS-LSAV-A · ✅ DS-LSAM-A · ✅ AE-N-A · ✅ AE-LS-A · ✅ AE-ACK-A · ✅ AE-AS-A · ✅ AE-LSAVM-A · ✅ AE-LSAVN-A · ✅ AE-ELVM-A · ✅ SCHED-AVM-A · ✅ T-AVM-A · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-ANM-A · ✅ DM-ADM-A · ✅ DM-DOB-B · ✅ DM-DCC-A · ✅ DM-MTS-A · ✅ DM-OCD-A · ✅ DM-RD-A · ✅ DM-BR-A · ✅ AR-AVM-A |
| **B-ACSD** Access Control Security Display | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-RPM-A · ✅ DS-WP-A · ✅ DS-WPM-A · ✅ DS-ACV-A · ✅ DS-ACM-A · ✅ AE-N-A · ✅ AE-AC-A · ✅ AE-ACK-A · ✅ AE-AS-A · ✅ AE-ACAVN-A · ✅ AE-ELV-A · ✅ SCHED-VM-A · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-MTS-A |
| **B-ACWS** Access Control Workstation | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-RPM-A · ✅ DS-WP-A · ✅ DS-WPM-A · ✅ DS-ACAV-A · ✅ DS-ACM-A · ✅ DS-ACUC-A · ✅ AE-N-A · ✅ AE-AC-A · ✅ AE-ACK-A · ✅ AE-AS-A · ✅ AE-ACVM-A · ✅ AE-ACAVN-A · ✅ AE-ELV-A · ✅ SCHED-VM-A · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-ANM-A · ✅ DM-ADM-A · ✅ DM-DOB-B · ✅ DM-DCC-A · ✅ DM-MTS-A · ✅ DM-OCD-A · ✅ DM-RD-A · ✅ DM-BR-A |
| **B-AACWS** Advanced Access Control Workstation | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-RPM-A · ✅ DS-WP-A · ✅ DS-WPM-A · ✅ DS-ACAV-A · ✅ DS-ACAM-A · ✅ DS-ACUC-A · ✅ DS-ACSC-A · ✅ AE-N-A · ✅ AE-AC-A · ✅ AE-ACK-A · ✅ AE-AS-A · ✅ AE-ACAVM-A · ✅ AE-ACAVN-A · ✅ AE-ELVM-A · ✅ SCHED-AVM-A · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-ANM-A · ✅ DM-ADM-A · ✅ DM-DOB-B · ✅ DM-DCC-A · ✅ DM-MTS-A · ✅ DM-OCD-A · ✅ DM-RD-A · ✅ DM-BR-A · ✅ AR-AVM-A |
| **B-LOD** Lighting Operator Display | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-WP-A · ✅ DS-LV-A · ✅ DS-WG-A · ✅ DS-ALO-A · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B |
| **B-ALWS** Advanced Lighting Workstation | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-RPM-A · ✅ DS-WP-A · ✅ DS-WPM-A · ✅ DS-LAV-A · ✅ DS-LAM-A · ✅ DS-WG-A · ✅ DS-ALO-A · ✅ AE-N-A · ✅ AE-ACK-A · ✅ AE-AS-A · ✅ AE-AVM-A · ✅ AE-AVN-A · ✅ AE-ELVM-A · ✅ SCHED-AVM-A · ✅ T-AVM-A · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-ANM-A · ✅ DM-ADM-A · ✅ DM-DOB-B · ✅ DM-DCC-A · ✅ DM-MTS-A · ✅ DM-OCD-A · ✅ DM-RD-A · ✅ DM-BR-A |
| **B-LCS** Lighting Control Station | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-WP-A · ✅ DS-LO-A · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ DM-TS-B / DM-UTC-B |
| **B-ALCS** Advanced Lighting Control Station | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-RPM-A · ✅ DS-WP-A · ✅ DS-WPM-A · ✅ DS-WG-A · ✅ DS-ALO-A · ✅ SCHED-E-B · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B · ✅ DM-DCC-B · ✅ DM-TS-B / DM-UTC-B |
| **B-ED** Elevator Display | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-WP-A · ✅ DS-EV-A · ✅ AE-N-A · ✅ AE-ACK-A · ✅ AE-EVN-A · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-DOB-B |
| **B-EWS** Elevator Workstation | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-RPM-A · ✅ DS-WP-A · ✅ DS-WPM-A · ✅ DS-COVM-A · ✅ DS-EV-A · ✅ DS-EM-A · ✅ AE-N-A · ✅ AE-ACK-A · ✅ AE-AS-A · ✅ AE-EVM-A · ✅ AE-EAVN-A · ✅ SCHED-VM-A · ✅ T-V-A · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-ANM-A · ✅ DM-ADM-A · ✅ DM-DOB-B · ✅ DM-DCC-A · ✅ DM-MTS-A |
| **B-AEWS** Advanced Elevator Workstation | planned | ✅ DS-RP-A · ✅ DS-RP-B · ✅ DS-RPM-A · ✅ DS-WP-A · ✅ DS-WPM-A · ✅ DS-COVM-A · ✅ DS-EAV-A · ✅ DS-EAM-A · ✅ AE-N-A · ✅ AE-ACK-A · ✅ AE-AS-A · ✅ AE-EAVM-A · ✅ AE-EAVN-A · ✅ AE-ELVM-A · ✅ SCHED-AVM-A · ✅ T-AVM-A · ✅ DM-DDB-A · ✅ DM-DDB-B · ✅ DM-ANM-A · ✅ DM-ADM-A · ✅ DM-DOB-B · ✅ DM-DCC-A · ✅ DM-MTS-A · ✅ DM-OCD-A · ✅ DM-RD-A · ✅ DM-BR-A |

Profile definitions: ANSI/ASHRAE 135-2024 Annex L. BIBB definitions: Annex K. Get the stack: <https://store.chipkin.com/services/stacks/bacnet-stack>.
<!-- PROFILE-TABLE:END -->

## Footprint

Release-build sizes and start-up timing, from the latest tagged release's CI
run (`metrics-windows.json` / `metrics-linux.json`), both built with
`CAS_BACNET_STACK_LINK=STATIC`:

<!-- METRICS -->
| Platform | Binary | Size | SHA-256 (prefix) | Start-up to `ready` | Stack commit | Link mode | Compiler |
|---|---|---|---|---|---|---|---|
| Windows x64 (windows-2022) | `BACnetExampleBBBMD.exe` | 3,255,808 bytes (~3.1 MiB) | `67b6ea3351d14852` | 69 ms | `abd4cee1` | STATIC | Visual Studio 17 2022 |
| Linux x64 (ubuntu-latest) | `BACnetExampleBBBMD` | 44,352 bytes (~43 KiB) | `2f7f83e5044b5901` | 108 ms | `abd4cee1` | STATIC | `/usr/bin/c++` |

From release [v1.1.0](https://github.com/chipkin/BACnetProfileExample-B-BBMD-CPP/releases/tag/v1.1.0) (`metrics-windows.json` / `metrics-linux.json`).

## License

The example source code is dedicated to the public domain under
[CC0-1.0](LICENSE) — copy it into your project freely. The **CAS BACnet Stack is
a separate, commercially licensed product** and is not covered by that
dedication; contact [Chipkin](https://store.chipkin.com/) for licensing.
