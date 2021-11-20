#!/usr/bin/python3

"""
Bluetooth HID keyboard emulator DBUS Service

Original idea taken from: http://yetanotherpointlesstechblog.blogspot.com/2016/04/emulating-bluetooth-keyboard-with.html
Rewritten and improved by: https://gist.github.com/ukBaz/a47e71e7b87fbc851b27cde7d1c0fcf0
Simplified and shortened by @MsmCode
"""

import os
import dbus
import time
import socket
from socket import AF_BLUETOOTH, SOCK_SEQPACKET, BTPROTO_L2CAP
from keycodes import char_to_keycode
from pathlib import Path


PROFILE_DBUS_PATH = "/bluez/msm/bluekeyboard"  # Profile path
P_CTRL = 17  # Control port (configured in SDP record)
P_INTR = 19  # Interrupt port (Configured in SDP record#Interrrupt port)

# UUID for HID service (1124)
# https://www.bluetooth.com/specifications/assigned-numbers/service-discovery
UUID = "00001124-0000-1000-8000-00805f9b34fb"


def send_char(char, cinterrupt):
    keycode, shift = char_to_keycode(char)
    modkey = (1 << 6) if shift else 0
    cinterrupt.send(bytes([0xA1, 1, modkey, 0, keycode, 0, 0, 0, 0, 0]))
    time.sleep(0.01)
    cinterrupt.send(bytes([0xA1, 1, 0, 0, 0, 0, 0, 0, 0, 0]))
    time.sleep(0.01)


def bluetooth_connect():
    bus = dbus.SystemBus()

    print("Registering the profile...")
    opts = {
        "Role": "server",
        "RequireAuthentication": False,
        "RequireAuthorization": False,
        "AutoConnect": True,
        "ServiceRecord": (Path(__file__).parent / "service.xml").read_text(),
    }
    bluez = bus.get_object("org.bluez", "/org/bluez")
    manager = dbus.Interface(bluez, "org.bluez.ProfileManager1")
    manager.RegisterProfile(PROFILE_DBUS_PATH, UUID, opts)

    print("Waiting for connections...")
    hci0 = bus.get_object("org.bluez", "/org/bluez/hci0")
    adapter_property = dbus.Interface(hci0, "org.freedesktop.DBus.Properties")
    address = adapter_property.Get("org.bluez.Adapter1", "Address")

    scontrol = socket.socket(AF_BLUETOOTH, SOCK_SEQPACKET, BTPROTO_L2CAP)
    scontrol.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    scontrol.bind((address, P_CTRL))
    scontrol.listen(1)

    sinterrupt = socket.socket(AF_BLUETOOTH, SOCK_SEQPACKET, BTPROTO_L2CAP)
    sinterrupt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sinterrupt.bind((address, P_INTR))
    sinterrupt.listen(1)

    scontrol, sinfo = scontrol.accept()
    print(f"Connected on the control socket {sinfo[0]}")

    cinterrupt, cinfo = sinterrupt.accept()
    print(f"Connected on the interrupt channel {cinfo[0]}")

    return cinterrupt


def main():
    assert os.geteuid() == 0  # This won't work without root

    cinterrupt = bluetooth_connect()

    try:
        while True:
            text = input()
            for c in text + "\n":
                send_char(c, cinterrupt)
    finally:
        cinterrupt.close()

if __name__ == "__main__":
    main()
