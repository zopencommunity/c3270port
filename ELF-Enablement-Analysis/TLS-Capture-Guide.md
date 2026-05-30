# TLS Handshake Capture and Analysis Guide

## Objective

Capture and compare TLS ClientHello messages from OpenSSL s_client (working) vs c3270 (failing) to identify why c3270 fails to connect to port 923.

## Prerequisites

- tcpdump (available at `/usr/sbin/tcpdump`)
- Wireshark (for GUI analysis) OR tshark (for command-line analysis)
- sudo access for packet capture

## Method 1: Capture with tcpdump, Analyze with Wireshark (RECOMMENDED)

### Step 1: Capture OpenSSL Traffic (Working Connection)

```bash
# Start packet capture in background
sudo tcpdump -i any -s 0 -w /tmp/openssl_port923.pcap \
  'host 9.47.80.126 and port 923' &

# Note the PID
TCPDUMP_PID=$!

# Wait a moment for tcpdump to start
sleep 2

# Make the connection
{ sleep 5; echo "Q"; } | openssl s_client -connect 9.47.80.126:923 -tls1_2 \
  -cert /tmp/fultonm_cert.pem \
  -key /tmp/fultonm_key.pem \
  -CAfile /tmp/STD1_server.pem \
  -showcerts

# Stop tcpdump
sudo kill $TCPDUMP_PID

echo "â OpenSSL capture saved to /tmp/openssl_port923.pcap"
```

### Step 2: Capture c3270 Traffic (Failing Connection)

```bash
# Start packet capture in background
sudo tcpdump -i any -s 0 -w /tmp/c3270_port923.pcap \
  'host 9.47.80.126 and port 923' &

# Note the PID
TCPDUMP_PID=$!

# Wait a moment for tcpdump to start
sleep 2

# Make the connection (will fail)
c3270 -trace -model 2 -secure \
  -tlsminprotocol TLS1.2 -tlsmaxprotocol TLS1.2 \
  -elf TSOVS01 -port 923 \
  -cafile /tmp/STD1_server.pem \
  -certfile /tmp/fultonm_cert.pem \
  -keyfile /tmp/fultonm_key.pem \
  STD1 &

# Wait for connection attempt
sleep 10

# Kill c3270 (it will be hung)
killall c3270

# Stop tcpdump
sudo kill $TCPDUMP_PID

echo "â c3270 capture saved to /tmp/c3270_port923.pcap"
```

### Step 3: Analyze with Wireshark

Open both files in Wireshark:
```bash
open /tmp/openssl_port923.pcap
open /tmp/c3270_port923.pcap
```

**In Wireshark, look for:**

1. **Filter for TLS handshake**: `tls.handshake.type == 1` (ClientHello)

2. **Compare these fields in ClientHello:**
   - TLS Version offered
   - Cipher Suites list
   - Extensions:
     - server_name (SNI)
     - signature_algorithms
     - supported_groups
     - ec_point_formats
     - application_layer_protocol_negotiation (ALPN)
     - extended_master_secret
     - renegotiation_info
   - Session ID
   - Random bytes

3. **Key differences to look for:**
   - â Missing SNI extension in c3270
   - â Different cipher suite order
   - â Missing or incompatible extensions
   - â Wrong TLS version in ClientHello

## Method 2: Quick Analysis with tcpdump (No Wireshark)

If you don't have Wireshark, use tcpdump to extract hex dumps:

### Capture and Display OpenSSL ClientHello

```bash
# Capture OpenSSL
sudo tcpdump -i any -s 0 -w /tmp/openssl_port923.pcap \
  'host 9.47.80.126 and port 923' &
TCPDUMP_PID=$!
sleep 2

{ sleep 5; echo "Q"; } | openssl s_client -connect 9.47.80.126:923 -tls1_2 \
  -cert /tmp/fultonm_cert.pem \
  -key /tmp/fultonm_key.pem \
  -CAfile /tmp/STD1_server.pem > /dev/null 2>&1

sudo kill $TCPDUMP_PID

# Display ClientHello hex dump
echo "=== OpenSSL ClientHello ==="
sudo tcpdump -r /tmp/openssl_port923.pcap -XX 'tcp[((tcp[12:1] & 0xf0) >> 2):1] = 0x16' | head -100
```

### Capture and Display c3270 ClientHello

```bash
# Capture c3270
sudo tcpdump -i any -s 0 -w /tmp/c3270_port923.pcap \
  'host 9.47.80.126 and port 923' &
TCPDUMP_PID=$!
sleep 2

c3270 -trace -model 2 -secure \
  -tlsminprotocol TLS1.2 -tlsmaxprotocol TLS1.2 \
  -elf TSOVS01 -port 923 \
  -cafile /tmp/STD1_server.pem \
  -certfile /tmp/fultonm_cert.pem \
  -keyfile /tmp/fultonm_key.pem \
  STD1 &

sleep 10
killall c3270
sudo kill $TCPDUMP_PID

# Display ClientHello hex dump
echo "=== c3270 ClientHello ==="
sudo tcpdump -r /tmp/c3270_port923.pcap -XX 'tcp[((tcp[12:1] & 0xf0) >> 2):1] = 0x16' | head -100
```

## Method 3: Install tshark for Command-Line Analysis

### Install tshark (if needed)

**macOS:**
```bash
brew install wireshark
```

**Linux:**
```bash
sudo apt-get install tshark  # Debian/Ubuntu
sudo yum install wireshark    # RHEL/CentOS
```

### Analyze with tshark

```bash
# Analyze OpenSSL ClientHello
echo "=== OpenSSL ClientHello Details ==="
tshark -r /tmp/openssl_port923.pcap -Y "tls.handshake.type == 1" -V | grep -A 200 "Client Hello"

# Analyze c3270 ClientHello
echo "=== c3270 ClientHello Details ==="
tshark -r /tmp/c3270_port923.pcap -Y "tls.handshake.type == 1" -V | grep -A 200 "Client Hello"
```

### Extract Specific Fields

```bash
# Compare TLS versions
echo "=== TLS Versions ==="
echo "OpenSSL:"
tshark -r /tmp/openssl_port923.pcap -Y "tls.handshake.type == 1" -T fields -e tls.handshake.version

echo "c3270:"
tshark -r /tmp/c3270_port923.pcap -Y "tls.handshake.type == 1" -T fields -e tls.handshake.version

# Compare SNI
echo "=== Server Name Indication (SNI) ==="
echo "OpenSSL:"
tshark -r /tmp/openssl_port923.pcap -Y "tls.handshake.type == 1" -T fields -e tls.handshake.extensions_server_name

echo "c3270:"
tshark -r /tmp/c3270_port923.pcap -Y "tls.handshake.type == 1" -T fields -e tls.handshake.extensions_server_name

# Compare cipher suites
echo "=== Cipher Suites ==="
echo "OpenSSL:"
tshark -r /tmp/openssl_port923.pcap -Y "tls.handshake.type == 1" -T fields -e tls.handshake.ciphersuite

echo "c3270:"
tshark -r /tmp/c3270_port923.pcap -Y "tls.handshake.type == 1" -T fields -e tls.handshake.ciphersuite
```

## Method 4: Alternative - Check c3270 Source Code

Instead of packet capture, examine c3270's TLS implementation:

### Find TLS/SSL Code

```bash
cd suite3270-4.4

# Find OpenSSL initialization
grep -r "SSL_CTX_new\|SSL_new\|SSL_connect" Common/

# Find SNI setting
grep -r "SSL_set_tlsext_host_name\|SNI" Common/

# Find certificate loading
grep -r "SSL_CTX_use_certificate\|SSL_use_certificate" Common/

# Find TLS version setting
grep -r "SSL_CTX_set_min_proto_version\|TLS_method" Common/
```

### Key Files to Check

1. **`Common/sio_openssl.c`** - OpenSSL implementation
2. **`Common/sio.c`** - Secure I/O layer
3. **`Common/telnet.c`** - Telnet protocol (already modified for ELF)

### Look for SNI Issues

Search for this pattern in `sio_openssl.c`:
```c
SSL_set_tlsext_host_name(ssl, hostname);
```

If this line is missing or commented out, that's likely the problem!

## Expected Findings

### If c3270 is Missing SNI:

**OpenSSL ClientHello will have:**
```
Extension: server_name (len=XX)
    Server Name Indication extension
        Server Name: STD1
```

**c3270 ClientHello will NOT have this extension**

### If c3270 has Wrong TLS Version:

**OpenSSL ClientHello:**
```
Version: TLS 1.2 (0x0303)
```

**c3270 ClientHello might show:**
```
Version: TLS 1.0 (0x0301)  â Wrong!
```

### If c3270 has Incompatible Cipher Suites:

AT-TLS requires specific cipher suites. Compare the lists.

## Quick Test: Force SNI in c3270

If c3270 has an option to set SNI, try:
```bash
c3270 -help | grep -i sni
c3270 -help | grep -i server
c3270 -help | grep -i name
```

## Next Steps After Analysis

1. **If SNI is missing**: Patch c3270 to add SNI support
2. **If TLS version is wrong**: Fix TLS version negotiation
3. **If cipher suites incompatible**: Add required cipher suites
4. **If extensions missing**: Add required TLS extensions

## Summary Commands

**Quick capture both (run in separate terminals):**

Terminal 1 - OpenSSL:
```bash
sudo tcpdump -i any -s 0 -w /tmp/openssl_port923.pcap 'host 9.47.80.126 and port 923' &
sleep 2
{ sleep 5; echo "Q"; } | openssl s_client -connect 9.47.80.126:923 -tls1_2 \
  -cert /tmp/fultonm_cert.pem -key /tmp/fultonm_key.pem -CAfile /tmp/STD1_server.pem
sudo killall tcpdump
```

Terminal 2 - c3270:
```bash
sudo tcpdump -i any -s 0 -w /tmp/c3270_port923.pcap 'host 9.47.80.126 and port 923' &
sleep 2
c3270 -trace -model 2 -secure -tlsminprotocol TLS1.2 -tlsmaxprotocol TLS1.2 \
  -elf TSOVS01 -port 923 -cafile /tmp/STD1_server.pem \
  -certfile /tmp/fultonm_cert.pem -keyfile /tmp/fultonm_key.pem STD1 &
sleep 10
killall c3270
sudo killall tcpdump
```

Then analyze with Wireshark or tshark.