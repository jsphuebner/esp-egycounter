SUMMARY = "esp-egycounter battery-control scripts"
HOMEPAGE = "https://github.com/jsphuebner/esp-egycounter"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "git://github.com/jsphuebner/esp-egycounter.git;branch=main;protocol=https"
SRCREV = "${AUTOREV}"

S = "${WORKDIR}/git"

do_install() {
    install -d ${D}/opt/esp-egycounter
    cp -R --no-preserve=ownership ${S}/battery-control ${D}/opt/esp-egycounter/
}

FILES:${PN} += "/opt/esp-egycounter/battery-control"

RDEPENDS:${PN} += " \
    python3-core \
    python3-modules \
    python3-paho-mqtt \
    python3-pyserial \
    python3-requests \
    python3-urllib3 \
    python3-pyyaml \
    python3-crcmod \
    python3-can \
    python3-pymodbus \
    python3-adafruit-bbio \
"
