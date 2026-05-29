# Phase 1: TN3270E ELF Application ID Implementation

## Overview

This document provides detailed code changes for Phase 1 of ELF enablement: transmitting the ELF Application ID during TN3270E negotiation.

## Objective

Send the ELF Application ID to z/OS during the TN3270E connection negotiation phase, allowing z/OS ELF to identify which application (e.g., TSOVS01) the client wants to connect to.

## Background

### TN3270E Protocol

TN3270E extends the basic TN3270 protocol with additional capabilities including:
- Device type negotiation
- Function negotiation
- Connection establishment
- **ELF Application ID transmission** (our focus)

### ELF Application ID in TN3270E

According to IBM documentation and PCOMM implementation:
- ELF Application ID is sent during TN3270E negotiation
- Transmitted as part of the CONNECT or DEVICE-TYPE subnegotiation
- Format: Application ID string (up to 8 alphanumeric characters)
- Example: "TSOVS01" for TSO VTAM application

## Architecture

### Communication Flow

```
c3270 Client                    z/OS TN3270 Server
     |                                  |
     |------ TCP Connection ---------->|
     |                                  |
     |<----- IAC DO TN3270E -----------|
     |                                  |
     |------ IAC WILL TN3270E -------->|
     |                                  |
     |<----- IAC SB TN3270E SEND ------|
     |       DEVICE-TYPE IAC SE         |
     |                                  |
     |------ IAC SB TN3270E IS ------->|
     |       DEVICE-TYPE REQUEST        |
     |       IBM-3278-2-E               |
     |       CONNECT <ELF-APP-ID>       | <-- OUR ADDITION
     |       IAC SE                     |
     |                                  |
     |<----- IAC SB TN3270E IS --------|
     |       DEVICE-TYPE IS             |
     |       IBM-3278-2-E               |
     |       CONNECT <device-name>      |
     |       IAC SE                     |
```

## File Locations

Based on suite3270 architecture, the relevant files are:

```
suite3270-4.4/
âââ Common/
â   âââ telnet.c          # Main telnet protocol handling
â   âââ tn3270e.c         # TN3270E-specific protocol (if separate)
â   âââ host.c            # Host connection management
â   âââ ctlr.c            # 3270 controller emulation
âââ include/
â   âââ telnet.h          # Telnet protocol definitions
â   âââ tn3270e.h         # TN3270E definitions (if exists)
```

**Note**: The exact file structure will be confirmed when source is downloaded during build.

## Implementation Strategy

### Approach 1: Modify TN3270E DEVICE-TYPE Negotiation (Recommended)

Add ELF Application ID to the DEVICE-TYPE CONNECT subnegotiation.

### Approach 2: Add Separate ELF Subnegotiation

Create a dedicated ELF subnegotiation sequence (if required by protocol).

## Detailed Code Changes

### Step 1: Add TN3270E Protocol Constants

**File**: `suite3270-4.4/include/telnet.h` (or `tn3270e.h`)

```c
/* TN3270E subnegotiation functions */
#define TN3270E_ASSOCIATE       0
#define TN3270E_CONNECT         1
#define TN3270E_DEVICE_TYPE     2
#define TN3270E_FUNCTIONS       3
#define TN3270E_IS              4
#define TN3270E_REASON          5
#define TN3270E_REJECT          6
#define TN3270E_REQUEST         7
#define TN3270E_SEND            8

/* TN3270E CONNECT reasons */
#define TN3270E_CONNECT_REASON_DEVICE_NAME  0
#define TN3270E_CONNECT_REASON_ELF_APPLID   1  /* ADD THIS */
```

### Step 2: Modify TN3270E Negotiation Function

**File**: `suite3270-4.4/Common/telnet.c` (or `tn3270e.c`)

**Location**: Find the function that handles TN3270E DEVICE-TYPE negotiation. It will look something like:

```c
static void
tn3270e_negotiate(void)
{
    // Existing code for TN3270E negotiation
}
```

**Changes**:

```c
/*
 * Send TN3270E DEVICE-TYPE subnegotiation with ELF Application ID
 */
static void
tn3270e_send_device_type(void)
{
    unsigned char buf[256];
    int len = 0;
    
    /* IAC SB TN3270E */
    buf[len++] = IAC;
    buf[len++] = SB;
    buf[len++] = TELOPT_TN3270E;
    
    /* DEVICE-TYPE REQUEST */
    buf[len++] = TN3270E_DEVICE_TYPE;
    buf[len++] = TN3270E_REQUEST;
    
    /* Terminal type (e.g., IBM-3278-2-E) */
    const char *term_type = get_terminal_type();
    strcpy((char *)&buf[len], term_type);
    len += strlen(term_type);
    
    /* CONNECT with device name or ELF Application ID */
    buf[len++] = TN3270E_CONNECT;
    
    /* ADD ELF APPLICATION ID SUPPORT */
    if (appres.elf != NULL) {
        /* Send ELF Application ID instead of device name */
        buf[len++] = TN3270E_CONNECT_REASON_ELF_APPLID;
        strcpy((char *)&buf[len], appres.elf);
        len += strlen(appres.elf);
    } else if (appres.devname != NULL) {
        /* Send device name (existing behavior) */
        buf[len++] = TN3270E_CONNECT_REASON_DEVICE_NAME;
        strcpy((char *)&buf[len], appres.devname);
        len += strlen(appres.devname);
    }
    /* END ELF ADDITION */
    
    /* IAC SE */
    buf[len++] = IAC;
    buf[len++] = SE;
    
    /* Send the subnegotiation */
    net_output(buf, len);
}
```

### Step 3: Add ELF Application ID Validation

**File**: `suite3270-4.4/Common/glue.c` (or create `suite3270-4.4/Common/elf.c`)

```c
/*
 * Validate ELF Application ID
 * Returns true if valid, false otherwise
 */
bool
validate_elf_applid(const char *applid)
{
    if (applid == NULL) {
        return false;
    }
    
    /* Check length (max 8 characters for mainframe) */
    size_t len = strlen(applid);
    if (len == 0 || len > 8) {
        xs_warning("ELF Application ID must be 1-8 characters");
        return false;
    }
    
    /* Check for valid characters (alphanumeric only) */
    for (size_t i = 0; i < len; i++) {
        if (!isalnum((unsigned char)applid[i])) {
            xs_warning("ELF Application ID must contain only alphanumeric characters");
            return false;
        }
    }
    
    return true;
}

/*
 * Initialize ELF support
 * Called during connection initialization
 */
void
elf_init(void)
{
    if (appres.elf != NULL) {
        if (!validate_elf_applid(appres.elf)) {
            xs_warning("Invalid ELF Application ID, disabling ELF");
            appres.elf = NULL;
        } else {
            vtrace("ELF Application ID: %s\n", appres.elf);
        }
    }
}
```

### Step 4: Call ELF Initialization

**File**: `suite3270-4.4/Common/host.c` (or connection initialization code)

**Location**: Find the function that initializes a host connection. It will look something like:

```c
static void
host_connect(const char *host)
{
    // Existing connection initialization
}
```

**Changes**:

```c
static void
host_connect(const char *host)
{
    /* Existing connection initialization code */
    
    /* ADD: Initialize ELF support */
    elf_init();
    
    /* Continue with existing connection code */
}
```

### Step 5: Add Trace Output

**File**: `suite3270-4.4/Common/telnet.c`

Add trace output to help debug ELF negotiation:

```c
static void
tn3270e_send_device_type(void)
{
    /* ... existing code ... */
    
    /* ADD: Trace output for ELF */
    if (appres.elf != NULL) {
        vtrace("TN3270E: Sending ELF Application ID: %s\n", appres.elf);
    }
    
    /* ... rest of function ... */
}
```

## Alternative Implementation: Separate ELF Subnegotiation

If the protocol requires a separate ELF subnegotiation (less common), use this approach:

```c
/*
 * Send ELF Application ID as separate subnegotiation
 */
static void
tn3270e_send_elf_applid(void)
{
    unsigned char buf[64];
    int len = 0;
    
    if (appres.elf == NULL) {
        return;
    }
    
    /* IAC SB TN3270E */
    buf[len++] = IAC;
    buf[len++] = SB;
    buf[len++] = TELOPT_TN3270E;
    
    /* ELF-specific function code (vendor-specific) */
    buf[len++] = TN3270E_ELF_APPLID;  /* Define this constant */
    
    /* Application ID */
    strcpy((char *)&buf[len], appres.elf);
    len += strlen(appres.elf);
    
    /* IAC SE */
    buf[len++] = IAC;
    buf[len++] = SE;
    
    /* Send */
    net_output(buf, len);
    
    vtrace("TN3270E: Sent ELF Application ID: %s\n", appres.elf);
}
```

## Patch File Creation

After making changes, create a patch file:

```bash
# Navigate to source directory
cd suite3270-4.4/

# Create patch for telnet.c changes
git diff Common/telnet.c > ../patches/004-elf-tn3270e-applid.patch

# Or create unified patch for all changes
git diff > ../patches/004-elf-phase1-complete.patch
```

## Testing Phase 1

### Test 1: Verify Option is Parsed

```bash
c3270 -elf TSOVS01 -trace hostname
# Check trace output for "ELF Application ID: TSOVS01"
```

### Test 2: Verify TN3270E Negotiation

```bash
# Capture packets
tcpdump -i any -w elf-test.pcap port 23

# Connect with ELF
c3270 -elf TSOVS01 mainframe.example.com

# Analyze capture
wireshark elf-test.pcap
# Look for TN3270E subnegotiation containing "TSOVS01"
```

### Test 3: Verify z/OS Receives Application ID

Check z/OS logs for ELF Application ID:
```
# On z/OS
D TCPIP,,NETSTAT,TELNET
# Should show connection with ELF Application ID
```

### Test 4: Validation Tests

```bash
# Test empty Application ID
c3270 -elf "" hostname
# Expected: Warning message, ELF disabled

# Test too long Application ID
c3270 -elf "TOOLONGID" hostname
# Expected: Warning message, ELF disabled

# Test invalid characters
c3270 -elf "TSO@VS01" hostname
# Expected: Warning message, ELF disabled

# Test valid Application ID
c3270 -elf "TSOVS01" hostname
# Expected: Success, ELF enabled
```

## Expected Behavior

### Success Case

1. User runs: `c3270 -elf TSOVS01 mainframe.example.com`
2. c3270 validates "TSOVS01" (8 chars, alphanumeric)
3. c3270 connects to mainframe
4. During TN3270E negotiation, c3270 sends:
   ```
   IAC SB TN3270E DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01 IAC SE
   ```
5. z/OS ELF receives Application ID "TSOVS01"
6. z/OS presents logon screen for TSOVS01 application
7. Connection established (Phase 2 will handle authentication)

### Failure Cases

**Invalid Application ID**:
```
c3270 -elf "TSO@VS01" mainframe.example.com
Warning: ELF Application ID must contain only alphanumeric characters
Warning: Invalid ELF Application ID, disabling ELF
# Connection proceeds without ELF
```

**ELF Not Enabled on z/OS**:
```
c3270 -elf TSOVS01 mainframe.example.com
# Connection succeeds but ELF features not available
# User sees standard logon screen
```

## Debugging

### Enable Trace Output

```bash
c3270 -trace -tracefile /tmp/c3270.trace -elf TSOVS01 hostname
```

### Check Trace File

```bash
grep -i "elf\|tn3270e" /tmp/c3270.trace
```

Expected output:
```
ELF Application ID: TSOVS01
TN3270E: Sending DEVICE-TYPE REQUEST
TN3270E: Sending ELF Application ID: TSOVS01
TN3270E: Received DEVICE-TYPE IS
```

### Packet Capture Analysis

Use Wireshark with TN3270 dissector:
1. Capture packets during connection
2. Filter: `telnet`
3. Look for TN3270E subnegotiation
4. Verify "TSOVS01" appears in CONNECT field

## Integration with Existing Code

### Compatibility Considerations

1. **Backward Compatibility**: If `-elf` is not specified, behavior is unchanged
2. **Device Name Priority**: If both `-elf` and `-devname` are specified, `-elf` takes precedence
3. **TN3270 vs TN3270E**: ELF only works with TN3270E, not basic TN3270

### Code Organization

```c
/* In telnet.c or tn3270e.c */

/* Existing TN3270E negotiation */
static void tn3270e_negotiate(void) {
    // Existing code
    tn3270e_send_device_type();  // Modified to include ELF
    // Existing code
}

/* Modified function */
static void tn3270e_send_device_type(void) {
    // Build subnegotiation with ELF support
    // (as shown in Step 2 above)
}

/* New validation function */
bool validate_elf_applid(const char *applid) {
    // (as shown in Step 3 above)
}

/* New initialization function */
void elf_init(void) {
    // (as shown in Step 3 above)
}
```

## Success Criteria

Phase 1 is complete when:

- â `-elf` option is parsed correctly
- â ELF Application ID is validated
- â ELF Application ID is transmitted during TN3270E negotiation
- â Packet capture shows Application ID in TN3270E subnegotiation
- â z/OS receives and processes Application ID
- â Connection establishes successfully
- â Trace output shows ELF activity
- â Invalid Application IDs are rejected with clear error messages

## Next Steps

After Phase 1 is complete:

1. **Phase 2**: Implement ELF token transmission (`)USR.ID(` and `)PSS.WD(`)
2. **Phase 2**: Implement screen detection for prompts
3. **Phase 2**: Integrate with login macro system
4. **Phase 3**: Certificate configuration and validation
5. **Phase 4**: Comprehensive error handling
6. **Phase 5**: Testing and documentation

## References

### Protocol Documentation
- RFC 2355: TN3270 Enhancements
- RFC 1576: TN3270 Current Practices
- IBM TN3270E Protocol Documentation
- IBM ELF Documentation

### Code References
- Existing patches: [`patches/`](../patches/)
- PCOMM reference: [`ELF-Enablement-Analysis/PCOMMOverview.md`](./PCOMMOverview.md)
- Implementation plan: [`ELF-Enablement-Analysis/c3270-ELF-Implementation-Plan.md`](./c3270-ELF-Implementation-Plan.md)

### IBM Documentation
- z/OS Communications Server: IP Configuration Guide
- z/OS Communications Server: IP Configuration Reference
- RACF Security Administrator's Guide

## Appendix: TN3270E Protocol Details

### TN3270E Subnegotiation Format

```
IAC SB TN3270E <function> <parameters> IAC SE

Where:
- IAC = 0xFF (255)
- SB  = 0xFA (250) - Subnegotiation Begin
- SE  = 0xF0 (240) - Subnegotiation End
- TN3270E = 0x28 (40)
```

### DEVICE-TYPE Subnegotiation

```
IAC SB TN3270E DEVICE-TYPE REQUEST <terminal-type> [CONNECT <name>] IAC SE

Example without ELF:
FF FA 28 02 07 IBM-3278-2-E FF F0

Example with ELF:
FF FA 28 02 07 IBM-3278-2-E 01 TSOVS01 FF F0
                              ^  ^^^^^^^
                              |  ELF Application ID
                              CONNECT function
```

### Hex Dump Example

```
Without ELF:
ff fa 28 02 07 49 42 4d 2d 33 32 37 38 2d 32 2d 45 ff f0
|  |  |  |  |  I  B  M  -  3  2  7  8  -  2  -  E  |  |
IAC SB TN DEVICE REQUEST  Terminal Type              IAC SE
      3270E TYPE

With ELF:
ff fa 28 02 07 49 42 4d 2d 33 32 37 38 2d 32 2d 45 01 54 53 4f 56 53 30 31 ff f0
|  |  |  |  |  I  B  M  -  3  2  7  8  -  2  -  E  |  T  S  O  V  S  0  1  |  |
IAC SB TN DEVICE REQUEST  Terminal Type              CONNECT  ELF App ID    IAC SE
      3270E TYPE
```

## Version History

- **v1.0** (2026-05-28) - Initial Phase 1 implementation guide