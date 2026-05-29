# File-Static Variable Options Analysis

## Question

Can we make `elf_state` file-static by:
1. Having `elf_init()` call a setter function in task.c?
2. Moving `elf_init()` to task.c instead of glue.c?

## Option 1: elf_init() Calls Setter in task.c

### Implementation

```c
// task.h (or glue.h)
typedef enum {
    ELF_DISABLED = 0,
    ELF_SEND_USERID,
    ELF_SEND_PASSWORD,
    ELF_COMPLETE
} elf_state_t;

void elf_set_initial_state(elf_state_t state);  // Setter in task.c

// task.c
static elf_state_t elf_state = ELF_DISABLED;  // â File-static!

void elf_set_initial_state(elf_state_t state) {
    elf_state = state;
}

void task_host_output(void) {
    if (elf_state != ELF_DISABLED && IN_3270 && CAN_PROCEED) {
        switch (elf_state) {
            case ELF_SEND_USERID:
                send_elf_token(")USR.ID(");
                elf_state = ELF_SEND_PASSWORD;  // â Direct access within file
                break;
            // ... etc
        }
    }
}

// glue.c
void elf_init(void) {
    const char *elf_applid = appres.elf_applid;
    
    if (elf_applid == NULL || *elf_applid == '\0') {
        elf_set_initial_state(ELF_DISABLED);
        return;
    }
    
    if (!validate_elf_applid(elf_applid)) {
        popup_an_error("Invalid ELF Application ID");
        elf_set_initial_state(ELF_DISABLED);
        return;
    }
    
    elf_set_initial_state(ELF_SEND_USERID);  // â Call setter
}
```

### Analysis of Option 1

**Advantages**:
â `elf_state` is file-static in task.c
â State transitions stay in task.c (good locality)
â Only initialization crosses file boundary
â Encapsulation achieved

**Disadvantages**:
â Adds one extra function (`elf_set_initial_state`)
â Slightly more complex than direct global access
â `elf_init()` still in glue.c (validation logic there)

**Verdict**: â **This works and is a good option!**

## Option 2: Move elf_init() to task.c

### Implementation

```c
// task.h (or glue.h)
typedef enum {
    ELF_DISABLED = 0,
    ELF_SEND_USERID,
    ELF_SEND_PASSWORD,
    ELF_COMPLETE
} elf_state_t;

void elf_init(void);  // Now in task.c

// task.c
static elf_state_t elf_state = ELF_DISABLED;  // â File-static!

void elf_init(void) {
    const char *elf_applid = appres.elf_applid;
    
    if (elf_applid == NULL || *elf_applid == '\0') {
        elf_state = ELF_DISABLED;
        return;
    }
    
    if (!validate_elf_applid(elf_applid)) {  // â Need to call glue.c function
        popup_an_error("Invalid ELF Application ID");
        elf_state = ELF_DISABLED;
        return;
    }
    
    elf_state = ELF_SEND_USERID;
}

void task_host_output(void) {
    if (elf_state != ELF_DISABLED && IN_3270 && CAN_PROCEED) {
        switch (elf_state) {
            case ELF_SEND_USERID:
                send_elf_token(")USR.ID(");  // â Need to call glue.c function
                elf_state = ELF_SEND_PASSWORD;
                break;
            // ... etc
        }
    }
}

// glue.c
bool validate_elf_applid(const char *applid) {
    // Validation logic stays here
}

void send_elf_token(const char *token) {
    // Token sending logic stays here
}
```

### Analysis of Option 2

**Advantages**:
â `elf_state` is file-static in task.c
â All ELF state management in one file (task.c)
â No setter function needed

**Disadvantages**:
â `elf_init()` now in task.c, but validation logic in glue.c
â Less logical - initialization separated from validation
â task.c must call glue.c functions (`validate_elf_applid`, `send_elf_token`)
â Breaks logical grouping (ELF functions split across files)

**Verdict**: â ï¸ **This works but is less clean than Option 1**

## Comparison: Three Approaches

| Aspect | Global Variable | Option 1: Setter | Option 2: Move Init |
|--------|----------------|------------------|---------------------|
| **Encapsulation** | Low | High | High |
| **Code Locality** | Medium | High | Medium |
| **Logical Grouping** | Good | Good | Poor |
| **Complexity** | Low | Low-Medium | Medium |
| **Extra Functions** | 0 | 1 (setter) | 0 |
| **Lines of Code** | ~40 | ~45 | ~40 |
| **Maintainability** | Easy | Easy | Medium |

## Detailed Comparison

### Global Variable (Current Plan)
```c
// glue.h
extern elf_state_t elf_state;

// glue.c
elf_state_t elf_state = ELF_DISABLED;
void elf_init(void) { elf_state = ...; }

// task.c
void task_host_output(void) { elf_state = ...; }
```

**Pros**: Simple, direct, matches c3270 patterns
**Cons**: Global state visible everywhere

### Option 1: Setter Function
```c
// task.h
void elf_set_initial_state(elf_state_t state);

// task.c
static elf_state_t elf_state = ELF_DISABLED;  // File-static!
void elf_set_initial_state(elf_state_t state) { elf_state = state; }
void task_host_output(void) { elf_state = ...; }

// glue.c
void elf_init(void) { elf_set_initial_state(...); }
```

**Pros**: File-static, good encapsulation, logical grouping
**Cons**: One extra function

### Option 2: Move elf_init()
```c
// task.c
static elf_state_t elf_state = ELF_DISABLED;  // File-static!
void elf_init(void) { elf_state = ...; }
void task_host_output(void) { elf_state = ...; }

// glue.c
bool validate_elf_applid(...) { ... }
void send_elf_token(...) { ... }
```

**Pros**: File-static, all state management in one file
**Cons**: Initialization separated from validation logic

## Recommendation

### **Option 1: Use Setter Function** â

This is the best balance of encapsulation and logical organization.

### Implementation Details

```c
// glue.h (or task.h)
typedef enum {
    ELF_DISABLED = 0,
    ELF_SEND_USERID,
    ELF_SEND_PASSWORD,
    ELF_COMPLETE
} elf_state_t;

void elf_init(void);                           // In glue.c
void elf_set_initial_state(elf_state_t state); // In task.c
void send_elf_token(const char *token);        // In glue.c

// task.c
/**
 * ELF authentication state (file-static).
 * Only accessible within task.c for better encapsulation.
 */
static elf_state_t elf_state = ELF_DISABLED;

/**
 * Set initial ELF state.
 * Called by elf_init() in glue.c during connection initialization.
 */
void elf_set_initial_state(elf_state_t state)
{
    elf_state = state;
}

void task_host_output(void)
{
    // ... existing code ...
    
    /* ELF automatic token transmission */
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
                
            case ELF_DISABLED:
            default:
                break;
        }
    }
}

// glue.c
void elf_init(void)
{
    const char *elf_applid = appres.elf_applid;
    
    if (elf_applid == NULL || *elf_applid == '\0') {
        elf_set_initial_state(ELF_DISABLED);
        return;
    }
    
    if (!validate_elf_applid(elf_applid)) {
        popup_an_error("Invalid ELF Application ID: must be 1-8 alphanumeric characters");
        elf_set_initial_state(ELF_DISABLED);
        return;
    }
    
    /* ELF enabled - start in SEND_USERID state */
    elf_set_initial_state(ELF_SEND_USERID);
}
```

## Why Option 1 is Best

1. **File-static encapsulation**: â State hidden in task.c
2. **Logical grouping**: â Validation in glue.c, state management in task.c
3. **Minimal complexity**: â Only one extra function (setter)
4. **Clear interface**: â Setter function documents initialization contract
5. **Maintainable**: â Easy to understand and modify
6. **Testable**: â Can test initialization via setter

## Trade-offs Summary

### What We Gain (Option 1 vs Global)
- â Better encapsulation (file-static)
- â State only accessible where needed (task.c)
- â Clear initialization interface (setter function)
- â Slightly better software engineering practice

### What We Pay (Option 1 vs Global)
- â ï¸ One extra function (5 lines)
- â ï¸ Slightly more verbose initialization
- â ï¸ One extra function call (negligible overhead)

### Is It Worth It?
**YES** - The encapsulation benefit outweighs the minimal added complexity.

## Final Recommendation

**Use Option 1: File-static with setter function**

This achieves your goal of avoiding a global variable while maintaining clean, logical code organization. The setter function is a small price to pay for proper encapsulation.

### Files Modified

1. **glue.h** (or task.h):
   - Add enum definition
   - Add `elf_set_initial_state()` declaration
   - Add `send_elf_token()` declaration

2. **task.c**:
   - Add file-static `elf_state` variable
   - Add `elf_set_initial_state()` function
   - Add ELF logic to `task_host_output()`

3. **glue.c**:
   - Keep `elf_init()` (calls setter)
   - Keep `validate_elf_applid()`
   - Add `send_elf_token()`

**Total**: ~45 lines of code, excellent encapsulation, clean design.