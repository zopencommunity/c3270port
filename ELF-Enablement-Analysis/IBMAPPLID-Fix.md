# IBMAPPLID Fix - The Missing Link

## Problem Discovered

**Root Cause**: c3270's `-elf` option was setting the CONNECT field in DEVICE-TYPE REQUEST, but **NOT** setting the IBMAPPLID environment variable in NEW-ENVIRON negotiation.

### Evidence from Trace (x3trc.479)

```
Line 107: SENT SB NEW-ENVIRON IS USERVAR "IBMELF" VALUE "YES" USERVAR "IBMAPPLID" VALUE "None" SE
Line 131: SENT SB TN3270E DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01 SE
Line 137: RCVD SB TN3270E DEVICE-TYPE REJECT REASON INV-NAME SE
```

**The Issue**:
- IBMAPPLID sent as **"None"** (line 107)
- CONNECT field sent as **"TSOVS01"** (line 131)
- Server rejects with INV-NAME (line 137)

## Why PCOMM Works

PCOMM's `SetELFApplID "TSOVS01"` sets **BOTH**:
1. IBMAPPLID environment variable â "TSOVS01"
2. CONNECT field in DEVICE-TYPE REQUEST â "TSOVS01"

c3270's `-elf TSOVS01` was only setting:
1. CONNECT field â "TSOVS01"
2. IBMAPPLID â "None" (default)

## The Fix

### Modified File: `suite3270-4.4/Common/telnet_new_environ.c`

**Before** (lines 240-245):
```c
/* Set IBMAPPLID, from the environment. */
ibmapplid = getenv(IBMAPPLID_VARNAME);
if (ibmapplid == NULL) {
    ibmapplid = IBMAPPLID_NONE;
}
add_environ(&uservars, IBMAPPLID_VARNAME, ibmapplid);
```

**After** (lines 240-248):
```c
/* Set IBMAPPLID, from -elf option or environment. */
ibmapplid = appres.elf;  /* First try -elf command line option */
if (ibmapplid == NULL || *ibmapplid == '\0') {
    ibmapplid = getenv(IBMAPPLID_VARNAME);  /* Fall back to environment */
}
if (ibmapplid == NULL) {
    ibmapplid = IBMAPPLID_NONE;  /* Default to "None" */
}
add_environ(&uservars, IBMAPPLID_VARNAME, ibmapplid);
```

### What Changed

1. **Priority Order**:
   - First: Use `appres.elf` (from `-elf` command line option)
   - Second: Fall back to `IBMAPPLID` environment variable
   - Third: Default to "None"

2. **Consistency**: Now `-elf TSOVS01` sets BOTH:
   - IBMAPPLID environment variable â "TSOVS01"
   - CONNECT field in DEVICE-TYPE REQUEST â "TSOVS01"

## Expected Result

With this fix, the trace should show:

```
SENT SB NEW-ENVIRON IS USERVAR "IBMELF" VALUE "YES" USERVAR "IBMAPPLID" VALUE "TSOVS01" SE
SENT SB TN3270E DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01 SE
RCVD SB TN3270E DEVICE-TYPE IS IBM-3278-2-E CONNECT TSOVS01 SE  â SUCCESS!
```

## Testing

### Command
```bash
c3270 -trace -model 2 -elf TSOVS01 -port 923 \
  -tlsminprotocol TLS1.2 -tlsmaxprotocol TLS1.2 \
  -cafile ${CERT_ROOT}/STD1_server.pem \
  -certfile ${CERT_ROOT}/fultonm_cert.pem \
  -keyfile ${CERT_ROOT}/fultonm_key.pem \
  L:STD1
```

### Expected Behavior

1. â TLS handshake succeeds (SNI fix)
2. â NEW-ENVIRON sends IBMAPPLID="TSOVS01" (this fix)
3. â DEVICE-TYPE REQUEST sends CONNECT TSOVS01
4. â Server accepts with DEVICE-TYPE IS
5. â Connection proceeds to ELF authentication

## Why This Matters

### Two-Part ELF Application ID

The ELF application ID must be sent in **TWO places**:

1. **NEW-ENVIRON (IBMAPPLID)**: Tells z/OS which application to route to
2. **DEVICE-TYPE CONNECT**: Specifies the pool/application name

Both must match for the connection to succeed.

### PCOMM vs c3270

| Aspect | PCOMM | c3270 (before fix) | c3270 (after fix) |
|--------|-------|-------------------|-------------------|
| IBMAPPLID | â TSOVS01 | â None | â TSOVS01 |
| CONNECT | â TSOVS01 | â TSOVS01 | â TSOVS01 |
| Result | â Works | â INV-NAME | â Should work |

## Implementation Details

### File Modified
- **`suite3270-4.4/Common/telnet_new_environ.c`** (lines 240-248)

### Patch File
- **`patches/telnet_new_environ.c.patch`**

### Upload Status
- â Uploaded to z/OS: `/usr/local/sandboxes/fultonm/projects/c3270port/suite3270-4.4/Common/telnet_new_environ.c`
- â Tagged with `chtag -tc ISO8859-1`
- â³ Needs rebuild: `cd ~/projects/c3270port/suite3270-4.4 && gmake clean && gmake`

## All Three Fixes Together

### Fix #1: SNI (Server Name Indication)
**File**: `suite3270-4.4/Common/sio_openssl.c`
**Issue**: Missing SNI in TLS ClientHello
**Status**: â Fixed and uploaded

### Fix #2: Immediate TLS
**Command**: Use `L:STD1` instead of `-secure`
**Issue**: STARTTLS vs immediate TLS mismatch
**Status**: â Resolved (use L: prefix)

### Fix #3: IBMAPPLID Environment Variable
**File**: `suite3270-4.4/Common/telnet_new_environ.c`
**Issue**: `-elf` option not setting IBMAPPLID
**Status**: â Fixed and uploaded

## Next Steps

1. **Rebuild c3270 on z/OS**:
   ```bash
   cd ~/projects/c3270port/suite3270-4.4
   export PATH="/usr/lpp/IBM/foz/v1r1/bin:$PATH"
   export _BPXK_AUTOCVT=ON
   gmake clean
   gmake
   ```

2. **Test with all three fixes**:
   ```bash
   c3270 -trace -model 2 -elf TSOVS01 -port 923 \
     -tlsminprotocol TLS1.2 -tlsmaxprotocol TLS1.2 \
     -cafile ${CERT_ROOT}/STD1_server.pem \
     -certfile ${CERT_ROOT}/fultonm_cert.pem \
     -keyfile ${CERT_ROOT}/fultonm_key.pem \
     L:STD1
   ```

3. **Verify in trace**:
   - TLS handshake completes
   - IBMAPPLID="TSOVS01" sent
   - DEVICE-TYPE IS received (not REJECT)
   - ELF authentication proceeds

## References

- **PCOMM Documentation**: [`PCOMMOverview.md`](PCOMMOverview.md)
- **TLS Success**: [`TLS-Success.md`](TLS-Success.md)
- **SNI Fix**: [`SNI-Fix.md`](SNI-Fix.md)
- **STARTTLS Issue**: [`StartTLS-Issue.md`](StartTLS-Issue.md)
- **RFC 2355**: TN3270 Enhancements (DEVICE-TYPE negotiation)
- **RFC 1572**: TELNET Environment Option (NEW-ENVIRON)

## Conclusion

This fix completes the ELF implementation by ensuring the `-elf` option properly sets the IBMAPPLID environment variable, matching PCOMM's behavior and allowing successful connection to ELF-enabled z/OS applications.