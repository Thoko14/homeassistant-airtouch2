# Airtouch 2 integration
Now with basic support for airtouch2+ in beta/testing.

> **This fork (Thoko14):** adds reliable reconnects. The airtouch2 library only notices a lost connection when the socket reports an error, so a connection that dies silently (for example after a Wi-Fi hiccup) leaves Home Assistant without updates until a restart. `connection_fix.py` switches TCP keepalive on properly (the keepalive helper in airtouch2 0.8.7 checks the socket object instead of the socket module, so keepalive stays off) and closes the old connection before reconnecting. A dead connection is now detected within about 10 seconds and reconnected. Tested against airtouch2 0.8.6 and 0.8.7 with a simulated silent link drop. Intended for upstream; remove once the library carries the fix.

_Component to integrate with Polyaire Airtouch 2._

Utilizes [airtouch2-python](https://github.com/nathanvdh/airtouch2-python)

**This component will set up the following platforms.**

Platform | Description
-- | --
`climate` | Control temperature, mode, fan speed
`fan`     | Control zones on/off and dampers

## Installation

1. Click install.
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "airtouch2".
1. Enter the host address (IP) of the airtouch 2 system
1. Check homeassistant logs and open an issue if gateway id is not recognised.
