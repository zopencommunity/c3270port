# How task_host_output() Gets Driven

## Call Chain Overview

```
Network Data Arrives
    â
telnet.c: net_input() receives data
    â
telnet.c: process_ds() - Process 3270 data stream
    â
ctlr.c: ctlr_write() - Write to screen buffer
    â
ctlr.c: task_host_output() - Notify tasks of screen change
    â
[OUR ELF CODE RUNS HERE]
```

## Detailed Call Chain

### 1. Network Layer (`telnet.c`)

**Function**: `net_input()`
- Called when data arrives from the network
- Reads data into input buffer
- Processes telnet protocol commands

**Location**: `suite3270-4.4/Common/telnet.c` (around line 2695-2810)

```c
// In TN3270E mode:
rv = process_ds(ibuf + EH_SIZE, (ibptr - ibuf) - EH_SIZE,
                (h->request_flag & TN3270E_RQF_KEYBOARD_RESTORE) != 0);

// In plain 3270 mode:
process_ds(ibuf, ibptr - ibuf, false);

// For SSCP-LU data:
ctlr_write_sscp_lu(ibuf + EH_SIZE, (ibptr - ibuf) - EH_SIZE);
```

### 2. Data Stream Processing (`ctlr.c`)

**Function**: `process_ds()`
- Parses 3270 data stream commands
- Identifies command type (Write, EraseWrite, etc.)
- Calls `ctlr_write()` to update screen

**Location**: `suite3270-4.4/Common/ctlr.c` (around line 602-631)

```c
enum pds
process_ds(unsigned char *buf, size_t buflen, bool kybd_restore)
{
    switch (buf[0]) {
    case CMD_EAU:    /* EraseWriteAlternate */
        rv = ctlr_write(buf, buflen, true);
        break;
    case CMD_EWA:    /* EraseWrite */
        rv = ctlr_write(buf, buflen, true);
        break;
    case CMD_W:      /* Write */
        rv = ctlr_write(buf, buflen, false);
        break;
    // ... other commands
    }
}
```

### 3. Screen Buffer Update (`ctlr.c`)

**Function**: `ctlr_write()`
- Updates the screen buffer (`ea_buf`)
- Processes field attributes
- Handles cursor positioning
- **Calls `task_host_output()` at the end**

**Location**: `suite3270-4.4/Common/ctlr.c` (around line 1341-2180)

```c
enum pds
ctlr_write(unsigned char buf[], size_t buflen, bool erase)
{
    // ... process 3270 data stream ...
    // ... update screen buffer ...
    // ... handle field attributes ...
    
    ps_process();
    
    /* Let a blocked task go. */
    task_host_output();  // <-- THIS IS WHERE IT'S CALLED
    
    return rv;
}
```

### 4. Task Notification (`task.c`)

**Function**: `task_host_output()`
- Notifies waiting tasks that screen has changed
- **This is where our ELF code will run**

**Location**: `suite3270-4.4/Common/task.c` (around line 3773)

```c
void
task_host_output(void)
{
    taskq_t *q;

    set_output_needed(false);

    FOREACH_LLIST(&taskq, q, taskq_t *) {
        task_t *s;
        for (s = q->top; s != NULL; s = s->next) {
            switch (s->state) {
            case TS_SWAIT_OUTPUT:
                snap_save();
                /* fall through... */
            case TS_WAIT_OUTPUT:
                task_set_state(s, TS_RUNNING, "host changed screen");
                break;
            default:
                break;
            }
        }
    } FOREACH_LLIST_END(&taskq, q, taskq_t *);
    
    /* OUR ELF CODE WILL GO HERE */
}
```

## When Does This Happen?

`task_host_output()` is called **every time the host sends data that updates the screen**:

1. **Initial connection** - Host sends welcome screen
2. **User ID prompt** - Host sends login screen with User ID field
3. **Password prompt** - Host sends password screen after User ID submitted
4. **Logged in screen** - Host sends main application screen
5. **Any screen update** - Any time host sends new data

## ELF Authentication Sequence

For ELF authentication, the sequence is:

```
1. Connection established with ELF Application ID
   â
2. Host sends User ID prompt screen
   â
   net_input() â process_ds() â ctlr_write() â task_host_output()
   â
   [ELF code: counter=1, send )USR.ID(]
   â
3. Host sends Password prompt screen
   â
   net_input() â process_ds() â ctlr_write() â task_host_output()
   â
   [ELF code: counter=2, send )PSS.WD(]
   â
4. Host sends logged-in screen
   â
   net_input() â process_ds() â ctlr_write() â task_host_output()
   â
   [ELF code: counter=3, disable]
```

## Why This Works Perfectly for ELF

1. **Automatic**: Called on every screen update from host
2. **Reliable**: Always called after screen buffer is updated
3. **Ordered**: Called in sequence for each screen update
4. **Predictable**: ELF authentication has a fixed sequence
5. **Simple**: Just count the calls and send tokens

## Other Callers of task_host_output()

Besides `ctlr_write()`, `task_host_output()` is also called from:

1. **`ctlr_write_sscp_lu()`** - SSCP-LU data (line 2346)
   ```c
   void
   ctlr_write_sscp_lu(unsigned char buf[], size_t buflen)
   {
       // ... process SSCP-LU data ...
       task_host_output();
   }
   ```

2. **`ctlr_clear()`** - Screen clear (line 555)
   ```c
   void
   ctlr_clear(bool can_snap)
   {
       // ... clear screen ...
       task_host_output();
   }
   ```

3. **NVT mode** - In `nvt.c` (line 1843)
   ```c
   void
   nvt_process(unsigned char c)
   {
       // ... process NVT character ...
       task_store(c);
       task_host_output();
   }
   ```

## Implications for ELF Implementation

### Good News

â **Always called** - Every screen update triggers it
â **Ordered** - Called in sequence, perfect for counting
â **After update** - Screen buffer is already updated
â **Reliable** - Part of core 3270 processing

### Considerations

â ï¸ **Multiple triggers** - Called for every screen update, not just ELF prompts
â ï¸ **NVT mode** - Also called in NVT mode (we check `IN_3270`)
â ï¸ **Timing** - Need to wait for `CAN_PROCEED` (keyboard unlocked)

### Why Our Counter Approach Works

Our simple counter approach works because:

1. **First call** after connection â User ID prompt â Send `)USR.ID(`
2. **Second call** after User ID sent â Password prompt â Send `)PSS.WD(`
3. **Third call** after Password sent â Logged in â Disable

The counter naturally tracks the sequence without needing to parse screen content!

## Summary

**Q**: How does `task_host_output()` get driven?

**A**: It's called automatically by `ctlr_write()` every time the host sends data that updates the 3270 screen. This happens:
- When host sends User ID prompt
- When host sends Password prompt  
- When host sends any screen update

This makes it the **perfect place** to implement ELF authentication because:
- It's called in the exact sequence we need
- We just count the calls (1st, 2nd, 3rd)
- No string parsing needed
- Simple and reliable