SUMMARY = "pyPLC V2G implementation"
HOMEPAGE = "https://github.com/uhi22/pyPLC"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE.md;md5=4f3f42db7e6d7f76fdcc71598ff5d5da"

SRC_URI = "git://github.com/uhi22/pyPLC.git;branch=master;protocol=https"
SRCREV = "${AUTOREV}"

S = "${WORKDIR}/git"

do_install() {
    install -d ${D}/opt/pyplc
    cp -R --no-preserve=ownership ${S}/* ${D}/opt/pyplc/
}

FILES:${PN} += "/opt/pyplc"

RDEPENDS:${PN} += " \
    python3-core \
    python3-modules \
    python3-pyserial \
    python3-asyncio \
    python3-json \
"
