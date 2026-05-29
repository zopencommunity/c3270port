# Phase 2: ELF Token Transmission - Seamless Authentication

## Overview

This document provides detailed implementation for Phase 2 of ELF enablement: automatically detecting ELF prompts and transmitting ELF tokens (`)USR.ID(` and `)PSS.WD(`) without requiring user macros.

## Objective

Implement seamless, automatic ELF authentication that:
- Detects User ID and Password prompts automatically
- Sends ELF tokens without user intervention
- Works transparently without requiring macro configuration
- Integrates with existing screen update mechanisms

## Background

### ELF Authentication Flow

```
1. z/OS presents User ID prompt
2. c3270 detects prompt â automatically sends )USR.ID(
3. z/OS extracts User ID from certificate
4. z/OS presents Password prompt  
5. c3270 detects prompt â automatically sends )PSS.WD(
6. z/OS extracts password from certificate
7. Authentication complete
```

### Key Architecture Components

From code analysis, c3270 has these key mechanisms:

1. **Screen Update Detection**: `task_host_output()` called after every screen change
2. **Input Field Detection**: `CAN_PROCEED` macro checks if input field is ready
3. **Keyboard Input**: `emulate_uinput()` sends strings to screen
4. **Field Attributes**: `FA_IS_PROTECTED()` checks if field is protected/unprotected

## Implementation Strategy

### Option B: Dedicated ELF Handler (Recommended)

Create a dedicated ELF authentication handler that:
- Hooks into `task_host_output()` callback
- Detects ELF prompts automatically
- Sends tokens seamlessly
- Tracks authentication state

**Advantages**:
- No macro dependency
- Completely transparent to user
- Integrates with existing screen update flow
- Can be enabled/disabled easily

## Detailed Implementation

### 1. ELF State Machine

Create an ELF authentication state tracker:

```c
/* ELF authentication states */
typedef enum {
    ELF_STATE_DISABLED,      /* ELF not enabled */
    ELF_STATE_IDLE,          /* Connected, waiting for prompts */
    ELF_STATE_USERID_SENT,   /* Sent )USR.ID(, waiting for password prompt */
    ELF_STATE_PASSWORD_SENT, /* Sent )PSS.WD(, authentication complete */
    ELF_STATE_FAILED         /* Authentication failed */
} elf_state_t;

static elf_state_t elf_state = ELF_STATE_DISABLED;
```

### 2. ELF Prompt Detection

Detect User ID and Password prompts by checking screen content:

```c
/*
 * Check if current screen shows a User ID prompt.
 * Common patterns:
 * - "User ID" or "USERID" or "TSO/E LOGON"
 * - Followed by an unprotected input field
 */
static bool
is_userid_prompt(void)
{
    int baddr;
    
    /* Only check in 3270 mode with formatted screen */
    if (!IN_3270 || !formatted) {
        return false;
    }
    
    /* Search for common User ID prompt patterns */
    for (baddr = 0; baddr < ROWS * COLS; baddr++) {
        /* Skip protected fields */
        if (ea_buf[baddr].fa && FA_IS_PROTECTED(ea_buf[baddr].fa)) {
            continue;
        }
        
        /* Check for "User ID" or "USERID" text */
        if (screen_contains_at(baddr, "User ID") ||
            screen_contains_at(baddr, "USERID") ||
            screen_contains_at(baddr, "TSO/E LOGON")) {
            
            /* Verify there's an unprotected input field nearby */
            int field_addr = find_next_unprotected_field(baddr);
            if (field_addr >= 0) {
                return true;
            }
        }
    }
    
    return false;
}

/*
 * Check if current screen shows a Password prompt.
 * Common patterns:
 * - "Password" or "PASSWORD" or "PASS WORD"
 * - Followed by an unprotected input field
 */
static bool
is_password_prompt(void)
{
    int baddr;
    
    /* Only check in 3270 mode with formatted screen */
    if (!IN_3270 || !formatted) {
        return false;
    }
    
    /* Search for common Password prompt patterns */
    for (baddr = 0; baddr < ROWS * COLS; baddr++) {
        /* Skip protected fields */
        if (ea_buf[baddr].fa && FA_IS_PROTECTED(ea_buf[baddr].fa)) {
            continue;
        }
        
        /* Check for "Password" text */
        if (screen_contains_at(baddr, "Password") ||
            screen_contains_at(baddr, "PASSWORD") ||
            screen_contains_at(baddr, "PASS WORD")) {
            
            /* Verify there's an unprotected input field nearby */
            int field_addr = find_next_unprotected_field(baddr);
            if (field_addr >= 0) {
                return true;
            }
        }
    }
    
    return false;
}
```

### 3. Helper Functions

```c
/*
 * Check if screen contains a specific string at or near a location.
 */
static bool
screen_contains_at(int baddr, const char *text)
{
    size_t len = strlen(text);
    size_t i;
    int addr = baddr;
    
    /* Check if text matches at this location */
    for (i = 0; i < len && addr < ROWS * COLS; i++, addr++) {
        ucs4_t screen_char = ebcdic_to_unicode(ea_buf[addr].ec, 
                                               ea_buf[addr].cs, 
                                               EUO_NONE);
        if (toupper(screen_char) != toupper((unsigned char)text[i])) {
            return false;
        }
    }
    
    return (i == len);
}

/*
 * Find the next unprotected input field after a given address.
 */
static int
find_next_unprotected_field(int start_baddr)
{
    int baddr = start_baddr;
    int count = 0;
    
    /* Search forward for an unprotected field */
    while (count < ROWS * COLS) {
        INC_BA(baddr);
        count++;
        
        if (ea_buf[baddr].fa) {
            /* Found a field attribute */
            if (!FA_IS_PROTECTED(ea_buf[baddr].fa)) {
                /* This is an unprotected field */
                return baddr;
            }
        }
    }
    
    return -1;  /* No unprotected field found */
}
```

### 4. ELF Token Transmission

```c
/*
 * Send an ELF token to the current input field.
 */
static void
send_elf_token(const char *token)
{
    ucs4_t *ucs_token;
    size_t len = strlen(token);
    size_t i;
    
    /* Convert token to UCS-4 */
    ucs_token = (ucs4_t *)Malloc((len + 1) * sizeof(ucs4_t));
    for (i = 0; i < len; i++) {
        ucs_token[i] = (ucs4_t)token[i];
    }
    ucs_token[len] = 0;
    
    /* Send the token string */
    emulate_uinput(ucs_token, len, false);
    
    /* Send Enter key */
    key_AID(AID_ENTER);
    
    Free(ucs_token);
    
    vtrace("ELF: Sent token %s\n", token);
}
```

### 5. Main ELF Handler

Hook into `task_host_output()` to check for ELF prompts:

```c
/*
 * ELF authentication handler.
 * Called from task_host_output() after every screen update.
 */
void
elf_check_prompts(void)
{
    /* Only process if ELF is enabled */
    if (appres.elf == NULL || elf_state == ELF_STATE_DISABLED) {
        return;
    }
    
    /* Only process in 3270 mode */
    if (!IN_3270) {
        return;
    }
    
    /* Only process when keyboard is unlocked and ready for input */
    if (!CAN_PROCEED) {
        return;
    }
    
    /* State machine for ELF authentication */
    switch (elf_state) {
    case ELF_STATE_IDLE:
        /* Check for User ID prompt */
        if (is_userid_prompt()) {
            vtrace("ELF: Detected User ID prompt\n");
            send_elf_token(")USR.ID(");
            elf_state = ELF_STATE_USERID_SENT;
        }
        break;
        
    case ELF_STATE_USERID_SENT:
        /* Check for Password prompt */
        if (is_password_prompt()) {
            vtrace("ELF: Detected Password prompt\n");
            send_elf_token(")PSS.WD(");
            elf_state = ELF_STATE_PASSWORD_SENT;
        }
        break;
        
    case ELF_STATE_PASSWORD_SENT:
        /* Authentication complete - disable further processing */
        vtrace("ELF: Authentication complete\n");
        elf_state = ELF_STATE_DISABLED;
        break;
        
    default:
        break;
    }
}
```

### 6. Integration Points

**File**: `suite3270-4.4/Common/glue.c`

Add to `elf_init()`:
```c
void
elf_init(void)
{
    if (appres.elf != NULL) {
        if (!validate_elf_applid(appres.elf)) {
            xs_warning("Invalid ELF Application ID, disabling ELF");
            appres.elf = NULL;
            elf_state = ELF_STATE_DISABLED;
        } else {
            vtrace("ELF Application ID: %s\n", appres.elf);
            elf_state = ELF_STATE_IDLE;  /* Enable ELF authentication */
        }
    } else {
        elf_state = ELF_STATE_DISABLED;
    }
}
```

**File**: `suite3270-4.4/Common/task.c`

Modify `task_host_output()`:
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
    
    /* Check for ELF prompts after screen update */
    elf_check_prompts();  /* NEW: ELF authentication handler */
}
```

## Files to Modify

### Primary Changes

1. **`suite3270-4.4/Common/glue.c`**
   - Add ELF state machine variables
   - Add `is_userid_prompt()` function
   - Add `is_password_prompt()` function
   - Add `screen_contains_at()` helper
   - Add `find_next_unprotected_field()` helper
   - Add `send_elf_token()` function
   - Add `elf_check_prompts()` function
   - Modify `elf_init()` to initialize state

2. **`suite3270-4.4/Common/task.c`**
   - Modify `task_host_output()` to call `elf_check_prompts()`

3. **`suite3270-4.4/include/glue.h`**
   - Add `void elf_check_prompts(void);` prototype

## Prompt Detection Strategy

### User ID Prompt Patterns

Common TSO/VTAM User ID prompts:
- "User ID  ===>"
- "USERID   ===>"
- "TSO/E LOGON"
- "Enter USERID"

### Password Prompt Patterns

Common TSO/VTAM Password prompts:
- "Password  ===>"
- "PASSWORD  ===>"
- "PASS WORD ===>"
- "Enter PASSWORD"

### Detection Algorithm

1. Search screen for prompt text (case-insensitive)
2. Verify an unprotected input field follows the prompt
3. Check that keyboard is unlocked (`CAN_PROCEED`)
4. Send appropriate ELF token

## Error Handling

### Timeout Handling

```c
/* Add timeout for ELF authentication */
#define ELF_TIMEOUT_MS 30000  /* 30 seconds */

static ioid_t elf_timeout_id = NULL_IOID;

static void
elf_timeout(ioid_t id _is_unused)
{
    vtrace("ELF: Authentication timeout\n");
    elf_state = ELF_STATE_FAILED;
    elf_timeout_id = NULL_IOID;
    
    /* Optionally notify user */
    popup_an_error("ELF authentication timeout");
}

/* Set timeout when entering IDLE state */
if (elf_state == ELF_STATE_IDLE) {
    elf_timeout_id = AddTimeOut(ELF_TIMEOUT_MS, elf_timeout);
}

/* Cancel timeout on success */
if (elf_state == ELF_STATE_PASSWORD_SENT) {
    if (elf_timeout_id != NULL_IOID) {
        RemoveTimeOut(elf_timeout_id);
        elf_timeout_id = NULL_IOID;
    }
}
```

### Prompt Detection Failures

```c
/* Track detection attempts */
static int userid_attempts = 0;
static int password_attempts = 0;

#define MAX_DETECTION_ATTEMPTS 5

/* In elf_check_prompts() */
if (elf_state == ELF_STATE_IDLE) {
    if (is_userid_prompt()) {
        userid_attempts = 0;
        send_elf_token(")USR.ID(");
        elf_state = ELF_STATE_USERID_SENT;
    } else {
        userid_attempts++;
        if (userid_attempts > MAX_DETECTION_ATTEMPTS) {
            vtrace("ELF: Failed to detect User ID prompt\n");
            elf_state = ELF_STATE_FAILED;
        }
    }
}
```

## Testing Strategy

### Unit Tests

1. **Prompt Detection**
   - Test `is_userid_prompt()` with various screen layouts
   - Test `is_password_prompt()` with various screen layouts
   - Test `screen_contains_at()` with different text patterns

2. **Token Transmission**
   - Verify `)USR.ID(` is sent correctly
   - Verify `)PSS.WD(` is sent correctly
   - Verify Enter key is sent after each token

3. **State Machine**
   - Test state transitions
   - Test timeout handling
   - Test error conditions

### Integration Tests

1. **End-to-End Authentication**
   - Connect to ELF-enabled z/OS system
   - Verify automatic User ID token transmission
   - Verify automatic Password token transmission
   - Verify successful authentication

2. **Error Scenarios**
   - Test with invalid Application ID
   - Test with missing certificate
   - Test with timeout
   - Test with non-ELF system

## Advantages of This Approach

1. **Seamless**: No user configuration required
2. **Transparent**: Works automatically when `-elf` option is used
3. **Robust**: Handles various prompt formats
4. **Maintainable**: Clean separation of concerns
5. **Testable**: Easy to unit test each component
6. **Flexible**: Can be extended for other authentication methods

## Next Steps

After Phase 2 implementation:
- Phase 3: TLS/SSL Certificate Integration
- Phase 4: Enhanced Error Handling
- Phase 5: Comprehensive Testing

## References

- Phase 1: ELF Application ID transmission (completed)
- c3270 task system: `suite3270-4.4/Common/task.c`
- Screen handling: `suite3270-4.4/Common/ctlr.c`
- Keyboard input: `suite3270-4.4/Common/kybd.c`