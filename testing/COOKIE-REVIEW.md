# Cookie and script-port validation

Validated on 2026-10-28 using IBM Clang 21.1.1 and installed zoslib on z/OS.

## Behavior

The emulator and x3270if use the same cookie open helper. It disables inherited
conversion on each cookie descriptor. New or regenerated cookies contain ASCII
protocol bytes and are tagged binary. Existing tagged text cookies, including
IBM-1047, explicitly enable descriptor conversion to ASCII. Existing untagged,
binary, ISO8859-1 (819), and UTF-8 (1208) cookies are read without translation.
Reads do not rewrite or retag existing cookies.

The original version of [PR #36](https://github.com/zopencommunity/c3270port/pull/36)
disabled conversion for every existing file. This made a correctly tagged
EBCDIC cookie stop matching its ASCII protocol value. Patched x3270if could
hide this interoperability problem because it also read the raw EBCDIC bytes.
The final helper preserves tagged text conversion, and the tests use both an
independent ASCII protocol client and the actual x3270if client.

File tags must describe the actual bytes. ASCII data tagged as EBCDIC, or
EBCDIC data tagged binary, must be repaired before use; the helper does not
attempt to guess the intended encoding. Descriptor conversion must support
the tagged CCSID. Changing a tag alone does not convert file contents.

The patch also applies after the termios-header patch already on main. The
original include hunk conflicted with that patch, and building the original
PR branch reproduced missing `struct termios`, `tcgetattr`, `ECHO`, and
`TCSANOW` compile errors.

## Checks

`testing/check-cookie-encoding.py` runs 20 checks, covering the following with
`_BPXK_AUTOCVT` set to both `ON` and `OFF`:

- Generation of missing and empty cookies, including an empty IBM-1047 file.
- Independent ASCII socket authentication and actual x3270if authentication
  with ASCII cookies tagged 0, 819, 1208, and binary, plus IBM-1047 cookies.
- Preservation of existing bytes and tags, cookie permissions, trailing
  whitespace, and authentication after restarting the emulator.
- Rejection of unsupported, incorrectly tagged fixtures.
- Missing and incorrect cookies, per-connection authorization with concurrent
  clients, and rejection of x3270if without `X3270COOKIEFILE`.
- Authenticated `Connect` to a disposable local NVT endpoint and clean `Quit`.

The EBCDIC fixture uses only characters shared by CCSIDs 037 and 1047, plus
EBCDIC space for trailing whitespace. It does not use the differing newline
mappings to construct a 1047 fixture.

All 20 checks passed on z/OS. `make -j4` completed for all configured binaries.
The port's build now runs this suite and reports its actual failure and test
counts; missing test results report a failure instead of a hardcoded success.
The upstream patch also retains a portable x3270if round-trip test.

Run against already-built binaries:

```sh
python3 testing/check-cookie-encoding.py /path/to/bin
```

Or run from a configured suite3270 source tree:

```sh
python3 /path/to/c3270port/testing/check-cookie-encoding.py --source-dir .
```

`zopen build` invokes the second form automatically. The test exits nonzero on
failure, prints build-framework result counts, and requires only the Python
standard library. It uses temporary files and processes. Tests use
`-scriptport 0` and read the assigned port from the trace, avoiding assumptions
about available fixed ports. They do not validate availability of port 4185 or
a real TN3270/TLS host connection. The original RCE failure trace and cookie
were not available, so the original integration failure remains unconfirmed.

## Script client usage

```sh
/path/to/s3270 -scriptport 4185 -cookiefile /path/to/cookie.txt
X3270COOKIEFILE=/path/to/cookie.txt /path/to/x3270if -t 4185 'Connect(HOST:PORT)'
```

x3270if reads the file and supplies `Cookie(...)` before the requested action.
A custom socket client must send `Cookie(VALUE)` on each connection before
`Connect(...)` or other protected commands. The two actions can also be sent
on one line as `Cookie(VALUE) Connect(HOST:PORT)`.
