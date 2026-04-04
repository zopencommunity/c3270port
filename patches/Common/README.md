# c3270 Express Logon Patches

## Current Patch

**File:** `telnet_new_environ.patch`  
**Version:** 2.0  
**Date:** 2026-04-04

### What It Does

Makes the `-expresslogon` option independent of `-ibmapplid`, allowing you to:
1. Use `-ibmapplid` alone to send only IBMAPPLID (matches PCOMM behavior)
2. Use `-expresslogon` to enable full Express Logon mode (IBMELF + USER)
3. Use both together for complete Express Logon with specific APPLID

### Key Changes from V1

**V1 Behavior (telnet_new_environ.patch.v1):**
- Using `-ibmapplid TSO3090` automatically enabled Express Logon mode
- Always sent: USER + IBMELF + IBMAPPLID
- Could not test IBMAPPLID alone

**V2 Behavior (telnet_new_environ.patch - current):**
- Using `-ibmapplid TSO3090` only sends IBMAPPLID
- Using `-expresslogon` enables Express Logon mode (IBMELF + USER)
- Can test different combinations independently

### Usage Examples

#### Example 1: IBMAPPLID Only (Matches PCOMM)
```bash
c3270 -ibmapplid TSO3090 Y:L:mvs3090.svl.ibm.com:992
```
**Sends:**
```
USERVAR "IBMAPPLID" VALUE "TSO3090"
```

#### Example 2: Full Express Logon
```bash
c3270 -expresslogon -ibmapplid TSO3090 Y:L:mvs3090.svl.ibm.com:992
```
**Sends:**
```
VAR "USER" VALUE "USER66"
USERVAR "IBMELF" VALUE "YES"
USERVAR "IBMAPPLID" VALUE "TSO3090"
```

#### Example 3: Express Logon Without Specific APPLID
```bash
c3270 -expresslogon Y:L:mvs3090.svl.ibm.com:992
```
**Sends:**
```
VAR "USER" VALUE "USER66"
USERVAR "IBMELF" VALUE "YES"
USERVAR "IBMAPPLID" VALUE "None"
```

## Patch Versions

### Version 2.0 (Current)
**File:** `telnet_new_environ.patch`  
**Date:** 2026-04-04  
**Changes:**
- Line 248: Changed condition from `appres.express_logon || appres.ibm_applid != NULL` to `appres.express_logon`
- Line 528: Same change for USER variable sending
- Makes `-expresslogon` independent of `-ibmapplid`

### Version 1.0 (Archived)
**File:** `telnet_new_environ.patch.v1`  
**Date:** 2026-04-02  
**Changes:**
- Added Express Logon support to c3270
- Registered `-expresslogon` and `-ibmapplid` options
- Automatically enabled Express Logon when `-ibmapplid` was used

## Application Instructions

### On macOS/Linux

```bash
cd /path/to/suite3270-4.4

# Restore original file if needed
cp Common/telnet_new_environ.c.orig Common/telnet_new_environ.c

# Apply patch
patch -p1 < /path/to/c3270port/patches/Common/telnet_new_environ.patch

# Verify
grep -A 2 "Set IBMELF only when Express Logon" Common/telnet_new_environ.c
# Should show: if (appres.express_logon) {
```

### On z/OS

```bash
cd /path/to/suite3270-4.4

# Restore original file if needed
cp Common/telnet_new_environ.c.orig Common/telnet_new_environ.c

# Apply patch
patch -p1 < /path/to/c3270port/patches/Common/telnet_new_environ.patch

# Build
make clean
make
```

## Verification

After applying the patch, verify the critical lines:

```bash
# Check line 248 (IBMELF setting)
sed -n '247,252p' Common/telnet_new_environ.c
# Should show: if (appres.express_logon) {

# Check line 528 (USER variable sending)
sed -n '527,543p' Common/telnet_new_environ.c
# Should show: if (appres.express_logon) {
```

## Testing

### Test 1: IBMAPPLID Only
```bash
c3270 -trace -tracefile /tmp/test1.trace -ibmapplid TSO3090 Y:L:mvs3090.svl.ibm.com:992
```
**Expected:** Only IBMAPPLID sent, no IBMELF or USER

### Test 2: Full Express Logon
```bash
c3270 -trace -tracefile /tmp/test2.trace -expresslogon -ibmapplid TSO3090 Y:L:mvs3090.svl.ibm.com:992
```
**Expected:** USER + IBMELF + IBMAPPLID sent

## Rollback

To revert to V1:
```bash
cd /path/to/suite3270-4.4
patch -R -p1 < /path/to/c3270port/patches/Common/telnet_new_environ.patch
patch -p1 < /path/to/c3270port/patches/Common/telnet_new_environ.patch.v1
```

## Documentation

See `/Users/fultonm/Documents/Development/TSOExpressLogon/HostOnDemand/` for:
- `PATCH_V2_TESTING_GUIDE.md` - Complete testing guide
- `PATCH_V2_VERIFICATION.md` - Verification summary
- `DISCONNECT_ISSUE_ANALYSIS.md` - Problem analysis
- `C3270_OPTIONS_EXPLAINED.md` - Option behavior details

## Support

This is internal IBM documentation for Express Logon implementation.

## Version History

- **2.0** (2026-04-04): Made `-expresslogon` independent of `-ibmapplid`
- **1.0** (2026-04-02): Initial Express Logon support