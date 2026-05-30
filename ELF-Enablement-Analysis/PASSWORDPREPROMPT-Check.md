# PASSWORDPREPROMPT Check Results

## IKJTSO00 PARMLIB Configuration

Checked `SYS1.PARMLIB(IKJTSO00)` and found:

```
LOGON                        +
   PASSPHRASE(ON)            +
   PASSWORDPREPROMPT(OFF)
```

## Result

â **PASSWORDPREPROMPT(OFF)** is correctly set.

This is **NOT** the cause of the problem. The TSO logon prompt appearing means that ELF authentication is not being recognized by the server at all.

## What This Means

The fact that we see "IKJ56700A ENTER USERID -" indicates:
1. The connection reached TSO
2. TSO is prompting for userid (normal behavior when ELF is not active)
3. ELF authentication was **not** performed by the server

## Next Steps

We need to verify:
1. **Does PCOMM actually work with ELF on this system?**
   - Can you confirm PCOMM logs in automatically without userid/password prompts?
   - Using the same certificate and APPLID "TSOVS01"?

2. **Check TN3270 Server Configuration**
   - Is ExpressLogon enabled for port 923?
   - Is certificate authentication configured?

3. **Check Certificate Mapping in RACF**
   - Is the certificate mapped to userid FULTONM?
   - Can the server extract the userid from the certificate?

## Key Question

**Is ELF actually configured and working on this z/OS system?**

If PCOMM also shows userid/password prompts, then ELF is not properly configured on the server side, and no amount of c3270 code changes will make it work.