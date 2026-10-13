"""Generate short original sine-wave cue sounds (no external audio assets)."""
import math
import struct
import wave
from pathlib import Path

RATE = 44100


def write(name, tones):
    samples = []
    for frequency, duration, volume in tones:
        count = round(RATE * duration)
        for i in range(count):
            # Short smooth envelopes avoid clicks and keep cue volume below music.
            envelope = min(1, i/(RATE*.008), (count-1-i)/(RATE*.015))
            samples.append(round(32767*volume*envelope*math.sin(2*math.pi*frequency*i/RATE)))
    with wave.open(str(Path(__file__).with_name(name)), 'wb') as audio:
        audio.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        audio.writeframes(struct.pack('<'+'h'*len(samples), *samples))


if __name__ == '__main__':
    write('ChallengeNotice.wav', [(660,.09,.23),(0,.03,0),(880,.13,.23)])
    write('ChallengeTick.wav', [(880,.055,.18)])
    write('ChallengeClear.wav', [(784,.07,.24),(988,.07,.24),(1175,.10,.24)])
