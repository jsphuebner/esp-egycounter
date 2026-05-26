SUMMARY = "RobertCNelson TI Linux kernel for BeagleBone"
DESCRIPTION = "Kernel from RobertCNelson/ti-linux-kernel-dev with additional config fragment"
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=d7810fab7487fb0aad327b76f1be7cd7"

inherit kernel

SRC_URI = "git://github.com/RobertCNelson/ti-linux-kernel-dev.git;branch=master;protocol=https \
           file://qca7k-usb-gadget.cfg"

SRCREV = "${AUTOREV}"
PV = "6.6+git${SRCPV}"

S = "${WORKDIR}/git"

KERNEL_IMAGETYPE = "zImage"

# Use upstream BeagleBone defconfig as baseline and append cfg fragment
KBUILD_DEFCONFIG = "omap2plus_defconfig"

KERNEL_CONFIG_FRAGMENTS += "${WORKDIR}/qca7k-usb-gadget.cfg"
