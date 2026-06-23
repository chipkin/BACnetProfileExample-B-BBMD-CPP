# Plan (STUB): B-BBMD (BACnet Broadcast Management Device) — C++ example

> **STATUS: STUB.** Seed facts below. Expand from
> [`bacnet-profile-plan-template.md`](../../bacnet-profile-plan-template.md) after the
> sample plans ([B-LD](../../BACnetProfileExample-B-LD-CPP/docs/plan.md),
> [B-BC](../../BACnetProfileExample-B-BC-CPP/docs/plan.md)) are reviewed.

**Profile:** B-BBMD · **Family:** Annex L.7 (Miscellaneous) · **Role:** B ·
**Archetype:** Infrastructure · **Difficulty:** 3/5 · **Phase:** B (deferred — infrastructure)

**Thesis:** a Broadcast Management Device — distributes BACnet broadcasts across IP
subnets via a **Broadcast Distribution Table (BDT)** and accepts **Foreign Device**
registrations (FDT). The interesting code is the Network Port's BBMD config.

## Required BIBBs (profiles.md L.7)
`DS-RP-B, DS-WP-B; DM-DDB-B, DM-DOB-B, DM-DCC-B, NM-BBMDC-B`.

## Services to enable
- ReadProperty (1), WriteProperty (15), DCC (17), baseline discovery, + BBMD.

## Objects (baseline + )
- Network Port 1 in **BBMD mode** (`BACnet_IP_Mode = BBMD`), serving
  `BBMD_Broadcast_Distribution_Table` + `BBMD_Foreign_Device_Table` +
  `BBMD_Accept_FD_Registrations`.

## Shared features
- **DEFINE:** F-BBMD (NM-BBMDC-B — BDT/FDT + Register-Foreign-Device).
- **REUSE:** F-DCC (B-ASC), F-OUTPUTS (B-SA writes).

## Known stack gaps
- Confirm the standard DLL's BBMD API: how to enable BBMD mode on the Network Port,
  seed a BDT, and serve/accept FDT entries. profiles.md: ✅ S64 (Annex-J ≥8
  BDT/FDT entries verified; 21 `14_*` BVLL gtests).

## Notes / open questions
- Infrastructure archetype (master plan §5). A single-host demo can show a BDT with
  one entry (itself) + accept a foreign-device registration. Spike the API first.
