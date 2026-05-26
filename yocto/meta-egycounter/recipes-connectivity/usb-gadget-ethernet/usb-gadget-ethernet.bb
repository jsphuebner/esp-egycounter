SUMMARY = "Enable USB gadget Ethernet on BeagleBone USB client port"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

inherit systemd

SRC_URI = "file://usb-gadget-ethernet.service"

SYSTEMD_SERVICE:${PN} = "usb-gadget-ethernet.service"
SYSTEMD_AUTO_ENABLE = "enable"

do_install() {
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/usb-gadget-ethernet.service ${D}${systemd_system_unitdir}/
}
