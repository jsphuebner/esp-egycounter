# Yocto configuration for BeagleBone (esp-egycounter)

This directory provides a Yocto setup that builds a BeagleBone image with:

- Debian-style package management (`apt`, `dpkg`) via `package_deb`
- No X server/UI stack
- SSH (`openssh`), Python 3 (with stdlib modules), and `nginx`
- USB client Ethernet gadget support (RNDIS/ECM style)
- Kernel based on RobertCNelson `ti-linux-kernel-dev` configuration with added `qca7k` support
- Integrated `battery-control` scripts from this repository
- Included `pyPLC` and `OpenV2Gx`

## Build quickstart (kas)

From repository root:

```bash
cd yocto
kas build kas-beaglebone.yml
```

The image target is `egycounter-image`.

## Notes

- `OpenV2Gx` is built as part of the Yocto build via the custom recipe.
- `pyPLC` is installed to `/opt/pyplc`.
- `battery-control` scripts are installed to `/opt/esp-egycounter/battery-control`.
