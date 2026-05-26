SUMMARY = "Headless BeagleBone image for esp-egycounter"
LICENSE = "MIT"

inherit core-image

IMAGE_FEATURES += "ssh-server-openssh package-management"

IMAGE_INSTALL:append = " \
    apt \
    dpkg \
    openssh \
    nginx \
    mosquitto \
    can-utils \
    iproute2 \
    iptables \
    usbutils \
    python3 \
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
    pyplc \
    openv2gx \
    egycounter-battery-control \
    usb-gadget-ethernet \
"
