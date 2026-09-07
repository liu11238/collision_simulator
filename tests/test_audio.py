"""Audio is optional, and disabling it also silences pending cues."""
import os
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import unittest
from unittest.mock import patch, Mock
import pygame
from core.audio import Soundscape


class SoundscapeTests(unittest.TestCase):
    def test_available_device_defaults_enabled(self):
        sound = Soundscape()
        if sound.available:
            self.assertTrue(sound.enabled)

    def test_missing_device_is_nonfatal(self):
        with patch('pygame.mixer.get_init', return_value=None), patch(
                'pygame.mixer.init', side_effect=pygame.error('No device')):
            sound = Soundscape()
        sound.toggle()
        sound.play('impact')
        self.assertFalse(sound.available)
        self.assertFalse(sound.enabled)

    def test_mute_blocks_and_stops_cues(self):
        sound = Soundscape()
        sound.available = True
        sound.enabled = True
        cue = Mock()
        sound._sounds = {'tap': cue, 'impact': cue}
        sound.play('impact')
        cue.play.assert_called_once()
        sound.toggle()
        self.assertFalse(sound.enabled)
        self.assertTrue(cue.stop.called)
        sound.play('impact')
        cue.play.assert_called_once()
        sound.toggle()
        self.assertTrue(sound.enabled)
        self.assertEqual(cue.play.call_count, 2)
