SUMMARY = "pyPLC V2G implementation"
HOMEPAGE = "https://github.com/uhi22/pyPLC"
LICENSE = "CLOSED"

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
"
