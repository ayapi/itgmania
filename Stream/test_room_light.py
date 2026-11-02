import math
import tempfile
import unittest
from pathlib import Path
from room_light import BeatLight,BLUE,ORANGE,RoomLight

class LightTests(unittest.TestCase):
    def status(self,**kw):return dict(protocol_version=5,ready=True,connected=True,song_beat=0,effective_bpm=120,trial_state={},**kw)
    def test_beat_clock_and_trial_color(self):
        light=BeatLight();light.sync(self.status(),10)
        self.assertEqual(light.color(10),light.rgb(BLUE,1))
        self.assertNotEqual(light.color(10.25),light.color(10))
        self.assertEqual(light.color(10.5),light.color(10))
        s=self.status();s['trial_state']={'trial':{'kind':'strong'}};light.sync(s,11)
        self.assertEqual(light.color(11),light.rgb(ORANGE,1))
        s['trial_state']={'announcement':{},'shield_waiting':1};light.sync(s,12)
        self.assertEqual(light.color(12),light.rgb(BLUE,1))
    def test_age_and_speed_changes(self):
        light=BeatLight();light.sync(self.status(snapshot_age_seconds=.1),0,.025)
        expected=.55+.45*math.exp(-.25*4)
        self.assertEqual(light.color(0),light.rgb(BLUE,expected))
        s=self.status();s['effective_bpm']=150;light.sync(s,1)
        self.assertEqual(light.color(1.4),light.rgb(BLUE,1))
    def test_stop_pause_disconnect_stale_and_invalid(self):
        light=BeatLight();idle=light.rgb(BLUE,1)
        for key,value in [('ready',False),('connected',False),('effective_bpm',0),('effective_bpm',float('nan')),('song_beat',float('inf')),('snapshot_age_seconds',2)]:
            s=self.status();s[key]=value;light.sync(s,0);self.assertEqual(light.color(.1),idle)
        light.sync({},0);self.assertEqual(light.color(0),idle)
        light.sync(self.status(),0);self.assertEqual(light.color(1.51),idle)
    def test_native_window_saves_and_restores(self):
        with tempfile.TemporaryDirectory() as folder:
            app=RoomLight(Path(folder));app.root.update();app.restore()
            app.root.geometry('820x510+70+80');app.root.update();app.save()
            self.assertEqual(app.normal['width'],820)
            app.set_fullscreen(True);app.root.update();app.save()
            self.assertTrue(app.fullscreen)
            app.set_fullscreen(False);app.root.update();app.close()
            again=RoomLight(Path(folder));again.root.update();again.restore()
            self.assertEqual(again.root.winfo_width(),820)
            again.close()
if __name__=='__main__':unittest.main()
