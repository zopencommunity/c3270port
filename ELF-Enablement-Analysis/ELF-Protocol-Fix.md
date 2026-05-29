# ELF Protocol Fix - Application ID Prefix

## Problem Identified

The trace file analysis revealed that the z/OS server was rejecting the ELF Application ID with error:
```
DEVICE-TYPE REJECT REASON INV-NAME
```

## Root Cause

The ELF Application ID "TSOVS01" was being sent in the TN3270E CONNECT field **without the required "(ELF) " prefix**.

### What Was Sent (Incorrect)
```
DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01
```

### What Should Be Sent (Correct)
```
DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT (ELF) TSOVS01
```

## Evidence from Documentation

### PCOMM Behavior
The PCOMM macro documentation shows that ELF Application IDs are sent with the "(ELF) " prefix to distinguish them from regular LU names.

### Trace File Analysis
The trace output showed "(ELF)" in the debug message but this was only for display purposes - the actual protocol data did not include the prefix.

## The Fix

### File: `patches/telnet.c.patch`

**Changes Made:**

1. **Length Calculation** (line 21):
   ```c
   tt_len += strlen("(ELF) ") + strlen(connect_name) + 1;
   ```
   Added 6 bytes for the "(ELF) " prefix.

2. **Protocol Data Transmission** (lines 40-46):
   ```c
   if (appres.elf != NULL && *appres.elf) {
       /* Send ELF Application ID with "(ELF) " prefix */
       t += sprintf(t, "%c(ELF) %s", TN3270E_OP_CONNECT, force_ascii(connect_name));
   } else {
       /* Send regular LU name */
       t += sprintf(t, "%c%s", TN3270E_OP_CONNECT, force_ascii(connect_name));
   }
   ```
   Now actually sends "(ELF) " in the protocol data when using ELF.

## Why This Matters

The "(ELF) " prefix serves as a protocol indicator that tells the z/OS server:
- This is an ELF Application ID, not a regular LU name
- The server should look up this Application ID in its ELF configuration
- The server should expect ELF tokens (`)USR.ID(` and `)PSS.WD(`) for authentication

Without this prefix, the server treats "TSOVS01" as a regular LU name and rejects it because no such LU exists.

## Expected Outcome

With this fix, the TN3270E negotiation should succeed:
1. Client sends: `DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT (ELF) TSOVS01`
2. Server recognizes "(ELF) TSOVS01" as an ELF Application ID
3. Server responds: `DEVICE-TYPE IS IBM-3278-2-E CONNECT (ELF) TSOVS01`
4. Connection proceeds to logon screen
5. Client sends ELF tokens for certificate-based authentication

## Testing Required

1. Rebuild c3270 with updated patch
2. Test connection with `-elf TSOVS01` option
3. Verify trace shows "(ELF) TSOVS01" in CONNECT field
4. Verify server accepts the connection
5. Verify ELF tokens are processed correctly

## Related Files

- `patches/telnet.c.patch` - Updated with "(ELF) " prefix fix
- `x3trc.83886345` - Original trace showing the rejection
- `PCOMMOverview.md` - PCOMM documentation reference

## Commit

```
commit 6c8bf18
Fix ELF Application ID transmission - add (ELF) prefix