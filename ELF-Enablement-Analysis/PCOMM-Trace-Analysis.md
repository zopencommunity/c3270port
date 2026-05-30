# PCOMM Trace Analysis - ELF Success

## Key Finding: PCOMM Also Sends IBMAPPLID="None"!

Looking at the PCOMM trace `Mike-3270-comm-tcp_ELF_only.TLG`:

**Line 1-6: Server sends IBMAPPLID request**
```
[1] IAC SB NEW-ENVIRONMENT
    USERVAR IBMAPPLID VALUE TSOVS01 IAC SE
```

Wait - this is **BACKWARDS**! The **SERVER** is sending IBMAPPLID=TSOVS01 to the **CLIENT**!

## Critical Discovery: ELF Flow is Reversed!

### What I Expected (Normal TN3270E)
1. Client sends: IBMELF=YES, IBMAPPLID=TSOVS01
2. Server receives and processes
3. Server performs ELF authentication

### What Actually Happens with ELF
1. **Server sends**: IBMAPPLID=TSOVS01 to client
2. Client receives the APPLID from server
3. Server already knows the APPLID (it's configured on the server side)
4. Server performs ELF authentication based on certificate

## Evidence from PCOMM Trace

**Entry [1] - Server to Client:**
```
Inbound data: ff fa 27 03 49 42 4d 41 50 50 4c 49 44 01 54 53 4f 56 53 30 31 ff f0
Translation: IAC SB NEW-ENVIRON USERVAR IBMAPPLID VALUE TSOVS01 IAC SE
```

This is **INBOUND** data (server â client), not outbound!

**Entry [4] - Client Response:**
```
[4] TN3270E (3270-DATA)
    IAC EOR
Inbound data: ')USR.ID('
```

The client is receiving the ELF token prompt `)USR.ID(` from the server!

**Entry [14] - TSO Logon Screen:**
```
[14] Outbound data: TSO/E LOGON screen with:
     - Userid: FULTONM (already filled in!)
     - Password field
     - Account: ACCT001 (already filled in!)
```

The TSO logon screen appears with **userid and account already filled in** by ELF!

**Entry [42] - Successful Logon:**
```
[42] 'ICH70001I FULTONM  LAST ACCESS AT 19:02:34 ON FRIDAY, MAY 29, 2026'
```

User is automatically logged in!

**Entry [56] - TSO READY:**
```
[56] 'READY'
```

User reaches TSO READY prompt without entering credentials!

## What This Means for c3270

### The Problem

c3270 is sending IBMAPPLID=TSOVS01 **TO** the server, but with ELF:
1. The server **already knows** the APPLID (it's configured in TN3270 server config)
2. The server **sends** the APPLID to the client (not the other way around)
3. The client should **receive** and acknowledge the APPLID

### Why c3270 Fails

1. c3270 sends IBMAPPLID=TSOVS01 in NEW-ENVIRON (wrong direction)
2. Server ignores this because it's not how ELF works
3. Server doesn't send APPLID to client (because it expects client to request it?)
4. ELF authentication never happens
5. User sees normal TSO logon screen

### The Fix Needed

c3270 needs to:
1. **NOT** send IBMAPPLID in NEW-ENVIRON IS
2. **WAIT** for server to send IBMAPPLID in NEW-ENVIRON SEND
3. **RECEIVE** the APPLID from the server
4. Let the server perform ELF authentication based on certificate

## Comparison

| Step | PCOMM (Working) | c3270 (Not Working) |
|------|-----------------|---------------------|
| 1. NEW-ENVIRON negotiation | Client: WILL NEW-ENVIRON | Client: WILL NEW-ENVIRON â |
| 2. Server request | Server: SEND IBMAPPLID | Server: SEND IBMELF, IBMAPPLID â |
| 3. Client response | Client: IS IBMELF=YES | Client: IS IBMELF=YES, IBMAPPLID=TSOVS01 â |
| 4. Server sends APPLID | Server: IBMAPPLID=TSOVS01 | **NOT HAPPENING** â |
| 5. ELF authentication | Server authenticates via cert | **NOT HAPPENING** â |
| 6. Result | TSO READY (auto-login) | TSO logon screen (manual) â |

## Root Cause

The `-elf TSOVS01` option in c3270 is being used to **send** IBMAPPLID to the server, but ELF works the opposite way - the server **sends** IBMAPPLID to the client!

The APPLID is configured on the **server side** in the TN3270 configuration, not sent by the client.

## Next Steps

Need to investigate:
1. How does the server know which APPLID to send?
2. Is it based on the port number (923)?
3. Is it based on the certificate?
4. Do we need to change how c3270 handles NEW-ENVIRON with ELF?