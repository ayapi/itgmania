import json,tempfile,unittest
from pathlib import Path
from bridge import Bridge,validate,APIError
class V5Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.api=Bridge(Path(self.tmp.name));self.s=dict(protocol_version=5,ready=True,session='s1',players=['P1'],server_id=self.api.server_id,cursor=0,note_remaining=3);self.write()
 def tearDown(self):self.tmp.cleanup()
 def write(self):(self.api.directory/'status.json').write_text(json.dumps(self.s))
 def test_duplicate_and_restart(self):
  body=dict(event_id='a',sender='名前',points=2);self.api.submit('rescue',body);again=Bridge(Path(self.tmp.name));self.assertTrue(again.submit('rescue',body)['duplicate']);self.assertEqual(again.server_id,self.api.server_id)
 def test_notes_inventory(self):
  self.api.submit('notes',dict(sender='A',count=2))
  with self.assertRaises(APIError):self.api.submit('notes',dict(sender='B',count=2))
 def test_paid_between_songs(self):
  self.s['ready']=False;self.write()
  for kind in ('trial','lock','rescue'):self.assertEqual(self.api.submit(kind,dict(sender='A',**({'points':4} if kind=='rescue' else {'count':1})))['session'],'*')
 def test_legacy_retired(self):
  with self.assertRaises(APIError) as c:validate('tempo',dict(bpm_delta=1))
  self.assertEqual(c.exception.status,410)
 def test_all_youtube_reactions(self):self.assertEqual(validate('hearts',dict(platform='youtube',reactions=[dict(key='🧡',value=3),dict(key='😄',value=4)]))['count'],7)
 def test_tiktok_not_delta(self):
  self.assertEqual(validate('hearts',dict(platform='tiktok',total=200))['total'],200)
  with self.assertRaises(APIError):validate('hearts',dict(platform='tiktok',count=2))
 def test_audience(self):
  self.api.input('audience',dict(tiktok=100,youtube=50));self.assertEqual(json.loads((self.api.directory/'audience.json').read_text())['youtube'],50)
 def test_replaceable_mapping(self):
  (self.api.directory/'gift-map.json').write_text(json.dumps({'youtube':{'star':dict(kind='rescue',points_per_unit=2)}}))
  self.api.input('gift',dict(event_id='star',sender='A',platform='youtube',gift_id='star',count=3))
  self.assertEqual(self.api.commands[-1]['points'],6)
 def test_unknown_mapping_rejected(self):
  with self.assertRaises(APIError):self.api.input('gift',dict(sender='A',platform='tiktok',gift_id='unknown'))
 def test_combo_actor_changes_are_recorded_within_one_second(self):
  self.s.update(music_seconds=12,current_combo=4,combo_display=dict(text='4',actor_visible=True))
  self.write();self.api.status()
  self.s.update(current_combo=5,combo_display=dict(text='5',actor_visible=True))
  self.write();self.api.status()
  records=[json.loads(line) for line in (self.api.directory/'stream-metrics.jsonl').read_text(encoding='utf-8').splitlines()]
  records=[row for row in records if row['kind']=='status']
  self.assertEqual([row['combo_display']['text'] for row in records],['4','5'])
 def test_bool_rejected(self):
  for kind,data in [('rescue',{'points':True}),('trial',{'count':True})]:
   with self.assertRaises(APIError):validate(kind,dict(sender='A',**data))
if __name__=='__main__':unittest.main()
