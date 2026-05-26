SUMMARY = "OpenV2Gx EXI decoder/encoder"
HOMEPAGE = "https://github.com/uhi22/OpenV2Gx"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=d41d8cd98f00b204e9800998ecf8427e"

inherit cmake pkgconfig

SRC_URI = "git://github.com/uhi22/OpenV2Gx.git;branch=master;protocol=https"
SRCREV = "${AUTOREV}"

S = "${WORKDIR}/git"

FILES:${PN} += "${bindir} ${libdir}"
