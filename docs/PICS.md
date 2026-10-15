# BACnet Protocol Implementation Conformance Statement (PICS)

For the **BACnet B-BBMD (Broadcast Management Device) C++ example** -
see [README.md](../README.md).

> This is the PICS **for the example as shipped**. It describes a tutorial
> device announcing itself as a Chipkin demo, not a product. When you turn this
> example into your own device, this document is one of the things you rewrite:
> the vendor, model and version rows all come from the
> `CHANGE ALL OF THIS BEFORE YOU SHIP` block at the top of `main.cpp`. The
> example has **not** been submitted for BTL certification.

## 1. Product description

| | |
|---|---|
| **Vendor Name** | Chipkin Automation Systems |
| **Vendor Identifier** | 389 |
| **Product Name** | CAS BACnet Stack Example - B-BBMD |
| **Product Model Number** | CAS BACnet Stack Example - B-BBMD |
| **Application Software Version** | 1.2.0 (`APP_VERSION` in `main.cpp`) |
| **Firmware Revision** | the linked CAS BACnet Stack version (6.0.23.0 at this Stack Pin) |
| **BACnet Protocol Version** | 1 |
| **BACnet Protocol Revision** | 30 |

**Product Description:** a BACnet/IP Broadcast Management Device built on the
CAS BACnet Stack. It carries the same object model as the B-ASC example - three
read-only sensor objects and three commandable (WriteProperty) output objects -
plus the one capability the profile exists for: its Network Port performs the
BBMD function (`BACnet_IP_Mode` = `bbmd`), forwarding local broadcasts to the
peers in its Broadcast Distribution Table and accepting Foreign Device
registrations. It is a tutorial for implementers of the B-BBMD profile.

## 2. BACnet standardized device profile (Annex L)

**B-BBMD - Broadcast Management Device** (Annex L.7, Miscellaneous).

This device claims exactly one profile. Annex L allows a Miscellaneous profile
to be combined with one other family (a real product is often "B-BC + B-BBMD");
this example claims only B-BBMD, to demonstrate the BBMD function on the
smallest device that can carry it. Because the B-BBMD requirements are a
superset of B-GENERAL's, a conformant B-BBMD device also satisfies
**B-GENERAL** (Annex L.8); that is subsumption, not a second claim.

## 3. BIBBs supported (Annex K)

| BIBB | Description |
|---|---|
| DS-RP-B | Data Sharing - ReadProperty - B |
| DS-WP-B | Data Sharing - WriteProperty - B |
| DM-DDB-B | Device Management - Dynamic Device Binding - B |
| DM-DOB-B | Device Management - Dynamic Object Binding - B |
| DM-DCC-B | Device Management - DeviceCommunicationControl - B |
| NM-BBMDC-B | Network Management - Broadcast Management Device Configuration - B |

No other BIBBs are supported. In particular this device does **not** support
DS-RPM-B (ReadPropertyMultiple), DS-COV-B, any alarm and event (AE-*) BIBB,
scheduling (SCHED-*), or trending (T-*).

## 4. Application services supported

| Service | Initiate | Execute |
|---|:---:|:---:|
| ReadProperty | no | **yes** |
| WriteProperty | no | **yes** |
| Who-Is | no | **yes** |
| I-Am | **yes** | - |
| Who-Has | no | **yes** |
| I-Have | **yes** | - |
| DeviceCommunicationControl | no | **yes** |
| ReinitializeDevice | no | **yes** - ACTIVATE_CHANGES and WARMSTART only (they make a written BDT effective, cl. 12.56.38); other states are refused with `optional-functionality-not-supported`. No password. |
| Register-Foreign-Device (Annex J) | no | **yes** (accepted into the FDT; NAK `X'0030'` when its 128 entries are full) |
| Read-Broadcast-Distribution-Table (Annex J) | no | **yes** |
| Read-Foreign-Device-Table (Annex J) | no | **yes** |
| Delete-Foreign-Device-Table-Entry (Annex J) | no | **yes** (entry removed; BVLC-Result NAK `X'0050'` if absent) |
| Distribute-Broadcast-To-Network (Annex J) | no | **yes** (from a registered foreign device; NAK `X'0060'` from any other) |
| Write-Broadcast-Distribution-Table (Annex J) | no | always **NAK** - BVLC-Result `X'0010'`, as J.4.4.2 requires |

An unsolicited I-Am is broadcast to the local subnet at start-up, as well as in
response to Who-Is. Every Annex J BVLL message above, and `Forwarded-NPDU`, is
handled entirely by the stack, not by application code. The BDT is configured
by WriteProperty of the Network Port's `BBMD_Broadcast_Distribution_Table`
(Annex J.4.4), never by `Write-Broadcast-Distribution-Table`. The stack makes
that property writable (cl. 12.56.38). Cl. 12.56.38 makes a written value
effective on ReinitializeDevice ACTIVATE_CHANGES or WARMSTART; at this Stack
Pin the stack applies it as soon as it acknowledges the write and leaves
`Changes_Pending` FALSE (a known deviation, stack #3930, `TODO.md`). A list without this
device's own entry is refused (`value-out-of-range`). At start-up the BDT comes from `--bdt`. Started with
`--no-bbmd`, the device answers every BBMD message above with the NAK Annex J
requires of a non-BBMD (`X'0030'`, `X'0020'`, `X'0040'`, `X'0050'`).

Any other confirmed service is rejected - including ReadPropertyMultiple,
SubscribeCOV, and any alarm/event or scheduling service.

## 5. Segmentation capability

Segmentation is **not supported** in either direction
(`Segmentation_Supported` = `no-segmentation`). `Max_APDU_Length_Accepted` is
1476 octets, the BACnet/IP maximum.

## 6. Standard object types supported

No object is dynamically creatable or deletable. The three output objects are
commandable (a 16-slot `Priority_Array` resolves `Present_Value`). The only
other writable properties are the Network Port's `BBMD_Broadcast_Distribution_Table`
and `BBMD_Accept_FD_Registrations` (section 9).

| Object type | Instance | Object_Name | Optional properties supported |
|---|:---:|---|---|
| Device | 389020 | Chipkin Example B-BBMD | Description |
| Analog Input | 1 | Bronze | - |
| Binary Input | 1 | Emerald | - |
| Multi-State Input | 1 | Hot Pink | State_Text |
| Analog Output | 1 | Chartreuse | - |
| Binary Output | 1 | Fuchsia | - |
| Multi-State Output | 1 | Indigo | - |
| Network Port | 1 | Vermilion | - |

The device instance is configurable at run time with `--deviceID` (BACnet
requires the device instance to be configurable).

## 7. Data link layer options

**BACnet/IP (Annex J)**, UDP port 47808 (0xBAC0) by default, configurable at run
time with `--port`.

**This Network Port performs the BBMD function** (`BACnetStack_SetBBMD`) and
reports `BACnet_IP_Mode` = `bbmd`, not `normal`. **Foreign Device registration is
supported** - the stack accepts `Register-Foreign-Device` into the Foreign
Device Table and ages entries out on TTL expiry. BACnet/SC, MS/TP, Ethernet
(Annex H) and PTP are not supported.

## 8. Device address binding

Static device binding is **not supported**. The device answers Who-Is/Who-Has
and does not initiate any confirmed request, so it never needs to bind a peer.

## 9. Networking options

**This device is a BBMD** (unless started with `--no-bbmd`). Its Broadcast
Distribution Table holds its own entry (computed from the live interface,
two-hop mask `255.255.255.255`) plus one entry per `--bdt <ip>[:<port>][/<mask>]`
option; a client can replace it by WriteProperty. It supports two-hop
distribution (one-hop by giving a peer its subnet mask), at least five peer
BBMDs and at least five foreign devices (K.6.6; the stack's tables hold 512 and
128 entries), and any foreign-device lifetime the 16-bit Time-to-Live can carry,
which covers K.6.6's 30 s - 9 h (each entry is purged Time-to-Live + 30 s after
its last registration, J.5.2.3; the Wire Tests exercise 30 s and 300 s).
`BBMD_Accept_FD_Registrations` reads TRUE at start-up and is writable: a
written FALSE becomes effective on ReinitializeDevice ACTIVATE_CHANGES or
WARMSTART (cl. 12.56.39), after which every Register-Foreign-Device is refused
with NAK `X'0030'` (J.5.2.2). It forwards a local broadcast to every
BDT peer as a unicast `Forwarded-NPDU`, and re-broadcasts what it receives from
a peer onto its own subnet - both handled entirely by the stack. It also
accepts Foreign Device registrations into its Foreign Device Table. The device
is not a router and does not perform network-layer routing.

The `BBMD_Broadcast_Distribution_Table`, `BBMD_Foreign_Device_Table`, and
`BBMD_Accept_FD_Registrations` properties on the Network Port are enabled by
`SetBBMD`, which also makes `BACnet_IP_Mode` read `bbmd`; the application does
neither itself.

## 10. Character sets supported

UTF-8 (ANSI X3.4). Supporting a character set does not imply the device can
handle data in all character sets.

## 11. Objects and properties

<!-- OBJECTS-PROPERTIES:BEGIN (generated by tools/gen-objects-properties.py from docs/objects.json - do not edit here) -->
Every object this example creates, and every REQUIRED property of each (per ANSI/ASHRAE 135-2024 clause 12 and the stack's `docs/property-profile-reference.md`), plus the optional properties the example turns on. **Served by** says who answers a ReadProperty: the **stack** generates it, or the **app** serves it from a `GetProperty*` callback in `main.cpp`. A ⚠ row is a required property the app does not serve and the stack would fill with a default - that is a defect, not a feature.

### Device 389020 "Chipkin Example B-BBMD" - vendor 389 (Chipkin Automation Systems); instance configurable with --deviceID. The stack rows are device-wide facts only the stack knows - the protocol version and revision it implements, the services and object types it was configured with (from the BACnetStack_SetServiceEnabled/AddObject calls this example makes), the live object list and address-binding table. The accepted rows are the stack's configured defaults for APDU limits, segmentation, system status and database revision; an application that answered them from its own constants could contradict the stack, so this example does not

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
| Protocol_Version | Unsigned | stack | no |
| Protocol_Revision | Unsigned | stack | no |
| Protocol_Services_Supported | BACnetServicesSupported | stack | no |
| Protocol_Object_Types_Supported | BACnetObjectTypesSupported | stack | no |
| Object_List | BACnetARRAY[N] of BACnetObjectIdentifier | stack | no |
| Max_APDU_Length_Accepted | Unsigned | stack default, accepted (`CAS_BACNET_DEVICE_DEFAULT_MAX_APDU_LENGTH_ACCEPTED`) | no |
| Segmentation_Supported | BACnetSegmentation | stack default, accepted (`BACnetSegmentation::segmentedBoth` with `STACK_OPTION_SEGME) | no |
| APDU_Timeout | Unsigned | stack default, accepted (`CAS_BACNET_DEVICE_DEFAULT_APDU_TIMEOUT`) | no |
| Number_Of_APDU_Retries | Unsigned | stack default, accepted (`CAS_BACNET_DEVICE_DEFAULT_NUMBER_OF_APDU_RETRIES`) | no |
| Device_Address_Binding | BACnetLIST of BACnetAddressBinding | stack | no |
| Database_Revision | Unsigned | stack default, accepted (Generic UnsignedInteger default: `0`) | no |
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |

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
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |

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
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |

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
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |

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
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |
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
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |
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
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |
| Current_Command_Priority | BACnetOptionalUnsigned | stack | no |

### Network Port 1 "Vermilion" - BACnet/IP, and this Network Port is the BBMD: BACnetStack_SetBBMD makes it one and it reports BACnet_IP_Mode=bbmd instead of normal (normal when started with --no-bbmd); SetBBMD also enables the BBMD_Broadcast_Distribution_Table/BBMD_Foreign_Device_Table/BBMD_Accept_FD_Registrations properties (not in this table - they are IPv4-BBMD-conditional properties outside property-profile-reference.md's base Network Port set), which are stack-computed from the live BDT/FDT, not app-served. BBMD_Broadcast_Distribution_Table is writable (cl. 12.56.38; a write must keep this device's own entry, and at this Stack Pin takes effect when acknowledged instead of on ReinitializeDevice ACTIVATE_CHANGES/WARMSTART as cl. 12.56.38 requires - stack #3930, TODO.md); BBMD_Accept_FD_Registrations is writable as a pending change that ReinitializeDevice ACTIVATE_CHANGES/WARMSTART makes effective (cl. 12.56.39). Network_Type and Protocol_Level are set from BACnetStack_AddNetworkPortObject()'s arguments (IPv4, BACnet Application) at start-up, not a GetProperty callback like the object's other app-served rows; Changes_Pending is likewise computed and answered natively by the stack's Network Port object. Reliability has no fault condition this example detects, so it is accepted at the generic default (normal)

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
| Property_List | BACnetARRAY[N] of BACnetPropertyIdentifier | stack | no |

<!-- OBJECTS-PROPERTIES:END -->

## 12. References

- ANSI/ASHRAE Standard 135-2024, Annex A (PICS template), Annex J (BACnet/IP
  and BBMDs), Annex K (BIBBs), Annex L (device profiles), Clause 12 (object
  types).
- [README.md](../README.md) - what this example is and how to build it.
- [TUTORIAL.md](../TUTORIAL.md) - how to extend it, and how to keep this
  document honest when you do.
