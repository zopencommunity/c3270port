# TN3270 Configuration Analysis

## Configuration File: tn3270.cfg

### Port 923 Configuration (Lines 14-20)

```
TelnetParms
  TTLSPort 923
  ConnType Secure
  Debug Detail
  ExpressLogon          â ELF ENABLED!
  MSG07
EndTelnetParms
```

### VTAM Configuration (Lines 22-29)

```
BeginVTAM
  Port 992 923
  DEFAULTAPPL TSO      â Default APPLID is "TSO"
  DEFAULTLUS
    TCP00001..TCP00030
  ENDDEFAULTLUS
  ALLOWAPPL *          â Allows any APPLID
EndVTAM
```

## Key Findings

### 1. ELF is Enabled
Line 18: `ExpressLogon` confirms ELF is enabled for port 923.

### 2. Default APPLID is "TSO"
Line 24: `DEFAULTAPPL TSO` - The default APPLID is "TSO", not "TSOVS01".

### 3. ALLOWAPPL * Permits Any APPLID
Line 28: `ALLOWAPPL *` means any APPLID is allowed, so "TSOVS01" should be acceptable.

## The Problem

c3270 is requesting APPLID "TSOVS01" but getting rejected with INV-NAME. This suggests:

1. **"TSOVS01" is not a valid VTAM APPLID** - It might not be defined in VTAM
2. **TN3270E CONNECT field is being rejected** - The CONNECT field in DEVICE-TYPE REQUEST is causing the rejection

## APPLID vs CONNECT Field

There's a distinction between:
- **IBMAPPLID** (NEW-ENVIRON) - Specifies which VTAM application to connect to
- **CONNECT** (TN3270E) - Specifies a specific LU or pool name within that application

### Current c3270 Behavior

```
Line 108: SENT IBMAPPLID=TSOVS01 (NEW-ENVIRON)
Line 132: SENT CONNECT TSOVS01 (TN3270E DEVICE-TYPE)
Line 138: RCVD DEVICE-TYPE REJECT REASON INV-NAME
```

The server is rejecting the CONNECT field "TSOVS01" because it's not a valid LU or pool name.

## How ELF Should Work

Based on the configuration and PCOMM trace:

### Option 1: Use Default APPLID
1. Client sends: `IBMELF=YES` (no IBMAPPLID)
2. Server uses: Default APPLID "TSO"
3. Server performs: ELF authentication
4. Result: Automatic logon to TSO

### Option 2: Specify APPLID
1. Client sends: `IBMELF=YES, IBMAPPLID=TSO`
2. Server uses: Specified APPLID "TSO"
3. Server performs: ELF authentication
4. Result: Automatic logon to TSO

### Option 3: Specify Different APPLID
1. Client sends: `IBMELF=YES, IBMAPPLID=CICS` (if CICS is defined)
2. Server uses: Specified APPLID "CICS"
3. Server performs: ELF authentication
4. Result: Automatic logon to CICS

## The CONNECT Field Issue

The CONNECT field in TN3270E DEVICE-TYPE REQUEST is for specifying:
- A specific LU name (e.g., "TCP00001")
- A pool name (e.g., "TSOPOOL")

It is **NOT** for specifying the APPLID. The APPLID is specified in NEW-ENVIRON.

### Current Problem

c3270 is using "TSOVS01" as both:
1. IBMAPPLID (correct usage)
2. CONNECT field (incorrect usage - "TSOVS01" is not an LU or pool name)

This is why we get INV-NAME rejection.

## Solution

### For ELF with Default APPLID

**Option A: Don't send CONNECT field**
```
IBMAPPLID=TSO (or omit for default)
DEVICE-TYPE REQUEST IBM-3278-2-E (no CONNECT field)
```

**Option B: Send valid LU/pool name**
```
IBMAPPLID=TSO
DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TCP00001
```

### For ELF with Specific APPLID

If user wants to connect to a different APPLID (e.g., CICS):
```
IBMAPPLID=CICS
DEVICE-TYPE REQUEST IBM-3278-2-E (no CONNECT field)
```

## Recommended Fix

Modify c3270 to:
1. Use `-elf` option value for IBMAPPLID only
2. **Do NOT use** `-elf` value for CONNECT field
3. Either omit CONNECT field or use a separate option for it

Example:
```bash
# Connect to default APPLID (TSO) with ELF
c3270 -elf TSO ...

# Connect to CICS with ELF
c3270 -elf CICS ...

# Connect to TSO with specific LU
c3270 -elf TSO -connect TCP00001 ...
```

## Why PCOMM Works

PCOMM likely:
1. Sends IBMAPPLID correctly
2. Does NOT send CONNECT field (or sends a valid LU name)
3. Server accepts and performs ELF authentication
4. User is automatically logged in

The PCOMM trace showing "IBMAPPLID=TSOVS01" from server might be:
- Server echoing back the client's request
- Or server sending its configured APPLID
- Need to see earlier in PCOMM trace to confirm

## Next Steps

1. Modify `telnet.c` to NOT use `-elf` value for CONNECT field
2. Test with `-elf TSO` (using default APPLID)
3. Verify ELF authentication works
4. Consider adding separate `-connect` option for LU/pool names