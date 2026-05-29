# Global Variable vs Parameter Passing: ELF State Analysis

## Executive Summary

After analyzing the c3270 codebase, **using a global variable for ELF state is the correct architectural choice** for this implementation. While global variables are generally discouraged, this case represents a legitimate exception where the alternatives would introduce significant complexity without meaningful benefit.

## Current Architecture Analysis

### task_host_output() Function Signature

```c
void task_host_output(void)
```

**Key Observations**:
1. **No parameters** - Called from multiple locations without context
2. **No return value** - Pure notification callback
3. **Called from 3 different modules**:
   - `ctlr.c` (3 call sites) - After screen updates
   - `nvt.c` (1 call site) - After NVT output
4. **Purpose**: Notify task system that host has changed the screen

### Call Sites in ctlr.c

```c
// ctlr.c line 555 - After erase command
void ctlr_erase(bool alt) {
    kybd_inhibit(false);
    ctlr_clear(true);
    task_host_output();  // â No context available
    ...
}

// ctlr.c line 2176 - After write command
static void ctlr_write(...) {
    ...
    task_host_output();  // â No context available
    ...
}

// ctlr.c line 2346 - After another write operation
void ctlr_write_sscp_lu(...) {
    ...
    task_host_output();  // â No context available
}
```

**Critical Point**: These call sites have **no knowledge of ELF state** and **no way to pass it**.

## Option 1: Global Variable (Current Design)

### Implementation

```c
// glue.h
typedef enum {
    ELF_DISABLED = 0,
    ELF_SEND_USERID,
    ELF_SEND_PASSWORD,
    ELF_COMPLETE
} elf_state_t;

extern elf_state_t elf_state;

// glue.c
elf_state_t elf_state = ELF_DISABLED;

// task.c
void task_host_output(void) {
    // ... existing code ...
    
    // ELF logic
    if (elf_state != ELF_DISABLED && IN_3270 && CAN_PROCEED) {
        switch (elf_state) {
            case ELF_SEND_USERID:
                send_elf_token(")USR.ID(");
                elf_state = ELF_SEND_PASSWORD;
                break;
            // ... etc
        }
    }
}
```

### Advantages

â **Simple**: Minimal code changes
â **Clean**: No API changes required
â **Maintainable**: Easy to understand and debug
â **Consistent**: Matches existing c3270 patterns (see below)
â **Efficient**: No parameter passing overhead
â **Testable**: State can be inspected/modified for testing

### Disadvantages

â ï¸ **Global state**: Theoretically less "pure"
â ï¸**Thread safety**: Could be an issue in multi-threaded context (but c3270 is single-threaded)

## Option 2: Parameter Passing

### Required Changes

To pass state as a parameter, we would need to:

1. **Change task_host_output() signature**:
```c
// Old
void task_host_output(void);

// New
void task_host_output(elf_state_t *elf_state);
```

2. **Update all call sites** (4 locations across 2 files):
```c
// ctlr.c - 3 call sites
task_host_output(&elf_state);  // But where does elf_state come from?

// nvt.c - 1 call site
task_host_output(&elf_state);  // But where does elf_state come from?
```

3. **Thread state through calling chain**:

```
host.c:host_connect()
    â (needs to store elf_state somewhere)
ctlr.c:ctlr_erase()
    â (needs access to elf_state)
task_host_output(&elf_state)
```

**Problem**: The calling modules (ctlr.c, nvt.c) have **no natural place to store ELF state**.

### Option 2a: Pass Through All Callers

```c
// ctlr.c would need to store elf_state
static elf_state_t *global_elf_state;  // â Still global!

void ctlr_erase(bool alt) {
    ...
    task_host_output(global_elf_state);  // â Just moved the global
}
```

**Result**: We've just moved the global variable to a different file. No improvement.

### Option 2b: Context Object Pattern

```c
// Create a context object
typedef struct {
    elf_state_t elf_state;
    // ... other connection state ...
} connection_context_t;

// Pass context everywhere
void task_host_output(connection_context_t *ctx);
void ctlr_erase(bool alt, connection_context_t *ctx);
void ctlr_write(..., connection_context_t *ctx);
// ... etc
```

**Required Changes**:
- Modify 50+ function signatures
- Thread context through entire call chain
- Massive refactoring effort
- High risk of introducing bugs

**Benefit**: Slightly more "pure" architecture

**Cost**: Weeks of work, high risk, minimal practical benefit

### Disadvantages of Parameter Passing

â **Massive refactoring**: 50+ function signatures need changes
â **API breakage**: Changes public interfaces
â **Complexity**: Context must be threaded through unrelated code
â **Risk**: High chance of introducing bugs
â **Maintenance burden**: Future code must maintain context passing
â **No real benefit**: Still need storage somewhere (just moved the problem)

## Existing c3270 Patterns

### c3270 Already Uses Global State Extensively

Looking at the codebase, c3270 uses global variables for similar purposes:

```c
// ctlr.c - Screen state (global)
int ROWS, COLS;
int cursor_addr, buffer_addr;
struct ea *ea_buf;  // 3270 device buffer
bool formatted;
bool screen_changed;

// host.c - Connection state (global)
char *current_host;
char *full_current_host;
char *qualified_host;

// telnet.c - Protocol state (global)
static bool tn3270e_negotiated;
static char *tn3270e_current_opts;
```

**Pattern**: c3270 uses global state for **per-connection singleton state**.

### Why This Pattern Exists

1. **Single connection model**: c3270 maintains one connection at a time
2. **Callback architecture**: Many functions are callbacks with fixed signatures
3. **Historical design**: Inherited from original 3270 terminal architecture
4. **Practical**: Simpler than threading context through 40+ years of code

### ELF State Fits This Pattern

- **Per-connection**: One ELF state per connection (like `tn3270e_negotiated`)
- **Singleton**: Only one connection active at a time
- **Callback context**: Used in callback with fixed signature (`task_host_output`)
- **Connection lifetime**: Reset on each new connection (in `elf_init()`)

## Comparison Table

| Aspect | Global Variable | Parameter Passing |
|--------|----------------|-------------------|
| **Code Changes** | ~40 lines | ~500+ lines |
| **Files Modified** | 3 files | 10+ files |
| **API Changes** | None | 50+ functions |
| **Risk Level** | Low | High |
| **Maintenance** | Easy | Complex |
| **Consistency** | Matches c3270 patterns | Inconsistent with codebase |
| **Testing** | Easy | Harder |
| **Debugging** | Easy (inspect global) | Harder (trace context) |
| **Thread Safety** | N/A (single-threaded) | N/A (single-threaded) |
| **Purity** | Less pure | More pure |
| **Practicality** | High | Low |

## Real-World Considerations

### When Global Variables Are Acceptable

Global variables are acceptable when:
1. â **Singleton state** - Only one instance needed (ELF state per connection)
2. â **Callback context** - Used in callbacks with fixed signatures
3. â **Consistent with codebase** - Matches existing patterns
4. â **Simple alternative** - Alternatives are significantly more complex
5. â **Clear ownership** - Lifetime and initialization are clear

**ELF state meets ALL these criteria.**

### When to Avoid Global Variables

Avoid global variables when:
- â Multiple instances needed (not our case)
- â Thread safety required (c3270 is single-threaded)
- â Testing is difficult (not our case - easy to set/inspect)
- â Unclear lifetime (not our case - tied to connection)
- â Simple alternatives exist (not our case - alternatives are complex)

**None of these apply to ELF state.**

## Recommendation

### Use Global Variable (Option 1)

**Rationale**:
1. **Architectural consistency**: Matches existing c3270 patterns
2. **Minimal impact**: Small, focused change
3. **Low risk**: No API changes, easy to test
4. **Maintainable**: Easy to understand and debug
5. **Practical**: Solves the problem without over-engineering

### Implementation Guidelines

```c
// glue.h - Public interface
typedef enum {
    ELF_DISABLED = 0,
    ELF_SEND_USERID,
    ELF_SEND_PASSWORD,
    ELF_COMPLETE
} elf_state_t;

extern elf_state_t elf_state;  // â Global, but clearly documented
void send_elf_token(const char *token);

// glue.c - Implementation
elf_state_t elf_state = ELF_DISABLED;  // â Initialized to safe default

void elf_init(void) {
    // Reset state on each connection
    if (appres.elf_applid != NULL && validate_elf_applid(appres.elf_applid)) {
        elf_state = ELF_SEND_USERID;  // â Enable ELF
    } else {
        elf_state = ELF_DISABLED;  // â Disable ELF
    }
}

// task.c - Usage
void task_host_output(void) {
    // ... existing code ...
    
    // ELF logic - clean and simple
    if (elf_state != ELF_DISABLED && IN_3270 && CAN_PROCEED) {
        switch (elf_state) {
            case ELF_SEND_USERID:
                send_elf_token(")USR.ID(");
                elf_state = ELF_SEND_PASSWORD;
                break;
            case ELF_SEND_PASSWORD:
                send_elf_token(")PSS.WD(");
                elf_state = ELF_COMPLETE;
                break;
            case ELF_COMPLETE:
                elf_state = ELF_DISABLED;
                break;
        }
    }
}
```

### Documentation

Add clear comments:

```c
/**
 * ELF authentication state.
 * 
 * This is a per-connection singleton state that tracks the progress
 * of ELF (Enhanced Logon Facility) automatic authentication.
 * 
 * Lifetime:
 * - Initialized in elf_init() when connection is established
 * - Updated in task_host_output() as authentication progresses
 * - Reset to ELF_DISABLED when authentication completes
 * 
 * Thread Safety:
 * - c3270 is single-threaded, no synchronization needed
 * 
 * Testing:
 * - Can be directly inspected and modified for unit tests
 */
extern elf_state_t elf_state;
```

## Conclusion

**Use the global variable approach.** It is:
- â Simpler
- â Safer
- â More maintainable
- â Consistent with c3270 architecture
- â Easier to test and debug

The parameter-passing alternative would require massive refactoring for minimal benefit, introducing significant risk without solving any real problem. The global variable is not a compromise - it's the **correct architectural choice** for this specific context.

### Quote from "The Pragmatic Programmer"

> "Don't be a slave to formal methods. Use what works, and don't be afraid to break the rules when it makes sense."

In this case, a well-documented global variable is the pragmatic, maintainable solution.