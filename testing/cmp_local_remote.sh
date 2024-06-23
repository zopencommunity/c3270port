#!/bin/sh

# Generate local with c3270 -trace -tracefile /tmp/local.trc Y:L:zoscan2b.pok.stglabs.ibm.com:992
# Generate remote with c3270 -trace -tracefile /tmp/remote.trc Y:L:aqft.pok.ibm.com:992

LOCAL=/tmp/local.trc
REMOTE=/tmp/remote.trc
LOCAL_NORM=/tmp/local.norm
REMOTE_NORM=/tmp/remote.norm

sed -E 's/^2024([0-9]+)\.([0-9]+)\.([0-9]+) /X /g;s/zoscan2b.pok.stglabs.ibm.com/SYS/g' "${LOCAL}" >"${LOCAL_NORM}"
sed -E 's/^2024([0-9]+)\.([0-9]+)\.([0-9]+) /X /g;;s/aqft.pok.ibm.com/SYS/g' "${REMOTE}" >"${REMOTE_NORM}"

diff "${LOCAL_NORM}" "${REMOTE_NORM}" | less
