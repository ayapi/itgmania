import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import struct
import tempfile
import threading
import time
import unittest
from urllib.request import urlopen,Request
from http.server import ThreadingHTTPServer
from bridge import Bridge,make_handler
from onecomme import Router,WebSocket,gift


def yt(key='microphone.png',count=1,id='gift-1'):
    return dict(id='service-y',service='youtube',data=dict(id=id,liveId='live-y',name='視聴者',displayName='名前😀',
        hasGift=True,giftType='jewel',giftId=f'yt-user-{key}#{id}',giftCount=count,jewels=3,giftName=('やる気満々' if key=='heart.png' else 'マイク'),timestamp='2026-10-23T00:00:01Z',
        comment=f'<img class="gift-image" src="https://www.gstatic.com/youtube/img/pdg/gift/assets/{key}=w480-h480">'))


def tt(count=1,id='gift-t'):
    return dict(id='service-t',service='tiktok',data=dict(id=id,liveId='live-t',name='名前',hasGift=True,
        gift=dict(giftId='17646',repeatCount=count,details=dict(giftName='バッド・マスター',diamondCount=99))))


class OneCommeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.api=Bridge(self.root); self.now=1792713600.; self.sent=[]
        self.router=Router(self.root,lambda k,b:self.sent.append((k,b)),clock=lambda:self.now)

    def tearDown(self): self.temp.cleanup()

    def event(self,c): self.router.handle(dict(type='comments',data=dict(comments=c))); self.router.flush()

    def test_snapshot_history_not_triggered(self):
        self.router.handle(dict(type='connected',data=dict(comments=[yt(),tt()],services=[]))); self.router.flush()
        self.assertFalse(any(k=='gift' for k,b in self.sent))
        self.event([yt(),tt()]); self.assertFalse(any(k=='gift' for k,b in self.sent))
        self.event([yt(id='new')]); self.assertEqual([b['count'] for k,b in self.sent if k=='gift'],[1])

    def test_count_updates_restarts_and_repeat_duplicates(self):
        self.event([tt(1)]); self.event([tt(3)]); self.event([tt(3)])
        self.router=Router(self.root,lambda k,b:self.sent.append((k,b)),clock=lambda:self.now)
        self.event([tt(3)]); self.event([tt(4)])
        gifts=[b for k,b in self.sent if k=='gift']
        self.assertEqual([x['count'] for x in gifts],[1,2,1])
        self.assertEqual(len({x['event_id'] for x in gifts}),3)

    def test_distinct_youtube_users_use_same_stable_key(self):
        a=yt(); b=yt(id='gift-2'); b['data']['giftId']='yt-other-user-microphone.png#gift-2'
        self.event([a,b]); self.assertEqual([b['gift_id'] for k,b in self.sent if k=='gift'],['microphone.png','microphone.png'])

    def test_gift_id_alone_does_not_replace_gift_image(self):
        c=yt();c['data']['comment']='';c['data']['giftId']='yt-sender-with-hyphens-heart.png#transaction'
        self.assertIsNone(gift(c))

    def test_invalid_shapes_do_not_become_gifts(self):
        self.router.handle([]);self.assertIsNone(gift(dict(service='youtube',data=[])))
        self.assertIsNone(gift(dict(service='tiktok',data=dict(hasGift=True,gift='text'))))

    def test_paid_heart_is_lock_not_free_taps(self):
        self.event([yt('heart.png')]); gifts=[b for k,b in self.sent if k=='gift']
        self.assertEqual(gifts[0]['gift_id'],'heart.png')
        self.assertFalse(any(k=='hearts' for k,b in self.sent))

    def test_tiktok_confirmed_name_shield(self):
        c=tt();c['data']['gift']['giftId']='unknown-id';c['data']['gift']['details']['giftName']='ボリュームアップ'
        self.router.send=self.api.input
        self.event([c]);self.assertEqual(self.api.commands[0]['kind'],'lock')

    def test_large_combo_is_split_without_losing_units(self):
        self.event([tt(257)])
        self.assertEqual([b['count'] for k,b in self.sent if k=='gift'],[256,1])

    def test_normal_chat_and_free_gift_do_not_trigger_paid_actions(self):
        a=yt();a['data']['hasGift']=False
        b=yt(id='b');b['meta']=dict(free=True)
        self.event([a,b]);self.assertFalse(any(k=='gift' for k,b in self.sent))

    def test_initial_comment_batch_is_seeded(self):
        self.router.handle(dict(type='comments',data=dict(comments=[yt()],options=dict(init=True))))
        self.event([yt()]);self.assertFalse(any(k=='gift' for k,b in self.sent))

    def test_singular_comment_and_batched_data(self):
        self.router.handle(dict(type='comment',data=[yt()]));self.router.flush()
        self.assertEqual([b['count'] for k,b in self.sent if k=='gift'],[1])

    def test_reconnect_recovers_recent_unseen_paid_history(self):
        self.router.handle(dict(type='connected',data=dict(comments=[],services=[])))
        self.router.handle(dict(type='connected',data=dict(comments=[yt()],services=[])));self.router.flush()
        self.assertEqual(len([b for k,b in self.sent if k=='gift']),1)

    def test_paid_failure_keeps_same_receipt_id(self):
        self.router.send=lambda k,b:(_ for _ in ()).throw(OSError('offline'))
        self.event([yt()]); first=deepcopy(self.router.state['pending'])
        sent=[];router=Router(self.root,lambda k,b:sent.append((k,b)),clock=lambda:self.now)
        router.flush()
        gift_entry=next(x['body'] for x in first.values() if x['kind']=='gift')
        self.assertEqual(next(b for k,b in sent if k=='gift'),gift_entry)

    def test_services_and_tiktok_cumulative_total(self):
        self.router.handle(dict(type='connected',data=dict(comments=[],services=[
            dict(id='t',name='TikTok',enabled=True,meta=dict(viewer=100,totalLikeCount=500,isLive=True,url='https://www.tiktok.com/@example/live')),
            dict(id='y',name='YouTube',enabled=True,meta=dict(viewer=50,isLive=True))])))
        self.router.flush()
        self.assertIn(('audience',dict(tiktok=100,youtube=50)),self.sent)
        total=[b for k,b in self.sent if k=='hearts'][-1]; self.assertEqual(total['total'],500);self.assertTrue(total['reset'])
        self.router.handle(dict(type='meta',data=dict(id='t',meta=dict(totalLikeCount=520,viewer=101))));self.router.flush()
        last=[b for k,b in self.sent if k=='hearts'][-1];self.assertEqual(last['total'],520);self.assertFalse(last['reset'])
        self.assertEqual(last['stream_id'],total['stream_id'])

    def test_all_reaction_types_and_expiry(self):
        self.router.handle(dict(type='reactions',data=dict(effect=False,reactions=[dict(key='❤️',value=10),dict(key='😆',value=7)])))
        self.router.flush(); body=[b for k,b in self.sent if k=='hearts'][-1]
        self.assertEqual(sum(x['value'] for x in body['reactions']),17);self.assertFalse(body['effect'])
        self.router.handle(dict(type='reactions',data=dict(reactions=[dict(key='❤️',value=30)])))
        self.now+=2;self.router.flush()
        self.assertEqual(len([b for k,b in self.sent if k=='hearts']),1)

    def test_http_mapping_and_durable_bridge_receipts(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.api))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            def send(k,b):
                req=Request(f'http://127.0.0.1:{server.server_port}/api/{k}',json.dumps(b).encode(),{'Content-Type':'application/json'})
                with urlopen(req) as r:return json.load(r)
            self.router.send=send
            self.event([yt('microphone.png',2),yt('fired_up.png',id='lock')])
            self.assertEqual([(c['kind'],c['count']) for c in self.api.commands],[('trial',2),('lock',1)])
            self.event([yt('microphone.png',2),yt('fired_up.png',id='lock')]);self.assertEqual(len(self.api.commands),2)
        finally:server.shutdown();server.server_close();thread.join()

    def test_other_paid_gifts_rescue_at_unit_price(self):
        self.router.send=self.api.input
        c=yt('other.png',5);c['data'].pop('giftName');c['data']['jewels']=2;c['data']['price']=10
        self.event([c]);self.event([c])
        self.assertEqual(len(self.api.commands),1)
        self.assertEqual(self.api.commands[0]['kind'],'rescue')
        self.assertEqual(self.api.commands[0]['points'],10)
        self.assertEqual(self.api.commands[0]['gift_count'],5)
        c=tt(id='other');c['data']['gift']['details']=dict(giftName='バラ',diamondCount=1)
        self.event([c]);self.assertEqual(self.api.commands[-1]['points'],1)

    def test_old_provisional_gifts_no_longer_attack(self):
        self.router.send=self.api.input
        c=yt('bow.png');c['data'].pop('giftName')
        self.event([c]);self.assertEqual(self.api.commands[0]['kind'],'rescue')
        self.assertEqual(self.api.commands[0]['points'],3)

    def test_unpriced_paid_receipt_is_retained(self):
        from bridge import APIError
        def send(k,b):
            try: return self.api.input(k,b)
            except APIError as e: raise ValueError(e.message)
        self.router.send=send
        c=yt('unknown.png');c['data'].pop('giftName');c['data'].pop('jewels')
        self.event([c]);self.assertEqual(sum(x['kind']=='gift' for x in self.router.state['pending'].values()),1)


    def test_youtube_image_identity_not_localized_label(self):
        self.router.send=self.api.input
        for key in ('microphone.png','fired_up.png'):
            c=yt(key,id=key);c['data']['comment']=c['data']['comment'].split('>')[0]+' />unrelated label'
            c['data']['giftName']='別の名前'
            self.event([c])
        self.assertEqual([c['kind'] for c in self.api.commands],['trial','lock'])
        c=yt('other.png',id='fake-label');c['data']['giftName']='マイク'
        self.event([c]);self.assertEqual(self.api.commands[-1]['kind'],'rescue')

    def test_youtube_requires_both_paid_gift_flags(self):
        for flag,value in [('hasGift',False),('hasGift','true'),('giftType','superchat'),('giftType',None)]:
            c=yt();c['data'][flag]=value
            self.assertIsNone(gift(c))
        c=yt();c['data'].pop('hasGift');self.assertIsNone(gift(c))

    def test_emoji_images_do_not_identify_gifts(self):
        for image in (
            '<img src="https://www.gstatic.com/youtube/img/pdg/gift/assets/microphone.png=w480-h480">',
            '<img class="gift-image" src="https://example.com/youtube/img/pdg/gift/assets/microphone.png">',
            '<img class="gift-image" src="https://www.gstatic.com/youtube/img/emojis/microphone.png">'):
            c=yt();c['data']['comment']=image;self.assertIsNone(gift(c))
        c=yt();c['data']['comment']+='<img class="gift-image" src="https://www.gstatic.com/youtube/img/pdg/gift/assets/fired_up.png=w480-h480">'
        self.assertIsNone(gift(c))



class SocketTests(unittest.TestCase):
    def test_upgrade_fragmentation_and_ping(self):
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();received=[]
        def server():
            connection,_=listener.accept()
            with connection:
                header=b''
                while b'\r\n\r\n' not in header:header+=connection.recv(4096)
                received.append(header.split(b'\r\n')[0])
                key=next(x.split(b':',1)[1].strip() for x in header.split(b'\r\n') if x.lower().startswith(b'sec-websocket-key:'))
                accept=base64.b64encode(hashlib.sha1(key+b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest())
                payload=json.dumps(dict(type='comments',data=dict(comments=[yt()]))).encode()
                def frame(op,data,final=True):
                    size=len(data);length=bytes([size]) if size<126 else b'\x7e'+struct.pack('!H',size)
                    return bytes([op|(128 if final else 0)])+length+data
                connection.sendall(b'HTTP/1.1 101 Switching Protocols\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n'+frame(1,payload[:100],False)+frame(9,b'ping')+frame(0,payload[100:]))
                received.append(connection.recv(100))
        thread=threading.Thread(target=server);thread.start()
        ws=WebSocket(f'ws://127.0.0.1:{listener.getsockname()[1]}/sub?p=comments,meta,reactions')
        try:self.assertEqual(ws.receive()['type'],'comments')
        finally:ws.close();thread.join(timeout=3);listener.close()
        self.assertIn(b'/sub?p=comments,meta,reactions',received[0]);self.assertEqual(received[1][0]&15,10)


if __name__=='__main__':unittest.main()
