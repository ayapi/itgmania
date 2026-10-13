"""V5 test gifts: notes, rescue points/hearts, strong trials and original locks."""
import argparse,json,random,time,uuid
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

def request_json(url,body=None):
 data=None if body is None else json.dumps(body,ensure_ascii=False).encode()
 with urlopen(Request(url,data=data,headers={'Content-Type':'application/json'}),timeout=2) as response:return json.load(response)
def main():
 p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8765');p.add_argument('--run-seconds',type=float,default=float('inf'))
 p.add_argument('--tiktok-viewers',type=int,default=100);p.add_argument('--youtube-viewers',type=int,default=0)
 p.add_argument('--notes-min',type=float,default=3);p.add_argument('--notes-max',type=float,default=6)
 p.add_argument('--small-tempo-min',type=float,default=3);p.add_argument('--small-tempo-max',type=float,default=10)
 p.add_argument('--lock-min',type=float,default=55);p.add_argument('--lock-max',type=float,default=85)
 p.add_argument('--trial-min',type=float,default=35);p.add_argument('--trial-max',type=float,default=55)
 a=p.parse_args();base=a.url.rstrip('/');end=time.monotonic()+a.run_seconds;due={};session=None;total=0
 print('Version 5 テスト：ノート、ハート、救済pt、強い試練、原曲ロック。Ctrl+Cで終了。',flush=True)
 request_json(base+'/api/audience',dict(tiktok=a.tiktok_viewers,youtube=a.youtube_viewers))
 intervals={'notes':(a.notes_min,a.notes_max),'rescue':(a.small_tempo_min,a.small_tempo_max),'trial':(a.trial_min,a.trial_max),'lock':(a.lock_min,a.lock_max),'hearts':(1,1)}
 if any(lo<=0 or hi<lo for lo,hi in intervals.values()):p.error('送信間隔を確認してください')
 while time.monotonic()<end:
  try:
   s=request_json(base+'/api/status');now=time.monotonic()
   if s.get('ready') and s.get('protocol_version')==5:
    if session!=s['session']:session=s['session'];due={k:now+random.uniform(*v) for k,v in intervals.items()}
    for kind in intervals:
     if now<due[kind]:continue
     due[kind]=now+random.uniform(*intervals[kind])
     body=dict(event_id='test-v5-'+str(uuid.uuid4()),sender=random.choice(['テスト視聴者A','テスト視聴者B','テスト視聴者C']))
     if kind=='notes':
      if not s.get('note_remaining'):continue
      body['count']=min(random.randint(1,3),s['note_remaining'])
     elif kind=='rescue':body['points']=random.randint(1,10)
     elif kind=='hearts':
      total+=random.randint(150,400);body=dict(platform='tiktok',total=total)
     else:
      if kind=='lock' and not s.get('lock_remaining'):continue
      body['count']=1
     try:print(kind,request_json(base+'/api/'+kind,body),flush=True)
     except HTTPError as e:print('受付結果',e.read().decode(),flush=True)
   time.sleep(.25)
  except (URLError,OSError,ValueError) as e:print('接続待機',e,flush=True);time.sleep(1)
if __name__=='__main__':
 try:main()
 except KeyboardInterrupt:print('テスト終了')
