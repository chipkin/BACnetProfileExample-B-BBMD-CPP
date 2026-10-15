# Tutorial - extending and reviewing the B-BBMD example

[README.md](README.md) says what this example *is*. This document is the *how*:
how to extend it into your own device, who serves which property, how to review
the result for conformance, and what goes wrong when you get it subtly right.

Read this once before you start changing `main.cpp`. The most expensive mistakes
in this example are silent, and the BBMD-specific ones live in
[Three traps worth knowing before you copy this](#three-traps-worth-knowing-before-you-copy-this).

- [Extending the example](#extending-the-example)
- [Configure it for your site](#configure-it-for-your-site)
- [Three traps worth knowing before you copy this](#three-traps-worth-knowing-before-you-copy-this)
- [What each object type needs you to serve](#what-each-object-type-needs-you-to-serve)
- [Who serves what: the application or the stack?](#who-serves-what-the-application-or-the-stack)
- [Reviewing your device](#reviewing-your-device)
- [Troubleshooting](#troubleshooting)

## Extending the example

The example is intentionally small so it's easy to change.

**Change a sensor's value or name** - edit the constants / callbacks in
`main.cpp` (e.g. the initial value of `g_analogInput1Value`, or the `"Bronze"`
string in `GetPropertyCharString`).

**Change the device identity before you ship** - vendor ID, vendor name, model
name, description, firmware revision, device name and the DeviceCommunicationControl
password are all in the `CHANGE ALL OF THIS BEFORE YOU SHIP` block at the top of
`main.cpp`, with a per-field note on each saying what to change it to. That block
is the authoritative checklist; it is in the source rather than here so it cannot
be skipped by someone who only reads the code.

**Add a second commandable or read-only object** - follow the same recipe as
[B-ASC](https://github.com/chipkin/BACnetProfileExample-B-ASC-CPP)'s tutorial:
walk every `GetProperty*` / `SetProperty*` callback (they match on **object type
AND instance**, so a new instance falls through every one of them, the same trap
described under [Who serves what](#who-serves-what-the-application-or-the-stack)
below), add the object, serve its required properties, and diff its readback
against the existing object of that type. This example's objects and
WriteProperty machinery are deliberately identical to B-ASC's - see
[AGENTS.md](AGENTS.md) for why, and change them in both places if you must
change them at all.

## Configure it for your site

Give the example its peer BBMDs on the command line - one `--bdt` per remote
subnet:

```bash
./build/BACnetExampleBBBMD --bdt 192.168.2.10 --bdt 192.168.4.10:47809
```

**You do not list this device:** the example computes this BBMD's own entry
from its live interface and adds it as entry `[0]` automatically (Trap 2 below
explains why the self-entry must exist). A real product would load the same
list from its own configuration store; `SetUpBbmd()` in `main.cpp` is the code
to copy.

Each entry carries a **broadcast-distribution mask** alongside the IP + port
(`--bdt <ip>[:<port>][/<mask>]`), and it is a real per-entry decision:

- `255.255.255.255` = **two-hop**: you unicast the broadcast to the peer BBMD
  and it re-broadcasts onto its own subnet. This is the normal, router-friendly
  choice, and the default. Use it unless you have a specific reason not to.
- *the peer's real subnet mask* = **one-hop**: you send a directed broadcast
  straight onto the peer's subnet. It needs the intervening routers to forward
  directed broadcasts, which most are configured **not** to do - so this usually
  fails silently.

**Every BBMD must give one subnet the same mask** (Annex J.4.3.2: "The
broadcast distribution masks referring to the same IP subnet shall be
identical in each BDT"). That includes this device's own entry: the stack
reads it to decide whether a peer's Forwarded-NPDU arrived by unicast (so it
must re-broadcast it here) or by directed broadcast (so everyone here already
has it) - Annex J.4.5. The own entry is two-hop by default. If the peers reach
this subnet one-hop, list this device's own address with that mask too
(`--bdt <this IP>:<port>/255.255.255.0`).

Over BACnet, Annex J.4.4 is explicit that the BDT "shall be supplied by
writing to the BBMD_Broadcast_Distribution_Table property of the Network Port
Object" - that is, **WriteProperty**, not the `Write-Broadcast-Distribution-Table`
BVLL message. J.4.4.2 requires every B/IP device to answer that BVLL message
with a BVLC-Result of `X'0010'` (NAK), and the stack does. The stack makes the
property writable (cl. 12.56.38 requires it of a BBMD). Cl. 12.56.38 also says
the written value becomes effective only when the device receives
ReinitializeDevice ACTIVATE_CHANGES or WARMSTART - which is why this example
registers a ReinitializeDevice callback even though no B-BBMD BIBB names
DM-RD-B. (At this Stack Pin the stack applies the write at once anyway; see
`TODO.md`. Send ACTIVATE_CHANGES regardless, so your tool keeps working when
the stack is fixed.) The written list must still contain this device's own
entry, or the stack refuses it with `value-out-of-range`.
`tests/tables_test.py` shows the encoding of both requests.

`--no-bbmd` starts the same device as a plain BACnet/IP device. Annex L.7.3
requires a device that is a BBMD "along with some other BACnet functionality"
to be capable of being reconfigured as a non-BBMD; in a product that is a
configuration setting read at start-up, as here.

## Three traps worth knowing before you copy this

All three cost real debugging time and fail in misleading ways:

**1. A BDT entry address is 6 octets, not 4 - and nothing checks this for you.**
It is a BACnet/IP ("B/IP") address: the 4 IP octets followed by the **UDP port,
high byte first** - the same layout the Network Port's `MAC_Address` uses.
`AddBDTEntry` takes a length argument, but **the stack ignores it** and always
copies 6 octets from your buffer; `AddBDTEntry` returns `true` even for a
malformed entry. So the length argument protects nothing - the guarantee *you*
must provide is that the buffer actually holds 6 octets (IP + port). Pass a
4-octet buffer and the stack reads 2 bytes of adjacent memory as the port and
silently forwards broadcasts to that garbage address. The safe habit: always
build the address with a helper like `MakeBip` in `main.cpp` that lays out all
6 octets.

**2. Populate the BDT *before* `SetBBMD`, and include this device's own entry.**
Per Annex J a BBMD's BDT includes itself, and `SetBBMD` **requires** that entry
to already exist: it reads this Network Port's `IP_Address` +
`BACnet_IP_UDP_Port` through your Get callbacks, builds the host's 6-octet B/IP
address, and looks for a matching BDT entry. **The stack does not add the
self-entry for you.** Get either trap wrong and you get the same unhelpful pair
of errors:

```
Error: Broadcast Distribution Table is not configured with host device entry
Error: Failed to UpdateHostBDTIndex, aborting BBMD setup
```

The self-entry's port must be the port the device is actually listening on, so
`main.cpp` builds it from `--port`, not a hardcoded `47808`.

**3. `SetBBMD` does not make the BBMD tables readable - you must enable them.**
The `BBMD_Broadcast_Distribution_Table`, `BBMD_Foreign_Device_Table`, and
`BBMD_Accept_FD_Registrations` properties on the Network Port are *optional*, so
they are not enabled automatically and `SetBBMD` does not enable them. Without
an explicit `SetPropertyEnabled` for each, a client's `ReadProperty` of them
returns `unknown-property` even though the BBMD is fully functional - the same
"serving a value is not enough, you must enable the property" trap the
Description property hits (see the note in `main.cpp` right before it). This
example enables all three right after `SetBBMD`.

Also worth knowing: do not probe `GetBDTEntry` upwards until it fails. An
out-of-range index is a genuine error to the stack and it logs one, so a probe
loop prints a spurious error at the end of an otherwise healthy start-up -
iterate a known count instead. And `GetBDTEntry` returns `uint32_t` (bytes
written; `0` = failure), not `bool` - `if (!GetBDTEntry(...))` compiles but
forces the `uint32_t` through a `bool` conversion the strict build (`/W4`)
flags as `C4800`; compare the result to `0` explicitly.

## What each object type needs you to serve

The application must serve every REQUIRED property the stack does not generate.
It differs per type - this is the checklist, so you do not have to infer it:

| Object type | You must serve | Plus |
|---|---|---|
| Analog Input | `Present_Value` (Real), `Object_Name`, `Units` | - |
| Binary Input | `Present_Value` (Enumerated), `Object_Name` | `Polarity` |
| Multi-State Input | `Present_Value` (Unsigned), `Object_Name` | `Number_Of_States` |
| Analog Output (commandable) | `Object_Name`, `Units`, `Relinquish_Default` | `Present_Value` and `Priority_Array` are resolved by the stack from the slots you serve through `GetPropertyReal` / `GetPropertyBool` |
| Binary Output (commandable) | `Object_Name`, `Polarity`, `Relinquish_Default` | `Present_Value` / `Priority_Array` resolved by the stack from `GetPropertyEnumerated` / `GetPropertyBool` |
| Multi-State Output (commandable) | `Object_Name`, `Number_Of_States`, `Relinquish_Default` | `Present_Value` / `Priority_Array` resolved by the stack from `GetPropertyUnsignedInteger` / `GetPropertyBool` |
| Network Port | `Object_Name`, `Network_Type`, `Protocol_Level`, `Changes_Pending`, plus `IP_Address` / `IP_Subnet_Mask` / `IP_Default_Gateway` / `BACnet_IP_UDP_Port` | Because this port is a BBMD: enable `BBMD_Broadcast_Distribution_Table`, `BBMD_Foreign_Device_Table`, `BBMD_Accept_FD_Registrations` (Trap 3), and serve `BACnet_IP_Mode` = `bbmd` |

## Who serves what: the application or the stack?

The single most common question when reading this file is "who answers this
property?" For the commandable **Analog Output "Chartreuse"** - the one with
the most moving parts:

| Property | Served by | How |
|---|---|---|
| `Object_Identifier`, `Object_Type`, `Object_List`, `Property_List`, `Status_Flags` | **stack** | generated from the object you added |
| `Current_Command_Priority` | **stack** | computed from the Priority_Array (required at Protocol_Revision 30) |
| `Present_Value` | **you (write) / stack (read)** | `SetPropertyReal` accepts a direct write; on read the **stack computes** it from the Priority_Array slots (highest non-null, or `Relinquish_Default`) |
| `Priority_Array`, `Relinquish_Default` | **you** | the typed getters serve each slot; `GetPropertyBool` reports whether a slot is null |
| `Object_Name` | **you** | `GetPropertyCharString` |
| `Units` | **you** | `GetPropertyEnumerated` |
| `Event_State` | **stack**, sort of | no intrinsic alarming here, so nothing serves it - it reads `normal` only because `normal` is the enumeration's zero value and the stack substitutes a datatype default. Correct by coincidence, not design. |

The Network Port additionally reports `BACnet_IP_Mode` = `bbmd` and, once you
enable them (Trap 3 above), the three BBMD table properties - which the stack
builds from the live BDT/FDT, not from a `GetProperty*` callback.

Every object, not just this one, is in [docs/PICS.md](docs/PICS.md).

Going beyond this (COV, alarms, scheduling) means implementing a richer
profile - see the series table in [README.md](README.md).

## Reviewing your device

After you have changed anything, review it against the conformance statement
rather than against "it looked fine in the explorer":

1. Regenerate [docs/PICS.md](docs/PICS.md) after editing `docs/objects.json`
   (see [Keeping the PICS honest](#keeping-the-pics-honest) below). A ⚠ row is a
   required property nothing serves.
2. Read **every** property listed for **every** object with a BACnet client, and
   compare the value against the PICS. `"undefined"`, `no-units` and `0` are
   three shapes a missed callback takes.
3. Diff a new object of a type against the existing one of that type. Anything
   that differs and shouldn't is a callback that matched on instance.
4. Confirm the services you do **not** implement are still rejected - for
   B-BBMD, ReadPropertyMultiple and SubscribeCOV.
5. Confirm start-up prints the BDT with **this device as entry `[0]`** and no
   stack errors. If `SetBBMD` failed the process exits non-zero - that alone
   catches Traps 1 and 2 above.
6. `ReadProperty` `Network Port 1` `BACnet_IP_Mode` - must be `bbmd` (2), not
   `normal`. This is what tells a client the port performs the BBMD function.
7. Exercise DM-DCC-B: `DeviceCommunicationControl` `disable-initiation` is
   accepted; the plain `disable` is answered `service-request-denied` at
   Protocol_Revision >= 20 - a deprecation the stack applies, not a bug here.
8. Run the Wire Tests (`python3 tests/run_wire_tests.py --exe <your build>`,
   [tests/README.md](tests/README.md)). They prove the BBMD function on one
   host: a broadcast from a foreign device on one instance reaches a foreign
   device on another. After you change the BBMD code, break the feature you
   changed on purpose and confirm a Wire Test fails - a test that cannot fail
   proves nothing. A test across **two real IP subnets** (two BBMDs, a device
   behind each) is still worth doing by hand before a product ships: it is the
   only way to see the local re-broadcast reach real devices.

### Keeping the PICS honest

`docs/PICS.md` is partly generated. `docs/objects.json` describes each object
and who serves which property; the series tool regenerates the object tables
from it plus the stack's own `docs/property-profile-reference.md` at the
pinned commit:

```bash
python tools/gen-objects-properties.py BACnetProfileExample-B-BBMD-CPP            # rewrite
python tools/gen-objects-properties.py BACnetProfileExample-B-BBMD-CPP --check    # fail if stale
```

(That tool lives in the example-series repository, not in this one. If you only
have this repository, edit the generated block by hand and keep it matching the
callbacks in `main.cpp`.)

When you add an object or a property to `main.cpp`, update `docs/objects.json`
in the same change and regenerate. The `app` list is what the callbacks serve;
`accepted` is for a required property you deliberately leave to the stack's
default, and each one needs a justification. Anything required, not in `app`
and not in `accepted`, comes out as a ⚠ row - that is a defect, not a feature.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| The app prints red `Error:` lines but the device works | **Usually expected - the stack's own debug logging.** Common benign ones: (1) the device receives its **own** broadcast I-Am and logs a decode cascade (*"Services is not supported service=[0]"* ... *"Failed to process the incoming NPDU"*) - any BACnet/IP device that listens for broadcasts hears itself; (2) a one-time *"UUID has not been set. A UUID must be set for the BACnetSC device to start."* - the stack starts a BACnet/SC datalink these IP-only examples never configure; (3) `Error occurred while sending the encoded packet` when a `--bdt` peer is unreachable; (4) `foreign device table is full ... refusing new entry` - the FDT holds 128 entries and the registration was refused with NAK X'0030', as Annex J.5.2.2 requires. |
| `Error: Broadcast Distribution Table is not configured with host device entry` / `Error: Failed to UpdateHostBDTIndex, aborting BBMD setup` | Trap 1 or Trap 2 above: a 4-octet (not 6-octet) BDT address, or `SetBBMD` called before the BDT (including the self-entry) is fully populated. |
| `ReadProperty` of `BBMD_Broadcast_Distribution_Table` / `BBMD_Foreign_Device_Table` returns `unknown-property` | Trap 3 above: those properties need an explicit `SetPropertyEnabled` after `SetBBMD` - it does not enable them for you. |
| CMake error: *"CAS BACnet Stack adapter not found under: ..."* | Submodules not initialized. Run `git submodule update --init --recursive` (or pass `-D CAS_STACK_DIR=...`). |
| `CASBACnetStackDLL.h: No such file or directory` | Same - submodules not checked out. |
| Windows: *"No CMAKE_CXX_COMPILER could be found"* | Install Visual Studio with the "Desktop development with C++" workload, then re-run from a fresh terminal. |
| First build seems stuck for minutes | Normal - it's compiling ~600 stack files. Only the first build is slow. |
| App prints *"Failed to bind UDP port 47808"* | Another BACnet program is already using 47808. Stop it, or run with `--port <n>`. |
| Client sends Who-Is but sees no I-Am | Firewall is blocking UDP 47808, or the client and device are on different subnets (Who-Is is a broadcast). Allow the port; test on the same subnet first. |
| Replies show an unexpected device instance or vendor | Another BACnet device is already answering on this host/port. On Linux/macOS two processes can share the port and both reply; on Windows the example asks for `SO_EXCLUSIVEADDRUSE` (`common/SimpleUDP.cpp`) so this shows up as a bind failure instead. Stop the other device, or use `--port`. |
