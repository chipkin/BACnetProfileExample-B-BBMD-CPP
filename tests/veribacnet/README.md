# VeriBACnet Project

This folder is the **VeriBACnet Project** for the BACnet B-BBMD (Broadcast
Management Device) C++ example. VeriBACnet is Chipkin's BACnet conformance
tool; it runs the BTL test plan (ANSI/ASHRAE 135.1) against a running BACnet
device. The files here describe this example the way VeriBACnet's desktop app
saves a project: which device to test, what that device is, and which tests
apply to it. You can open the project in the app, or run it from the command
line.

Nothing in here is needed to build or run the example itself.

## Which mode each project tests

The example runs in two modes: as a BBMD (the default) and, with `--no-bbmd`,
as a plain BACnet/IP device. The two answer some properties differently (the
Network Port's `BACnet_IP_Mode` reads `bbmd` or `normal`, and the BBMD table
properties exist only in BBMD mode), so each mode gets its own project:

| Project | Mode | Start the example with |
|---|---|---|
| `b-bbmd-cpp` | BBMD mode (the default): the device is a BBMD with no peers in its Broadcast Distribution Table | no mode flag |
| `b-bbmd-cpp-no-bbmd` | plain BACnet/IP device | `--no-bbmd` |

In `--no-bbmd` mode the device is not a BBMD, so it cannot pass the BBMD tests
themselves (NM-BBMDC-B); they belong to the BBMD-mode project.

## What is in the project

Each project is a set of files with the project's id as their prefix
(`<id>` below is `b-bbmd-cpp` or `b-bbmd-cpp-no-bbmd`):

| File | What it is |
|---|---|
| `<id>.project.json` | The project: its name and id, the device to test (address 127.0.0.1, UDP port 47837, device instance 389020), the profile (B-BBMD), and the list of selected tests. It names the other files. |
| `<id>.iut-description.json` | What the tests expect the device to be: its identity strings, the services and object types it supports, its segmentation and maximum APDU size, its objects, and the BIBBs it claims. Written from this example's `docs/PICS.md`, `docs/objects.json` and `main.cpp`. |
| `<id>.device-model.json` | The desktop app's view of the same device: the claimed BIBBs, the EPICS header (profile, product description), and the test settings. |
| `<id>.tpi` | The EPICS (the device's capabilities statement), consistent with `docs/PICS.md`, as the device answers in that project's mode. |
| `<id>.device-snapshot.json` | What VeriBACnet read from the running example in that project's mode (its objects and properties). The device's own network settings (IP address, subnet mask, gateway, DNS server, MAC address, the Broadcast Distribution and Foreign Device Tables and the like) are replaced by the text `host-specific (not recorded)`. |

The files contain no machine names and no absolute paths, and the target is
always `127.0.0.1`. In the EPICS, a property shown as `?` is one the tool could
not decode from the device.

If you change what the example does (a new object, a new service, a different
identity string), change these files to match, the same way you would update
`docs/PICS.md`.

## How to re-run it

1. Build the example (see the top-level README).
2. Start it on UDP port 47837 with device instance 389020, from the root of
   this repository, in the mode of the project you want to run:

   ```
   build\Release\BACnetExampleBBBMD.exe --port 47837 --deviceID 389020
   build\Release\BACnetExampleBBBMD.exe --port 47837 --deviceID 389020 --no-bbmd
   ```

   The first line is BBMD mode (`b-bbmd-cpp`), the second `--no-bbmd` mode
   (`b-bbmd-cpp-no-bbmd`). Wait until it prints
   `FYI: Device 389020 ("Chipkin Example B-BBMD") ready.`
   Use port 47837, not the standard 47808, so the test does not collide with
   other BACnet software on the machine. The example ships with no
   DeviceCommunicationControl password, and the projects carry none. Leave it
   running.
3. In a second terminal, from the root of this repository:

   ```
   VeriBACnet.exe --cli run --project tests/veribacnet/b-bbmd-cpp.project.json
   VeriBACnet.exe --cli run --project tests/veribacnet/b-bbmd-cpp-no-bbmd.project.json
   ```

   (the one that matches the mode you started).
4. Stop the example when the run has finished.

VeriBACnet does not start or stop the example; you do.

## Where the results go

Each run writes its own **Results Folder**: the report (`report.md` and
`report.json`), the findings (`findings.json`), a summary of the run
(`run.json`), and the evidence for every test (a packet capture and a decoded
wire log). By default it is a new, time-stamped folder under
`tests/veribacnet/veribacnet-output/`, which git ignores. Pass
`--out-dir <folder>` to put it somewhere else. The evidence holds the IP
addresses of the machine that ran the test, so do not commit it or publish it.

## What "BTL-clean" means

A run executes the BTL tests that apply to this example's profile and BIBBs.
The example is **BTL-clean** when, on the transport tested, no failure or error
is the example's own fault, every other failure or error is tracked, and every
skipped test has a stated reason (for example, it needs hardware the example
does not simulate). Each failure, error or coverage gap is recorded as a
**Finding**, so a result that is not clean tells you exactly what to look at.

BTL-clean is a statement about this tool's test run. It is not BTL
certification, which is granted by a BACnet Testing Laboratory; the example
has not been submitted for certification.
