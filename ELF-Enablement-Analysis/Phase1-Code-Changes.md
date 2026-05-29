# Phase 1: Detailed Code Changes for ELF Application ID

## Overview

This document provides the exact code changes needed to implement Phase 1 of ELF enablement: transmitting the ELF Application ID during TN3270E negotiation.

Based on analysis of the actual c3270 source code in `suite3270-4.4/`, here are the precise modifications required.

## File 1: `suite3270-4.4/Common/telnet.c`

### Change 1: Modify `tn3270e_request()` Function

**Location**: Lines 2110-2149

**Current Code**:
```c
/* Send a TN3270E terminal type request. */
static void
tn3270e_request(void)
{
    size_t tt_len, tb_len;
    char *tt_out;
    char *t;
    char *xtn;

    /* Always use 3278, per the RFC. */
    xtn = create_3270_termtype(true);
    tt_len = strlen(xtn);
    if (try_lu != NULL && *try_lu) {
	tt_len += strlen(try_lu) + 1;
    }

    tb_len = 5 + tt_len + 2;
    tt_out = Malloc(tb_len + 1);
    t = tt_out;
    t += sprintf(tt_out, "%c%c%c%c%c%s",
	IAC, SB, TELOPT_TN3270E, TN3270E_OP_DEVICE_TYPE, TN3270E_OP_REQUEST,
	force_ascii(xtn));

    if (try_lu != NULL && *try_lu) {
	t += sprintf(t, "%c%s", TN3270E_OP_CONNECT, force_ascii(try_lu));
    }

    sprintf(t, "%c%c", IAC, SE);

    net_hexnvt_out_framed((unsigned char *)tt_out, tb_len, true);
    Free(tt_out);

    vtrace("SENT %s %s DEVICE-TYPE REQUEST %s%s%s %s\n",
	cmd(SB), opt(TELOPT_TN3270E), xtn,
	(try_lu != NULL && *try_lu)? " CONNECT ": "",
	(try_lu != NULL && *try_lu)? try_lu: "",
	cmd(SE));

    Free(xtn);
}
```

**Modified Code**:
```c
/* Send a TN3270E terminal type request. */
static void
tn3270e_request(void)
{
    size_t tt_len, tb_len;
    char *tt_out;
    char *t;
    char *xtn;
    const char *connect_name = NULL;  /* ADD THIS */

    /* Always use 3278, per the RFC. */
    xtn = create_3270_termtype(true);
    tt_len = strlen(xtn);
    
    /* ADD: Determine what to send in CONNECT field */
    if (appres.elf != NULL && *appres.elf) {
        /* ELF Application ID takes precedence */
        connect_name = appres.elf;
        tt_len += strlen(connect_name) + 1;
    } else if (try_lu != NULL && *try_lu) {
        /* Fall back to LU name if no ELF */
        connect_name = try_lu;
        tt_len += strlen(connect_name) + 1;
    }
    /* END ADD */

    tb_len = 5 + tt_len + 2;
    tt_out = Malloc(tb_len + 1);
    t = tt_out;
    t += sprintf(tt_out, "%c%c%c%c%c%s",
	IAC, SB, TELOPT_TN3270E, TN3270E_OP_DEVICE_TYPE, TN3270E_OP_REQUEST,
	force_ascii(xtn));

    /* MODIFY: Use connect_name instead of try_lu */
    if (connect_name != NULL) {
	t += sprintf(t, "%c%s", TN3270E_OP_CONNECT, force_ascii(connect_name));
    }

    sprintf(t, "%c%c", IAC, SE);

    net_hexnvt_out_framed((unsigned char *)tt_out, tb_len, true);
    Free(tt_out);

    /* MODIFY: Update trace output to show ELF or LU */
    vtrace("SENT %s %s DEVICE-TYPE REQUEST %s%s%s%s %s\n",
	cmd(SB), opt(TELOPT_TN3270E), xtn,
	(connect_name != NULL)? " CONNECT ": "",
	(appres.elf != NULL && *appres.elf)? "(ELF) ": "",  /* ADD THIS */
	(connect_name != NULL)? connect_name: "",
	cmd(SE));

    Free(xtn);
}
```

**Summary of Changes**:
1. Added `connect_name` variable to hold either ELF Application ID or LU name
2. Check `appres.elf` first (takes precedence over `try_lu`)
3. Use `connect_name` for CONNECT field
4. Updated trace output to indicate when ELF is being used

## File 2: `suite3270-4.4/Common/glue.c`

### Change 2: Add ELF Validation Function

**Location**: Add after `set_appres_defaults()` function (around line 500)

**New Code**:
```c
/*
 * Validate ELF Application ID.
 * Returns true if valid, false otherwise.
 */
static bool
validate_elf_applid(const char *applid)
{
    size_t len;
    size_t i;

    if (applid == NULL) {
	return false;
    }

    /* Check length (max 8 characters for mainframe applications) */
    len = strlen(applid);
    if (len == 0) {
	xs_warning("ELF Application ID cannot be empty");
	return false;
    }
    if (len > 8) {
	xs_warning("ELF Application ID too long (max 8 characters): %s", applid);
	return false;
    }

    /* Check for valid characters (alphanumeric only) */
    for (i = 0; i < len; i++) {
	if (!isalnum((unsigned char)applid[i])) {
	    xs_warning("ELF Application ID must contain only alphanumeric characters: %s", applid);
	    return false;
	}
    }

    return true;
}

/*
 * Initialize ELF support.
 * Called during connection initialization.
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

## File 3: `suite3270-4.4/Common/host.c`

### Change 3: Call ELF Initialization

**Location**: Find the `host_connect()` or similar connection initialization function

**Search for**: Function that initializes host connection (likely around line 500-1000)

**Add**: Call to `elf_init()` early in the connection process

**Example Location** (exact location depends on code structure):
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

**Note**: The exact function name and location will need to be confirmed by searching for the connection initialization code. Look for functions that:
- Initialize telnet connection
- Are called before TN3270E negotiation
- Set up connection parameters

## File 4: `suite3270-4.4/include/protos.h` (or appropriate header)

### Change 4: Add Function Prototype

**Location**: Add with other function prototypes

**New Code**:
```c
/* ELF support */
void elf_init(void);
```

## Patch File Creation

After making these changes, create a patch file:

```bash
cd suite3270-4.4/

# Create patch for all changes
git diff Common/telnet.c Common/glue.c Common/host.c include/protos.h > ../patches/004-elf-phase1-tn3270e.patch

# Or create individual patches
git diff Common/telnet.c > ../patches/004-elf-telnet-applid.patch
git diff Common/glue.c > ../patches/005-elf-validation.patch
git diff Common/host.c > ../patches/006-elf-init.patch
```

## Testing the Changes

### Test 1: Compile and Basic Functionality

```bash
# Build c3270
cd suite3270-4.4
./configure --enable-c3270
make

# Test that -elf option is recognized
./c3270/c3270 -elf TSOVS01 -help
# Should show -elf in help output

# Test validation
./c3270/c3270 -elf "" hostname
# Expected: Warning about empty Application ID

./c3270/c3270 -elf "TOOLONGID" hostname
# Expected: Warning about length

./c3270/c3270 -elf "TSO@VS01" hostname
# Expected: Warning about invalid characters
```

### Test 2: Trace Output

```bash
# Enable trace to see ELF Application ID being sent
./c3270/c3270 -trace -tracefile /tmp/c3270.trace -elf TSOVS01 hostname

# Check trace file
grep -i "elf\|device-type" /tmp/c3270.trace
```

Expected output:
```
ELF Application ID: TSOVS01
SENT IAC SB TN3270E DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT (ELF) TSOVS01 IAC SE
```

### Test 3: Packet Capture

```bash
# Capture packets
sudo tcpdump -i any -w /tmp/elf-test.pcap port 23 &

# Connect with ELF
./c3270/c3270 -elf TSOVS01 mainframe.example.com

# Stop capture
sudo killall tcpdump

# Analyze with Wireshark
wireshark /tmp/elf-test.pcap
```

Look for TN3270E subnegotiation containing "TSOVS01" in the CONNECT field.

### Test 4: Integration Test with z/OS

```bash
# Connect to actual z/OS system with ELF enabled
./c3270/c3270 -elf TSOVS01 -trace mainframe.example.com

# Verify:
# 1. Connection establishes
# 2. ELF Application ID is sent
# 3. z/OS presents logon screen for TSOVS01 application
```

## Expected Behavior

### Success Case

**Command**:
```bash
c3270 -elf TSOVS01 mainframe.example.com
```

**What Happens**:
1. c3270 validates "TSOVS01" (8 chars, alphanumeric) â
2. c3270 connects to mainframe
3. During TN3270E negotiation, c3270 sends:
   ```
   IAC SB TN3270E DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01 IAC SE
   ```
4. z/OS ELF receives Application ID "TSOVS01"
5. z/OS presents logon screen for TSOVS01 application
6. Connection established (ready for Phase 2 authentication)

**Trace Output**:
```
ELF Application ID: TSOVS01
SENT IAC SB TN3270E DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT (ELF) TSOVS01 IAC SE
RCVD IAC SB TN3270E DEVICE-TYPE IS IBM-3278-2-E CONNECT <device-name> IAC SE
```

### Failure Cases

**Invalid Application ID**:
```bash
c3270 -elf "TSO@VS01" mainframe.example.com
```
Output:
```
Warning: ELF Application ID must contain only alphanumeric characters: TSO@VS01
Warning: Invalid ELF Application ID, disabling ELF
# Connection proceeds without ELF
```

**Too Long**:
```bash
c3270 -elf "TOOLONGID" mainframe.example.com
```
Output:
```
Warning: ELF Application ID too long (max 8 characters): TOOLONGID
Warning: Invalid ELF Application ID, disabling ELF
# Connection proceeds without ELF
```

**Empty**:
```bash
c3270 -elf "" mainframe.example.com
```
Output:
```
Warning: ELF Application ID cannot be empty
Warning: Invalid ELF Application ID, disabling ELF
# Connection proceeds without ELF
```

## Compatibility Notes

### Backward Compatibility

1. **Without `-elf` option**: Behavior is unchanged
   ```bash
   c3270 hostname
   # Works exactly as before
   ```

2. **With `-lu` option only**: Behavior is unchanged
   ```bash
   c3270 -lu MYLU hostname
   # Works exactly as before, sends LU name in CONNECT
   ```

3. **With both `-elf` and `-lu`**: ELF takes precedence
   ```bash
   c3270 -elf TSOVS01 -lu MYLU hostname
   # Sends TSOVS01 (ELF) in CONNECT, not MYLU
   ```

### TN3270 vs TN3270E

- ELF only works with TN3270E protocol
- If host doesn't support TN3270E, connection falls back to basic TN3270
- ELF Application ID is only sent during TN3270E negotiation

## Debugging

### Enable Verbose Trace

```bash
c3270 -trace -tracefile /tmp/c3270.trace -elf TSOVS01 hostname
```

### Check Trace File

```bash
# Look for ELF-related messages
grep -i "elf" /tmp/c3270.trace

# Look for TN3270E negotiation
grep -i "tn3270e\|device-type" /tmp/c3270.trace

# Look for CONNECT messages
grep -i "connect" /tmp/c3270.trace
```

### Expected Trace Patterns

**Successful ELF Negotiation**:
```
ELF Application ID: TSOVS01
SENT IAC SB TN3270E DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT (ELF) TSOVS01 IAC SE
RCVD IAC SB TN3270E DEVICE-TYPE IS IBM-3278-2-E CONNECT <device> IAC SE
SENT IAC SB TN3270E FUNCTIONS REQUEST BIND-IMAGE RESPONSES SYSREQ IAC SE
RCVD IAC SB TN3270E FUNCTIONS IS BIND-IMAGE RESPONSES SYSREQ IAC SE
TN3270E option negotiation complete.
```

**Failed Validation**:
```
Warning: ELF Application ID <reason>
Warning: Invalid ELF Application ID, disabling ELF
SENT IAC SB TN3270E DEVICE-TYPE REQUEST IBM-3278-2-E IAC SE
# Note: No CONNECT field
```

## Code Review Checklist

Before submitting the patch:

- [ ] All changes compile without warnings
- [ ] `-elf` option is recognized and parsed
- [ ] ELF Application ID is validated correctly
- [ ] Invalid IDs are rejected with clear error messages
- [ ] ELF Application ID is sent in TN3270E CONNECT field
- [ ] Trace output shows ELF activity
- [ ] Backward compatibility maintained (works without `-elf`)
- [ ] ELF takes precedence over `-lu` when both specified
- [ ] Code follows existing c3270 style and conventions
- [ ] No memory leaks (all `Malloc` have corresponding `Free`)
- [ ] Function prototypes added to appropriate headers

## Next Steps After Phase 1

Once Phase 1 is complete and tested:

1. **Phase 2**: Implement ELF token transmission
   - Detect User ID prompt
   - Send `)USR.ID(` token
   - Detect Password prompt
   - Send `)PSS.WD(` token

2. **Phase 3**: Certificate configuration
   - Verify TLS/SSL support
   - Document certificate requirements
   - Test with actual certificates

3. **Phase 4**: Error handling
   - Handle authentication failures
   - Provide clear error messages
   - Add recovery mechanisms

4. **Phase 5**: Testing and documentation
   - Comprehensive test suite
   - User documentation
   - Man page updates

## References

- **TN3270E Protocol**: RFC 2355
- **Current Implementation**: `suite3270-4.4/Common/telnet.c`
- **PCOMM Reference**: `ELF-Enablement-Analysis/PCOMMOverview.md`
- **Overall Plan**: `ELF-Enablement-Analysis/c3270-ELF-Implementation-Plan.md`
- **Existing Patches**: `patches/appres.h.patch`, `patches/resources.h.patch`, `patches/glue.c.patch`

## Version History

- **v1.0** (2026-05-28) - Initial Phase 1 code changes based on actual source analysis