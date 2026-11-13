"""Synthesize the three original ScreenFish cues using the standard library."""

from array import array
from math import exp, sin, tau
from pathlib import Path
import random
import sys
import wave


SAMPLE_RATE = 44100
SOUNDS = Path(__file__).resolve().parents[1] / "sounds"


def droplet(time, pitch, strength):
    # An upward chirp decays quickly, with a softer lower bubble resonance.
    phase = tau * (pitch * time + 260 * (time + (exp(-time * 70) - 1) / 70))
    attack = min(1, time / 0.003)
    body = sin(phase) * exp(-time * 25)
    resonance = sin(tau * pitch * 0.48 * time) * exp(-time * 43)
    return strength * attack * (body + 0.3 * resonance)


def write_sound(name, duration, sample):
    frames = array("h")
    for index in range(int(SAMPLE_RATE * duration)):
        time = index / SAMPLE_RATE
        fade = min(1, (duration - time) / 0.01)
        value = max(-1, min(1, sample(time) * fade))
        frames.append(round(value * 32767))
    if sys.byteorder != "little":
        frames.byteswap()
    with wave.open(str(SOUNDS / (name + ".wav")), "wb") as output:
        output.setparams((1, 2, SAMPLE_RATE, 0, "NONE", "not compressed"))
        output.writeframes(frames.tobytes())


def main():
    SOUNDS.mkdir(exist_ok=True)
    noise = random.Random(592)

    def reel(time):
        tick = (time * 22) % 1
        fade = min(1, time / 0.025) * exp(-time * 5)
        return 0.10 * noise.uniform(-1, 1) * fade * exp(-tick * 5)

    write_sound("drop", 0.25, lambda time: droplet(time, 650, 0.26))
    write_sound("bite", 0.31, lambda time: droplet(time, 910, 0.23)
                + droplet(max(0, time - 0.06), 745, 0.12))
    write_sound("reel", 0.42, reel)


if __name__ == "__main__":
    main()
