"""Quiet procedural cues. No files, no background music, no audio-device dependency."""
from array import array
import math
import pygame


class Soundscape:
    def __init__(self):
        self.enabled = False
        self.available = False
        self._sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2)
            rate, fmt, channels = pygame.mixer.get_init()
            if fmt != -16:
                return
            for name, frequency, duration in (("tap", 660, .065), ("impact", 220, .28)):
                samples = array('h')
                for i in range(int(rate * duration)):
                    t = i / rate
                    envelope = min(1, t/.004) * math.exp(-t/(duration/5))
                    tone = math.sin(math.tau * frequency * t)
                    tone += .24 * math.sin(math.tau * frequency * 2.76 * t)
                    value = int(32767 * .15 * envelope * tone)
                    samples.extend([value] * channels)
                self._sounds[name] = pygame.mixer.Sound(buffer=samples.tobytes())
            self.available = True
        except pygame.error:
            pass

    def toggle(self):
        self.enabled = not self.enabled if self.available else False
        if not self.enabled:
            for sound in self._sounds.values():
                sound.stop()
        self.play("tap")

    def play(self, name):
        if self.enabled and name in self._sounds:
            self._sounds[name].play()
