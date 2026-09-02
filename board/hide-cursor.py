# Hides the X cursor for the whole session — handhelds have no mouse, so a stray
# pointer parked over the game is just screen litter. XFixes hides the cursor for
# as long as this client stays connected; the autostart entry launches it at login.
import ctypes
import time

x11 = ctypes.CDLL("libX11.so.6")
xfixes = ctypes.CDLL("libXfixes.so.3")
dpy = x11.XOpenDisplay(b":0")
if not dpy:
    raise SystemExit("no display")
root = x11.XDefaultRootWindow(dpy)
xfixes.XFixesHideCursor(dpy, root)
x11.XFlush(dpy)
while True:
    time.sleep(3600)
