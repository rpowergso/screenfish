# ScreenFish

ScreenFish is a small Windows desktop aquarium and fishing game. Fish swim across your screens while you work. You can watch them, feed them, or lower a line and see what bites.

## Get started

1. Install [64-bit Python 3 for Windows](https://www.python.org/downloads/windows/) with Tcl/Tk and add Python to PATH.
2. Download `ScreenFish-Windows.zip` from [GitHub Releases](https://github.com/rpowergso/screenfish/releases/latest) and extract it.
3. Double-click `Start Fish.cmd` in the extracted folder. You can also run `python ScreenFish.pyw` from that folder.

## Controls

- Left-click to lower the line. Click again to reel it in, with or without a fish.
- Right-click to feed nearby fish. Up to three food patches can be active at once.
- Use the control window to adjust fish activity, mute sounds, or turn off the water tint.
- Turn off **Click to drop / click to reel** to watch the aquarium without reacting to mouse clicks.
- Minimize the control window to leave the aquarium running. Use **Pause** to hide it or **Quit** to close it.

Clicks still reach whatever is beneath the fish. Cast over an empty area of the desktop if you want to avoid clicking another app.

## How it works

ScreenFish uses Python's standard library and draws the fish and water effects with Tkinter. Windows provides the click-through overlay and playback for the bundled synthesized sound effects. The app reads mouse button states and cursor position locally for the fishing controls. It makes no network requests and does not register itself to launch at startup.

The sound effects can be rebuilt from source with `python tools/generate_sounds.py`.

## License

ScreenFish and the included sound effects are available under the [MIT License](LICENSE).
