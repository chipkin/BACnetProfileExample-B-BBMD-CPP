# VeriBACnet results

The latest VeriBACnet run of each of this folder's projects, summarised by hand
from that run's `report.json`, one section per mode (see [README.md](README.md)
for the two projects). The runs' own Results Folders (reports, packet captures,
wire logs) are not published: they hold the testing machine's network
addresses.

## BBMD mode (project `b-bbmd-cpp`)

| | |
|---|---|
| Date | 2026-10-27 |
| Example | BACnet B-BBMD (BACnet Broadcast Management Device) Example - C++ v1.2.0 (`common/` 3.5.0), CAS BACnet Stack `6.x` @ `69b6249f` (6.0.23.0) |
| Mode | **BBMD mode** (the default: started without `--no-bbmd`, a BBMD with no peers in its Broadcast Distribution Table) |
| Profile | B-BBMD (BACnet Broadcast Management Device) |
| Transport | BACnet/IP, UDP port 47837 |
| VeriBACnet | 0.20.0 (its test device uses CAS BACnet Stack 6.0.23.0) |
| Test plan | 68 BTL tests (ANSI/ASHRAE 135.1-2023) selected for the B-BBMD profile |
| Result | **48 PASS · 1 FAIL · 0 ERROR · 19 SKIP** |

**Judged BTL-clean on BACnet/IP, in BBMD mode**: the one failure is a limit of
the CAS BACnet Stack, not of the example's own code (below, reported to the
stack), and every skipped test has a stated reason. See "What BTL-clean means"
in [README.md](README.md). This is not BTL certification.

The test plan is 68 tests: the project states which kinds of writable property
the device has (REAL, Enumerated, Unsigned and BOOLEAN values, a list, a
commandable value), that it takes DeviceCommunicationControl with no time
limit, and which services it initiates (below).

**Measured coverage:** 49 of the 68 selected tests ran (48 passed, 1 failed on
the stack's missing host-name resolution). Of the 19 skipped, 4 need an
operator and 15 do not apply to this device (no writable REAL with a restricted
range, no writable fixed-size array, no property tied to unsupported optional
functionality, no writable non-commandable Present_Value, objects are neither
created nor deleted, no object's name or identifier changes over BACnet, three
DeviceCommunicationControl tests apply only to devices older than this one's
Protocol_Revision, and four disable-initiation tests apply only to a device
that initiates more than an I-Am, below). Nothing waits on VeriBACnet.

**Measured now:** **the BBMD function (NM-BBMDC-B)**: the Broadcast
Distribution Table takes and reports its own entry plus five peers (12.3.11.1),
five foreign devices register and are listed (12.3.11.2), and with
`BBMD_Accept_FD_Registrations` written FALSE and activated a registration is
refused (12.3.11.3). ReadProperty (all 8 tests), WriteProperty (7.2.2,
9.22.1.2, 9.22.1.3, 9.22.1.5, 9.22.2.1, 9.22.2.3 and 9.22.2.9 passed), command prioritization on
the three outputs, Who-Is (9 of 9) and Who-Has (15 of 17; the other 2 need an
operator), the refusal of the deprecated DeviceCommunicationControl DISABLE,
and the Multi-state Input's State_Text and Number_Of_States.

**DeviceCommunicationControl disable-initiation (DM-DCC-B) does not apply**:
the project declares that this device initiates only an I-Am (once at
start-up, and in answer to Who-Is) and an I-Have (in answer to Who-Has), and
BACnet lets a device keep sending those while initiation is disabled (checked
by hand earlier: both are still answered). The four tests (9.24.1.6, .8, .9
and .10) take the clause's own skip. 9.24.1.11, which passed, checks that the
deprecated DISABLE is refused. This example's own Wire Tests also cover the
BBMD function end to end (98 checks, all passed on the build that was run).

**Host-name entries (12.3.11.4).** At this Stack Pin the CAS BACnet Stack
accepts a host-name entry in `BBMD_Broadcast_Distribution_Table` when it
carries a broadcast mask, as BACnet/IP requires: the write is acknowledged,
read back as written, and activated by ReinitializeDevice ACTIVATE_CHANGES. A
name written in dotted-decimal form (for example `192.168.1.10`) is used at
once. Any other name is reported as `X'000000000000'` (not resolved) and gets
no forwarded broadcasts, because the stack does not yet resolve host names.
12.3.11.4 therefore fails at its resolution steps (it waits for a forwarded
broadcast at the `localhost` entry and none arrives); this is reported to the
CAS BACnet Stack. The example's `--bdt` option takes IP addresses.

### Tests that did not pass (BBMD mode)

| Test | Result | Why |
|---|---|---|
| 12.3.11.4 Broadcast Distribution Table Configuration via Hostname Entries | FAIL | The device accepts and activates the table with a host-name entry (write, ReinitializeDevice and read-back are right), and forwards a broadcast to the numeric entry. It never resolves the name `localhost`, so no forwarded broadcast reaches that entry within the test's 5 s. This is the CAS BACnet Stack's missing host-name resolution (reported to the stack). |
| 9.24.1.6 Indefinite Time Duration, Disable-Initiation, Restored by DeviceCommunicationControl | SKIP | The clause skips the test for a device that initiates nothing other than an I-Am in response to a Who-Is; this one initiates only I-Am and I-Have, both of which continue while initiation is disabled (above). |
| 9.24.1.8 Finite Time Duration, Disable Initiation | SKIP | Same as 9.24.1.6. |
| 9.24.1.9 Disable of Service Initiation Restored by Time Duration | SKIP | The test's configuration requirement (the device initiates client requests) is not met; same reason as 9.24.1.6. |
| 9.24.1.10 Disable of Service Initiation Restored by DeviceCommunicationControl | SKIP | Same as 9.24.1.9. |
| 9.32.1.12 Who-Has After Object_Name Changed | SKIP | Needs an operator: the Device's name changes only when the example is restarted with `--deviceName`. |
| 9.32.1.13 Who-Has After Object_Identifier Changed | SKIP | Same as 9.32.1.12, with `--deviceID`. |
| 7.3.2.10.9 Device Object_Name is configurable | SKIP | Needs an operator: the name is set at start-up (`--deviceName`), not over BACnet. |
| 7.3.2.10.10 Device Object_Identifier is configurable | SKIP | Same as 7.3.2.10.9, with `--deviceID`. |
| 9.24.1.1, 9.24.1.3, 9.24.1.4 (DeviceCommunicationControl, older revisions) | SKIP | These tests apply only to devices below Protocol_Revision 20; this one is at 30 (9.24.1.11, which passed, checks that it refuses the deprecated DISABLE). |
| 9.22.2.4 Writing with a Property Value that is Out of Range | SKIP | Needs a writable property with a restricted range; the outputs accept any value of their type. The test says to skip in that case. |
| 9.22.2.10 Resizing a writable fixed size array property | SKIP | Needs a writable fixed-size array; this device has none. |
| 9.22.2.11 Writing a Property Value Related to Non-supported Optional Functionality | SKIP | Needs a property tied to optional functionality the device does not support; this device has none. |
| 9.22.1.6 Writing NULL to Non-commandable Properties | SKIP | Needs a writable Present_Value that is not commandable; this device's are all commandable. The BTL Test Plan says to skip. |
| 7.3.2.10.3 Database_Revision after creating an object | SKIP | The device does not create objects (no CreateObject). |
| 7.3.2.10.4 Database_Revision after deleting an object | SKIP | The device does not delete objects. |
| 7.3.2.10.5 Database_Revision after changing an Object_Name | SKIP | Only the Device's name can change, and only at start-up. |
| 7.3.2.10.6 Database_Revision after changing an Object_Identifier | SKIP | No other object's identifier can change. |

The run used no DeviceCommunicationControl password: the example has none (a
source constant, empty), and it has no command-line option for one.

## `--no-bbmd` mode (project `b-bbmd-cpp-no-bbmd`)

| | |
|---|---|
| Date | 2026-10-27 |
| Example | BACnet B-BBMD (BACnet Broadcast Management Device) Example - C++ v1.2.0 (`common/` 3.5.0), CAS BACnet Stack `6.x` @ `69b6249f` (6.0.23.0) |
| Mode | **started with `--no-bbmd`** (a plain BACnet/IP device, not a BBMD) |
| Profile | B-BBMD (BACnet Broadcast Management Device) |
| Transport | BACnet/IP, UDP port 47837 |
| VeriBACnet | 0.20.0 (its test device uses CAS BACnet Stack 6.0.23.0) |
| Test plan | 67 BTL tests (ANSI/ASHRAE 135.1-2023) selected for the B-BBMD profile |
| Result | **43 PASS · 0 FAIL · 0 ERROR · 24 SKIP** |

**Judged BTL-clean on BACnet/IP, in `--no-bbmd` mode, with a star**: no test
failed or errored, and every skipped test has a stated reason. The star is
NM-BBMDC-B (the BBMD function), which this mode does not have by design; it is
measured in the BBMD-mode run. See "What
BTL-clean means" in [README.md](README.md). This is not BTL certification.

**Measured coverage:** 43 of the 67 selected tests ran (all 43 passed). Of the
24 skipped, 4 need an operator, as in BBMD mode; 16 do not apply to this device
(the 15 of BBMD mode, plus 9.22.1.3, which needs a writable property that is
not commandable: the writable BBMD properties exist only in BBMD mode); and
the 4 BBMD tests (12.3.11.1 to 12.3.11.4) do not apply
in this mode, because the device is not a BBMD: it answers a
Read-Broadcast-Distribution-Table with the "not a BBMD" result, as BACnet/IP
requires. 9.22.1.5, which the BBMD-only writable properties bring in, is
not selected in this mode.

Every other result is the same as in the BBMD-mode run above. The
DeviceCommunicationControl disable-initiation tests take the same clause skip
(the device initiates only I-Am and I-Have), and NM-BBMDC-B is measured in the
BBMD-mode run, not here.

No public issue has been opened for any of these.
