SUMMARY = "OpenV2Gx EXI decoder/encoder"
HOMEPAGE = "https://github.com/uhi22/OpenV2Gx"
LICENSE = "CLOSED"

inherit cmake pkgconfig

SRC_URI = "git://github.com/uhi22/OpenV2Gx.git;branch=master;protocol=https"
SRCREV = "${AUTOREV}"

S = "${WORKDIR}/git"

FILES:${PN} += "${bindir} ${libdir}"
