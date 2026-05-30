# ELF Implementation Correction Based on RFC 2355

## Executive Summary

After analyzing RFC 2355 (TN3270 Enhancements), we discovered that our ELF implementation was **incorrect**. The CONNECT field should **include** the Application ID, not omit it.

## Previous Implementation (INCORRECT)

**What we did:**
```c
if (appres.elf != NULL && *appres.elf) {
    /* ELF mode: Don't send CONNECT field */
    connect_name = NULL;
}
```

**Result:**
- Sent: `DEVICE-TYPE REQUEST IBM-3278-2-E` (no CONNECT field)
- This is a "generic session request" per RFC 2355
- Server selects device from default pool
- Default pool may not have ExpressLogon enabled
- Connection rejected

**Why this was wrong:**
- We assumed Application ID was server-side only
- We thought client shouldn't send it in protocol
- This was based on misunderstanding of ELF architecture

## Corrected Implementation (CORRECT)

**What we should do:**
```c
if (appres.elf != NULL && *appres.elf) {
    /* ELF mode: Send Application ID as resource-name in CONNECT field
     * Per RFC 2355, CONNECT specifies a resource-name (device or pool).
     * The ELF Application ID (e.g., "TSOVS01") is configured on the server
     * as a resource-name that maps to an ELF-enabled device pool.
     * This allows the server to select a device from the ELF pool.
     */
    connect_name = appres.elf;
    tt_len += strlen(connect_name) + 1;
}
```

**Result:**
- Sends: `DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01`
- This is a "specific session request" per RFC 2355
- Server uses "TSOVS01" as resource-name to select device
- "TSOVS01" maps to ELF-enabled device pool on server
- Server returns actual device-name from that pool

## RFC 2355 Key Findings

### 1. CONNECT Field is Optional

**RFC 2355 Section 7.1:**
> "The REQUEST command may optionally include either the CONNECT or the ASSOCIATE command (but not both)."

**Two types of requests:**
- **Generic**: No CONNECT field â server chooses from default pool
- **Specific**: With CONNECT field â server uses specified resource

### 2. Resource-Name vs Device-Name

**RFC 2355 Section 7.1.1:**

**Resource-Name:**
- May refer to a device-name OR a pool name
- Less specific than device-name
- Example: "TSOVS01" (pool name), "T1000001" (device name)

**Device-Name:**
- Specific terminal or printer device
- Synonymous with "LU name" and "network name"
- Example: "T1000001", "P1000001"

### 3. CONNECT Command Purpose

**RFC 2355 Section 7.1.2:**
> "CONNECT can be used by the client in two ways: if the resource-name it specifies is a device-name, then the client is requesting a specific device-name. If the specified resource-name is not a device-name, then the client is requesting any one of the device-names associated with the resource-name."

**Two use cases:**
1. **Specific device**: `CONNECT T1000001` â request specific terminal
2. **Pool request**: `CONNECT TSOVS01` â request any device from TSOVS01 pool

### 4. Server Always Returns Device-Name

**RFC 2355 Section 7.1.4:**
```
IAC SB TN3270E DEVICE-TYPE IS <device-type> CONNECT <device-name> IAC SE
```

**Key point:**
- Server **always** returns CONNECT with actual device-name
- Even if client didn't send CONNECT
- Even if client sent pool name (server returns actual device from pool)

## ELF Application ID Explained

### What is TSOVS01?

**In ELF context, TSOVS01 is:**
1. **A resource-name** (RFC 2355 terminology)
2. **An Application ID** (ELF terminology)
3. **A pool name** configured on the server
4. **Maps to ELF-enabled devices** via server configuration

### Server-Side Configuration

**In tn3270.cfg:**
```
Port 923
  ExpressLogon TSOVS01
  ...
```

**What this means:**
- Port 923 has ExpressLogon enabled
- "TSOVS01" is the Application ID for this port
- Devices on this port are in the "TSOVS01" pool
- Client certificates are mapped to this Application ID

### Client-Side Usage

**Client sends:**
```
DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01
```

**Server interprets:**
1. Client wants device from "TSOVS01" resource pool
2. "TSOVS01" pool has ExpressLogon enabled
3. Server validates client certificate
4. Server maps certificate to userid via RACF
5. Server selects device from TSOVS01 pool
6. Server returns: `DEVICE-TYPE IS IBM-3278-2-E CONNECT T1000001`

## Why Previous Attempts Failed

### Attempt 1: No CONNECT Field
```
DEVICE-TYPE REQUEST IBM-3278-2-E
```
**Problem:** Generic request â default pool â no ExpressLogon

### Attempt 2: Invalid Format
```
DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT (ELF) TSOVS01
```
**Problem:** 
- "(ELF) TSOVS01" is 13 bytes (exceeds 8-byte limit)
- Parentheses not standard in resource-names
- Server rejected as INV-NAME

### Attempt 3: Correct Format (Should Work)
```
DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01
```
**Should work IF:**
- TSOVS01 is defined as resource-name on server
- TSOVS01 pool has ExpressLogon enabled
- Testing on correct port (923, not 992)
- Certificate is properly mapped in RACF

## Implementation Changes

### File: patches/telnet.c.patch

**Changed lines 17-25:**
```c
/* Determine what to send in CONNECT field */
if (appres.elf != NULL && *appres.elf) {
    /* ELF mode: Send Application ID as resource-name in CONNECT field
     * Per RFC 2355, CONNECT specifies a resource-name (device or pool).
     * The ELF Application ID (e.g., "TSOVS01") is configured on the server
     * as a resource-name that maps to an ELF-enabled device pool.
     * This allows the server to select a device from the ELF pool.
     */
    connect_name = appres.elf;
    tt_len += strlen(connect_name) + 1;
} else if (try_lu != NULL && *try_lu) {
    /* Regular mode: Send LU name in CONNECT field */
    connect_name = try_lu;
    tt_len += strlen(connect_name) + 1;
}
```

**Changed lines 47-55 (vtrace):**
```c
vtrace("SENT %s %s DEVICE-TYPE REQUEST %s%s%s %s\n",
    cmd(SB), opt(TELOPT_TN3270E), xtn,
    (connect_name != NULL)? " CONNECT ": "",
    (connect_name != NULL)? connect_name: "",
    cmd(SE));
```

**Removed:**
- "(ELF) " prefix in vtrace (was for debugging only)
- Logic that set connect_name to NULL for ELF

**Added:**
- Proper RFC 2355 compliant CONNECT field with Application ID
- Detailed comments explaining the RFC 2355 rationale

## Testing Plan

### 1. Rebuild c3270
```bash
cd c3270port
localzopen clean
localzopen build
```

### 2. Sync to z/OS
```bash
remotezopen build
```

### 3. Test Connection
```bash
c3270 -elf TSOVS01 host:923
```

**Expected protocol:**
```
SENT IAC SB TN3270E DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01 IAC SE
RECV IAC SB TN3270E DEVICE-TYPE IS IBM-3278-2-E CONNECT T1000001 IAC SE
```

### 4. Verify Server-Side

**Check tn3270.cfg:**
```
Port 923
  ExpressLogon TSOVS01
```

**Check RACF certificate mapping:**
```
RACDCERT CERTMAP ID(userid) WITHLABEL('cert-label')
```

**Check TSO/E configuration:**
```
D IKJTSO,LOGON
```
Verify: `PASSWORDPREPROMPT(OFF)`

### 5. Capture New Trace

**On z/OS:**
```bash
export X3270TRACE=1
c3270 -elf TSOVS01 host:923
```

**Compare with previous traces:**
- x3trc.83886345 (no CONNECT)
- x3trc.16777786 (invalid "(ELF) " prefix)
- New trace (correct CONNECT TSOVS01)

## Expected Outcome

**If server is configured correctly:**
1. Client sends: `DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01`
2. Server validates certificate
3. Server maps certificate to userid
4. Server selects device from TSOVS01 pool
5. Server responds: `DEVICE-TYPE IS IBM-3278-2-E CONNECT T1000001`
6. Connection succeeds
7. ELF tokens are sent: `)USR.ID(` and `)PSS.WD(`
8. TSO logon completes automatically

**If still failing:**
- Check server configuration (TSOVS01 definition, ExpressLogon, port)
- Verify certificate mapping in RACF
- Confirm PASSWORDPREPROMPT(OFF) in TSO/E
- Compare with PCOMM trace to see exact protocol differences

## Conclusion

**Key Learnings:**
1. RFC 2355 CONNECT field is for device/pool selection
2. ELF Application ID should be sent as resource-name in CONNECT
3. Server uses Application ID to select from ELF-enabled pool
4. This is separate from certificate-based authentication
5. Both mechanisms work together for ELF

**Implementation Status:**
- â Corrected telnet.c patch to send Application ID in CONNECT field
- â Added RFC 2355 compliant comments
- â Removed invalid "(ELF) " prefix
- â³ Ready for rebuild and testing

**Next Steps:**
1. Rebuild c3270 with corrected patch
2. Sync to z/OS
3. Test with `-elf TSOVS01` option
4. Verify server-side configuration
5. Capture and analyze new trace

---

**References:**
- RFC 2355: TN3270 Enhancements (Sections 7.1, 7.1.1, 7.1.2, 7.1.4)
- ELF-Enablement-Analysis/RFC-2355-CONNECT-Analysis.md
- IBM TN3270 Server Configuration Guide
- IBM ELF Documentation