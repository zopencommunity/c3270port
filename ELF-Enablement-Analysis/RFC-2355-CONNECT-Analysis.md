# RFC 2355 CONNECT Field Analysis for ELF Implementation

## Document Purpose
Analysis of RFC 2355 TN3270E specification to understand the proper use of the CONNECT field in DEVICE-TYPE negotiation, specifically for ELF (Enhanced Logon Facility) implementation.

## Key RFC 2355 Sections

### DEVICE-TYPE REQUEST Command (Section 7.1)

**RFC 2355 Specification:**
```
IAC SB TN3270E DEVICE-TYPE REQUEST <device-type>
    [ [CONNECT <resource-name>] | [ASSOCIATE <device-name>] ] IAC SE
```

**Key Points:**
1. The REQUEST command **MAY OPTIONALLY** include either CONNECT or ASSOCIATE
2. CONNECT and ASSOCIATE are **mutually exclusive** (cannot use both)
3. CONNECT is followed by a `<resource-name>`
4. The CONNECT field is **OPTIONAL** - it can be omitted entirely

### CONNECT Command Purpose (Section 7.1.2)

**RFC 2355 States:**
> "CONNECT can be used by the client in two ways: if the resource-name it specifies is a device-name, then the client is requesting a specific device-name. If the specified resource-name is not a device-name, then the client is requesting any one of the device-names associated with the resource-name."

**Two Use Cases:**
1. **Specific Device Request**: `CONNECT T1000001` (requesting specific terminal T1000001)
2. **Pool Request**: `CONNECT pool1` (requesting any device from pool named "pool1")

**Validation Rules:**
- Resource-name must match the device-type (terminal vs printer)
- Device-name must not be already in use by another session
- Device-name must be defined to the server
- Server must deny request if any validation fails

### Resource-Name vs Device-Name (Section 7.1.1)

**RFC 2355 Definitions:**

**Device-Name:**
- Synonymous with "LU name" and "network name"
- Refers to a **specific** terminal or printer device
- Example: `T1000001`, `P1000001`

**Resource-Name:**
- **Less specific** than device-name
- May refer to a device-name OR a pool name
- Pool name groups devices with similar characteristics
- Example: `pool1`, `dept-terminals`, `TSOVS01`

**Naming Rules:**
- NVT ASCII strings
- Upper and lower case considered equivalent
- Length should not exceed 8 bytes
- Servers must avoid ambiguity (no device-name can have same name as a pool)

### Generic vs Specific Session Requests (Section 7.1.1)

**RFC 2355 Definitions:**

**Generic Session Request:**
- Includes **neither** CONNECT nor ASSOCIATE
- Example: `DEVICE-TYPE REQUEST IBM-3278-2-E`
- Server selects device-name from default pool

**Specific Session Request:**
- Includes **either** CONNECT or ASSOCIATE
- Example: `DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01`
- Client specifies which resource to use

### DEVICE-TYPE IS Response (Section 7.1.4)

**RFC 2355 Specification:**
```
IAC SB TN3270E DEVICE-TYPE IS <device-type> CONNECT <device-name> IAC SE
```

**Key Points:**
1. Server **ALWAYS** returns a device-name in the CONNECT field
2. This is true whether client sent CONNECT or not
3. The device-name is what the server actually assigned
4. This may differ from what client requested (if client requested a pool)

### RFC 2355 Examples

**Example 1: Generic Terminal Session (Section 13.4)**
```
Server:  IAC SB TN3270E SEND DEVICE-TYPE IAC SE
Client:  IAC SB TN3270E DEVICE-TYPE REQUEST IBM-3278-2 IAC SE
Server:  IAC SB TN3270E DEVICE-TYPE IS IBM-3278-2 CONNECT anyterm IAC SE
```
- Client did NOT send CONNECT field
- Server still returns CONNECT with device-name "anyterm"

**Example 2: Specific Device Request (Section 13.4)**
```
Server:  IAC SB TN3270E SEND DEVICE-TYPE IAC SE
Client:  IAC SB TN3270E DEVICE-TYPE REQUEST IBM-3278-5-E CONNECT myterm IAC SE
Server:  IAC SB TN3270E DEVICE-TYPE IS IBM-3278-5-E CONNECT myterm IAC SE
```
- Client requested specific device "myterm"
- Server accepted and returned same device-name

**Example 3: Resource Pool Request (Section 13.4)**
```
Server:  IAC SB TN3270E SEND DEVICE-TYPE IAC SE
Client:  IAC SB TN3270E DEVICE-TYPE REQUEST IBM-3278-5-E CONNECT pool1 IAC SE
Server:  IAC SB TN3270E DEVICE-TYPE IS IBM-3278-5-E CONNECT term0013 IAC SE
```
- Client requested resource pool "pool1"
- Server selected device "term0013" from that pool
- Server returned actual device-name, not pool name

## Analysis for ELF Implementation

### What is TSOVS01?

Based on RFC 2355 terminology:
- **TSOVS01 is a resource-name** (not a device-name)
- It likely refers to a **pool of terminals** configured for TSO access
- Or it could be a **specific device-name** if configured that way
- The server determines how to interpret it

### ELF Application ID vs CONNECT Field

**Critical Understanding:**
1. **CONNECT field is for device/pool selection** (RFC 2355 protocol)
2. **ELF Application ID is for authentication** (IBM ELF feature)
3. **These are separate concepts** that happen to use similar names

**ELF Application ID:**
- Server-side configuration in `tn3270.cfg` ExpressLogon directive
- Maps client certificate to TSO userid
- NOT transmitted in TN3270E protocol by client
- Server determines Application ID from certificate

**CONNECT Field:**
- TN3270E protocol field for device/pool selection
- Client MAY send it to request specific device or pool
- Server uses it to select which device-name to assign
- Has nothing to do with authentication

### Why Our Implementation Failed

**Attempt 1: No CONNECT field**
```
DEVICE-TYPE REQUEST IBM-3278-2-E
```
- This is a **generic session request**
- Server selects device from default pool
- May have been rejected because default pool doesn't have ExpressLogon enabled

**Attempt 2: CONNECT with "(ELF) " prefix**
```
DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT (ELF) TSOVS01
```
- Invalid resource-name format
- RFC 2355 says resource-names should not exceed 8 bytes
- "(ELF) TSOVS01" is 13 bytes
- Parentheses are not standard in resource-names
- Server rejected as INV-NAME (invalid name)

**Attempt 3: CONNECT without prefix**
```
DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01
```
- Valid RFC 2355 format
- "TSOVS01" is 7 bytes (within 8-byte limit)
- Should have worked IF:
  - TSOVS01 is defined as a resource-name or device-name
  - TSOVS01 pool/device has ExpressLogon enabled
  - TSOVS01 is not already in use
- Rejection suggests server-side configuration issue

### Correct ELF Implementation

**Based on RFC 2355 and ELF architecture:**

**Option 1: Use CONNECT with Application ID as resource-name**
```c
if (appres.elf != NULL && *appres.elf) {
    // Send Application ID as resource-name in CONNECT field
    connect_name = appres.elf;  // e.g., "TSOVS01"
}
```
- Assumes Application ID is configured as a resource-name on server
- Server uses it to select device from ELF-enabled pool
- This is likely the correct approach

**Option 2: Generic request (no CONNECT)**
```c
if (appres.elf != NULL && *appres.elf) {
    // Don't send CONNECT - let server choose from default pool
    connect_name = NULL;
}
```
- Only works if default pool has ExpressLogon enabled
- Less control over which pool is used

**Option 3: Use CONNECT with explicit pool name**
```c
if (appres.elf != NULL && *appres.elf) {
    // Send known ELF pool name
    connect_name = "ELFPOOL";  // or whatever the pool is named
}
```
- Requires knowing the pool name in advance
- More flexible than Option 2

## Recommendations

### Immediate Actions

1. **Verify Server Configuration**
   - Check if "TSOVS01" is defined as a resource-name or device-name
   - Verify TSOVS01 has ExpressLogon enabled in tn3270.cfg
   - Confirm TSOVS01 is not already in use

2. **Test with Correct Port**
   - Ensure testing on port 923 (ExpressLogon-enabled)
   - Not port 992 (may not have ExpressLogon)

3. **Use Option 1 Implementation**
   ```c
   if (appres.elf != NULL && *appres.elf) {
       connect_name = appres.elf;  // Send Application ID as resource-name
   }
   ```

4. **Capture PCOMM Trace**
   - See if PCOMM sends CONNECT field
   - See what resource-name PCOMM uses
   - Compare with our implementation

### Testing Strategy

**Test 1: Generic Request**
```
c3270 -elf TSOVS01 host:923
```
Expected: `DEVICE-TYPE REQUEST IBM-3278-2-E` (no CONNECT)

**Test 2: Specific Request**
```
c3270 -elf TSOVS01 host:923
```
Expected: `DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01`

**Test 3: Different Pool**
```
c3270 -elf ELFPOOL host:923
```
Expected: `DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT ELFPOOL`

### Server-Side Verification

**Check tn3270.cfg:**
```
Port 923
  ExpressLogon TSOVS01
  ...
```

**Check RACF:**
```
RACDCERT CERTMAP ID(userid) WITHLABEL('cert-label')
```

**Check TSO/E:**
```
D IKJTSO,LOGON
```
Verify: `PASSWORDPREPROMPT(OFF)`

## Conclusion

**Key Findings:**
1. CONNECT field is **optional** in RFC 2355
2. CONNECT is for **device/pool selection**, not authentication
3. ELF Application ID is **server-side configuration**, not protocol
4. Our "(ELF) " prefix was **invalid** per RFC 2355
5. Plain "TSOVS01" is **correct RFC 2355 format**
6. Rejection likely due to **server configuration**, not protocol

**Next Steps:**
1. Verify server-side configuration (TSOVS01 definition, ExpressLogon, port)
2. Test with correct port (923 vs 992)
3. Capture PCOMM trace for comparison
4. Use Option 1 implementation (send Application ID as resource-name)

**Implementation Status:**
- Current code (no CONNECT when ELF enabled) may be incorrect
- Should send CONNECT with Application ID as resource-name
- This aligns with RFC 2355 and allows server to select ELF-enabled device

---

**References:**
- RFC 2355: TN3270 Enhancements
- IBM TN3270 Server Configuration Guide
- IBM ELF Documentation